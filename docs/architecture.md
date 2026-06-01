# System Architecture

This document provides a deep dive into the architecture of Manifold, a self-hosted financial observability platform.

## System Overview

Manifold is designed as a distributed system composed of several interoperable services, optimized for single-node deployment via Docker Compose.

```text
                                  ┌───────────────────────────┐
                                  │      Client (Browser)     │
                                  └─────────────┬─────────────┘
                                                │ HTTPS (Cookies/Bearer)
                                  ┌─────────────▼─────────────┐
                                  │    Nginx Reverse Proxy    │
                                  └─────────────┬─────────────┘
                                                │
                ┌───────────────────────────────┼──────────────────────────────┐
                │                               │                              │
  ┌─────────────▼─────────────┐   ┌─────────────▼─────────────┐   ┌────────────▼────────────┐
  │   React/TS Frontend       │   │      FastAPI Backend      │   │     SQL Database        │
  │   (Static Assets)         │   │      (REST API Core)      │   │  (SQLite/PG/MariaDB)    │
  └───────────────────────────┘   └─────────────┬─────────────┘   └────────────▲────────────┘
                                                │                              │
                                                │ Task Submission              │
                                  ┌─────────────▼─────────────┐                │
                                  │       Redis Broker        │                │
                                  └─────────────┬─────────────┘                │
                                                │                              │
                                                │ Task Consumption             │
                                  ┌─────────────▼─────────────┐                │
                                  │      Taskiq Worker        │────────────────┘
                                  │     (Sync/Alarms/etc)     │
                                  └─────────────┬─────────────┘
                                                │
                                  ┌─────────────▼─────────────┐
                                  │    External Services      │
                                  │ (Banks/Notifiers/Webhooks)│
                                  └───────────────────────────┘
```

## Layer Responsibilities

### API Layer (FastAPI)

The entry point for all client interactions.

- **Routing**: Clean, versioned REST endpoints (`/api/v1/...`).
- **Authentication**: Validates session cookies and JWT Bearer tokens.
- **Validation**: Uses Pydantic for strict request/response schema enforcement.
- **Task Dispatch**: Submits heavy lifting (syncs, evaluations) to the worker queue.

### Domain Layer (Business Logic)

The core of the application, independent of infrastructure.

- **Canonical Models**: Defines what an "Account" or "Transaction" is within Manifold.
- **Orchestration**: Manages the flow between data ingestion, alarm evaluation, and notification.
- **Ownership/RBAC**: Ensures users can only access data they own or have been delegated.
- **Account Identity** (`domain/account_identity.py`, `domain/identity_backfill.py`): Resolves which `Account` rows across different provider connections represent the same real-world bank account, grouping them under a shared `AccountIdentity` node. Runs inside the sync pipeline after every account upsert.
- **Transaction Deduplication** (`domain/transaction_fingerprint.py`): Computes identity-scoped HMAC fingerprints for transactions so that the same physical transaction fetched by two connections belonging to the same identity is stored only once.

### Provider Layer (Adapters)

Handles communication with external financial institutions.

- **Normalization**: Maps provider-specific JSON to Manifold canonical models.
- **Auth Management**: Manages OAuth2 flows, token rotation, and API key storage.
- **Resilience**: Implements rate limiting and retry logic specific to each provider.

### Email Transport Layer (`email/`)

A pluggable outbound email subsystem used by alarm notifications and system messages.

- **Transport Protocol** (`email/base.py`): The `EmailTransport` protocol defines `send`, `validate_config`, `verify_webhook`, and `parse_webhook` — allowing any adapter to slot in transparently.
- **Adapters** (`email/adapters/`): Six production-ready adapters ship out of the box: `smtp`, `ses`, `resend`, `postmark`, `mailgun`, and `brevo`.
- **Factory** (`email/factory.py`): `get_transport(provider, config)` resolves the correct adapter at runtime from `InstanceEmailSettings.provider`.
- **Suppression** (`models/email_suppression.py`): Bounce and complaint events received via provider webhooks write to `email_suppression`; the `address_hmac` column (BLAKE2 / HMAC of the address) keeps the list private while remaining queryable.

### Alarm Engine

The reactive heart of the system.

- **Condition Tree**: Parses and evaluates complex logical expressions.
- **State Machine**: Tracks alarm transitions (OK -> FIRING) to avoid duplicate alerts.
- **Context injection**: Populates evaluation context with real-time financial data.

## Data Flow: From Sync to Notification

1. **Trigger**: A sync job is triggered via cron (scheduler) or manually (API).
2. **Ingestion**: The Taskiq worker calls a Provider Adapter to fetch new data.
3. **Account Identity Resolution**: For each upserted `Account`, `_sync_accounts` in `SyncEngine` calls `extract_identifiers` (normalizes IBAN / SCAN / ABA to HMAC fingerprints via `security/fingerprint.py`) then `resolve_account_identity` to assign or merge `AccountIdentity` nodes. This happens inside the same database transaction as the account upsert so identity assignment is always consistent.
4. **Persistence**: New transactions/balances are upserted into the SQL Database.
5. **Transaction Deduplication**: `_sync_transactions` computes a Tier 1 identity-scoped hash (`identity_dedup_hash`) via `compute_tier1_hash` when `account.identity_id` is set. The upsert conflict key is `identity_dedup_hash`, ensuring the same physical transaction from two connections in the same identity is written only once. A Tier 2 content hash (`content_hash`) is also computed and stored for future opt-in dedup. Accounts without an identity fall back to the legacy MD5 `dedup_hash` path, preserving backward compatibility.
6. **Events**: The system detects notable changes (e.g., large transaction, low balance).
7. **Evaluation**: The Alarm Engine runs active rules against the updated state.
8. **Dispatch**: If an alarm fires, the Notifier Subsystem sends messages to configured channels. For email channels, `email/factory.py` selects the configured `EmailTransport` adapter and checks `email_suppression` before delivery.

## Key Data-Model Entities

### Account Identity Graph

The identity subsystem introduces three new tables that sit alongside the existing `accounts` table:

| Entity | Table | Purpose |
|---|---|---|
| `AccountIdentity` | `account_identities` | Stable node representing one real-world bank account. Holds `master_account_id` (oldest member `Account`), `origin` (`auto` / `manual`), and tombstone fields (`merged_into`, `merged_at`). |
| `AccountIdentifier` | `account_identifiers` | Append-only log of observed bank identifiers (IBAN, SCAN, ABA) keyed to an `AccountIdentity`. Values are stored as HMAC-SHA256 hex (`value_hmac`), never plaintext. `retired_at` excludes a row from future matching without deleting it. |
| `AccountIdentityAssertion` | `account_identity_assertions` | User-level statements about an ordered account pair: `same` (force merge) or `do_not_merge` (block auto-merge). Stored at the `Account`-pair level so assertions survive identity churn. |

Relationships:

- `Account.identity_id → account_identities.id` — each `Account` row belongs to at most one live identity.
- `AccountIdentity.master_account_id → accounts.id` — the canonical display source for the group; recomputed after every merge or sync.
- `AccountIdentifier.identity_id → account_identities.id` — identifiers accrete onto an identity and may be re-pointed on merge.

### Transaction Deduplication Columns

`Transaction` gains three new columns (migration `0006_txn_dedup`):

| Column | Type | Description |
|---|---|---|
| `identity_dedup_hash` | `String(64)` / UNIQUE | Tier 1: `HMAC(manifold-txn-dedup, identity_id + ':' + provider_transaction_id)`. Primary upsert conflict key when `identity_id` is set. |
| `content_hash` | `String(64)` / indexed | Tier 2: `HMAC(manifold-txn-content, identity_id + ':' + amount + ':' + date + ':' + desc)`. Stored for future opt-in dedup; not a unique constraint. |
| `is_cross_connection_duplicate` | `Boolean` | Set by backfill when a row is identified as a duplicate of a canonical row under the same identity. Read-time queries filter `WHERE is_cross_connection_duplicate = FALSE`. |

### Email Subsystem Entities

| Entity | Table | Purpose |
|---|---|---|
| `InstanceEmailSettings` | `instance_email_settings` | Singleton row (`id = 'default'`) holding the active provider name, encrypted config JSON, and from-address. |
| `EmailSuppression` | `email_suppression` | Bounce/complaint list. `address_hmac` stores a keyed hash of the recipient address so the list is queryable without storing plaintext addresses. |
| `EmailWebhookEvent` | `email_webhook_events` | Raw inbound webhook payloads from the email provider, encrypted at rest. Indexed on `(provider, event_type)` for replay and audit. |

## Encryption Architecture (DEK/KEK)

Manifold uses a "Envelope Encryption" model to secure sensitive user data:

- **Master Key (KEK)**: Derived from the environment's `SECRET_KEY` using HKDF-SHA256.
- **User DEK**: Each user has a unique Data Encryption Key, generated on first use.
- **Wrapping**: The User DEK is encrypted with the Master Key and stored in the database.
- **Application**: Sensitive fields (tokens, keys, secrets) are encrypted with the User DEK using AES-256-GCM before being persisted.
- **Isolation**: Data is only decrypted in memory during the execution of a task for that specific user.

## Background Job Architecture

Manifold leverages **Taskiq** for robust background task management:

- **Broker**: Redis 7 acts as the message transport.
- **Worker**: A separate process (or container) that executes the actual Python logic.
- **Scheduler**: Emits heartbeat tasks based on cron expressions defined in `.env`.
- **Concurrency**: Distributed locks in Redis prevent multiple workers from syncing the same account simultaneously.

## Database Backend Abstraction

The `DatabaseBackend` ABC allows Manifold to be dialect-agnostic:

- **SQLite**: Perfect for single-user, low-resource environments. Uses `aiosqlite` for async I/O.
- **PostgreSQL**: Recommended for multi-user or high-traffic setups. Uses `asyncpg`.
- **MariaDB/MySQL**: Supported for users with existing infrastructure. Uses `asyncmy`.
- **Migrations**: Alembic handles schema versioning across all supported dialects. The current head is `0007_email_subsystem`; earlier milestones are `0005_account_identity` (identity graph tables) and `0006_txn_dedup` (cross-connection dedup columns on `transactions`).

## Auth and Session Model

- **Session Management**: Secure, HttpOnly cookies for web sessions.
- **Bootstrap**: The first user (superadmin) is created based on environment variables if the database is empty.
- **Delegation**: A unique "Access Share" system allows users to delegate granular permissions (Viewer/Admin) to others without sharing credentials.

## In-Depth Component Analysis

### The Sync Engine

The Sync Engine orchestrates data retrieval across multiple providers. It is designed to be resilient and non-blocking:

1. **Job Queuing**: Sync requests are placed in the Redis-backed Taskiq queue. This prevents long-running HTTP requests to banks from tying up the API worker.
2. **Locking Mechanism**: Distributed locks in Redis ensure that two workers never attempt to sync the same provider connection simultaneously, preventing race conditions and potential bank-side rate limits.
3. **State Management**: Every sync run is tracked in the database with a start time, end time, and status. This provides a full audit trail of data ingestion.
4. **Error Handling**: Transient network errors are caught and logged, while authorization errors (expired tokens) trigger an update to the connection status, alerting the user to re-link their account.

### The Canonical Model

Manifold normalizes all external data into a "Canonical Model" before persistence. This ensures that the frontend and the alarm engine can interact with data in a consistent format regardless of whether it came from TrueLayer, a JSON endpoint, or a future CSV upload.

- **Accounts**: Standardizes balances, currencies, and account types (Current, Savings, Credit Card).
- **Transactions**: Standardizes amounts (always as Decimal), dates (ISO 8601 UTC), and merchant names.
- **Cards**: Tracks physical and virtual card metadata where available.

### Notification Router

The notification router is responsible for delivering alerts triggered by the Alarm Engine:

- **Template Rendering**: Translates internal alarm state into human-readable messages tailored for each channel (e.g., short for Telegram, rich for Email).
- **Batching**: Future-proofing for high-volume accounts to prevent alert fatigue.
- **Provider Isolation**: Each notifier (Slack, SMTP, etc.) is isolated; a failure in one channel does not prevent delivery through others.

### Account Identity Subsystem

The identity subsystem solves a fundamental aggregation problem: the same physical bank account may appear under multiple `ProviderConnection` rows (e.g., a current account linked via TrueLayer and again via a JSON endpoint). Without grouping, balances and transactions are double-counted.

**Identifier extraction** (`domain/account_identity.py: extract_identifiers`): At sync time, raw IBAN, UK sort-code/account-number (SCAN), and US routing/account-number (ABA) fields from the provider `AccountData` DTO are normalized and hashed with `compute_identifier_hmac` (`security/fingerprint.py`). The HMAC key is derived via HKDF with label `manifold-fingerprint` from the application secret, scoped by `user_id` to make cross-user comparison structurally impossible. Multi-currency providers (e.g., Wise, Revolut) that issue multiple wallets under a single IBAN include the `currency` dimension in the hash so wallets remain distinct.

**Identity resolution** (`resolve_account_identity`): After each account upsert the engine runs a three-way match:

- **0 matches** — mint a new `AccountIdentity` node and bind the account to it.
- **1 match** — bind the account to the existing identity; accrete any new identifiers onto it.
- **≥2 matches** — auto-merge: the identity owning the oldest `Account` (by `created_at`, tie-broken by smallest UUID) is the survivor; losers are tombstoned (`merged_into`/`merged_at` set). A `do_not_merge` `AccountIdentityAssertion` for any pair in the cluster vetoes the merge entirely.

**Manual merge / unmerge** (`IdentityMergeService`, `IdentityUnmergeService`): Users can explicitly merge account pairs via the frontend. Unmerge reconstructs the pre-merge partition using `merged_from_identity` provenance on identifier rows and re-derives each account's HMAC fingerprints. Bridge accounts — those whose identifiers span two origin groups — are retained with the survivor.

**Backfill** (`domain/identity_backfill.py`): A one-shot idempotent task (migration `0005_account_identity`) processes all existing `Account` rows that have `identity_id IS NULL`, running the same Phase 3 match/create/merge logic against each user's DEK context.

**Merge suggestions** (`suggest_merges`): A scoring function surfaces candidate pairs for manual review. Pairs are scored on display-name trigram similarity, account-type match, currency match, and same provider type; pairs with an existing `do_not_merge` assertion or a shared identity are excluded.

For full details see [`docs/account-identity.md`](account-identity.md).

### Transaction Cross-Connection Deduplication

When two `Account` rows belong to the same `AccountIdentity`, both connections will independently fetch many of the same transactions from the bank. The Tier 1 dedup mechanism in `SyncEngine._sync_transactions` prevents double-insertion.

**Tier 1** (`domain/transaction_fingerprint.py: compute_tier1_hash`): For each transaction the engine computes `HMAC(manifold-txn-dedup, identity_id + ':' + normalized_provider_transaction_id)`. The 64-char hex digest is stored in `Transaction.identity_dedup_hash`. Because it is covered by a `UNIQUE` constraint, the upsert with conflict key `identity_dedup_hash` silently updates the existing row rather than inserting a duplicate. No DEK is required — `provider_transaction_id` is plaintext.

**Tier 2** (`compute_content_hash`): A content-based fallback hash (`HMAC(manifold-txn-content, identity_id + ':' + amount + ':' + date + ':' + normalized_description)`) is computed from already-decrypted values while the DEK context is active and stored in `Transaction.content_hash`. It is indexed for lookup but carries no unique constraint and is **disabled by default** — it exists for future opt-in dedup of transactions where the provider assigns different IDs to the same payment across connections.

**Backward compatibility**: Accounts without an `identity_id` continue to use the legacy `MD5(connection_id:provider_transaction_id)` hash stored in `Transaction.dedup_hash`. The upsert conflict key switches to `dedup_hash` for these rows. Both columns are always written, so the `uq_transactions_dedup_hash` constraint is never violated during the transition period.

**Duplicate flagging**: The `Transaction.is_cross_connection_duplicate` boolean is set by a post-backfill pass to mark legacy duplicate rows. All read-time queries filter `WHERE is_cross_connection_duplicate = FALSE` to avoid double-counting balances and spending summaries.

### Email Transport Subsystem

Manifold's outbound email is decoupled from any specific provider through the `EmailTransport` protocol (`email/base.py`). The protocol enforces four methods: `send`, `validate_config`, `verify_webhook`, and `parse_webhook` — covering the full lifecycle of transactional email plus suppression list maintenance.

**Adapters** (`email/adapters/`): Six adapters ship in-tree: `smtp` (direct SMTP via `aiosmtplib`), `ses` (AWS SES v2 via `boto3`), `resend`, `postmark`, `mailgun`, and `brevo`. Each is a thin wrapper around the provider's HTTP or SDK API; all config is encrypted at rest in `InstanceEmailSettings.config`.

**Factory** (`email/factory.py: get_transport`): The factory function is the only place that knows which adapter class to instantiate. API and worker code depends only on the `EmailTransport` protocol, never on a concrete adapter.

**Suppression management**: Providers deliver bounce and complaint events as webhooks. Each adapter's `verify_webhook` validates the provider-specific signature before `parse_webhook` extracts `SuppressionEvent` objects. The API layer writes `EmailSuppression` rows with an HMAC of the address (`address_hmac`) so suppression lookups are O(1) without storing plaintext email addresses. Raw webhook payloads are journalled in `EmailWebhookEvent` (encrypted) for audit and replay.

**Settings persistence**: `InstanceEmailSettings` is a singleton row (`id = 'default'`) in `instance_email_settings`. `provider` and `config` (encrypted JSON) are loaded by `get_transport` at send time. `from_address` and `from_name` are also encrypted.

For full details see [`docs/email.md`](email.md).

### Security and Isolation

- **Request ID Tracking**: Every request is assigned a unique UUID, which is propagated through logs and task execution context. This allows for seamless end-to-end tracing of operations.
- **RBAC (Role-Based Access Control)**:
  - `superadmin`: Can manage users and system settings but cannot see financial data.
  - `user`: Owns their data and can manage their own connections/alarms.
  - `viewer`: Can view data delegated to them by another user but cannot modify connections or alarms.

## Database Backend Deep-Dive

The pluggable database layer is one of Manifold's core strengths. By utilizing the `DatabaseBackend` abstraction, we ensure that the application logic remains decoupled from the underlying storage engine.

### SQLite Implementation

- **Driver**: `aiosqlite`
- **Use Case**: Individual users, development, or low-power hardware.
- **Optimization**: We enable WAL (Write-Ahead Logging) mode by default to support concurrent reads and writes, essential for a multi-process environment like Manifold.

### PostgreSQL Implementation

- **Driver**: `asyncpg`
- **Use Case**: Multi-user households, teams, or high-volume data ingestion.
- **Optimization**: Leverages native PostgreSQL JSONB columns for storing provider-specific metadata and alarm condition histories, providing superior query performance over traditional text columns.

### MariaDB / MySQL Implementation

- **Driver**: `asyncmy`
- **Use Case**: Users with existing MySQL-compatible infrastructure.
- **Optimization**: Uses the `JSON` data type where available to ensure parity with the PostgreSQL experience.

## The Middleware Stack

Every request to the Manifold API passes through a series of specialized middlewares:

1. **Request ID Middleware**: Injects a unique `X-Request-ID` header into every response and populates the logging context.
2. **CORS Middleware**: Strictly enforces cross-origin policies based on your `.env` configuration.
3. **Authentication Middleware**: Resolves the current user from session cookies or Bearer tokens.
4. **Error Handling Middleware**: Catches domain exceptions (like `NotFoundError` or `ValidationError`) and translates them into standardized RFC 7807 problem details.

## Front-to-Back Flow Example: Viewing a Dashboard

1. **Request**: The React frontend sends a `GET /api/v1/dashboard/summary` request.
2. **Auth**: Middleware verifies the session cookie and identifies User A.
3. **Service**: The `DashboardService` is called. It queries the `Account` and `Transaction` models, filtered by `owner_id == User A`.
4. **Encryption**: If the view requires sensitive data (rare for the summary), the User's DEK is used to decrypt fields on-the-fly.
5. **Response**: A normalized JSON object is returned.
6. **UI**: TanStack Query on the frontend caches the response and updates the Recharts-based visualizations.

## Task Orchestration and Reliability

The relationship between the API, Redis, and the Taskiq worker is built for reliability.

### Resilience Patterns

- **Retries**: If a sync task fails due to an external API timeout, Taskiq is configured to retry with an exponential backoff.
- **Timeouts**: Every task has a hard execution limit (e.g., 5 minutes for a full account sync) to prevent "zombie" workers from consuming resources indefinitely.
- **Idempotency**: All domain upsert operations (transactions, accounts) are idempotent. If a task runs twice, the resulting state in the database remains the same.

### The Scheduler (manifold-tasker)

The scheduler process is a lightweight heartbeat generator. It does not execute business logic. Instead, it periodically pushes "Trigger" messages into Redis based on the cron schedules defined in your `.env`. This separation ensures that even if a worker is overwhelmed, the schedule itself remains consistent.

## Frontend Architecture

The Manifold UI is a high-performance Single Page Application (SPA):

- **Routing**: `TanStack Router` provides full type-safety for URLs and search parameters.
- **State Management**: We avoid complex global stores, instead relying on `TanStack Query` for server state and standard React `useState/useContext` for UI state.
- **Components**: Built on `shadcn/ui`, ensuring that the interface is accessible, responsive, and easy to maintain.
- **Visualization**: `Recharts` is used for all financial charting, allowing for interactive exploration of spending patterns and balance history.

## Future Architectural Directions

As Manifold evolves, we are exploring several architectural enhancements:

1. **Event Sourcing**: Moving from a purely state-based model to an event-sourced model for transaction history to provide even better auditability.
2. **Plugin System**: Allowing users to load custom provider and notifier code without modifying the core Manifold package.
3. **GraphQL Support**: Providing a GraphQL API alongside REST for more flexible data retrieval by third-party dashboards.

## Deployment Topology and Scaling

While Manifold is optimized for single-node deployment, its components can be scaled independently if needed:

- **API Workers**: Horizontal scaling of the FastAPI container behind a load balancer.
- **Taskiq Workers**: Scaling background workers to handle higher sync frequencies or more complex alarm evaluations.
- **Database**: Moving from the local volume to a managed RDS or high-availability cluster.
