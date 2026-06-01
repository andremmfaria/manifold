# Email Subsystem

This document describes the pluggable email subsystem added in migration `0007_email_subsystem`. It covers the transport abstraction, the six supported adapters, runtime configuration, suppression, and inbound webhooks.

## Overview

Manifold has two distinct email concerns that must not be confused:

- **Email Transport (this subsystem)** — a single, instance-wide delivery mechanism. A superadmin selects a provider (SMTP, SES, Brevo, Mailgun, Postmark, or Resend), stores its credentials in the database, and all outbound email flows through it. There is exactly one active transport at a time, identified by the `"default"` row in `instance_email_settings`.

- **Email Notifier Channel** (`manifold/notifiers/email.py`) — the per-user notification channel that alarm dispatchers call when a user has configured email as a notification target. The `EmailNotifier` does not own its own transport; it calls `get_transport()` at send time to pick up whatever the superadmin has configured instance-wide.

The relationship is one-way: the notifier consumes the transport. Changing the transport (switching from SMTP to Resend, for example) automatically affects all email notifications without any per-user reconfiguration.

## Architecture

### Transport Interface — `EmailTransport`

Defined in `manifold/email/base.py`. It is a `@runtime_checkable` `Protocol` with four methods:

| Method | Signature | Purpose |
| :--- | :--- | :--- |
| `send` | `async (msg: EmailMessage) -> str` | Deliver the message; return a provider message ID. |
| `validate_config` | `(config: dict) -> list[str]` | Return a list of error codes for missing or invalid fields. |
| `verify_webhook` | `(headers: dict, body: bytes) -> bool` | Authenticate an inbound webhook POST. |
| `parse_webhook` | `(payload: dict) -> list[SuppressionEvent]` | Extract zero or more suppression events from a verified payload. |

`verify_webhook` is synchronous per the Protocol definition. Adapters that must perform async work (e.g., SES SNS signature verification requiring an HTTP cert fetch) bridge to async internally.

Also exported from `base.py`: `SuppressionEvent`, a dataclass with fields `address: str`, `reason: Literal["bounce", "complaint"]`, and `provider: str`.

### Message Model — `EmailMessage`

Defined in `manifold/email/message.py`:

```python
@dataclass
class EmailMessage:
    to: list[str]
    subject: str
    html_body: str
    text_body: str | None = None
    from_address: str | None = None
    reply_to: str | None = None
    tags: list[str] = field(default_factory=list)
```

`tags` is only used by the Resend adapter; other adapters ignore it.

### Factory — `get_transport`

`manifold/email/factory.py` exports a single function:

```python
def get_transport(provider: str, config: dict) -> EmailTransport
```

It maps the `provider` string to the corresponding adapter class, instantiates it with `config`, and returns it. An unrecognised provider raises `ValueError("unknown provider: <value>")`. Adapter imports are deferred (inside `if` branches) so unused adapter dependencies are never loaded.

Valid `provider` values: `"smtp"`, `"ses"`, `"resend"`, `"postmark"`, `"mailgun"`, `"brevo"`.

## Adapter Reference

### SMTP — `SMTPTransport`

**File**: `manifold/email/adapters/smtp.py`  
**Library**: `aiosmtplib`

| Config key | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `host` | Yes | — | SMTP server hostname. |
| `port` | Yes | — | TCP port (typically 587 or 465). |
| `use_tls` | No | `True` | Wrap the connection in TLS from the start (implicit TLS / SMTPS). |
| `use_starttls` | No | `False` | Upgrade a plain connection with STARTTLS. |
| `username` | No | — | SMTP auth username. |
| `password` | No | — | SMTP auth password. |

`validate_config` requires `host` and `port`. `verify_webhook` always returns `False` (SMTP has no webhook mechanism). `parse_webhook` always returns `[]`. The returned message ID is the `Message-ID` MIME header, which may be empty if the SMTP server does not set one.

**Environment bootstrap**: if no DB row exists, the notifier and the settings API fall back to the `SMTP_*` env vars (see [Configuration](#configuration)).

### SES — `SESTransport`

**File**: `manifold/email/adapters/ses.py`  
**Library**: `aiobotocore`

| Config key | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `region` | Yes | — | AWS region (e.g. `us-east-1`). |
| `access_key_id` | No | — | AWS access key. Omit to use the instance IAM role. |
| `secret_access_key` | No | — | AWS secret key. Omit to use the instance IAM role. |

`validate_config` requires `region`. When `access_key_id` / `secret_access_key` are absent the adapter creates a scoped `aiobotocore` client per send, which will attempt to resolve credentials from the standard AWS chain (instance metadata, env vars, shared credentials). The botocore config uses a 2-second connect/read timeout with zero retries to fail fast when metadata is unavailable.

**Webhook verification (SNS)**: SES delivers bounce and complaint notifications via Amazon SNS. The adapter verifies the RSA signature on every incoming SNS message:

1. Validates that `SigningCertURL` ends in `.amazonaws.com`.
2. Fetches the signing certificate with a 24-hour module-level in-process cache.
3. Builds the SNS canonical string using the AWS-documented field order.
4. Verifies the signature with PKCS1v15 + SHA-1 (SNS signature version 1) or SHA-256 (version 2).
5. If the message type is `SubscriptionConfirmation`, automatically fires a GET to the `SubscribeURL` to confirm the subscription.

Because `verify_webhook` is sync, the async verification logic runs via a thread-pool executor when called from within a running event loop (FastAPI context).

**Webhook parsing**: Extracts addresses from the `bouncedRecipients` or `complainedRecipients` arrays nested inside the SNS `Message` JSON envelope. Supports both `notificationType` and `eventType` field names.

### Brevo — `BrevoTransport`

**File**: `manifold/email/adapters/brevo.py`  
**API endpoint**: `https://api.brevo.com/v3/smtp/email`

| Config key | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `api_key` | Yes | — | Brevo API key (passed in the `api-key` header). |
| `webhook_secret` | No | — | Secret for HMAC-SHA256 webhook signature verification. |

`from_address` is parsed with `email.utils.parseaddr` so both `"Name <addr>"` and bare `"addr"` forms are accepted and the sender object is constructed correctly. Brevo's webhook signing scheme is not formally published; the adapter implements HMAC-SHA256 of the raw body against the `X-Brevo-Webhook-Signature` header. If no `webhook_secret` is configured `verify_webhook` returns `False`.

**Webhook events recognised**: `hard_bounce` → `"bounce"`, `spam` → `"complaint"`. All other event types are ignored.

### Mailgun — `MailgunTransport`

**File**: `manifold/email/adapters/mailgun.py`

| Config key | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `api_key` | Yes | — | Mailgun API key. |
| `domain` | Yes | — | Sending domain (e.g. `mail.example.com`). |
| `region` | Yes | — | `"us"` or `"eu"`. Routes to `api.mailgun.net` or `api.eu.mailgun.net`. |
| `webhook_signing_key` | No | — | Mailgun webhook signing key for HMAC-SHA256 body verification. |

**Quirk**: Mailgun's webhook signature lives inside the JSON body (not in HTTP headers), in a `signature` object containing `timestamp`, `token`, and `signature` fields. `verify_webhook` parses the body as JSON to read these fields.

**Webhook events recognised**: `failed` with `severity == "permanent"` → `"bounce"`, `complained` → `"complaint"`. Supports both the modern `event-data` envelope and the flat payload shape.

### Postmark — `PostmarkTransport`

**File**: `manifold/email/adapters/postmark.py`  
**API endpoint**: `https://api.postmarkapp.com/email`

| Config key | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `api_key` | Yes | — | Postmark Server API Token (sent as `X-Postmark-Server-Token` header). |
| `webhook_token` | No | — | Token for webhook verification (compared against `X-Postmark-Signature` header via `hmac.compare_digest`). |

Sends always target the `"outbound"` message stream (`"MessageStream": "outbound"`). `verify_webhook` performs a constant-time string comparison between the header value and the stored `webhook_token`; no HMAC is computed.

**Webhook events recognised**: `RecordType == "Bounce"` → `"bounce"`, `RecordType == "SpamComplaint"` → `"complaint"`. The recipient address is read from the top-level `Email` field.

### Resend — `ResendTransport`

**File**: `manifold/email/adapters/resend.py`  
**API endpoint**: `https://api.resend.com/emails`

| Config key | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `api_key` | Yes | — | Resend API key (sent as `Authorization: Bearer` header). |
| `webhook_secret` | No | — | Svix webhook secret (with or without `whsec_` prefix). |

Resend is the only adapter that forwards `tags` from `EmailMessage`. Tags are sent as `[{"name": "tag", "value": <tag_string>}]`.

**Webhook verification (Svix)**: Resend uses the Svix webhook infrastructure. `verify_webhook` reads `svix-id`, `svix-timestamp`, and `svix-signature` headers. The signed payload is `"{svix_id}.{svix_timestamp}.{body}"`. The secret is base64-decoded after stripping any `whsec_` prefix. The `svix-signature` value may contain multiple space-separated `v1,<b64sig>` tokens; verification succeeds if any of them matches.

**Webhook events recognised**: `email.bounced` → `"bounce"`, `email.complained` → `"complaint"`. Addresses are read from `data.to`, which may be a string or a list.

## Email Settings Model and API

### Database Model — `InstanceEmailSettings`

Table: `instance_email_settings`

| Column | Type | Encrypted | Notes |
| :--- | :--- | :---: | :--- |
| `id` | `String(36)` | No | Always `"default"`. One row per instance. |
| `provider` | `String(32)` | No | Active adapter key (e.g. `"smtp"`, `"ses"`). |
| `config` | `EncryptedJSON` | Yes | Provider-specific credential map. |
| `from_address` | `EncryptedText` | Yes | Sender address used by the notifier. |
| `from_name` | `EncryptedText` | Yes | Display name when no per-user name can be resolved. |
| `is_configured` | `Boolean` | No | Set to `True` on the first successful `PUT`. |
| `created_at` / `updated_at` | `DateTime(tz)` | No | From `TimestampMixin`. |

`config`, `from_address`, and `from_name` are stored as `LargeBinary` in the physical schema and decrypted at the ORM layer using the instance master DEK. All reads and writes to this table are wrapped in `with_master_dek`.

### Secret masking

The following `config` keys are considered secrets and are never returned in plaintext from any endpoint:

`api_key`, `password`, `secret_access_key`, `webhook_secret`, `webhook_signing_key`, `webhook_token`

On read these are replaced with `"********"` (or `null` if unset). On write, if a secret field arrives as `""`, `null`, or `"********"`, the existing stored value is preserved, so a partial update cannot accidentally wipe credentials.

### API Endpoints

All email settings endpoints require the `superadmin` role.

#### `GET /api/v1/email/settings`

Returns the current transport configuration (`EmailSettingsResponse`). If no DB row exists, synthesises a response from the `SMTP_*` env vars with `is_configured: false`.

#### `PUT /api/v1/email/settings`

Body: `EmailSettingsUpdateRequest` — `provider`, `config` (dict), `from_address?`, `from_name?`.

Creates or replaces the `"default"` row. Before persisting, calls `get_transport(provider, merged_config)` and then `transport.validate_config(merged_config)`. Returns HTTP 422 with `{"error": "invalid_config", "fields": [...]}` on failure.

#### `POST /api/v1/email/settings/test`

Body: `EmailSettingsTestRequest` — `to_address`.

Sends a test email (`subject: "Manifold test email"`) using the stored configuration (or env SMTP fallback). Returns `{"ok": true, "message_id": "..."}` or `{"ok": false, "error": "..."}`.

#### `GET /api/v1/email/settings/suppressions`

Query params: `page` (default `1`), `page_size` (default `50`, max `100`).

Returns `SuppressionListResponse` with `items`, `total`, `page`, `page_size`. Each item exposes `address_hmac` as a hex string — the actual email address is never stored or returned.

#### `POST /api/v1/email/settings/suppressions`

Body: `SuppressionCreateRequest` — `address`, `reason` (default `"manual"`).

Idempotent: returns the existing row if the address is already suppressed. Normalises the address (lowercase, strip whitespace), then computes HMAC-SHA256 keyed on the master DEK. Sets `source` to `"superadmin"`.

#### `DELETE /api/v1/email/settings/suppressions/{suppression_id}`

Removes a suppression entry. Returns HTTP 204. Returns HTTP 404 if the ID is not found.

## Suppression

### Model — `EmailSuppression`

Table: `email_suppression`

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | `String(36)` UUID | Primary key. |
| `address_hmac` | `LargeBinary` | HMAC-SHA256 of the normalised address. Unique index. |
| `reason` | `String(16)` | `"bounce"`, `"complaint"`, or `"manual"`. |
| `source` | `String(32)` | Provider name (e.g. `"ses"`) or `"superadmin"`. |
| `created_at` | `DateTime(tz)` | Set by `server_default=func.now()`. |

The email address itself is never stored. The HMAC key is `EncryptionService().dek_master_key` — the same master key used to wrap user DEKs — so suppression lookup requires the master key to be available.

### Suppression check

Before delivering any email, `EmailNotifier.send` computes the HMAC of the recipient address and queries `email_suppression`. If a match is found, delivery is skipped and the method logs `email.suppressed` and returns `False`. The check is performed inside a `with_master_dek` block so the HMAC key is available.

## Inbound Webhooks

### Endpoint

```
POST /api/v1/email/webhooks/{provider}
```

No authentication is required from the client (the provider posts here). Signature verification is the authentication mechanism.

### Processing flow

1. Read the raw request body.
2. Load `instance_email_settings` under the master DEK.
3. Call `get_transport(provider, config)` — returns HTTP 404 if the provider string is unrecognised.
4. Call `transport.verify_webhook(headers, body)` — returns HTTP 401 on failure.
5. Parse the body as JSON — returns HTTP 400 on parse failure.
6. Call `transport.parse_webhook(payload)` to extract `SuppressionEvent` objects.
7. For each event: normalise the address, compute HMAC, insert into `email_suppression` if not already present. Logs `email.suppression_added` on insert.
8. Insert one `EmailWebhookEvent` row regardless of how many suppression events were extracted (even zero). The `event_type` field is resolved from `payload.Type`, `payload.event`, or `payload.type`, falling back to `"unknown"`.
9. Return HTTP 200.

### Model — `EmailWebhookEvent`

Table: `email_webhook_events`

| Column | Type | Encrypted | Notes |
| :--- | :--- | :---: | :--- |
| `id` | `String(36)` UUID | No | Primary key. |
| `provider` | `String(32)` | No | Provider name from the URL path. |
| `event_type` | `String(32)` | No | Normalised event type string. |
| `raw` | `EncryptedJSON` | Yes | Full decoded payload, encrypted at rest. |
| `created_at` | `DateTime(tz)` | No | Server default. |

Composite index on `(provider, event_type)`.

### Provider webhook support matrix

| Provider | Webhook supported | Signature scheme | Events → suppression |
| :--- | :---: | :--- | :--- |
| SMTP | No | — | — |
| SES | Yes | SNS RSA (SHA-1 v1 / SHA-256 v2) | `Bounce`, `Complaint` |
| Brevo | Yes | HMAC-SHA256 (`X-Brevo-Webhook-Signature`) | `hard_bounce`, `spam` |
| Mailgun | Yes | HMAC-SHA256 (in body `signature` object) | `failed`/`permanent`, `complained` |
| Postmark | Yes | Static token (`X-Postmark-Signature`) | `Bounce`, `SpamComplaint` |
| Resend | Yes | Svix HMAC-SHA256 (`svix-*` headers) | `email.bounced`, `email.complained` |

## Configuration

### Environment variables

These variables configure the SMTP fallback used when no DB row exists in `instance_email_settings`. They are also used by the notifier settings API to synthesise the `GET` response before a superadmin has saved any settings.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SMTP_HOST` | `""` | SMTP server hostname. |
| `SMTP_PORT` | `587` | SMTP server port. |
| `SMTP_USE_TLS` | `true` | Use implicit TLS (SMTPS). |
| `SMTP_USER` | `""` | SMTP auth username. |
| `SMTP_PASSWORD` | `""` | SMTP auth password. |
| `SMTP_FROM_ADDRESS` | `""` | Default sender address. |

These are the only email-related env vars. Non-SMTP providers (SES, Resend, etc.) are configured exclusively via the database row — there are no env vars for their API keys.

### Runtime settings

Transport configuration is stored and managed via the `PUT /api/v1/email/settings` endpoint. Changes take effect immediately on the next send; there is no caching of the transport instance between requests.

## From-Address Composition

When `EmailNotifier` sends an alarm notification, the From address is composed by `_compose_from` in `manifold/notifiers/email.py`:

1. Uses `global_from_address` from `InstanceEmailSettings` (falling back to `SMTP_FROM_ADDRESS`).
2. Appends the recipient user's sanitised `username` as a plus-tag (`local+username@domain`), truncated at 64 characters to respect RFC 5321.
3. The display name priority is: full name (`first_name last_name`) > `username` > `email` > `"User"`. If no user context is available, `global_from_name` is used, falling back to `"User"`.
4. The display name is RFC 2047-encoded with UTF-8 charset via `email.header.Header`.
