# Provider Adapter Guide

Providers are the bridge between Manifold and the external financial world. This document explains how providers work and how to add new ones.

## Overview

A Provider is a pluggable module that implements a standard interface for fetching financial data. All providers in Manifold are asynchronous and isolated from the core domain logic.

## BaseProvider Interface

Every provider must inherit from `BaseProvider` and implement the following methods:

- `sync_accounts()`: Fetch all accounts accessible to the connection.
- `sync_transactions(account_id, since)`: Fetch transactions for a specific account.
- `sync_balances()`: Fetch current balances for all accounts.
- `handle_callback(params)`: (Optional) Handle OAuth2 redirect payloads.
- `refresh_connection()`: (Optional) Rotate expired tokens.

## TrueLayer Adapter

The TrueLayer adapter connects to the TrueLayer Open Banking API, providing access to thousands of banks across the UK and EU.

### OAuth2 Flow
1.  **Authorization**: User is redirected to TrueLayer to select their bank.
2.  **Callback**: TrueLayer redirects back to Manifold with an auth code.
3.  **Exchange**: Manifold exchanges the code for an `access_token` and `refresh_token`.
4.  **Persistence**: Tokens are encrypted with the user's DEK and stored.

### Implementation Details
- **Token Rotation**: Tokens are refreshed automatically when they expire (typically every 60 minutes).
- **Consent Expiry**: TrueLayer consents usually expire every 90 days, requiring the user to re-authorize.
- **Sandbox vs Production**: Controlled via the `TRUELAYER_SANDBOX` environment variable.

## JSON Provider

The JSON provider is a flexible adapter for ingesting data from custom sources or manual uploads.

### Config Format
The JSON provider expects a configuration that defines where to fetch data and how to map it:
```json
{
  "url": "https://api.example.com/finance",
  "auth_type": "bearer",
  "mappings": {
    "account_name": "$.data.name",
    "balance": "$.data.current_balance"
  }
}
```

### Supported Auth Modes
- **No Auth**: For public or internal endpoints.
- **ApiKey**: Via custom header (e.g., `X-API-KEY`).
- **Bearer**: Standard `Authorization: Bearer <token>`.
- **Basic**: Standard `Authorization: Basic <base64>`.

## Provider Registry

Providers are registered at application startup. The `ProviderRegistry` maintains a map of provider IDs to their implementation classes.

```python
# registry.py
from manifold.providers.truelayer import TrueLayerProvider
from manifold.providers.json import JSONProvider

def register_all():
    registry.register("truelayer", TrueLayerProvider)
    registry.register("json", JSONProvider)
```

## How to Add a New Provider

Adding a new provider involves three steps:

### 1. Define the Schema
Create a Pydantic model in `backend/src/manifold/schemas/providers/<provider_id>.py` for any provider-specific configuration.

### 2. Implement the Adapter
Create a new class in `backend/src/manifold/providers/<provider_id>.py`:

```python
from manifold.providers.base import BaseProvider
from manifold.models.canonical import Account, Transaction

class MyNewProvider(BaseProvider):
    async def sync_accounts(self) -> list[Account]:
        # Implement logic to fetch and map accounts
        pass

    async def sync_transactions(self, account_id: str, since: datetime) -> list[Transaction]:
        # Implement logic to fetch and map transactions
        pass
```

### 3. Register the Provider
Add your provider to the `register_all()` function in the provider registry.

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

If you are developing your own provider for a local credit union or a niche financial service, keep these principles in mind:

### 1. Minimal Persistence
Only map and return the data you absolutely need. If the bank provides 50 fields for a transaction but Manifold only uses 5, discard the rest at the provider boundary. This minimizes the risk and size of your encrypted data store.

### 2. Robust Identification
Use stable, unique IDs provided by the bank for accounts and transactions. This ensures that the `upsert` logic in Manifold can correctly identify existing records and avoid duplicates. If a stable ID is not available, consider generating a deterministic hash from a combination of the date, amount, and description.

### 3. Handle Partial Success
Some bank APIs return multiple accounts. If one account fails to sync but others succeed, your provider should log the error for the failing account but still return the data for the successful ones. Manifold's sync engine is designed to handle these partial results gracefully.

### 4. Respect User Privacy
Never log raw credentials or full account numbers. Use the provided logging helpers to mask sensitive information before it hits the disk.

## Provider Versioning and Compatibility

As external APIs change, so must our adapters.
- **Backwards Compatibility**: We strive to maintain stable canonical models so that updates to a provider adapter do not require database migrations.
- **Provider Metadata**: Providers can store small amounts of state (like the "Last Synced ID" or "Cursor") in the `ProviderConnection` metadata field. This state is encrypted along with the credentials.

## Testing Provider Adapters

Building reliable providers requires robust testing:
- **Mocking**: Providers are tested against recorded HTTP interactions using `vcrpy` or equivalent tools. This ensures that tests are fast and don't require live bank access.
- **Contract Testing**: Ensuring that changes in bank APIs don't break the canonical mapping. We use schema validation to verify that the provider output matches the Manifold `Account` and `Transaction` models.
- **Sandbox Testing**: Using TrueLayer or bank-specific sandbox environments for end-to-end verification during development. This is the only way to test the full OAuth flow and real-world token rotation.
- **Error Simulation**: We explicitly test how providers handle `503 Service Unavailable`, `401 Unauthorized`, and malformed JSON to ensure the system fails gracefully and provides actionable feedback to the user.

## Provider Performance and Resources

Syncing financial data can be resource-intensive. To keep Manifold snappy:
- **Streaming Responses**: For banks with thousands of transactions, providers use asynchronous generators to stream data into the database, keeping memory usage constant regardless of the transaction count.
- **Connection Pooling**: Providers share a global HTTPX client with an optimized connection pool, minimizing the overhead of repeated TLS handshakes.
- **Concurrency Control**: While multiple connections can sync in parallel, a single connection is always limited to one active sync task to prevent session conflicts.
