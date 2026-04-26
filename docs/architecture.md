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

### Provider Layer (Adapters)

Handles communication with external financial institutions.

- **Normalization**: Maps provider-specific JSON to Manifold canonical models.
- **Auth Management**: Manages OAuth2 flows, token rotation, and API key storage.
- **Resilience**: Implements rate limiting and retry logic specific to each provider.

### Alarm Engine

The reactive heart of the system.

- **Condition Tree**: Parses and evaluates complex logical expressions.
- **State Machine**: Tracks alarm transitions (OK -> FIRING) to avoid duplicate alerts.
- **Context injection**: Populates evaluation context with real-time financial data.

## Data Flow: From Sync to Notification

1. **Trigger**: A sync job is triggered via cron (scheduler) or manually (API).
2. **Ingestion**: The Taskiq worker calls a Provider Adapter to fetch new data.
3. **Persistence**: New transactions/balances are upserted into the SQL Database.
4. **Events**: The system detects notable changes (e.g., large transaction, low balance).
5. **Evaluation**: The Alarm Engine runs active rules against the updated state.
6. **Dispatch**: If an alarm fires, the Notifier Subsystem sends messages to configured channels.

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
- **Migrations**: Alembic handles schema versioning across all supported dialects.

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
