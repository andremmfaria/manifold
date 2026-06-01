# Provider Adapter Guide

Providers are the bridge between Manifold and the external financial world. This document explains how providers work and how to add new ones.

## Overview

A Provider is a pluggable module that implements a standard interface for fetching financial data. All providers in Manifold are asynchronous and isolated from the core domain logic.

## BaseProvider Interface

Every provider must inherit from `BaseProvider` (`manifold.providers.base`) and implement the three abstract methods below. All methods receive a `ProviderConnectionContext` (defined in `manifold.providers.types`) which carries the decrypted connection credentials and configuration for the current request.

### Abstract methods (must implement)

```python
async def get_accounts(self, context: ProviderConnectionContext) -> list[AccountData]: ...

async def get_balances(
    self, context: ProviderConnectionContext, accounts: list[AccountData]
) -> list[BalanceData]: ...

async def get_transactions(
    self, context: ProviderConnectionContext, account: AccountData
) -> list[TransactionData]: ...
```

### Optional capability methods (default to no-op)

Override these and set the corresponding capability flag to `True` if your provider supports these data types:

| Method | Capability flag | Default return |
|---|---|---|
| `get_pending_transactions(context, account)` | `supports_pending` | `[]` |
| `get_cards(context)` | `supports_cards` | `[]` |
| `get_direct_debits(context, account)` | `supports_direct_debits` | `[]` |
| `get_standing_orders(context, account)` | `supports_standing_orders` | `[]` |

### Auth delegation methods (provided by BaseProvider)

`BaseProvider` delegates auth to a `BaseProviderAuth` instance stored as `self.auth`. These methods are available to callers without overriding:

- `get_auth_url(context)` — build the OAuth2 authorization URL.
- `exchange_code(context, code, state)` — exchange an auth code for tokens.
- `refresh_if_needed(context)` — refresh an expired access token; returns updated credentials dict.
- `is_connection_valid(context)` — check whether a connection has usable credentials.

Every concrete provider **must** assign `self.auth` before calling `super().__init__()`.

### Data transfer types

Providers return typed dataclasses from `manifold.providers.types`, not ORM models. The sync engine maps these into the database:

| Dataclass | Purpose |
|---|---|
| `ProviderConnectionContext` | Input context: connection id, user id, credentials, config |
| `AccountData` | Normalized account descriptor (IBAN, sort code, account number, currency, display name) |
| `BalanceData` | Current/available/overdraft balance for one account |
| `TransactionData` | Settled transaction |
| `PendingTransactionData` | Pending/authorised transaction |
| `CardData` | Credit/debit card linked to a connection |
| `DirectDebitData` | Direct debit mandate |
| `StandingOrderData` | Standing order |

## Auth Abstraction

Every provider owns an `auth` object that implements `BaseProviderAuth` (`manifold.providers.auth.base`). The base class provides no-op defaults for all methods; concrete subclasses override as needed.

Available implementations in `manifold/providers/auth/`:

| Class | Module | Used by |
|---|---|---|
| `OAuth2CodeFlowAuth` | `oauth2` | TrueLayer |
| `BearerTokenAuth` | `bearer` | JSON provider (bearer mode) |
| `ApiKeyAuth` | `api_key` | JSON provider (api_key mode) |
| `BasicAuth` | `basic` | JSON provider (basic mode) |
| `NoAuth` | `noauth` | JSON provider (none mode) |

The auth object is typically constructed in a `build_auth()` factory function in the provider's own `auth.py` module and assigned inside `__init__`.

## TrueLayer Adapter

The TrueLayer adapter connects to the TrueLayer Open Banking API, providing access to thousands of banks across the UK and EU.

### Credential scoping

Two distinct credential levels coexist:

- **App-level**: `client_id`, `client_secret`, and `redirect_uri` are global settings loaded from environment variables via `manifold.config.settings` (`TRUELAYER_CLIENT_ID`, `TRUELAYER_CLIENT_SECRET`, `TRUELAYER_REDIRECT_URI`). These are wired into the `OAuth2CodeFlowAuth` instance at startup in `truelayer/auth.py:build_auth()`.
- **Per-connection**: Each user's `access_token` and `refresh_token` (plus the computed `expires_at`) are stored encrypted in `ProviderConnection.credentials_encrypted` (an `EncryptedJSON` column). They are never shared across connections or users.

### OAuth2 Flow

1. **Authorization**: User is redirected to TrueLayer to select their bank. The URL is built by `OAuth2CodeFlowAuth.get_auth_url()` using the app-level `client_id`.
2. **Callback**: TrueLayer redirects back to Manifold with an auth code.
3. **Exchange**: Manifold calls `exchange_code()`, which POSTs to TrueLayer's token endpoint using `client_id` and `client_secret`, and returns the token payload.
4. **Persistence**: The token dict (including a computed `expires_at` ISO timestamp) is stored in `ProviderConnection.credentials_encrypted`.

### Token refresh

`OAuth2CodeFlowAuth.refresh_if_needed()` is called automatically at the start of each sync. It checks `expires_at` and re-issues a `refresh_token` grant if the access token expires within 5 minutes. The refreshed credentials are written back to `ProviderConnection.credentials_encrypted` by the sync engine.

### Sandbox vs Production

Controlled via the `TRUELAYER_SANDBOX` environment variable (`settings.truelayer_sandbox`). Both `build_auth()` and `TrueLayerClient` branch on this flag to select the correct base URLs (`auth.truelayer-sandbox.com` / `api.truelayer-sandbox.com` vs the production equivalents).

### Implementation Details

- **Consent Expiry**: TrueLayer consents usually expire every 90 days, requiring the user to re-authorize. The sync engine detects a `consent_expires_at` in the past and sets `auth_status = "consent_expired"`.
- **Rate Limiting**: `TrueLayerClient.get()` retries on HTTP 429 with exponential backoff (up to 3 attempts, doubling delay). A `ProviderRateLimitError` is raised after the last attempt.
- **Supported scopes**: `accounts`, `balance`, `transactions`, `direct_debits`, `standing_orders`, `offline_access`.

## JSON Provider

The JSON provider (`manifold.providers.json_provider.adapter.JsonProvider`) is a flexible adapter for ingesting data from static files or custom HTTP sources — useful for fixtures, manual uploads, and testing.

### Source configuration

The source is configured via the connection's `config` dict (stored in `ProviderConnection.config`, an `EncryptedJSON` column). At minimum, either `url` (HTTP/HTTPS) or `path` (local filesystem) must be set.

```json
{
  "url": "https://api.example.com/finance",
  "auth_mode": "bearer",
  "mapping": {
    "accounts_path": "accounts",
    "balances_path": "balances",
    "transactions_path": "transactions",
    "transaction_account_id": "account_id"
  }
}
```

All `mapping` values are top-level JSON keys in the fetched payload (not JSONPath expressions). The defaults are `"accounts"`, `"balances"`, `"transactions"`, and `"account_id"` respectively.

### Supported auth modes (`auth_mode`)

- **`none`** (default): No authentication.
- **`api_key`**: Injects a key via a custom header (configured via `ApiKeyAuth`).
- **`bearer`**: Standard `Authorization: Bearer <token>`.
- **`basic`**: Standard `Authorization: Basic <base64>`.

The auth mode is resolved at fetch time by `json_provider/auth.py:build_auth()`.

## Provider Registry

Providers are registered at application startup by `register_all()` in `manifold.providers.registry`. The `ProviderRegistry` maps each provider's `provider_type` class attribute to its implementation class.

```python
# manifold/providers/registry.py

class ProviderRegistry:
    def register(self, provider_cls: type[BaseProvider]) -> None:
        self._providers[provider_cls.provider_type] = provider_cls

    def get(self, provider_type: str) -> BaseProvider:
        provider_cls = self._providers.get(provider_type)
        if provider_cls is None:
            raise KeyError(f"provider '{provider_type}' not registered")
        return provider_cls()


def register_all() -> None:
    from manifold.providers.json_provider.adapter import JsonProvider
    from manifold.providers.truelayer.adapter import TrueLayerProvider

    registry.register(TrueLayerProvider)
    registry.register(JsonProvider)
```

Note: `register()` takes the class itself; the registry key is derived from `provider_cls.provider_type`, not passed as a separate string argument.

## How to Add a New Provider

Adding a new provider involves three steps.

### 1. Define the Schema

Create a Pydantic model in `backend/src/manifold/schemas/providers/<provider_id>.py` for any provider-specific configuration that will be stored in `ProviderConnection.config`.

### 2. Implement the Adapter

Create a new package at `backend/src/manifold/providers/<provider_id>/`:

- `adapter.py` — the `BaseProvider` subclass
- `auth.py` — a `build_auth()` factory returning a `BaseProviderAuth` instance
- `mappers.py` — functions mapping raw provider payloads to `manifold.providers.types` dataclasses

```python
# adapter.py
from manifold.providers.base import BaseProvider
from manifold.providers.types import (
    AccountData, BalanceData, TransactionData, ProviderConnectionContext
)
from manifold.providers.<provider_id>.auth import build_auth


class MyNewProvider(BaseProvider):
    provider_type = "myprovider"
    display_name = "My Provider"

    def __init__(self) -> None:
        self.auth = build_auth()
        super().__init__()

    async def get_accounts(self, context: ProviderConnectionContext) -> list[AccountData]:
        ...

    async def get_balances(
        self, context: ProviderConnectionContext, accounts: list[AccountData]
    ) -> list[BalanceData]:
        ...

    async def get_transactions(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[TransactionData]:
        ...
```

Return `AccountData` objects with as many of `iban`, `sort_code`, and `account_number` populated as the provider exposes — these fields drive account-identity matching (see below).

### 3. Register the Provider

Add your provider to `register_all()` in `manifold.providers.registry`:

```python
from manifold.providers.<provider_id>.adapter import MyNewProvider
registry.register(MyNewProvider)
```

## Account-Identity Matching and Transaction Deduplication

The data a provider returns does not go straight to storage in isolation — it feeds two cross-cutting subsystems that operate at sync time. Understanding these is important when writing a provider adapter.

### Account-identity matching

After each account is upserted, the sync engine calls `domain.account_identity.resolve_account_identity()` on the resulting `Account` row. This function:

1. **Extracts identifiers** from the account's `iban`, `sort_code`, and `account_number` fields (via `extract_identifiers()`). Each field is normalized — IBANs are stripped to uppercase alphanumeric and validated with mod-97; UK sort-code/account-number pairs are canonicalized to `NNNNNN:NNNNNNNN`.
2. **HMAC-fingerprints** each normalized value under a per-type HKDF-derived key (`manifold-fingerprint` label), scoped to `user_id` so cross-user comparison is impossible by construction.
3. **Matches or mints** an `AccountIdentity`. If any fingerprint matches an existing `AccountIdentifier` row for the same user, the account joins that identity. If fingerprints span multiple identities, those identities are auto-merged (survivor = oldest by `created_at`). Accounts that yield zero identifiers (no IBAN, no sort-code/account-number) remain identity-less until a manual merge.

**Implication for adapter authors**: populate `AccountData.iban`, `AccountData.sort_code`, and `AccountData.account_number` whenever the provider exposes them. Omitting these prevents accounts from grouping across connections, which degrades the merged balance view.

### Cross-connection transaction deduplication

Transactions are deduplicated scoped by `identity_id` rather than by `provider_connection_id`. This means that if the same real-world transaction appears in two connections that share an identity (e.g. the same bank account connected twice), only one copy is stored.

The dedup uses a two-tier fingerprint (`domain.transaction_fingerprint`):

- **Tier 1** (always active when `account.identity_id` is set): `HMAC(manifold-txn-dedup, identity_id + ':' + normalized_provider_transaction_id)`. No DEK required.
- **Tier 2** (opt-in content hash): `HMAC(manifold-txn-content, identity_id + ':' + amount + ':' + date + ':' + normalized_description)`. Requires the DEK context to be active at sync time.

**Implication for adapter authors**: return a stable, unique `provider_transaction_id` on every `TransactionData`. If the provider does not provide one, Tier 1 dedup is unavailable and duplicate transactions can appear when the same account is connected more than once under a shared identity.

For the full design of account identities, merge/unmerge semantics, and manual assertions, see `docs/account-identity.md`.

## ProviderConnection Model

`ProviderConnection` (`manifold.models.provider_connection`) is the database record that anchors a connection. Key fields:

| Field | Type | Purpose |
|---|---|---|
| `provider_type` | `EncryptedText` | Matches a registered `provider_type` value |
| `credentials_encrypted` | `EncryptedJSON` | Per-user OAuth tokens (access\_token, refresh\_token, expires\_at) or other auth state |
| `config` | `EncryptedJSON` | Provider-specific configuration (e.g. JSON provider source URL and mappings) |
| `consent_expires_at` | `DateTime` | When the provider consent lapses (TrueLayer: ~90 days) |
| `last_sync_at` | `DateTime` | Timestamp of the last successful sync |
| `status` | `Text` | `active` / `inactive` / `error` / `expired` |
| `auth_status` | `Text` | `connected` / `refresh_failed` / `consent_expired` |

Both `credentials_encrypted` and `config` are encrypted at rest with the user's Data Encryption Key (DEK) via the `EncryptedJSON` column type. The sync engine decrypts them before constructing `ProviderConnectionContext`.

## Operational Considerations for Providers

### Rate Limiting and Backoff

Financial APIs are notoriously sensitive to high request volumes. The Provider layer implements:

- **Provider-Level Rate Limits**: Hard-coded or configuration-based limits on requests per minute.
- **Exponential Backoff**: Automatic retries for `429 Too Many Requests` or `5xx` server errors.
- **Circuit Breaking**: Temporarily disabling a provider if it consistently returns errors, preventing wasteful worker cycles.

### Data Sensitivity and Masking

To protect user privacy, providers follow a "Strict Ingestion" policy:

- **No Raw Storage**: Raw JSON responses from banks are never stored in the database. Only the normalized data required for Manifold's canonical model is kept.
- **PII Handling**: Personal Identifiable Information (like full name or address) is discarded if not essential for account identification.
- **Log Masking**: Sensitive tokens and account numbers are automatically masked in application logs.

### Multi-Region and Currency Support

The provider layer is built with internationalization in mind:

- **Currency Normalization**: All balances and transactions include an ISO 4217 currency code.
- **Timezone Awareness**: Timestamps are converted to UTC at the provider boundary to ensure consistent ordering in the UI and Alarm Engine.
- **Regional Adapters**: While TrueLayer covers UK/EU, the adapter pattern allows for the addition of regional specific providers (e.g., Plaid for US/Canada) without core logic changes.

### Best Practices for Custom Adapters

If you are developing your own provider for a local credit union or a niche financial service, keep these principles in mind.

#### 1. Minimal Persistence

Only map and return the data you absolutely need. If the bank provides 50 fields for a transaction but Manifold only uses 5, discard the rest at the provider boundary. This minimizes the risk and size of your encrypted data store.

#### 2. Robust Identification

Use stable, unique IDs provided by the bank for accounts and transactions. This ensures that the upsert logic in Manifold can correctly identify existing records and avoid duplicates. If a stable ID is not available, consider generating a deterministic hash from a combination of the date, amount, and description.

Populate `iban`, `sort_code`, and `account_number` wherever available — these drive the account-identity matching system and are essential for correct cross-connection deduplication.

#### 3. Handle Partial Success

Some bank APIs return multiple accounts. If one account fails to sync but others succeed, your provider should log the error for the failing account but still return the data for the successful ones. Manifold's sync engine is designed to handle these partial results gracefully.

#### 4. Respect User Privacy

Never log raw credentials or full account numbers. Use the provided logging helpers to mask sensitive information before it hits the disk.

## Provider Versioning and Compatibility

As external APIs change, so must our adapters.

- **Backwards Compatibility**: We strive to maintain stable canonical models so that updates to a provider adapter do not require database migrations.
- **Provider Metadata**: Providers can store small amounts of state (like a cursor or last-synced marker) in the `ProviderConnection.config` field. This state is encrypted along with the rest of the config.

## Testing Provider Adapters

Building reliable providers requires robust testing:

- **Mocking**: Providers are tested against recorded HTTP interactions using `vcrpy` or equivalent tools. This ensures that tests are fast and don't require live bank access.
- **Contract Testing**: Ensuring that changes in bank APIs don't break the canonical mapping. We use schema validation to verify that the provider output matches the `AccountData` and `TransactionData` dataclasses.
- **Sandbox Testing**: Using TrueLayer or bank-specific sandbox environments for end-to-end verification during development. This is the only way to test the full OAuth flow and real-world token rotation.
- **Error Simulation**: We explicitly test how providers handle `503 Service Unavailable`, `401 Unauthorized`, and malformed JSON to ensure the system fails gracefully and provides actionable feedback to the user.

## Provider Performance and Resources

Syncing financial data can be resource-intensive. To keep Manifold snappy:

- **Streaming Responses**: For banks with thousands of transactions, providers use asynchronous generators to stream data into the database, keeping memory usage constant regardless of the transaction count.
- **Connection Pooling**: Providers share a global HTTPX client with an optimized connection pool, minimizing the overhead of repeated TLS handshakes.
- **Concurrency Control**: While multiple connections can sync in parallel, a single connection is always limited to one active sync task to prevent session conflicts.
