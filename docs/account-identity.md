# Account Identity and Transaction Cross-Connection Dedup

Manifold is designed to aggregate data from multiple provider connections — a user may connect the same bank account through two different TrueLayer consents, or through both TrueLayer and a JSON provider. Without coordination, the same physical bank account appears as two separate `Account` rows, and the same transaction appears twice. The Account Identity subsystem eliminates this duplication by building a stable, cross-connection identity graph and using it to deduplicate transactions at sync time.

## Problem Statement

A single real-world bank account can produce multiple `Account` rows in Manifold:

- The user connects two provider connections to the same institution (e.g., two TrueLayer consents), each of which reports the same IBAN or sort-code/account-number.
- The user re-links a disconnected connection, generating a new `Account` row for the same underlying account.
- Two different providers (e.g., TrueLayer and a JSON import) both report the same account.

Without deduplication, balance summaries double-count balances and transaction lists contain the same transaction twice. The Account Identity subsystem solves this by:

1. Extracting bank-standard identifiers (IBAN, UK sort-code+account-number, US routing+account-number) from each `Account` row.
2. Hashing them with a keyed HMAC so the raw values are never stored.
3. Grouping `Account` rows that share a hash into a shared `AccountIdentity` node.
4. Using the `identity_id` on each account to scope transaction deduplication across connections.

---

## Data Model

Four tables implement the subsystem. They are created together in migration `0005_account_identity` (revision `0005_account_identity`, revises `0004_user_names`).

### `account_identities`

The stable internal node representing one real-world bank account. Once assigned, it is never recomputed — new evidence accretes onto it.

| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` UUID PK | Assigned once, never recomputed. |
| `user_id` | FK → `users.id` | Index. Scopes the identity to a user. |
| `master_account_id` | FK → `accounts.id`, nullable | Canonical display/metadata source. Set to the oldest member `Account` by `created_at` (tie-break: smallest UUID). Nullable until the first account is bound. |
| `origin` | `Text` | `'auto'` (sync engine) or `'manual'` (explicit user merge). `CHECK` constraint enforces these two values. |
| `merged_into` | FK → `account_identities.id`, nullable | Self-referential. Non-null means this identity is a tombstone absorbed into the survivor. |
| `merged_at` | `DateTime(timezone=True)`, nullable | When the tombstone merge occurred. |
| `created_at`, `updated_at` | `DateTime(timezone=True)` | From `TimestampMixin`. |

A tombstone identity (`merged_into` non-null) is kept permanently for audit and to support reversible unmerge. It is never deleted.

### `account_identifiers`

Append-only table of observed bank identifiers, each keyed to an `AccountIdentity`. One identity may accumulate multiple identifier rows across syncs (e.g., both an IBAN row and a SCAN row for the same account).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `identity_id` | FK → `account_identities.id` | Index. Which identity owns this identifier. |
| `user_id` | FK → `users.id` | Index. Denormalised for the unique constraint. |
| `id_type` | `String(16)` | `'iban'`, `'scan'`, or `'aba'`. `CHECK` constraint. `String(16)` (not `Text`) so MariaDB can index it without a prefix-length fallback. |
| `value_hmac` | `String(64)` | HMAC-SHA256 hex digest of the normalized identifier value (see §Fingerprinting). Always exactly 64 chars. |
| `currency` | `String(8)`, nullable | ISO 4217 code for multi-currency providers; sentinel `'-'` for single-currency providers so the column is never NULL inside the unique index. |
| `last_seen_at` | `DateTime(timezone=True)` | Bumped on every sync the identifier is observed. |
| `retired_at` | `DateTime(timezone=True)`, nullable | Non-null means excluded from matching. Set when a collision is detected during merge. |
| `merged_from_identity` | FK → `account_identities.id`, nullable | Provenance: the original identity this row belonged to before a merge re-pointed it. Null when born in the current identity. |
| `created_at` | `DateTime(timezone=True)` | |

**Unique constraint** `uq_account_identifiers_user_type_hmac_currency` on `(user_id, id_type, value_hmac, currency)` guarantees that the same real-world identifier is represented by exactly one live row per user.

Rows are never deleted. Append-only semantics enable unmerge to resurrect them.

### `account_identity_assertions`

User assertions about the relationship between two `Account` rows. Stored at the account-pair level (not the identity level) so assertions survive identity churn.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | FK → `users.id` | Index. |
| `kind` | `Text` | `'same'` or `'do_not_merge'`. `CHECK` constraint. |
| `account_a_id` | FK → `accounts.id` | Index. Always the smaller UUID of the pair (canonical ordering). |
| `account_b_id` | FK → `accounts.id` | Index. Always the larger UUID of the pair. |
| `created_at` | `DateTime(timezone=True)` | |

`'same'` pins two accounts as identical even without shared identifiers. `'do_not_merge'` blocks auto-merge for the pair. When an assertion is written, any contradicting assertion of the opposite kind is deleted first.

### `accounts.identity_id`

Added to the existing `accounts` table by the same migration:

```sql
ALTER TABLE accounts ADD COLUMN identity_id String(36) NULL REFERENCES account_identities(id);
CREATE INDEX ix_accounts_identity_id ON accounts(identity_id);
```

This is a soft additive link — the pre-existing unique constraint `uq_accounts_provider_account` on `(provider_connection_id, provider_account_id)` is deliberately preserved. `identity_id` is null for accounts not yet processed by the matching engine and for accounts that yield no normalizable identifiers.

---

## Identifier Normalization and HMAC Fingerprinting

Raw identifier values (IBANs, sort codes, account numbers) are never stored in the database. Instead, each value is normalized to a canonical form and then hashed with a keyed HMAC before being written to `account_identifiers.value_hmac`.

### Key derivation

`security/fingerprint.py` defines a single public function `compute_identifier_hmac`. The key is derived once per process via HKDF (using `EncryptionService._derive`) with the fixed info label `b"manifold-fingerprint"`. This makes the fingerprint key cryptographically independent from both the per-user DEK and the JWT signing key, while remaining anchored to the application's `SECRET_KEY` environment variable.

The HMAC preimage is:

```
user_id + ':' + id_type + ':' + normalized_value
```

Including `user_id` makes cross-user comparison impossible by construction. Including `id_type` prevents a SCAN value that coincidentally matches an ABA pattern from colliding even before the column type filter applies.

The digest is HMAC-SHA256, returned as a 64-character lowercase hex string.

### Normalization rules

These are implemented in `domain/account_identity.py`.

**IBAN** (`normalize_iban`):
1. Strip all non-alphanumeric characters, uppercase.
2. Validate ISO 7064 mod-97 checksum: rearrange the IBAN (move first 4 characters to the end), convert letters to digits (A=10 … Z=35), verify that `int(result) % 97 == 1`.
3. Values shorter than 5 characters after stripping, or failing the mod-97 check, are logged at DEBUG level and discarded — they produce no identifier row.

**SCAN** (UK sort-code + account-number) (`normalize_scan`):
1. Strip non-digit characters from sort code; require exactly 6 digits.
2. Strip non-digit characters from account number; zero-pad to 8 digits.
3. Produce canonical form `"NNNNNN:NNNNNNNN"`.
4. A bare account number without a sort code is not globally unique and is discarded.

**ABA** (US routing + account-number) (`normalize_aba`):
1. Strip non-digit characters from both fields.
2. Produce canonical form `"routing:number"`.
3. `AccountData` has no `routing_number` field in the current provider set, so this branch never fires for current providers. The function is implemented ready for future use.

**Currency dimension**: For providers in the `MULTI_CURRENCY_PROVIDERS` frozenset (currently empty — populated before any Wise or Revolut adapter ships), the account's ISO 4217 currency code participates in the match key. For all other providers the sentinel string `"-"` is used. This allows a GBP Wise wallet and a USD Wise wallet sharing the same IBAN to remain distinct identities.

---

## Identity Matching and Auto-Merge

`domain/account_identity.py` contains the Phase 3 matching logic, called by the sync engine inside `_sync_accounts` immediately after each `Account` row is upserted.

### Entry point: `resolve_account_identity`

Called with an `Account` ORM row and the list of `IdentifierRow` tuples extracted by `extract_identifiers`. It modifies `account.identity_id` in place; the caller is responsible for the subsequent flush/commit.

**Zero identifiers**: When `extract_identifiers` returns an empty list (account has no IBAN, no sort-code+account-number pair, and no routing+account-number pair), `resolve_account_identity` returns immediately without assigning an identity. The account remains identity-less and falls back to the per-connection unique constraint for transaction dedup.

### Phase A — identifier insert or get

For each `(id_type, value_hmac, currency)` tuple:

1. A provisional `AccountIdentity` is created lazily on the first tuple that needs a new identity (origin `'auto'`).
2. `_get_or_insert_identifier` is called. This uses a SELECT-then-INSERT pattern portable across SQLite, PostgreSQL, and MariaDB. On `IntegrityError` (concurrent first-sight race between two tasks processing the same identifier simultaneously), the loser catches the error and re-SELECTs to get the winner's row.
3. Retired identifier rows (`retired_at` non-null) are skipped as if absent.
4. `last_seen_at` is bumped on every observed identifier, regardless of whether the row was just inserted or already existed.
5. The `identity_id` of each returned row is collected into `matched_identity_ids`.

### Phase B — resolution by match count

Tombstoned identity IDs (those with `merged_into` non-null) in `matched_identity_ids` are followed to their live successors before counting.

**0 or 1 live identity matched**: The account is bound to that single identity. If a provisional identity was created but the match resolved to a different (pre-existing) identity, the provisional identity is deleted and any identifier rows pointing at it are re-pointed to the winner.

**≥2 live identities matched**: A merge is required.

- **Step 0 — `do_not_merge` assertion check**: All pairs of accounts across the matched identities are checked for a `do_not_merge` assertion. The check uses canonical ordering (smaller UUID as `account_a_id`). If _any_ pair is blocked, the entire cluster merge is suppressed (conservative: partial merges are avoided). The account is bound to its existing identity or the provisional one.

- **Step 1 — survivor selection**: The survivor is the identity whose oldest member `Account` (by `created_at`, tie-break: smallest `Account.id`) is the oldest among all matched identities. If no member accounts exist, the smallest identity UUID is used as a fallback.

- **`_merge_identities`** (called with `trigger='auto'`):
  1. For each loser identity, re-point all non-retired `AccountIdentifier` rows to the survivor. If the survivor already owns an identical `(user_id, id_type, value_hmac, currency)` row, the loser row is retired (`retired_at = now()`) and stamped with `merged_from_identity` rather than being deleted.
  2. Re-point all `Account.identity_id` values pointing at losers to the survivor.
  3. Recompute `survivor.master_account_id` as the oldest member account.
  4. Tombstone each loser identity (`merged_into = survivor_id`, `merged_at = now()`).
  5. Emit an `identity_merged` event with payload `{"survivor": ..., "absorbed": [...], "trigger": "auto"}`.

The incoming account's `identity_id` is set to the survivor after the merge.

---

## Manual Merge, Unmerge, and Assertions

Phase 6 exposes user-driven control over the identity graph.

### `IdentityMergeService.merge`

Accepts a list of ≥2 account IDs belonging to the same user. Steps:

1. Load and validate all accounts.
2. Mint singleton `AccountIdentity` rows (origin `'manual'`) for any account that has no `identity_id`.
3. Write a `'same'` assertion for every unordered pair (deleting any contradicting `'do_not_merge'` first).
4. Determine the survivor as the identity of the oldest account by `created_at`.
5. Call `_merge_identities(trigger='manual')`.
6. Set `survivor.origin = 'manual'`.
7. Recompute `master_account_id`.

Returns the survivor `identity_id`.

### `IdentityUnmergeService.unmerge`

Peels one pre-merge origin group back out of a merged identity. Takes a single `account_id` as the peel target. The algorithm:

1. Load the account and its current live identity (must not be a tombstone).
2. Group all non-retired `AccountIdentifier` rows on the identity by their origin: `coalesce(merged_from_identity, identity_id)`. This reconstructs the pre-merge groups.
3. Also load retired-on-collision rows (those with `merged_from_identity` non-null) so they can be resurrected.
4. Re-derive the target account's identifier HMACs by re-running `extract_identifiers` on its decrypted fields. Find which origin group the account's HMACs intersect. If the account's HMACs straddle multiple groups, it is a bridge account and cannot be unmerged — it stays with the survivor.
5. Collect all accounts belonging to the peel group (same logic: re-derive HMACs, check overlap with the peel group's identifiers).
6. Resurrect the peel identity:
   - If the peel group's origin key is the current identity's own ID or a special `"__native__"` sentinel (meaning the account accreted without identifier evidence), a fresh `AccountIdentity` is minted.
   - Otherwise, the original tombstone identity for that origin is resurrected: `merged_into` and `merged_at` are cleared, and the group's identifier rows are re-pointed back to it (clearing `merged_from_identity` for immediately-homed rows; resurrecting retired-on-collision rows by clearing `retired_at`).
7. Re-point peel-group accounts to the resurrected identity.
8. Recompute `master_account_id` for both identities.
9. Write a `'do_not_merge'` assertion between every peel-side account and every stay-side account (deleting contradicting `'same'` assertions and logging `assertion_superseded`).

Returns a caveat string: `"Unmerge is best-effort. Identifiers accreted while merged, and any Phase-5 transaction-dedup decisions, may not fully re-split. Review balances after unmerge."`

### `suggest_merges`

Read-only scoring of candidate account pairs for manual merge. Pairs are scored on:

| Signal | Weight |
|---|---|
| Display name trigram Jaccard similarity | 0.5 |
| Account type match | 0.2 |
| Currency match | 0.2 |
| Same provider type (required gate — pairs with different `provider_type` are excluded before scoring) | 0.1 |

Pairs with a combined score ≥ 0.8 are returned as suggestions. Pairs with an existing `do_not_merge` assertion are suppressed. Pairs already sharing an `identity_id` are excluded (already merged).

### Assertion writer: `_write_assertion`

Idempotent. Canonical ordering: `account_a_id = min(uuid)`, `account_b_id = max(uuid)`. Deletes the contradicting kind before inserting. Does not insert a duplicate of the same kind.

---

## Phase 4 Backfill

`domain/identity_backfill.py` provides `backfill_identities`, a one-shot idempotent function that assigns `identity_id` to every `Account` row with `identity_id IS NULL`.

Design:

- Iterates one user at a time. For each user, decrypts the user's DEK and enters `user_dek_context` before touching any encrypted column (`iban`, `sort_code`, `account_number`, `currency`).
- Queries `Account` rows with `identity_id IS NULL`, ordered oldest-first (`created_at ASC, id ASC`). The sort is a processing courtesy — correctness of the oldest-wins survivor selection does not depend on order.
- For each account, constructs an `AccountData` DTO from the decrypted ORM fields and calls `extract_identifiers` with `provider_type="json"` (a sentinel safe because `MULTI_CURRENCY_PROVIDERS` is empty, making the currency dimension a no-op) and `secret_key=settings.secret_key`.
- Calls `resolve_account_identity` — the same Phase 3 function used by the live sync engine.
- Idempotency: a second run finds no rows with `identity_id IS NULL` and returns zero processed counts.

Returns a summary dict with keys `users_processed`, `accounts_processed`, `accounts_skipped`, `identities_created`.

---

## Transaction Cross-Connection Dedup (Phase 5)

Migration `0006_txn_dedup` (revises `0005_account_identity`) adds three columns to `transactions`:

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `identity_dedup_hash` | `String(64)`, nullable | `UNIQUE` (`uq_transactions_identity_dedup_hash`) | Tier 1 dedup key. |
| `content_hash` | `String(64)`, nullable | Non-unique index `ix_transactions_content_hash` | Tier 2 lookup key. |
| `is_cross_connection_duplicate` | `Boolean NOT NULL DEFAULT FALSE` | — | Soft-delete flag for Phase 5d backfill. |

`String(64)` is used for both hash columns (not `Text`) because MariaDB rejects `TEXT` in a unique constraint without a prefix length, or silently builds a `USING HASH` index. `NULL` rows are excluded from uniqueness on all three supported backends (SQL:2003 §4.15.2).

### Tier 1 — identity-scoped provider-id hash (always active when `identity_id` is set)

Implemented in `compute_tier1_hash` (`domain/transaction_fingerprint.py`).

The key is derived via HKDF from `EncryptionService._derive` with the label `b"manifold-txn-dedup"`. This label is distinct from the identifier fingerprint label `b"manifold-fingerprint"` and from the Tier 2 label, making the three hash spaces structurally disjoint.

Preimage:

```
identity_id + ':' + normalized_provider_transaction_id
```

`provider_transaction_id` is normalized by stripping and lowercasing. The function returns `None` if either input is blank.

No DEK is required — `provider_transaction_id` is stored as plaintext.

At sync time (`SyncEngine._sync_transactions`), when `account.identity_id` is set, Tier 1 is computed and used as the upsert conflict key (`["identity_dedup_hash"]`). This prevents the same physical transaction from being double-inserted when two provider connections both fetch it under the same identity. The legacy `dedup_hash` (`MD5(connection_id + ':' + provider_transaction_id)`) is always written alongside it to satisfy the pre-existing `uq_transactions_dedup_hash` unique constraint during the transition period.

If the Tier 1 hash matches an existing row belonging to an account in a different identity, the sync engine logs `tier1_identity_mismatch_skipped` at WARNING level and skips the transaction (guards against hash collisions or identity mis-merges).

### Legacy fallback (when `account.identity_id` is null)

When an account has no `identity_id` (not yet resolved by the matching engine), the sync engine falls back to the pre-Phase 5 behavior: MD5 of `connection_id + ':' + provider_transaction_id` as the upsert conflict key. `identity_dedup_hash` and `content_hash` are written as `NULL` for these rows.

### Tier 2 — content hash fallback (computed but disabled by default)

Implemented in `compute_content_hash` (`domain/transaction_fingerprint.py`).

The key is derived with the label `b"manifold-txn-content"`.

Preimage:

```
identity_id + ':' + str(amount) + ':' + date_part + ':' + normalized_description
```

Where:
- `date_part` is the first 10 characters of `transaction_date` (ISO 8601 `YYYY-MM-DD`).
- `normalized_description` passes through `normalize_description`: strip/collapse whitespace, strip trailing reference-number patterns and location codes iteratively (up to 3 passes), lowercase, truncate to 128 characters. Returns `None` if the result is shorter than 4 characters.

Returns `None` if any required field is missing or ineligible. The caller must ensure the DEK context is active before calling, as amount, date, and description are decrypted values.

Tier 2 is computed and stored in `content_hash` at sync time but is **not** used as a dedup match key. It has only a non-unique index. The `transactions` model docstring notes it is "opt-in per identity pair" — Tier 2 would be promoted to a match key only when a specific identity pair explicitly enables it (not yet implemented in Phase 5).

### `is_cross_connection_duplicate`

A boolean soft-delete flag defaulting to `FALSE`. Set to `TRUE` by the Phase 5d backfill process (not by the live sync engine) when a row is identified as a cross-connection duplicate of a row already stored under the canonical (oldest) account for the same identity. Read-time queries are expected to filter `WHERE is_cross_connection_duplicate = FALSE` to avoid double-counting. The backfill that writes this flag is not part of the current codebase (Phase 5d is referenced in comments but not yet implemented).

### `IDENTITY_AGGREGATION_ENABLED`

A module-level boolean constant in `domain/account_identity.py`, currently `False`. When `True`, identity-aware read-time aggregation (summing balances and transactions across all member accounts of an identity) would be activated. This flag gates the `aggregated` field returned in API responses for identity and suggestion endpoints.

---

## API Reference

All endpoints are registered on the `identities` router, mounted at `/api/v1/identities`.

| Method | Path | Operation ID | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/identities/merge` | `mergeIdentities` | Merge ≥2 accounts into one identity. Body: `{"account_ids": [...]}`. Returns `{"identity_id": "...", "account_ids": [...]}`. |
| `POST` | `/api/v1/identities/unmerge` | `unmergeIdentity` | Peel one account's pre-merge origin group back out of a merged identity. Body: `{"account_id": "..."}`. Returns `{"caveat": "..."}`. |
| `GET` | `/api/v1/identities/suggestions` | `getIdentitySuggestions` | Return scored merge suggestions for the authenticated user. Read-only. Returns `{"suggestions": [...], "aggregated": bool}`. |
| `POST` | `/api/v1/identities/suggestions/dismiss` | `dismissSuggestion` | Dismiss a suggestion pair. Optionally writes a `do_not_merge` assertion (`write_do_not_merge` defaults to `true`). |
| `GET` | `/api/v1/identities/{identity_id}` | `getIdentity` | Return a single identity with its member accounts. Tombstones are returned with `merged_into` and `merged_at` populated. |

The `identity_id` field is also exposed in the existing accounts API:

| Method | Path | Operation ID | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/accounts` | `listAccounts` | Each item in the response includes `identity_id` (string UUID or null). |
| `GET` | `/api/v1/accounts/{account_id}` | `getAccount` | Response includes `identity_id`. |

All identity endpoints use `404` (not `403`) for non-existent or inaccessible resources to avoid leaking the existence of cross-user data. The `merge` and `unmerge` endpoints require that all accounts share a single owner; a `422` is returned if accounts belong to different users.

---

## Key Invariants and Notable Implementation Details

- **Identifier rows are append-only.** Rows are never deleted; `retired_at` is used to exclude them from matching. This preserves the full history needed for reversible unmerge.
- **`created_at` on `Account` rows is never updated on conflict.** The sync engine explicitly excludes `created_at` from the `update_values` on upsert. This stability is required for the oldest-wins master selection to be deterministic across re-syncs.
- **The provisional identity pattern.** `resolve_account_identity` creates a provisional `AccountIdentity` before knowing whether a match will be found. If a match is found, the provisional identity is deleted. This avoids a two-pass approach (first resolve, then create) while remaining safe under concurrent access via the SELECT-then-INSERT pattern in `_get_or_insert_identifier`.
- **Tier 1 hash is always written alongside the legacy `dedup_hash`.** During the transition period, both columns are populated on every upserted transaction row so neither unique constraint is violated.
- **The `MULTI_CURRENCY_PROVIDERS` frozenset is currently empty.** Currency does not participate in the identifier match key for any current provider. The sentinel `"-"` fills the `currency` column in the unique constraint so it is never NULL.
- **Assertions are stored at the account-pair level, not the identity level.** This means they survive identity churn — if identities are merged and re-split, the assertion remains anchored to the original account UUIDs and continues to be honoured.
