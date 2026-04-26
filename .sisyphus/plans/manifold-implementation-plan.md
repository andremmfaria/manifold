# Manifold — Implementation Plan

> **Self-Hosted Financial Observability Platform**
> Version: 1.0 | Date: 2026-04-18

---

## TL;DR

> **Quick Summary**: Manifold is a self-hosted financial observability platform built on a Python/FastAPI backend, React/TypeScript frontend, and a pluggable SQL database tier. **v1 includes the DatabaseBackend abstraction and supports SQLite, PostgreSQL, and MariaDB as first-class execution targets.** It ingests data from provider adapters (TrueLayer, JSON, and future providers), normalizes it to canonical internal models, detects financial events, evaluates user-defined alarm expressions, and dispatches notifications via a pluggable notifier subsystem.
>
> **Deliverables**:
>
> - Python FastAPI backend with provider adapters, alarm engine, notifier subsystem, Taskiq background job queue
> - React/TypeScript/Vite frontend dashboard
> - Dialect-agnostic schema managed by Alembic migrations across SQLite, PostgreSQL, and MariaDB
> - Database Backend connector architecture (mirrors the provider plugin pattern)
> - Manifold logo (SVG + PNG)
> - Docker Compose stack for local/self-hosted deployment
> - GitHub Actions CI/CD pipelines
> - Full `.env.example` and documentation
>
> **Estimated Effort**: XL (4–6 months for full v1 feature set)
> **Parallel Execution**: YES — frontend, backend, and infra work can proceed in parallel after foundation
> **Critical Path**: DB schema → backend core → provider adapters → alarm engine → notifier → frontend

---

## 1. Executive Summary

Manifold is a self-hosted, multi-user financial observability platform designed for household or small-team use. It is not a budgeting app. Its identity is that of an **operations control plane for personal finance**: it ingests raw data from open banking providers, normalizes it into a stable canonical domain model, detects significant financial events, evaluates user-defined alarm conditions, predicts future events from observed patterns, and surfaces all of this through an observability-oriented frontend dashboard. Each user owns their own financial data; access to that data can be delegated to other users as viewers or co-admins. A global superadmin manages user accounts and sees cross-account operational metadata without ever accessing financial figures or encrypted provider/notifier details.

### Core design commitments

1. **Provider-agnostic core** — The application domain never imports provider-specific code. TrueLayer, JSON provider, and all future providers are adapters behind a stable interface.
2. **Notifier-agnostic outbound layer** — Email, Webhook, Slack, Telegram, and any future channel are pluggable notifiers behind a stable interface. WhatsApp is deferred beyond v1.
3. **Observability-first** — Every sync, event, prediction, alarm firing, and notification delivery is a durable, queryable record. The system explains itself.
4. **Operational simplicity** — Runs on a single Docker Compose stack. Works without Docker via Makefile. Database is user-managed; SQLite by default (zero-ops, file backup), with PostgreSQL and MariaDB as supported alternatives. The app brings its own Alembic migrations and autodetects the backend from `DATABASE_URL`.
5. **Multi-user household-first** — Each user owns their own financial data. Users can be invited (by a superadmin) and may delegate read-only (viewer) or full (admin) access to their account to other users. A `superadmin` role manages the user roster and can see cross-account operational metadata across all accounts, but never financial figures or encrypted provider/notifier details. Designed for a single household or small team. No SaaS assumptions.

### Existing repository state

The `manifold` repository is currently a **greenfield repository** containing only `.gitignore` and `.sisyphus/` configuration. No application code exists yet. The first implementation task will bootstrap it as a monorepo with `frontend/` and `backend/` as primary workspaces.

### Key technology decisions (research-backed)

| Concern                   | Decision                                 | Rationale                                                                                                                                 |
| ------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Backend framework         | FastAPI                                  | Async-first, typed, minimal footprint; ideal for self-hosted single-node                                                                  |
| Database                  | SQLite · PostgreSQL · MariaDB            | Pluggable SQL tier via `DATABASE_URL`; all three are supported in v1 through the `DatabaseBackend` abstraction                            |
| ORM                       | SQLAlchemy 2.0 async + SQLModel          | Pydantic-aligned models; `sa.JSON` for portable JSON columns; works with Alembic                                                          |
| Migrations                | Alembic (`render_as_batch=True`)         | Standard SQLAlchemy migration tool; batch mode required for SQLite ALTER TABLE compatibility                                              |
| Background jobs           | Taskiq + taskiq-redis + taskiq-fastapi   | Out-of-process task queue; Redis broker + result backend; separate scheduler and worker processes in a single `manifold-tasker` container |
| Task broker               | Redis 7                                  | Message transport for Taskiq; also used for distributed sync locks                                                                        |
| Config                    | Pydantic Settings                        | Type-safe, env-var-first, integrates with FastAPI naturally                                                                               |
| Alarm evaluation          | Custom JSON AST tree-walker + simpleeval | Auditable, sandboxed, no arbitrary code execution                                                                                         |
| Python package management | uv + pyproject.toml                      | Modern (2025/2026 standard), fast, deterministic                                                                                          |
| Frontend framework        | React 18 + TypeScript + Vite             | Fast builds, mature ecosystem                                                                                                             |
| Data fetching             | TanStack Query                           | Full-featured cache management, mutations, DevTools                                                                                       |
| UI components             | shadcn/ui + Tailwind CSS                 | Headless, Tailwind-first, composable                                                                                                      |
| Charts                    | Recharts                                 | Stable, composable, good TypeScript support                                                                                               |
| Routing                   | TanStack Router                          | Type-safe, pairs well with TanStack Query                                                                                                 |
| Alarm rule UI             | react-querybuilder                       | Config-driven, supports AND/OR/NOT trees                                                                                                  |

### Implementation baseline (normative for initial execution)

- **v1 scope**: `DatabaseBackend` abstraction, SQLite/PostgreSQL/MariaDB support, auth/RBAC, per-user DEK encryption model, JSON provider and TrueLayer provider, manual/cron sync, accounts/transactions/balances/cards/pending-transactions/direct-debits/standing-orders, account-bound alarms, notifications (email + webhook + expanded channels), same-origin cookie auth, optional HTTPS reverse proxy.

---

## 2. Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MANIFOLD SYSTEM                              │
│                                                                     │
│  ┌──────────────┐    REST/JSON    ┌──────────────────────────────┐  │
│  │              │ ◄─────────────► │        FastAPI Backend       │  │
│  │  React/TS    │                 │                              │  │
│  │  Frontend    │                 │  ┌──────────┐ ┌───────────┐  │  │
│  │  (Vite)      │                 │  │ API Layer│ │   Auth    │  │  │
│  │              │                 │  └──────────┘ └───────────┘  │  │
│  └──────────────┘                 │  ┌──────────────────────────┐│  │
│                                   │  │    Domain Services       ││  │
│                                   │  │  Accounts | Txns | Debits││  │
│                                   │  │  Alarms   | Notifiers    ││  │
│                                   │  └──────────────────────────┘│  │
│                                   │  ┌──────────────────────────┐│  │
│                                   │  │  Provider Adapter Layer  ││  │
│                                   │  │  TrueLayer | JSON | ...  ││  │
│                                   │  └──────────────────────────┘│  │
│                                   │  ┌──────────────────────────┐│  │
│                                   │  │  Background Jobs         ││  │
│                                   │  │  (Taskiq → Redis broker) ││  │
│                                   │  └──────────────────────────┘│  │
│                                   │  ┌──────────────────────────┐│  │
│                                   │  │  Alarm Engine            ││  │
│                                   │  │  JSON AST evaluator      ││  │
│                                   │  └──────────────────────────┘│  │
│                                   │  ┌──────────────────────────┐│  │
│                                   │  │  Notifier Subsystem      ││  │
│                                   │  │  Email|Webhook|Slack|Telegram ││  │
│                                   │  └──────────────────────────┘│  │
│                                   └──────────────────────────────┘  │
│                                            │                        │
│                                   ┌────────▼─────────────────┐      │
│                                   │    SQLite (default)      │      │
│                                   │  / PostgreSQL / MariaDB  │      │
│                                   │  (user-managed)          │      │
│                                   └──────────────────────────┘      │
│                                                                     │
│  External providers (via HTTPS from backend only):                  │
│  TrueLayer API | JSON endpoints | future providers                  │
│                                                                     │
│  External notifiers (via HTTPS from backend only):                  │
│  SMTP | Generic Webhook | Slack API | Telegram Bot API              │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer responsibilities

| Layer                                                | Responsibility                                                   | May NOT                                                           |
| ---------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------- |
| Frontend                                             | Display canonical data, manage UI state, auth session            | Talk to providers or notifiers directly                           |
| API Layer                                            | HTTP routing, request validation, response serialization         | Contain business logic                                            |
| Domain Services                                      | Orchestrate business operations, enforce invariants              | Import provider-specific code                                     |
| Provider Adapters                                    | Translate provider data → canonical models, manage provider auth | Be imported by domain services directly (always behind interface) |
| Background Scheduler                                 | Trigger sync runs, alarm evaluations, recurrence detection       | Own business logic                                                |
| Alarm Engine                                         | Evaluate alarm conditions against domain data                    | Send notifications directly                                       |
| Notifier Subsystem                                   | Format and dispatch notification messages                        | Evaluate alarm conditions                                         |
| SQL database backend (SQLite / PostgreSQL / MariaDB) | Persist all state                                                | —                                                                 |

---

## 3. Monorepo Structure

### Repository root layout

```
manifold/
├── frontend/                    # React + TypeScript + Vite
│   ├── src/
│   ├── public/
│   ├── Dockerfile
│   ├── nginx.conf               # nginx config for production container
│   ├── package.json
│   ├── vite.config.ts           # Dev server configured with /api proxy → http://localhost:8000
│   │                            # IMPORTANT: The Vite dev proxy makes API calls same-origin,
│   │                            # which is required for HttpOnly session cookies to work in dev.
│   │                            # Production: nginx proxies /api → backend (same-origin by default).
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── .eslintrc.cjs
│   └── .env.example
│
├── backend/                     # Python FastAPI
│   ├── manifold/                # Python package
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory
│   │   ├── config.py            # Pydantic Settings
│   │   ├── database/            # Pluggable DB backend package (see §10a)
│   │   │   ├── __init__.py      # Engine factory; exports engine, get_session, db_session
│   │   │   ├── base.py          # DatabaseBackend ABC
│   │   │   ├── factory.py       # DatabaseBackendFactory
│   │   │   └── backends/        # SQLiteBackend, PostgreSQLBackend, MariaDBBackend
│   │   ├── api/                 # HTTP route handlers (thin layer)
│   │   │   ├── __init__.py
│   │   │   ├── deps.py          # FastAPI dependency injection
│   │   │   ├── auth.py
│   │   │   ├── users.py         # User management + delegation routes (superadmin CRUD, /users/me/access)
│   │   │   ├── providers.py     # Provider-type registry + OAuth callback routes
│   │   │   ├── connections.py   # User-owned provider connection CRUD + sync routes
│   │   │   ├── accounts.py
│   │   │   ├── transactions.py
│   │   │   ├── direct_debits.py
│   │   │   ├── standing_orders.py
│   │   │   ├── cards.py
│   │   │   ├── alarms.py
│   │   │   ├── notifiers.py
│   │   │   ├── sync.py
│   │   │   ├── events.py
│   │   │   ├── recurrence_profiles.py  # Recurrence profile CRUD
│   │   │   ├── notification_deliveries.py  # Delivery log read endpoints
│   │   │   ├── dashboard.py     # Dashboard summary endpoint
│   │   │   ├── settings.py      # App settings read endpoint (non-secret fields)
│   │   │   └── admin.py         # Admin job trigger routes (POST /admin/jobs/*/trigger)
│   │   ├── domain/              # Domain services and logic
│   │   │   ├── __init__.py
│   │   │   ├── accounts.py
│   │   │   ├── transactions.py
│   │   │   ├── direct_debits.py
│   │   │   ├── standing_orders.py
│   │   │   ├── sync_engine.py
│   │   │   ├── recurrence.py    # Recurring payment detection
│   │   │   ├── events.py
│   │   │   ├── alarm_evaluator.py  # Domain service wrapper: queries active alarms, calls AlarmEvaluator per alarm, manages state transitions
│   │   │   ├── users.py         # User management domain service
│   │   │   ├── ownership.py     # Ownership resolution (user → resource access)
│   │   │   └── _upsert.py       # Backend-agnostic upsert helpers delegating to DatabaseBackend
│   │   ├── models/              # SQLAlchemy/SQLModel ORM models
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── provider_connection.py
│   │   │   ├── account.py
│   │   │   ├── card.py
│   │   │   ├── transaction.py
│   │   │   ├── pending_transaction.py
│   │   │   ├── direct_debit.py
│   │   │   ├── standing_order.py
│   │   │   ├── balance.py
│   │   │   ├── sync_run.py
│   │   │   ├── event.py
│   │   │   ├── recurrence_profile.py
│   │   │   ├── alarm.py
│   │   │   ├── notifier.py
│   │   │   ├── notification_delivery.py
│   │   │   └── user.py          # User, AccountAccess, UserSession, RefreshToken ORM models
│   │   ├── schemas/             # Pydantic request/response schemas (API layer)
│   │   │   ├── __init__.py
│   │   │   └── ...              # One file per domain concept
│   │   ├── providers/           # Provider adapter layer
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Abstract BaseProvider + auth abstractions
│   │   │   ├── types.py         # Canonical DTOs used by provider adapters
│   │   │   ├── registry.py      # ProviderRegistry
│   │   │   ├── auth/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py      # Abstract BaseProviderAuth
│   │   │   │   ├── oauth2.py    # OAuth2CodeFlowAuth
│   │   │   │   ├── api_key.py   # ApiKeyAuth
│   │   │   │   ├── bearer.py    # BearerTokenAuth
│   │   │   │   ├── basic.py     # BasicAuth (HTTP Basic)
│   │   │   │   └── noauth.py    # NoAuth (unauthenticated endpoints)
│   │   │   ├── truelayer/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── adapter.py   # TrueLayerProvider(BaseProvider)
│   │   │   │   ├── auth.py      # TrueLayer-specific OAuth2 flow
│   │   │   │   ├── client.py    # Raw HTTP client for TrueLayer API
│   │   │   │   └── mappers.py   # TrueLayer response → canonical models
│   │   │   └── json_provider/
│   │   │       ├── __init__.py
│   │   │       ├── adapter.py   # JsonProvider(BaseProvider)
│   │   │       ├── auth.py      # Auth strategies for JSON provider
│   │   │       └── mappers.py   # JSON payload → canonical models
│   │   ├── alarm_engine/        # Alarm evaluation subsystem
│   │   │   ├── __init__.py
│   │   │   ├── evaluator.py     # AlarmEvaluator: JSON AST → bool
│   │   │   ├── predicates.py    # Leaf predicate implementations
│   │   │   ├── state_machine.py # ok/pending/firing/resolved/muted
│   │   │   └── explainer.py     # Human-readable alarm explanation
│   │   ├── notifiers/           # Notifier subsystem
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Abstract BaseNotifier
│   │   │   ├── registry.py      # NotifierRegistry
│   │   │   ├── dispatcher.py    # Routing + retry logic
│   │   │   ├── templates/       # Jinja2-based message templates (directory)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── email/       # Email-specific templates (plain text + HTML)
│   │   │   │   ├── webhook/     # Webhook JSON payload templates
│   │   │   │   ├── slack/       # Slack-specific templates (Block Kit JSON)
│   │   │   │   └── telegram/    # Telegram-specific templates (alarm_firing.md)
│   │   │   ├── email.py         # EmailNotifier (SMTP)
│   │   │   ├── webhook.py       # WebhookNotifier (generic HTTP POST)
│   │   │   ├── slack.py         # SlackNotifier (Incoming Webhooks)
│   │   │   └── telegram.py      # TelegramNotifier (Bot API)
│   │   │   # whatsapp.py intentionally absent — deferred to v2
│   │   ├── tasks/               # Taskiq task definitions
│   │   │   ├── __init__.py
│   │   │   ├── broker.py        # Broker + result backend init (RedisStreamBroker)
│   │   │   ├── scheduler.py     # Periodic schedule definitions (cron/interval)
│   │   │   ├── sync.py          # sync_connection, sync_all_connections tasks
│   │   │   ├── alarms.py        # evaluate_all_alarms task
│   │   │   ├── notifications.py # dispatch_alarm_notifications task
│   │   │   └── maintenance.py   # recurrence detection, cleanup tasks
│   │   ├── security/            # Encryption at rest
│   │   │   ├── __init__.py
│   │   │   ├── encryption.py    # EncryptionService: HKDF-SHA256 master key derivation, per-user DEK generation, AES-256-GCM field encrypt/decrypt
│   │   │   └── types.py         # SQLAlchemy TypeDecorators: EncryptedText, EncryptedJSON, EncryptedDecimal
│   │   └── cli.py               # CLI tools: `uv run manifold create-user`, `python -m manifold.cli check-config`
│   │
│   ├── migrations/              # Alembic migrations
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── fixtures/
│   │   │   └── manifold-fixture.json  # JSON provider fixture (2 accounts, 5 transactions, 2 balances)
│   │   └── conftest.py
│   ├── Dockerfile
│   ├── supervisord.conf          # Process manager for manifold-tasker container
│   ├── pyproject.toml
│   ├── uv.lock
│   └── .env.example
│
├── docs/                        # Project documentation
│   ├── architecture.md
│   ├── providers.md
│   ├── alarm-engine.md
│   └── deployment.md
│
├── .github/
│   └── workflows/
│       ├── frontend-ci.yml
│       ├── backend-ci.yml
│       ├── docker-build.yml
│       └── release.yml
│
├── docker-compose.yml           # Local/self-hosted full stack
├── docker-compose.dev.yml       # Dev overrides (bind mounts, hot reload)
├── Makefile                     # Developer workflow targets
├── .env.example                 # Root env example (for Docker Compose)
├── .gitignore
├── LICENSE.md
└── README.md
```

### Repository bootstrap note

The repository root contains only `.gitignore` and `.sisyphus/`. The first implementation commit creates the monorepo structure from scratch: `frontend/`, `backend/`, root `Makefile`, `docker-compose.yml`, `.github/`, and `README.md`. Each workspace manages its own `package.json` (frontend) or `pyproject.toml` (backend). No files need to be deleted.

---

## 4. Backend Design

### Framework: FastAPI

FastAPI is chosen over Django REST Framework for this project because:

- Async-first (ASGI): matches async SQLAlchemy and Taskiq naturally
- Pydantic-native: validation, settings, and API schemas use the same library
- Lightweight: smaller operational footprint for single-node self-hosted deployment
- OpenAPI/Swagger docs generated automatically (useful during development)
- No admin UI requirement: Manifold's frontend is the only UI needed

### Python version and tooling

- **Python 3.12** (minimum; 3.13 when stable)
- **uv** for dependency management and virtual environments (replaces pip/poetry in 2025/2026 practice; dramatically faster)
- **pyproject.toml** as the single source of truth for package metadata, dependencies, and tool config
- **Alembic** for database migrations (managed separately from SQLModel model definitions)

### Backend package structure conventions

```python
# manifold/main.py — App factory
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from taskiq_fastapi import init as taskiq_init
from manifold.tasks.broker import broker
from manifold.api import providers, accounts, transactions, alarms, notifiers, sync, events, auth
from manifold.providers.registry import register_all as register_providers
from manifold.notifiers.registry import register_all as register_notifiers

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic migrations run before startup (e.g., `alembic upgrade head`).
    # No DDL is executed here — only a lightweight connectivity ping.
    from manifold.database import engine
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))  # Fail fast if DB unreachable
    # Register all provider and notifier implementations into their registries
    register_providers()
    register_notifiers()
    # Broker startup: connects to Redis; no-op if already connected (worker process)
    if not broker.is_worker_process:
        await broker.startup()
    yield
    if not broker.is_worker_process:
        await broker.shutdown()

def create_app() -> FastAPI:
    app = FastAPI(title="Manifold", lifespan=lifespan)
    taskiq_init(broker, app)
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(providers.router, prefix="/api/v1/providers")
app.include_router(connections.router, prefix="/api/v1/connections")
app.include_router(accounts.router, prefix="/api/v1/accounts")
    # ... etc
    return app

app = create_app()
```

### Layer responsibilities (backend)

| Layer           | What it does                                                    | What it doesn't do                |
| --------------- | --------------------------------------------------------------- | --------------------------------- |
| `api/`          | HTTP routing, Pydantic input validation, response serialization | Business logic, DB access         |
| `domain/`       | Orchestrates business logic, calls ORM via repositories         | Knows about HTTP or provider SDKs |
| `models/`       | SQLAlchemy ORM models (source of truth for DB schema)           | Business logic                    |
| `schemas/`      | Pydantic request/response models (API contract)                 | Touch DB                          |
| `providers/`    | Provider adapters: fetch + normalize external data              | Know about alarms or notifiers    |
| `alarm_engine/` | Evaluate alarm conditions, manage state transitions             | Send notifications                |
| `notifiers/`    | Dispatch notifications to external channels                     | Evaluate alarms                   |
| `tasks/`        | Define and enqueue background tasks; broker/scheduler config    | Own business logic                |

### ORM approach

Use **SQLAlchemy 2.0 async** with **SQLModel** for model definitions. This gives:

- Pydantic-compatible model classes (reuse between ORM and schemas where appropriate)
- Full async support with `AsyncSession`
- Alembic migration support via SQLAlchemy metadata

```python
# manifold/models/account.py
from sqlmodel import SQLModel, Field
import sqlalchemy as sa
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from manifold.security.types import EncryptedJSON

class Account(SQLModel, table=True):
    __tablename__ = "accounts"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_connection_id: UUID = Field(foreign_key="provider_connections.id")
    provider_account_id: str  # The provider's native ID
    account_type: str          # current, savings, card, etc.
    currency: str
    display_name: Optional[str]
    iban: Optional[str]
    sort_code: Optional[str]
    account_number: Optional[str]
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Optional[dict] = Field(default=None, sa_column=sa.Column(EncryptedJSON))
    # EncryptedJSON: AES-256-GCM via owner's per-user DEK (see manifold/security/types.py)
```

### Settings management

```python
# manifold/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_env: str = "production"
    secret_key: str  # Both the JWT signing key and the master DEK encryption key are HKDF-SHA256–derived from this value (see manifold/security/encryption.py); SECRET_KEY is never used directly for signing or encryption
    allowed_origins: list[str] = ["http://localhost:5173"]
    # NOTE: In .env, supply as JSON: ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
    # Dev convention: Vite dev server runs on :5173, Docker/nginx frontend runs on :3000.
    # Pydantic-settings parses this as a JSON list. A bare string will cause a validation error.
    timezone: str = "UTC"  # IANA timezone name, e.g. "Europe/London"
    frontend_url: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_format: str = "json"

    # Database — accepts any SQLAlchemy async URL
    # SQLite (default, zero-ops):    sqlite+aiosqlite:///data/manifold.db
    # PostgreSQL (production):       postgresql+asyncpg://user:pass@host:5432/db
    # MariaDB:                       mysql+asyncmy://user:pass@host:3306/db
    database_url: str = "sqlite+aiosqlite:///data/manifold.db"

    # First-run bootstrap (single-use env vars — remove from .env after first login)
    # If the users table is empty on startup, a superadmin is seeded from these values.
    # ADMIN_PASSWORD is plaintext here; it is Argon2id-hashed before storage and never persisted as plaintext.
    # Both vars must be set if the users table is empty; startup fails loudly if missing.
    admin_username: str = ""   # no default — must be set explicitly
    admin_password: str = ""   # plaintext, ephemeral; hashed immediately on seed, must_change_password=True

    # Auth tokens
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # TrueLayer
    truelayer_client_id: str = ""
    truelayer_client_secret: str = ""
    truelayer_redirect_uri: str = ""
    truelayer_sandbox: bool = False

    # Redis (Taskiq broker + distributed locks)
    redis_url: str = "redis://manifold-redis:6379/0"
    taskiq_result_ttl: int = 3600  # seconds; how long task results are kept in Redis

    # Background job schedules (cron strings, UTC)
    sync_cron: str = "0 * * * *"         # hourly on the hour
    alarm_eval_cron: str = "*/5 * * * *" # every 5 minutes
    recurrence_detect_cron: str = "0 3 * * *"  # 3 AM daily
    cleanup_cron: str = "0 4 * * *"            # 4 AM daily

    # DB connection pool (per-process)
    db_pool_size: int = 3
    db_pool_max_overflow: int = 2
    db_pool_timeout: int = 30

    # Notifiers (optional per-notifier)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    slack_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    system_notifier_id: str = ""  # UUID of the notifier used for system alerts (sync failures, consent expiry)

settings = Settings()
```

### Error handling strategy

- Domain exceptions defined in `manifold/exceptions.py` (e.g., `ProviderAuthError`, `SyncError`, `AlarmEvaluationError`)
- FastAPI exception handlers translate domain exceptions to HTTP responses
- Provider errors are logged with full context but never surface stack traces to API clients
  - All sync failures create a `SyncRun` record with `status=failed` and `error_detail` JSON

### Logging

Use **structlog** for structured JSON logging:

- Every log entry includes `request_id` and other applicable correlation IDs (`user_id`, `session_id`, `provider_connection_id`, `sync_run_id`)
- Financial data and secrets are excluded from normal logs; see the v1 structured logging policy in §18
- Production default: `INFO` level, JSON format
  - Sensitive fields are redacted via the `structlog` processor pipeline before emission

### CLI Tools (`manifold/cli.py`)

Two administrative CLI commands provided via `manifold/cli.py`:

```python
# manifold/cli.py — invoked as `uv run manifold <command>` or `python -m manifold.cli <command>`
import click, sys
from manifold.config import settings

@click.group()
def cli(): ...

@cli.command("create-user")
@click.argument("username")
@click.argument("password")
@click.option("--role", default="regular", type=click.Choice(["regular", "superadmin"]))
@click.option("--must-change-password", is_flag=True, default=False)
def create_user(username: str, password: str, role: str, must_change_password: bool):
    """Create a new user directly (bypasses bootstrap; useful for CLI-provisioned accounts).
    Password is hashed with Argon2id before storage — plaintext never persists."""
    import asyncio
    from manifold.database import get_session
    from manifold.domain.users import create_user_record
    asyncio.run(create_user_record(
        username=username,
        password=password,
        role=role,
        must_change_password=must_change_password,
    ))
    click.echo(f"Created user '{username}' with role '{role}'.")

@cli.command("check-config")
def check_config():
    """Validate all required environment variables and print a config summary.

    Checks: SECRET_KEY always required. Bootstrap vars (ADMIN_USERNAME + ADMIN_PASSWORD)
    required only if the users table is empty — i.e. a fresh database with no users yet.
    Prints OK/WARN per item; exits 1 if any errors found."""
    errors = []
    if not settings.secret_key:
        errors.append("SECRET_KEY is not set")
    # Bootstrap vars are only required when database has no users; check-config warns if
    # they are absent but does not fail — the DB state is checked at runtime, not here.
    if not settings.admin_username:
        click.echo("WARN: ADMIN_USERNAME not set — required on first run (empty users table)")
    if not settings.admin_password:
        click.echo("WARN: ADMIN_PASSWORD not set — required on first run (empty users table)")
    if errors:
        for e in errors:
            click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)
    click.echo(f"OK  database_url    = {settings.database_url}")
    click.echo(f"OK  redis_url       = {settings.redis_url}")
    click.echo("Configuration OK")
```

Usage:

- `uv run manifold create-user alice secretpass --role superadmin --must-change-password` → creates a superadmin (Argon2id-hashed)
- `python -m manifold.cli check-config` → validates config inside a running container (used in milestone QA)

`pyproject.toml` entry point: `[project.scripts] manifold = "manifold.cli:cli"`

---

## 5. Frontend Design

### Toolchain

- **Vite 5** — build tool
- **React 18** — UI framework
- **TypeScript 5** — type safety
- **TanStack Router** — type-safe routing with loader support
- **TanStack Query** — server state management, caching, polling
- **shadcn/ui + Tailwind CSS** — component primitives
- **Recharts** — financial charts (balance history, transaction trends)
- **react-querybuilder** — alarm rule expression builder (AND/OR/NOT trees)
- **Axios** — HTTP client with interceptors for token refresh
- **Zod** — runtime validation for API responses

### Frontend package structure

```
frontend/src/
├── routes/                  # TanStack Router route tree
│   ├── __root.tsx           # Root layout (navigation shell)
│   ├── index.tsx            # Redirects to /dashboard
│   ├── login.tsx
│   ├── change-password.tsx    # Forced password change screen (redirected here when mustChangePassword=true)
│   ├── dashboard/
│   │   └── index.tsx
│   ├── connections/
│   │   ├── index.tsx        # User-owned connection list + status
│   │   ├── connect.tsx      # Provider selection + OAuth flow initiation
│   │   └── $connectionId.tsx  # Connection detail
│   ├── accounts/
│   │   ├── index.tsx
│   │   └── $accountId.tsx
│   ├── cards/
│   │   ├── index.tsx
│   │   └── $cardId.tsx
│   ├── transactions/
│   │   └── index.tsx        # Filterable transaction list
│   ├── direct-debits/
│   │   └── index.tsx
│   ├── standing-orders/
│   │   └── index.tsx
│   ├── alarms/
│   │   ├── index.tsx        # Alarm list + status
│   │   ├── new.tsx          # Create alarm (rule builder)
│   │   └── $alarmId.tsx     # Alarm detail + history
│   ├── notifiers/
│   │   ├── index.tsx        # Configured notifiers
│   │   └── new.tsx          # Add notifier
│   └── settings/
│       ├── index.tsx
│       ├── users.tsx          # Superadmin: user list, create user, deactivate
│       ├── access.tsx         # Account owner: grant/revoke viewer/admin access
│       └── sessions.tsx       # User session inventory + revoke actions
│
├── features/               # Feature-scoped hooks, components, services
│   ├── auth/
│   │   ├── AuthProvider.tsx
│   │   ├── useAuth.ts
│   │   └── ProtectedRoute.tsx
│   ├── dashboard/
│   │   ├── BalanceSummaryCard.tsx
│   │   ├── RecentTransactionsFeed.tsx
│   │   ├── UpcomingDebitsWidget.tsx
│   │   ├── AlarmStatusWidget.tsx
│   │   └── SyncStatusWidget.tsx
│   ├── connections/
│   │   ├── ConnectionCard.tsx
│   │   ├── ConnectionStatusBadge.tsx
│   │   └── useConnections.ts
│   ├── accounts/
│   │   ├── AccountCard.tsx
│   │   ├── BalanceHistoryChart.tsx
│   │   └── useAccounts.ts
│   ├── cards/
│   │   ├── CardList.tsx
│   │   ├── CardDetail.tsx
│   │   └── useCards.ts
│   ├── transactions/
│   │   ├── TransactionTable.tsx
│   │   ├── TransactionFilters.tsx
│   │   └── useTransactions.ts
│   ├── direct-debits/
│   │   ├── DirectDebitList.tsx
│   │   ├── PredictionBadge.tsx  # Observed vs Predicted indicator
│   │   └── useDirectDebits.ts
│   ├── standing-orders/
│   │   ├── StandingOrderList.tsx
│   │   └── useStandingOrders.ts
│   ├── alarms/
│   │   ├── AlarmCard.tsx
│   │   ├── AlarmStateBadge.tsx  # ok/pending/firing/resolved/muted
│   │   ├── AlarmRuleBuilder.tsx # react-querybuilder integration
│   │   ├── AlarmHistory.tsx
│   │   └── useAlarms.ts
│   └── notifiers/
│       ├── NotifierCard.tsx
│       └── useNotifiers.ts
│
├── api/                    # Typed API client functions
│   ├── client.ts           # Axios instance + interceptors
│   ├── auth.ts
│   ├── providers.ts        # Provider-type registry + OAuth helpers
│   ├── connections.ts      # User-owned provider connections
│   ├── accounts.ts
│   ├── transactions.ts
│   ├── direct_debits.ts
│   ├── standing_orders.ts
│   ├── cards.ts
│   ├── dashboard.ts
│   ├── users.ts
│   ├── sessions.ts
│   ├── settings.ts
│   ├── sync_runs.ts
│   ├── events.ts
│   ├── recurrence_profiles.ts
│   ├── notification_deliveries.ts
│   ├── alarms.ts
│   └── notifiers.ts
│
├── components/             # Shared UI components
│   ├── ui/                 # shadcn/ui generated components
│   ├── layout/
│   │   ├── AppShell.tsx
│   │   ├── Sidebar.tsx
│   │   └── TopBar.tsx
│   ├── StatusBadge.tsx
│   ├── ObservabilityTag.tsx  # Observed vs Inferred/Predicted badge
│   ├── ConfidenceIndicator.tsx
│   └── SyncRunLog.tsx
│
├── lib/
│   ├── queryClient.ts      # TanStack Query configuration
│   └── utils.ts
│
└── types/                  # Shared TypeScript types (mirror backend schemas)
    ├── provider.ts
    ├── account.ts
    ├── transaction.ts
    ├── alarm.ts
    └── notifier.ts
```

### Auth / session model (frontend)

- On login, the backend sets a short-lived JWT access token (15 min) as an **HttpOnly cookie** and also returns it in the JSON response body (`{"access_token":"...","token_type":"bearer","expires_in":900}`)
- A refresh token (7 days) is stored as an **HttpOnly cookie** (not in the response body)
- A device-binding cookie (90 days) is stored as an **HttpOnly cookie** and paired server-side with the session
- Cookie policy: `SameSite=Lax` by default for access, refresh, and device-binding cookies; `Secure=true` in production and `Secure=false` only in explicit local development mode
- Browser clients rely on the cookie; it is sent automatically on every same-origin request
- Axios request interceptor catches 401 responses, attempts token refresh via `/api/v1/auth/refresh` (using the refresh cookie + device-binding cookie), then retries original request
- TanStack Router uses a `beforeLoad` guard to redirect unauthenticated users to `/login`
- No token is stored in localStorage or sessionStorage; the access token in the login JSON body is used only for non-browser API clients (curl, scripts)
- Frontend exposes a sessions page so users can see active sessions/devices and revoke them individually

### Key UI pages

| Page             | Purpose                        | Key observability elements                                         |
| ---------------- | ------------------------------ | ------------------------------------------------------------------ |
| Dashboard        | Summary overview               | Balance totals, upcoming debits, active alarms, last sync time     |
| Connections      | Connection health              | Connection status, consent expiry countdown, last sync result      |
| Accounts / Cards | Account detail                 | Balance history chart, account metadata, provider attribution      |
| Transactions     | Filterable list                | Observed vs pending badge, merchant, category, amount              |
| Direct Debits    | Mandates + predictions         | Confirmed vs Predicted badge, confidence score, next expected date |
| Alarms           | Active alarm rules             | State badge (ok/firing/muted), last evaluation, explanation text   |
| Alarm detail     | Single alarm drill-down        | Full evaluation history, firing conditions, linked notifiers       |
| Notifiers        | Delivery channel config        | Type, enabled state, last delivery status                          |
| Settings         | Read-only operational metadata | App version, scheduler status, connection counts, notifier counts  |

### Frontend environment config

```bash
# frontend/.env.example
# In local dev, leave this unset (or set to empty) — Vite proxy handles /api routing.
# Set this only when building for production without the Docker/nginx proxy.
VITE_API_BASE_URL=
VITE_APP_ENV=development
```

Runtime API URL is injected at build time via Vite's `import.meta.env.VITE_API_BASE_URL`. For Docker deployments, this is supplied at image build time. For truly dynamic injection, a `/api/config` endpoint can be used, but build-time injection is simpler for v1.

> **⚠️ Auth cookie requirement — IMPORTANT**: Session authentication uses HttpOnly cookies. For cookies to be set correctly, the browser must treat API requests as same-origin. This is achieved in two ways:
>
> - **Local dev**: Vite's built-in dev proxy rewrites `/api` calls to `http://localhost:8000`, making them same-origin from the browser's perspective. `VITE_API_BASE_URL` should be left empty or unset in dev.
> - **Production**: nginx proxies `/api` to the backend container — already same-origin.
>
> **Never set `VITE_API_BASE_URL=http://localhost:8000` in local dev** — that bypasses the proxy, causes cross-origin requests, and breaks cookie-based auth.
>
> The required `vite.config.ts` proxy config:
>
> ```typescript
> // frontend/vite.config.ts
> const apiProxyTarget = process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000';
>
> export default defineConfig({
>   server: {
>     proxy: {
>       '/api': {
>         target: apiProxyTarget,
>         changeOrigin: false,   // same-origin: cookies flow correctly
>       },
>     },
>   },
> });
> ```
>
> - Host local dev: `VITE_DEV_PROXY_TARGET=http://localhost:8000`
> - Docker Compose frontend container: `VITE_DEV_PROXY_TARGET=http://backend:8000`

---

## 6. Provider Adapter / Plugin Architecture

### Design principle

The application core **never imports any provider-specific module**. All provider interactions are mediated by a `BaseProvider` abstract class and a `ProviderRegistry`. Domain services call `registry.get(connection.provider_type)` and work with canonical return types only.

### BaseProvider interface

```python
# manifold/providers/base.py
from abc import ABC, abstractmethod
from typing import Optional
from manifold.providers.types import (
    ProviderConnectionContext,
    AccountData,
    BalanceData,
    TransactionData,
    PendingTransactionData,
    CardData,
    DirectDebitData,
    StandingOrderData,
)

class BaseProvider(ABC):
    provider_type: str        # e.g., "truelayer", "json"
    display_name: str         # e.g., "TrueLayer", "JSON Feed"
    supports_pending: bool = False
    supports_direct_debits: bool = False
    supports_standing_orders: bool = False
    supports_cards: bool = False

    @abstractmethod
    async def get_auth_url(self, state: str) -> str:
        """Return the URL to initiate provider authorization."""
        ...

    @abstractmethod
    async def exchange_code(self, code: str, connection: ProviderConnectionContext) -> dict:
        """Exchange an auth code for tokens; return normalized credential/config updates for persistence by the domain layer."""
        ...

    @abstractmethod
    async def refresh_if_needed(self, connection: ProviderConnectionContext) -> dict:
        """Refresh credentials if needed; return normalized credential/config updates for persistence by the domain layer."""
        ...

    @abstractmethod
    async def get_accounts(self, connection: ProviderConnectionContext) -> list[AccountData]:
        """Return normalized provider DTOs, not ORM models."""
        ...

    @abstractmethod
    async def get_balances(self, connection: ProviderConnectionContext, account_id: str) -> list[BalanceData]:
        ...

    @abstractmethod
    async def get_transactions(
        self,
        connection: ProviderConnectionContext,
        account_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> list[TransactionData]:
        ...

    async def get_pending_transactions(
        self, connection: ProviderConnectionContext, account_id: str
    ) -> list[PendingTransactionData]:
        return []  # Default: not supported

    async def get_cards(self, connection: ProviderConnectionContext) -> list[CardData]:
        return []  # Default: not supported

    async def get_direct_debits(
        self, connection: ProviderConnectionContext, account_id: str
    ) -> list[DirectDebitData]:
        return []  # Default: not supported

    async def get_standing_orders(
        self, connection: ProviderConnectionContext, account_id: str
    ) -> list[StandingOrderData]:
        return []  # Default: not supported

    @abstractmethod
    async def is_connection_valid(self, connection: ProviderConnectionContext) -> bool:
        """Return True if current credentials are valid."""
        ...
```

> **Boundary rule**: Provider adapters return canonical DTOs and credential/config deltas only. ORM model creation, persistence, deduplication, and ownership-aware writes remain in the domain/sync layer.

### ProviderRegistry

```python
# manifold/providers/registry.py
from manifold.providers.base import BaseProvider

class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, type[BaseProvider]] = {}

    def register(self, provider_class: type[BaseProvider]) -> None:
        self._providers[provider_class.provider_type] = provider_class

    def get(self, provider_type: str) -> BaseProvider:
        cls = self._providers.get(provider_type)
        if not cls:
            raise KeyError(f"Unknown provider type: {provider_type}")
        return cls()

    def list_types(self) -> list[str]:
        return list(self._providers.keys())

# Singleton
registry = ProviderRegistry()

# Registration (called at app startup in lifespan)
def register_all():
    from manifold.providers.truelayer.adapter import TrueLayerProvider
    from manifold.providers.json_provider.adapter import JsonProvider
    registry.register(TrueLayerProvider)
    registry.register(JsonProvider)
```

### TrueLayer provider adapter

TrueLayer uses OAuth2 Authorization Code Flow. The adapter is a **confidential client** (backend holds `client_secret`) so PKCE is not required. The adapter:

1. Generates an authorization URL with `response_type=code&scope=accounts balance transactions direct_debits standing_orders offline_access`
2. Stores the `state` parameter in the `oauth_states` table (with 10-minute TTL) before redirecting, to prevent CSRF and support concurrent auth flows
3. Handles the callback at `/api/v1/providers/{type}/callback`; validates the `state` parameter from `oauth_states`
4. Exchanges code for `access_token` + `refresh_token`; stores both (encrypted at rest) in `ProviderConnection.credentials_encrypted`
5. On each sync, refreshes the access token if it expires within 5 minutes
6. After refresh, stores the **new** refresh token returned by TrueLayer (TrueLayer rotates refresh tokens on use; failing to store the new one causes `invalid_grant` on the next refresh)
7. Maps TrueLayer responses to canonical models via `mappers.py`

**TrueLayer data availability**:

- `/data/v1/accounts` → Accounts
- `/data/v1/cards` → Cards  
- `/data/v1/accounts/{id}/balance` → Balances
- `/data/v1/accounts/{id}/transactions` → Booked transactions
- `/data/v1/accounts/{id}/transactions/pending` → Pending transactions
- `/data/v1/accounts/{id}/direct_debits` → Direct debit mandates
- `/data/v1/accounts/{id}/standing_orders` → Standing orders

**Sandbox vs production domains**:

- Sandbox: `auth.truelayer-sandbox.com` / `api.truelayer-sandbox.com`
- Production: `auth.truelayer.com` / `api.truelayer.com`
- The `TRUELAYER_SANDBOX=true` env var controls which base URLs the adapter uses.

**Token lifetime**: TrueLayer access tokens expire after **1 hour** by default. Refresh tokens are issued when the `offline_access` scope is requested. The adapter proactively refreshes any access token that expires within 5 minutes of the current time.

**Rate limiting**: TrueLayer enforces per-consumer rate limits. The adapter must handle HTTP `429 Too Many Requests` responses with exponential backoff. A failed sync due to rate limiting sets `SyncRun.status = "failed"` with `error_code = "rate_limited"` and schedules retry after the `Retry-After` header value (or 60 seconds if absent).

**Consent expiry**: TrueLayer consent windows are typically 90 days. The system tracks `consent_expires_at` on `ProviderConnection` and generates an alarm when expiry is within 7 days.

### JSON provider adapter

The JSON provider is a first-class built-in adapter that:

- Fetches JSON from a configured URL
- Maps the payload to canonical models using a configurable field-mapping definition
- Supports multiple auth methods (none, API key header, Bearer token)

**Configuration** (per-connection, stored in `ProviderConnection.config EncryptedJSON`):

```json
{
  "url": "https://example.com/api/finance",
  "auth_type": "api_key",
  "auth_config": {
    "header_name": "X-Api-Key",
    "header_value_env": "JSON_PROVIDER_API_KEY"
  },
  "mapping": {
    "accounts_path": "$.data.accounts",
    "account_id_field": "id",
    "account_name_field": "name",
    "balance_field": "balance",
    "currency_field": "currency",
    "transactions_path": "$.data.transactions",
    "transaction_id_field": "txn_id",
    "transaction_amount_field": "amount",
    "transaction_date_field": "posted_at"
  },
  "poll_interval_override_minutes": 60
}
```

**Supported auth types for JSON provider**:

- `none` — no auth, public endpoint
- `api_key` — header-based API key (`header_name` + `header_value` or `header_value_env`)
- `bearer` — `Authorization: Bearer <token>`
- `basic` — HTTP Basic Auth

**Validation**: The JSON provider validates fetched payloads against a minimal JSONSchema defined in mapping config. Validation failures create a SyncRun record with `status=failed`; only the error code and failing field path are logged — raw payloads are **never stored** because they may contain plaintext financial data.

> **`mapping` field is optional.** If omitted, the adapter uses a default canonical field mapping (common fields: `id`, `amount`, `currency`, `description`, `date`, `balance`). Provide `mapping` only to override field names for non-standard JSON shapes.

**Purpose**: The JSON provider proves the abstraction is real because it exercises the same `BaseProvider` interface without OAuth. Domain services, sync engine, and alarm engine never know whether they're working with TrueLayer or JSON data — they see only canonical models.

### Adding a future provider

To add a new provider (e.g., Plaid, Nordigen, Tink):

1. Create `manifold/providers/{name}/` directory
2. Implement `Adapter(BaseProvider)`, `mappers.py`, `auth.py`
3. Register in `registry.register_all()`
4. Add provider-specific env vars to `Settings`
5. No changes to domain services, alarm engine, or notifiers required

---

## 7. Provider Auth Architecture

### Design principle

Auth is a provider-level concern. The application core does not know or care what auth mechanism a provider uses. Auth strategies implement a common interface and are composed into provider adapters.

### Auth strategy interface

```python
# manifold/providers/auth/base.py
from abc import ABC, abstractmethod
from typing import Optional
from manifold.models import ProviderConnection

class BaseProviderAuth(ABC):
    @abstractmethod
    async def get_auth_url(self, state: str) -> Optional[str]:
        """
        For OAuth: return the authorization URL.
        For API key / bearer: return None (no user-facing auth URL).
        """
        ...

    @abstractmethod
    async def exchange_code(self, code: str, connection: ProviderConnection) -> None:
        """For OAuth flows only. API key auth is a no-op."""
        ...

    @abstractmethod
    async def prepare_request_headers(self, connection: ProviderConnection) -> dict:
        """Return HTTP headers to attach to provider API requests."""
        ...

    @abstractmethod
    async def refresh_if_needed(self, connection: ProviderConnection) -> bool:
        """
        Check credential freshness; refresh if needed.
        Returns True if refresh was performed.
        """
        ...

    @abstractmethod
    async def is_valid(self, connection: ProviderConnection) -> bool:
        """Return True if current credentials allow API access."""
        ...
```

### Concrete auth implementations

| Class                | Used by                | Auth method                                                                        |
| -------------------- | ---------------------- | ---------------------------------------------------------------------------------- |
| `OAuth2CodeFlowAuth` | TrueLayer              | OAuth2 Authorization Code, refresh tokens (confidential client; PKCE not required) |
| `ApiKeyAuth`         | JSON provider          | Static key in request header                                                       |
| `BearerTokenAuth`    | JSON provider          | Static Bearer token                                                                |
| `BasicAuth`          | JSON provider          | HTTP Basic Auth                                                                    |
| `NoAuth`             | JSON provider (public) | No authentication                                                                  |

### OAuth2 token storage

OAuth tokens (access + refresh) are **never stored in plaintext**. They are stored in `provider_connections.credentials_encrypted`, which is declared as `EncryptedJSON` — an SQLAlchemy TypeDecorator backed by AES-256-GCM using the user's per-user DEK (see §18 "Encryption at rest"). Encryption and decryption are transparent to application code: the ORM handles `process_bind_param` / `process_result_value` automatically via `manifold/security/types.py`. No manual `encrypt_credentials` / `decrypt_credentials` functions are needed in the provider layer.

### Token refresh strategy

- Access token expiry is stored alongside the token in encrypted credentials
- Before each sync, `refresh_if_needed()` is called; if token expires within 5 minutes, it refreshes proactively
- Refresh failures set `ProviderConnection.auth_status = "refresh_failed"` and trigger a system alarm
- The frontend surfaces `auth_status` so users can re-authorize connections

### Non-OAuth auth flows

For non-OAuth providers (API key, bearer token):

- `get_auth_url()` returns `None`; the frontend shows a credential input form instead
- `exchange_code()` is a no-op
- `refresh_if_needed()` is a no-op (static credentials)
- Credentials are stored via the same encrypted JSON column (`EncryptedJSON` TypeDecorator) for consistency

---

## 8. Alarming and Rule Engine Architecture

### Overview

The alarm engine is modeled after Prometheus/Alertmanager concepts but adapted for financial domain events. Alarms have:

1. A **definition** (persistent rule with a condition expression)
2. A **state** (current evaluation outcome: ok / pending / firing / resolved / muted)
3. A **history** (every state transition is recorded)
4. **Notifier routing** (which notifiers receive messages when state changes)

### Alarm condition model

Alarm conditions are stored as **JSON boolean expression trees** in `alarm_definitions.condition` (stored as `EncryptedJSON` — encrypted under the owner's per-user DEK; see §10 schema). This allows:

- Editing conditions without code changes
- Auditing condition history (versioned)
- Generating human-readable explanations from the tree

**Expression tree format**:

```json
{
  "op": "AND",
  "args": [
    {
      "op": "GT",
      "field": "predicted_debit.amount",
      "value": 200
    },
    {
      "op": "LTE",
      "field": "predicted_debit.days_until_due",
      "value": 3
    }
  ]
}
```

**Supported operators**:

- Logic: `AND`, `OR`, `NOT`
- Comparison: `EQ`, `NEQ`, `GT`, `GTE`, `LT`, `LTE`
- String: `CONTAINS`, `STARTS_WITH`, `MATCHES` (regex)
- Domain: `IN_LIST`, `IS_NULL`, `IS_NOT_NULL`
- Existence: `SYNC_FAILED`, `CONSENT_EXPIRING_WITHIN_DAYS`

**Evaluation context** (the data available to alarm predicates):

```python
{
    "account": { "id": ..., "balance": ..., "currency": ... },
    "transaction": { "amount": ..., "merchant": ..., "description": ... },
    "predicted_debit": { "amount": ..., "days_until_due": ..., "confidence": ... },
    "sync_run": { "status": ..., "provider_type": ..., "error_code": ... },
    "provider_connection": { "auth_status": ..., "consent_expires_at": ... }
}
```

### Alarm evaluator

```python
# manifold/alarm_engine/evaluator.py
from typing import Any

class AlarmEvaluator:
    def evaluate(self, condition: dict, context: dict) -> tuple[bool, str]:
        """
        Evaluate a condition tree against a context dict.
        Returns (result: bool, explanation: str).
        """
        op = condition["op"]
        if op == "AND":
            results = [self.evaluate(arg, context) for arg in condition["args"]]
            result = all(r for r, _ in results)
            explanation = " AND ".join(e for _, e in results)
            return result, f"({explanation})"
        elif op == "OR":
            results = [self.evaluate(arg, context) for arg in condition["args"]]
            result = any(r for r, _ in results)
            explanation = " OR ".join(e for _, e in results)
            return result, f"({explanation})"
        elif op == "NOT":
            inner_result, inner_exp = self.evaluate(condition["args"][0], context)
            return not inner_result, f"NOT ({inner_exp})"
        else:
            return self._evaluate_leaf(op, condition, context)

    def _evaluate_leaf(self, op: str, condition: dict, context: dict) -> tuple[bool, str]:
        field_value = self._resolve_field(condition["field"], context)
        target = condition.get("value")
        # Dispatch to predicate implementations
        ...
```

`manifold/domain/alarm_evaluator.py` contains the domain service wrapper (`class AlarmEvaluatorService`) that holds the database session, queries all active alarms, builds evaluation context per alarm, calls `AlarmEvaluator.evaluate()`, and manages state transitions (writing `AlarmState` and `AlarmEvaluationResult` rows, creating `AlarmFiringEvent` rows, and enqueuing `dispatch_alarm_notifications` tasks).

### Alarm state machine

```
         ┌──────────┐
         │    OK    │ ◄── initial state, condition evaluates False
         └────┬─────┘
              │ condition becomes True
              ▼
         ┌──────────┐
         │ PENDING  │ ◄── condition True, waiting for repeat_count evaluations
         └────┬─────┘
              │ repeat_count reached (e.g., 3 consecutive True evaluations)
              ▼
         ┌──────────┐      user mutes alarm
         │  FIRING  │ ──────────────────────► MUTED
         └────┬─────┘                         │
              │ condition becomes False        │ mute expires
              ▼                               │
         ┌──────────┐ ◄──────────────────────┘
         │ RESOLVED │ ──► notification sent (if configured)
         └──────────┘
```

State transitions are logged to `alarm_evaluation_results` table with timestamps and evaluation context snapshot.

### Alarm deduplication / suppression

- `repeat_count`: minimum consecutive `True` evaluations before transitioning `PENDING → FIRING` (default: 1; configurable per alarm)
- `for_duration_minutes`: alarm must be True for at least N minutes before firing
- `mute_until`: `MUTED` state with expiry timestamp; evaluations continue but no notifications sent
- `cooldown_minutes`: minimum time between FIRING → notification events for the same alarm
- Deduplicated by: alarm_id + evaluation_window; duplicate evaluations within the same minute are ignored

### Observed vs predicted alarm evaluation

Alarms can be configured to evaluate against:

- **Observed data** (confirmed transactions, real balances, actual direct debit appearances): evaluated immediately when new data arrives from sync
- **Predicted data** (upcoming predicted direct debits, projected balance): evaluated by the alarm evaluation scheduler job, not triggered by sync

The evaluation context includes a `data_type` field (`"observed"` or `"predicted"`) so alarm conditions can differentiate.

### Alarm explanation generation

Every alarm firing generates an explanation string:

```python
# Example generated explanation
"Alarm fired: predicted_debit.amount (£285.00) > 200 AND 
predicted_debit.days_until_due (2 days) <= 3 
[Prediction confidence: 87%]"
```

This explanation is stored in `alarm_firing_events.explanation` and surfaced in both the frontend UI and notification messages.

### Alarm condition versioning

When a user edits an alarm condition, the old condition is archived in `alarm_definition_versions` with a version number. Firing events persist a condition snapshot taken at fire time. This ensures alarm history is auditable even after rule changes.

### End-to-end notification latency

Three sequential delays sit between a real-world event occurring and a notification landing:

```
Real-world event occurs (e.g. balance drops, transaction appears)
         │
         ▼ ① Sync delay
Data enters Manifold's DB (next periodic sync picks it up)
         │
         ▼ ② Eval delay
Alarm condition evaluated; notification task enqueued
         │
         ▼ ③ Dispatch delay
Notification task picked up by a worker; HTTP call sent
```

**① Sync delay — dominant factor**

The periodic sync cron defaults to `"0 * * * *"` (hourly). A condition may be breached in the real world but Manifold cannot know until the next sync completes.

- Worst case: ~59 minutes (condition breaches 1 minute after a sync)
- Average: ~30 minutes
- Manual sync: ~0 (user triggers "Sync Now" → data in DB within seconds)

> **Primary lever**: reducing `SYNC_CRON` to `*/15 * * * *` drops worst-case to 15 minutes with no code changes.

> **Provider caveat**: TrueLayer itself may lag behind the underlying bank by 30–60 minutes depending on the bank's Open Banking implementation. More aggressive syncing helps, but cannot compensate for upstream provider delay.

**② Eval delay**

The alarm evaluation cron defaults to `"*/5 * * * *"`. Once data is in the DB, the next evaluation window catches it.

- Worst case: 5 minutes
- Average: ~2.5 minutes

Because `evaluate_all_alarms` only reads, evaluates, writes state, and enqueues — it never makes HTTP calls — this delay stays bounded regardless of how many alarms or notifiers are configured.

**③ Dispatch delay — negligible**

With three workers all consuming the `manual` queue first, and `manual` being low-traffic, `dispatch_alarm_notifications` tasks are picked up within seconds of being enqueued. The subsequent HTTP call to a notification channel (Slack, email, Telegram) typically takes 100–500 ms.

**Combined latency table**

| Scenario                              | Sync    | Eval     | Dispatch | **Total**       |
| ------------------------------------- | ------- | -------- | -------- | --------------- |
| Manual sync + eval just ran           | 0       | 0        | ~1 s     | **~1 second**   |
| Manual sync + worst-case eval window  | 0       | 5 min    | ~1 s     | **~5 minutes**  |
| Hourly sync (average) + average eval  | ~30 min | ~2.5 min | ~1 s     | **~33 minutes** |
| Hourly sync (worst case) + worst eval | ~59 min | 5 min    | ~1 s     | **~64 minutes** |

**Practical recommendation**: for users who want sub-10-minute alerting, set `SYNC_CRON=*/10 * * * *` in `.env`. The alarm evaluation at `*/5 * * * *` is already fast enough that it is never the bottleneck.

---

## 9. Notifier Architecture

### Design

The notifier subsystem is symmetric to the provider subsystem: pluggable adapters behind a stable interface, loaded via a registry.

### BaseNotifier interface

```python
# manifold/notifiers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class NotificationType(str, Enum):
    ALARM_FIRING = "alarm_firing"
    ALARM_RESOLVED = "alarm_resolved"
    SYSTEM_EVENT = "system_event"
    INFORMATIONAL = "informational"
    TEST = "test"

@dataclass
class NotificationPayload:
    type: NotificationType
    subject: str
    body: str
    alarm_id: Optional[str] = None
    explanation: Optional[str] = None
    metadata: dict = field(default_factory=dict)

class BaseNotifier(ABC):
    notifier_type: str

    @abstractmethod
    async def send(self, payload: NotificationPayload, config: dict) -> bool:
        """Send notification. Returns True on success."""
        ...

    @abstractmethod
    async def test(self, config: dict) -> bool:
        """Send a test notification to verify config. Returns True on success."""
        ...

    @abstractmethod
    def validate_config(self, config: dict) -> list[str]:
        """Validate notifier config dict. Return list of error messages (empty = valid)."""
        ...
```

### Notifier implementations

| Class              | Channel                | Library/Method                     | Status        |
| ------------------ | ---------------------- | ---------------------------------- | ------------- |
| `EmailNotifier`    | SMTP email             | `aiosmtplib`                       | v1 (required) |
| `WebhookNotifier`  | Generic HTTP webhook   | `httpx` POST to configured URL     | v1            |
| `SlackNotifier`    | Slack Incoming Webhook | `httpx` POST to webhook URL        | v1            |
| `TelegramNotifier` | Telegram Bot API       | `httpx` POST to `api.telegram.org` | v1            |
| `WhatsAppNotifier` | WhatsApp Business API  | Twilio API or Meta Cloud API       | v2            |

### Notifier dispatcher

```python
# manifold/notifiers/dispatcher.py
class NotifierDispatcher:
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 30

    async def dispatch(
        self,
        payload: NotificationPayload,
        notifier_configs: list[dict]  # From alarm's linked notifiers
    ) -> None:
        for config in notifier_configs:
            notifier = registry.get(config["type"])
            await self._dispatch_with_retry(notifier, payload, config)

    async def _dispatch_with_retry(self, notifier, payload, config):
        delivery = NotificationDelivery(...)
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                success = await notifier.send(payload, config)
                if success:
                    delivery.status = "delivered"
                    delivery.delivered_at = utcnow()
                    break
            except Exception as e:
                wait = self.BACKOFF_BASE_SECONDS * (2 ** attempt)
                delivery.error_message = str(e)
                await asyncio.sleep(wait)
        else:
            delivery.status = "failed"
        await save_delivery(delivery)

    async def dispatch_for_firing_event(self, alarm_firing_event_id: str) -> None:
        """Entry point called by dispatch_alarm_notifications task."""
        firing_event = await load_firing_event(self._session, alarm_firing_event_id)
        alarm = await load_alarm(self._session, firing_event.alarm_id)
        notifier_ids = await load_notifier_assignments(self._session, alarm.id)
        payload = build_payload(firing_event, alarm)
        for nid in notifier_ids:
            config = await load_notifier_config(self._session, nid)
            await self._dispatch_with_retry(registry.get(config["type"]), payload, config)

    async def dispatch_system_notification(
        self,
        notification_type: str,
        notifier_ids: list[str],
        notifier_owner_user_id: str,
        affected_user_id: str,
        payload: NotificationPayload,
    ) -> None:
        """Entry point for non-alarm notifications (system_event, informational, test).
        notifier_owner_user_id is the user whose DEK is used to read notifier config.
        affected_user_id is the user recorded on notification_deliveries.user_id for ownership/audit visibility.
        notification_type: one of 'system_event', 'informational', 'test'
        """
        for nid in notifier_ids:
            config = await load_notifier_config(self._session, nid, owner_user_id=notifier_owner_user_id)
            await self._dispatch_with_retry(
                registry.get(config["type"]),
                payload,
                config,
                delivery_user_id=affected_user_id,
            )
```

### Message templating

Messages are rendered using **Jinja2** templates. Templates are defined per notifier type:

```
manifold/notifiers/templates/
├── email/
│   ├── alarm_firing.html
│   ├── alarm_firing.txt
│   └── alarm_resolved.html
├── slack/
│   └── alarm_firing.json  # Block Kit payload template
└── telegram/
    └── alarm_firing.md    # Telegram Markdown
```

Template variables include: `alarm_name`, `alarm_explanation`, `fired_at`, `account_name`, `provider_name`, `dashboard_url`.

For `WebhookNotifier`, the rendered payload is sent as JSON to a configured endpoint and should include:

- `event_type`
- `notification_type`
- `subject`
- `body`
- `metadata`
- `triggered_at`
- `delivery_id`

Webhook delivery metadata/history is stored in the same `notification_deliveries` table as other notifiers, including request payload, response detail, status, attempts, and timestamps.

### Delivery logging

One `NotificationDelivery` record is created per notifier assignment; `attempt_count` is incremented on each retry:

- `id`, `alarm_firing_event_id`, `notifier_id`, `notification_type`
- `status`: `pending | delivered | failed`
- `attempt_count`, `last_attempted_at`, `delivered_at`
- `request_payload` (EncryptedJSON, for debugging), `response_detail` (EncryptedJSON)
- `error_message`
- (notifier type is derivable from `notifier_id → notifier_configs.type`)

### Notification types

| Type             | Trigger                                                | Example                             |
| ---------------- | ------------------------------------------------------ | ----------------------------------- |
| `alarm_firing`   | Alarm state → FIRING                                   | "Balance below £100"                |
| `alarm_resolved` | Alarm state → RESOLVED                                 | "Balance recovered above £100"      |
| `system_event`   | Sync failure, auth expiry, consent near-expiry         | "TrueLayer sync failed: rate limit" |
| `informational`  | Predicted debit notification (informational, no alarm) | "Sky subscription due in 3 days"    |
| `test`           | User-triggered test from notifier settings UI          | "Test message from Manifold"        |

> **Generic alert webhooks**: Webhook notifiers are first-class notifiers, not a separate alerting subsystem. They can receive alarm-firing, alarm-resolved, system-event, informational, and test messages, and their full delivery history/metadata is queryable through the existing notification delivery log endpoints.

### Per-alarm notifier routing

Each `AlarmDefinition` routes to one or more notifiers via the `alarm_notifier_assignments` join table (see §10 schema). At the API layer, `notifier_ids: list[UUID]` is a convenience field on request/response shapes that maps to this join table — it is not a persisted column on `alarm_definitions`. Multiple alarms can route to the same notifier. Notifiers can be disabled without removing them from alarms.

---

## 10. Data Model and Database Strategy

### Database Backend: Pluggable SQL Tier

Manifold supports three SQL backends, selected automatically from `DATABASE_URL`:

| Backend              | URL prefix              | Async driver | Pool strategy                                 | Use case                          |
| -------------------- | ----------------------- | ------------ | --------------------------------------------- | --------------------------------- |
| **SQLite** (default) | `sqlite+aiosqlite://`   | `aiosqlite`  | `NullPool` (file) / `StaticPool` (`:memory:`) | Zero-ops self-hosted; 1-5 users   |
| **PostgreSQL**       | `postgresql+asyncpg://` | `asyncpg`    | `QueuePool` (`pool_size`, `max_overflow`)     | Power user; full concurrency      |
| **MariaDB**          | `mysql+asyncmy://`      | `asyncmy`    | `QueuePool` (`pool_size`, `max_overflow`)     | Users with existing MariaDB setup |

**MongoDB and SurrealDB are explicitly not supported**: their migration tooling is not production-ready and the Manifold data model is fundamentally relational (transactions link to accounts, which link to provider connections; alarms evaluate cross-table conditions).

**Schema design principle for portability**: All column types use SQLAlchemy generic types (`sa.JSON`, `DateTime(timezone=True)`, `UUID(as_uuid=True)`) so that migrations are dialect-agnostic. PostgreSQL-specific features (JSONB binary indexing, GIN indexes) are intentionally not used; the `raw_payload` access pattern is store-and-retrieve, not filter-in-SQL.

### Schema conventions

- All primary keys are UUIDs — generated application-side via `uuid4()` (portable across all backends)
- All timestamps use `DateTime(timezone=True)` — maps to `TIMESTAMPTZ` on PostgreSQL, `DATETIME` with UTC enforcement on SQLite/MariaDB
- Soft deletes via `deleted_at` nullable column where appropriate
- `created_at` / `updated_at` on most tables. Exceptions (append-only or state tables with no `updated_at`): `balances` (has `recorded_at` instead of `updated_at`; `created_at` tracks insert time), `sync_runs` (immutable once completed; has `created_at` only), `alarm_states` (has `created_at` only), `alarm_evaluation_results` (has `created_at` only), `alarm_firing_events` (has `created_at` only).
- `raw_payload EncryptedJSON` on all tables that store data fetched from external providers — provider responses may contain financial data, so this field is always encrypted using the owner's per-user DEK. `[encrypted]`
- Provider-native IDs stored alongside internal UUIDs (e.g., `provider_account_id text`)
- `UNIQUE (provider_connection_id, provider_account_id)` constraints to prevent duplicates

### Core tables

#### `provider_connections`

```sql
id               UUID PK              -- app-generated uuid4()
user_id          UUID FK users NOT NULL  -- owner of this connection
provider_type    EncryptedText NOT NULL  -- "truelayer", "json"  [encrypted]
display_name     EncryptedText           -- human-readable connection name  [encrypted]
status           TEXT NOT NULL          -- active, inactive, error, expired, disconnected
auth_status      TEXT NOT NULL          -- connected, refresh_failed, consent_expired
credentials_encrypted EncryptedJSON     -- OAuth tokens / API keys  [encrypted; replaces former Fernet TEXT approach]
config           EncryptedJSON           -- provider-specific config  [encrypted; default set app-side as empty dict under active DEK — no DB-level default, as ciphertext depends on owner DEK and nonce]
consent_expires_at DATETIME (UTC)
last_sync_at     DATETIME (UTC)
created_at       DATETIME (UTC)
updated_at       DATETIME (UTC)
```

#### `accounts`

```sql
id                    UUID PK
user_id               UUID FK users NOT NULL  -- owner of this account (direct FK for fast access checks)
provider_connection_id UUID FK provider_connections
provider_account_id   TEXT NOT NULL
account_type          EncryptedText NOT NULL  -- current, savings, card, loan, mortgage  [encrypted]
currency              EncryptedText NOT NULL  -- ISO 4217  [encrypted]
display_name          EncryptedText           -- [encrypted]
iban                  EncryptedText           -- [encrypted]
sort_code             EncryptedText           -- [encrypted]
account_number        EncryptedText           -- [encrypted]
is_active             BOOLEAN DEFAULT true
raw_payload           EncryptedJSON  -- [encrypted]
created_at            DATETIME (UTC)
updated_at            DATETIME (UTC)
UNIQUE (provider_connection_id, provider_account_id)
-- `accounts.user_id` is intentionally denormalized for fast access checks.
-- Invariant: it MUST always equal `provider_connections.user_id` for the referenced connection.
-- The sync/domain layer is responsible for maintaining this invariant on create/update.
```

#### `cards`

```sql
id                    UUID PK
provider_connection_id UUID FK provider_connections NOT NULL
provider_card_id      TEXT NOT NULL
account_id            UUID FK accounts  -- may link to associated current account
display_name          EncryptedText   -- [encrypted]
card_network          TEXT             -- VISA, MASTERCARD
partial_card_number   EncryptedText   -- last 4 digits only  [encrypted]
currency              EncryptedText   -- ISO 4217  [encrypted]
credit_limit          EncryptedDecimal  -- [encrypted]
raw_payload           EncryptedJSON  -- [encrypted]
created_at            DATETIME (UTC)
updated_at            DATETIME (UTC)
UNIQUE (provider_connection_id, provider_card_id)
```

#### `balances`

```sql
id            UUID PK
account_id    UUID FK accounts         -- null for card-only balances
card_id       UUID FK cards            -- null for bank accounts
-- CHECK (account_id IS NOT NULL OR card_id IS NOT NULL)
available     EncryptedDecimal  -- [encrypted]
current       EncryptedDecimal  -- [encrypted]
currency      EncryptedText   -- ISO 4217  [encrypted]
overdraft     EncryptedDecimal  -- [encrypted]
credit_limit  EncryptedDecimal  -- [encrypted]
as_of         DATETIME (UTC)  -- when the balance was accurate
recorded_at   DATETIME (UTC)  -- when we stored it
created_at    DATETIME (UTC)  -- when this row was inserted (same as recorded_at; kept for schema consistency)
raw_payload   EncryptedJSON  -- [encrypted]
-- No UNIQUE constraint: balances are historical snapshots
```

#### `transactions`

```sql
id                     UUID PK
account_id             UUID FK accounts         -- null for card-only transactions
card_id                UUID FK cards            -- null for bank account transactions; populated when providers return card-scoped data
-- CHECK (account_id IS NOT NULL OR card_id IS NOT NULL)
provider_transaction_id TEXT NOT NULL
status                 TEXT NOT NULL    -- booked, pending
amount                 EncryptedDecimal  -- [encrypted]
currency               EncryptedText   -- ISO 4217  [encrypted]
transaction_type       TEXT            -- debit, credit
transaction_category   EncryptedText   -- [encrypted]
description            EncryptedText   -- [encrypted]
merchant_name          EncryptedText   -- [encrypted]
merchant_category      EncryptedText   -- [encrypted]
transaction_date       EncryptedText   -- ISO-8601 UTC  [encrypted]
settled_date           EncryptedText   -- ISO-8601 UTC  [encrypted]
running_balance        EncryptedDecimal  -- [encrypted]
dedup_hash             TEXT UNIQUE     -- MD5(provider_connection_id + provider_transaction_id), computed app-side
is_recurring_candidate BOOLEAN DEFAULT false
recurrence_profile_id  UUID FK recurrence_profiles
raw_payload            EncryptedJSON  -- [encrypted]
created_at             DATETIME (UTC)
updated_at             DATETIME (UTC)
UNIQUE (account_id, provider_transaction_id)
```

#### `pending_transactions`

```sql
id                        UUID PK
account_id                UUID FK accounts NOT NULL
provider_transaction_id   TEXT
amount                    EncryptedDecimal  -- [encrypted]
currency                  EncryptedText     -- ISO 4217  [encrypted]
description               EncryptedText     -- [encrypted]
merchant_name             EncryptedText     -- [encrypted]
transaction_date          EncryptedText     -- ISO-8601 UTC  [encrypted]
raw_payload               EncryptedJSON  -- [encrypted]
created_at                DATETIME (UTC)
-- Pending transactions are ephemeral; settlement strategy:
-- 1. On each sync, re-fetch pending transactions for the account.
-- 2. Any pending record no longer returned by the provider is treated as settled.
-- 3. TrueLayer does NOT guarantee stable provider_transaction_id across pending→booked
--    transitions. Match by amount + description + date within ±2 days for best-effort linking.
-- 4. Unmatched settled transactions are simply inserted as new booked transactions.
-- 5. Pending records older than 7 days with no match are purged by the cleanup job.
```

#### `direct_debits`

```sql
id                    UUID PK
account_id            UUID FK accounts NOT NULL
provider_mandate_id   TEXT
name                  EncryptedText NOT NULL  -- e.g., "Sky Broadband"  [encrypted]
status                TEXT            -- active, cancelled, expired
amount                EncryptedDecimal  -- [encrypted]
currency              EncryptedText   -- ISO 4217  [encrypted]
frequency             TEXT            -- monthly, quarterly, annual, irregular
reference             EncryptedText   -- mandate reference  [encrypted]
last_payment_date     EncryptedText   -- ISO-8601 UTC  [encrypted]
next_payment_date     EncryptedText   -- ISO-8601 UTC  [encrypted]
next_payment_amount   EncryptedDecimal  -- [encrypted]
raw_payload           EncryptedJSON  -- [encrypted]
created_at            DATETIME (UTC)
updated_at            DATETIME (UTC)
UNIQUE (account_id, provider_mandate_id)
```

#### `standing_orders`

```sql
id                         UUID PK
account_id                 UUID FK accounts NOT NULL
provider_standing_order_id TEXT
reference                  EncryptedText   -- [encrypted]
status                     TEXT            -- active, cancelled, expired
currency                   EncryptedText   -- ISO 4217  [encrypted]
frequency                  TEXT            -- weekly, fortnightly, monthly, quarterly, annual
first_payment_date         EncryptedText   -- ISO-8601 UTC  [encrypted]
first_payment_amount       EncryptedDecimal  -- [encrypted]
next_payment_date          EncryptedText   -- ISO-8601 UTC  [encrypted]
next_payment_amount        EncryptedDecimal  -- [encrypted]
final_payment_date         EncryptedText   -- ISO-8601 UTC  [encrypted]
final_payment_amount       EncryptedDecimal  -- [encrypted]
previous_payment_date      EncryptedText   -- ISO-8601 UTC  [encrypted]
previous_payment_amount    EncryptedDecimal  -- [encrypted]
raw_payload                EncryptedJSON  -- [encrypted]
created_at                 DATETIME (UTC)
updated_at                 DATETIME (UTC)
UNIQUE (account_id, provider_standing_order_id)
```

#### `recurrence_profiles`

```sql
id                UUID PK
account_id        UUID FK accounts NOT NULL
label             EncryptedText   -- human-readable "Sky Broadband"  [encrypted]
merchant_pattern  EncryptedText   -- regex or exact match  [encrypted]
amount_mean       EncryptedDecimal  -- [encrypted]
amount_stddev     EncryptedDecimal  -- [encrypted]
cadence_days      INTEGER          -- e.g., 30 for monthly
cadence_stddev    NUMERIC(6,2)
confidence        NUMERIC(5,4)     -- 0.0 to 1.0
first_seen        DATETIME (UTC)
last_seen         DATETIME (UTC)
next_predicted_at DATETIME (UTC)
next_predicted_amount EncryptedDecimal  -- [encrypted]
status            TEXT             -- active, dormant, cancelled
data_source       TEXT             -- "observed" or "inferred"
created_at        DATETIME (UTC)
updated_at        DATETIME (UTC)
```

#### `sync_runs`

```sql
id                    UUID PK
provider_connection_id UUID FK provider_connections NOT NULL
account_id             UUID FK accounts  -- null for full-connection syncs
status                 TEXT NOT NULL     -- queued, running, success, partial, failed
started_at             DATETIME (UTC)
completed_at           DATETIME (UTC)
accounts_synced        INTEGER
transactions_synced    INTEGER
new_transactions       INTEGER
error_code             TEXT
error_detail           JSON
created_at             DATETIME (UTC)
-- raw_response_sample intentionally omitted: raw provider responses may contain plaintext financial data
```

#### `user_sessions`

```sql
id                 UUID PK
user_id            UUID FK users NOT NULL
device_cookie_hash TEXT NOT NULL      -- SHA-256 of opaque device-binding cookie (raw cookie value never stored)
device_label       TEXT               -- e.g. "Chrome on MacBook"
user_agent         TEXT
ip_first           TEXT               -- IP at session creation (soft signal; never used for hard auth decisions)
ip_last            TEXT               -- most recent IP seen (updated on each refresh)
last_seen_at       DATETIME (UTC)
created_at         DATETIME (UTC)
revoked_at         DATETIME (UTC)
revoke_reason      TEXT
```

> **Refresh token storage**: Refresh tokens are stored in the separate `refresh_tokens` table (as `token_hash TEXT` — SHA-256 of the raw token) and linked back to `user_sessions` via `refresh_tokens.session_id`. `user_sessions` intentionally does not include a `refresh_token_hash` column; query active tokens via `refresh_tokens WHERE session_id = <session.id> AND revoked_at IS NULL`.
>
> **IP tracking**: `ip_first` / `ip_last` track the session's first and most-recent observed IP. This provides richer session context for the session management UI than a single `ip_address` snapshot. Neither field is used for hard authentication decisions; both are soft anomaly signals only.

#### `events`

```sql
id           UUID PK
event_type   TEXT NOT NULL    -- "transaction_detected", "balance_changed", "debit_predicted", "sync_failed", etc.
source_type  TEXT NOT NULL    -- "observed", "predicted", "system"
confidence   NUMERIC(5,4)     -- for predicted events
account_id   UUID FK accounts
user_id      UUID FK users NOT NULL  -- DEK owner; always present, even for system events (set to the user the event concerns; enables DEK lookup for encryption/decryption)
payload      EncryptedJSON NOT NULL  -- full event payload  [encrypted; always uses owner user's per-user DEK regardless of event type]
occurred_at  DATETIME (UTC)
recorded_at  DATETIME (UTC)
explanation  EncryptedText   -- human-readable explanation (may contain amounts/dates)  [encrypted]
```

> **Naming rule**: canonical event type is `debit_predicted` everywhere in backend code, API payloads, tests, and QA examples. `predicted_debit` is reserved only for alarm evaluation context field paths (e.g. `predicted_debit.amount`).

#### `alarm_definitions`

```sql
id               UUID PK
user_id          UUID FK users NOT NULL  -- owner of this alarm
name             EncryptedText NOT NULL  -- alarm display name  [encrypted]
condition        EncryptedJSON           -- alarm condition expression tree (JSON AST)  [encrypted]
condition_version INTEGER DEFAULT 1
status           TEXT DEFAULT 'active'  -- active, paused, archived
repeat_count     INTEGER DEFAULT 1
for_duration_minutes INTEGER DEFAULT 0
cooldown_minutes INTEGER DEFAULT 60
notify_on_resolve BOOLEAN DEFAULT false
-- notifier_ids removed (was UUID[] — not portable). Use alarm_notifier_assignments join table.
created_at       DATETIME (UTC)
updated_at       DATETIME (UTC)
```

#### `alarm_account_assignments`

```sql
id          UUID PK
alarm_id    UUID FK alarm_definitions NOT NULL
account_id  UUID FK accounts NOT NULL
created_at  DATETIME (UTC)
UNIQUE (alarm_id, account_id)
-- Required to make alarm evaluation deterministic for multi-account users.
-- Alarms evaluate only against accounts explicitly linked here.
```

#### `alarm_notifier_assignments`

```sql
id          UUID PK
alarm_id    UUID FK alarm_definitions NOT NULL
notifier_id UUID FK notifier_configs NOT NULL
created_at  DATETIME (UTC)
UNIQUE (alarm_id, notifier_id)
-- Replaces the former `notifier_ids UUID[]` column on alarm_definitions.
-- Portable across all SQL backends. Allows easy extension (e.g., per-assignment config).
```

#### `alarm_states`

```sql
id               UUID PK
alarm_id         UUID FK alarm_definitions
state            TEXT NOT NULL    -- ok, pending, firing, resolved, muted
mute_until       DATETIME (UTC)
consecutive_true INTEGER DEFAULT 0
last_evaluated_at DATETIME (UTC)
last_fired_at    DATETIME (UTC)
last_resolved_at DATETIME (UTC)
created_at       DATETIME (UTC)
UNIQUE (alarm_id)
```

#### `alarm_evaluation_results`

```sql
id               UUID PK
alarm_id         UUID FK alarm_definitions
evaluated_at     DATETIME (UTC)
result           BOOLEAN
previous_state   TEXT
new_state        TEXT
condition_version INTEGER
context_snapshot EncryptedJSON   -- evaluation context at the time  [encrypted]
explanation      EncryptedText   -- may contain amounts/dates  [encrypted]
created_at       DATETIME (UTC)
```

#### `alarm_firing_events`

```sql
id               UUID PK
alarm_id         UUID FK alarm_definitions
fired_at         DATETIME (UTC)
resolved_at      DATETIME (UTC)
explanation      EncryptedText   -- may contain amounts/dates  [encrypted]
condition_snapshot EncryptedJSON  -- condition tree at time of firing  [encrypted]
context_snapshot   EncryptedJSON  -- evaluation context at time of firing  [encrypted]
notifications_sent INTEGER DEFAULT 0
created_at         DATETIME (UTC)
```

#### `notifier_configs`

```sql
id           UUID PK
user_id      UUID FK users NOT NULL  -- owner of this notifier
name         EncryptedText NOT NULL   -- [encrypted]
type         EncryptedText NOT NULL   -- email, webhook, slack, telegram  (whatsapp deferred to v2)  [encrypted]
config       EncryptedJSON NOT NULL   -- channel-specific config (webhook URL, API key, etc.)  [encrypted]
is_enabled   BOOLEAN DEFAULT true
created_at   DATETIME (UTC)
updated_at   DATETIME (UTC)
```

#### `notification_deliveries`

```sql
id                    UUID PK
alarm_firing_event_id UUID FK alarm_firing_events NULL  -- NULL for system-event notifications (sync_failed, auth_expired, consent_expiry)
notifier_id           UUID FK notifier_configs
user_id               UUID FK users NULL  -- set for system/test notifications where alarm_firing_event_id IS NULL; ownership resolved directly
notification_type     TEXT NOT NULL
status                TEXT NOT NULL    -- pending, delivered, failed
attempt_count         INTEGER DEFAULT 0
rendered_subject      EncryptedText   -- notification subject line  [encrypted]
rendered_body         EncryptedText   -- rendered notification message body  [encrypted]
created_at            DATETIME (UTC)
first_attempted_at    DATETIME (UTC)
last_attempted_at     DATETIME (UTC)
delivered_at          DATETIME (UTC)
request_payload       EncryptedJSON   -- outbound payload (may contain recipient address or rendered content)  [encrypted]
response_detail       EncryptedJSON   -- provider response body  [encrypted]
error_message         TEXT
```

#### `oauth_states`

```sql
id             UUID PK
state          TEXT UNIQUE NOT NULL  -- random value passed in OAuth redirect
provider_type  TEXT NOT NULL          -- e.g., "truelayer"
connection_id  UUID FK provider_connections NOT NULL  -- which connection this flow will complete; resolved in callback to update status/tokens
created_at     DATETIME (UTC) NOT NULL
expires_at     DATETIME (UTC) NOT NULL   -- 10 minutes after creation; records older than this are invalid and should be purged
```

#### `alarm_definition_versions`

```sql
id                   UUID PK
alarm_definition_id  UUID FK alarm_definitions NOT NULL
version              INTEGER NOT NULL
condition            EncryptedJSON NOT NULL  -- condition tree at this version  [encrypted]
changed_at           DATETIME (UTC) NOT NULL
UNIQUE (alarm_definition_id, version)
```

> When an alarm's condition is updated, the current condition is archived here before replacement.
> `alarm_evaluation_results.condition_version` references the version that was active at evaluation time.
>
> **API exposure**: `alarm_definition_versions` is **internal-only in v1** — no REST endpoint is exposed for it directly. Alarm evaluation history (which version was active at each evaluation) is accessible via `GET /api/v1/alarms/{id}/history`. Condition archives are retained for audit correlation and are not returned via the public API.

#### `users`

```sql
id                   UUID PK
username             TEXT UNIQUE NOT NULL
email                TEXT UNIQUE
password_hash        TEXT NOT NULL          -- Argon2id (m=65536, t=3, p=4) via passlib
role                 TEXT NOT NULL          -- 'superadmin' | 'regular'
is_active            BOOLEAN DEFAULT TRUE
must_change_password BOOLEAN DEFAULT FALSE  -- forced on bootstrap seed; server enforces on all endpoints
encrypted_dek        LargeBinary NOT NULL   -- per-user Data Encryption Key, encrypted under master key derived from SECRET_KEY via HKDF-SHA256 (maps to BLOB/MEDIUMBLOB/BYTEA by dialect)
created_at           DATETIME (UTC)
updated_at           DATETIME (UTC)
```

#### `account_access`

```sql
id               UUID PK
owner_user_id    UUID FK users NOT NULL   -- whose data is being shared
grantee_user_id  UUID FK users NOT NULL   -- who receives access
role             TEXT NOT NULL            -- 'viewer' | 'admin'
granted_at       DATETIME (UTC)
granted_by       UUID FK users            -- who granted it (audit trail)
-- No account_id column: delegation is user-level (all-or-nothing)
-- Self-grant prevented at application layer
INDEX (grantee_user_id)                   -- fast scope resolution for get_accessible_scope()
UNIQUE (owner_user_id, grantee_user_id)   -- one grant per pair
```

#### `refresh_tokens`

```sql
id           UUID PK
user_id      UUID FK users NOT NULL  ON DELETE CASCADE
token_hash   TEXT UNIQUE NOT NULL    -- SHA-256 of the actual token; never store plaintext
issued_at    DATETIME (UTC) NOT NULL
expires_at   DATETIME (UTC) NOT NULL
revoked_at   DATETIME (UTC)          -- NULL = active; set on logout or user deactivation
INDEX (user_id)
INDEX (token_hash)
INDEX (expires_at)                   -- for the periodic cleanup job
```

> Deactivating a user sets `revoked_at = datetime.now(timezone.utc)` (Python-side UTC) on all their active `refresh_tokens` rows,
> instantly invalidating all sessions. Token rotation on refresh issues a new row and revokes the old one.

### Deduplication strategy

Transactions are deduplicated using a `dedup_hash`:

```python
dedup_hash = md5(f"{provider_connection_id}:{provider_transaction_id}".encode()).hexdigest()
```

The `dedup_hash` is computed application-side (Python `hashlib.md5`) before insert. Upsert is implemented via a portable repository helper:

```python
# Portable upsert — works across all backends
async def upsert_transaction(session: AsyncSession, values: dict) -> None:
    try:
        session.add(Transaction(**values))
        await session.flush()
    except IntegrityError:
        await session.rollback()
        stmt = update(Transaction).where(Transaction.dedup_hash == values["dedup_hash"]).values(**values)
        await session.execute(stmt)
```

> **Per-dialect upsert strategy**: Each backend uses its native upsert syntax for performance-critical paths.
>
> - **SQLite**: `INSERT OR REPLACE` / `INSERT ... ON CONFLICT (dedup_hash) DO UPDATE SET ...`
> - **PostgreSQL**: `INSERT ... ON CONFLICT (dedup_hash) DO UPDATE SET ...` (via `PostgreSQLBackend.upsert()`)
> - **MariaDB**: `INSERT ... ON DUPLICATE KEY UPDATE ...` (via `MariaDBBackend.upsert()` using raw SQL with `VALUES()` function semantics)
>
> **v1 requirement**: the full `DatabaseBackend` abstraction is part of the implementation scope. Performance-critical persistence paths must route through backend-specific implementations where dialect behavior differs.

### JSON storage philosophy

> **Note on sa.JSON vs JSONB**: Using `sa.JSON` instead of `postgresql.JSONB` means PostgreSQL users lose binary JSON storage compression and GIN-indexed JSON containment queries. For Manifold's access patterns — `raw_payload` is stored for audit/debug and read whole, alarm `condition` trees are read and parsed in Python, `context_snapshot` is written once and read for history — **the performance impact is negligible**. No SQL JSON containment queries (`@>`, `?&`) are used in Manifold's codebase. This is an intentional, documented trade-off for portability.

- `raw_payload`: Store the original provider response encrypted as `EncryptedJSON` using the owner's per-user DEK. Never delete. Used for debugging, audit, and future re-processing. Raw provider responses may contain financial data and must not be stored in plaintext.
- `config`: Provider-specific and notifier-specific configuration that varies by type.
- `condition`: Alarm expression tree.
- `context_snapshot`: Evaluation context preserved at evaluation time for audit.
- **Do not** use JSON for fields that need indexing or frequent filtering — these go in typed columns.

### Data retention policy

- **Balance snapshots**: Full resolution retained indefinitely for the first 90 days. After 90 days, keep one snapshot per calendar day (delete intra-day duplicates in the `run_data_retention_jobs` job, which also handles balance compaction). This prevents unbounded growth from 30-minute sync intervals.
- **`sync_runs`**: Retain all records (low volume; useful for audit).
- **`alarm_evaluation_results`**: Retain all records (useful for alarm history UI).
- **`events`**: Retain all records.
- **`oauth_states`**: Purge records where `expires_at < CURRENT_TIMESTAMP` during the daily `run_data_retention_jobs` job.

### Connection deletion semantics

When a `ProviderConnection` is deleted:

- The connection record is **soft-deleted**: `status` is set to `'disconnected'`. The row is **not hard-deleted**, preserving FK integrity for all associated rows (`accounts`, `sync_runs`, `cards`, `oauth_states`). Subsequent sync queries filter for `status = 'active'` and will not pick up disconnected connections.
- All associated `accounts` are also marked `is_active = false`.
- Transactions, balances, direct debits, standing orders, and other financial data are **retained** for historical reference.
- The UI shows a "disconnected" badge on accounts that have no active connection.
- This preserves the observability record even after a provider is removed.

---

## 10a. Database Backend Connector Architecture

This section documents the pluggable database backend system as a **required v1 architecture**. SQLite, PostgreSQL, and MariaDB support are delivered through this abstraction from the start.

### Design principle

Just as `BaseProvider` → `TrueLayerProvider` / `JsonProvider` / `...`, the database layer follows:

```
DatabaseBackend (ABC)
├── SQLiteBackend       # default — zero-ops file-based
├── PostgreSQLBackend   # asyncpg — QueuePool + ON CONFLICT upsert
└── MariaDBBackend      # asyncmy — QueuePool + ON DUPLICATE KEY UPDATE
```

Selection is automatic at startup: `DatabaseBackendFactory.create()` (or `DatabaseBackendFactory.create(settings.database_url)`) inspects the configured database URL prefix and returns the appropriate backend instance.

### File layout

```
backend/manifold/database/
├── __init__.py          # exports: engine, get_session, db_session
├── base.py              # DatabaseBackend ABC
├── factory.py           # DatabaseBackendFactory
└── backends/
    ├── __init__.py
    ├── sqlite.py        # SQLiteBackend
    ├── postgresql.py    # PostgreSQLBackend
    └── mariadb.py       # MariaDBBackend
```

### `DatabaseBackend` ABC (`base.py`)

```python
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncEngine

class DatabaseBackend(ABC):
    """Abstract database backend. Each subclass encapsulates
    all driver-specific configuration for one SQL dialect."""

    @property
    @abstractmethod
    def dialect_name(self) -> str:
        """Short name: 'sqlite' | 'postgresql' | 'mariadb'"""

    @abstractmethod
    def create_engine(self, url: str) -> AsyncEngine:
        """Build and return a configured async engine for this backend."""

    @abstractmethod
    def upsert(self, table, values: dict, conflict_columns: list[str]) -> Any:
        """Return a portable upsert statement for this backend."""
```

### `SQLiteBackend` (`backends/sqlite.py`)

```python
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.pool import NullPool, StaticPool
from manifold.database.base import DatabaseBackend

class SQLiteBackend(DatabaseBackend):
    dialect_name = "sqlite"

    def create_engine(self, url: str) -> AsyncEngine:
        poolclass = StaticPool if ":memory:" in url else NullPool
        engine = create_async_engine(
            url,
            poolclass=poolclass,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine.sync_engine, "connect")
        def _on_connect(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine

    def upsert(self, table, values: dict, conflict_columns: list[str]):
        # SQLite 3.24+ supports ON CONFLICT DO UPDATE; used here for upsert semantics.
        # (Callers use the backend-agnostic helper in manifold/domain/_upsert.py)
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = sqlite_insert(table).values(**values)
        return stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_=values,
        )
```

### `PostgreSQLBackend` (`backends/postgresql.py`)

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from manifold.database.base import DatabaseBackend
from manifold.config import settings as _settings

class PostgreSQLBackend(DatabaseBackend):
    dialect_name = "postgresql"

    def create_engine(self, url: str) -> AsyncEngine:
        return create_async_engine(
            url,
            pool_size=_settings.db_pool_size,
            max_overflow=_settings.db_pool_max_overflow,
            pool_timeout=_settings.db_pool_timeout,
            pool_pre_ping=True,
        )

    def upsert(self, table, values: dict, conflict_columns: list[str]):
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(table).values(**values)
        return stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_=values,
        )
```

### `MariaDBBackend` (`backends/mariadb.py`)

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from manifold.database.base import DatabaseBackend
from manifold.config import settings as _settings

class MariaDBBackend(DatabaseBackend):
    dialect_name = "mariadb"

    def create_engine(self, url: str) -> AsyncEngine:
        return create_async_engine(
            url,
            pool_size=_settings.db_pool_size,
            max_overflow=_settings.db_pool_max_overflow,
            pool_timeout=_settings.db_pool_timeout,
            pool_pre_ping=True,
        )

    def upsert(self, table, values: dict, conflict_columns: list[str]):
        # MariaDB does not support ON CONFLICT; use SQLAlchemy MySQL dialect insert
        # `conflict_columns` must be the PRIMARY KEY or a UNIQUE index
        from sqlalchemy.dialects.mysql import insert as mysql_insert
        stmt = mysql_insert(table).values(**values)
        update_cols = {k: stmt.inserted[k] for k in values.keys() if k not in conflict_columns}
        return stmt.on_duplicate_key_update(**update_cols)
```

### `DatabaseBackendFactory` (`factory.py`)

```python
from manifold.config import settings
from manifold.database.base import DatabaseBackend
from manifold.database.backends.sqlite import SQLiteBackend
from manifold.database.backends.postgresql import PostgreSQLBackend
from manifold.database.backends.mariadb import MariaDBBackend

_BACKENDS: dict[str, type[DatabaseBackend]] = {
    "sqlite": SQLiteBackend,
    "postgresql": PostgreSQLBackend,
    "mysql": MariaDBBackend,      # asyncmy uses mysql+asyncmy://
}

class DatabaseBackendFactory:
    @staticmethod
    def create(database_url: str | None = None) -> DatabaseBackend:
        url = database_url or settings.database_url
        scheme = url.split("+")[0].split(":")[0]  # "sqlite", "postgresql", "mysql"
        backend_cls = _BACKENDS.get(scheme)
        if backend_cls is None:
            supported = ", ".join(_BACKENDS)
            raise ValueError(
                f"Unsupported database scheme '{scheme}' in DATABASE_URL. "
                f"Supported: {supported}"
            )
        return backend_cls()
```

### Top-level `database/__init__.py`

```python
# manifold/database/__init__.py
from manifold.config import settings
from manifold.database.factory import DatabaseBackendFactory
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

_backend = DatabaseBackendFactory.create()
engine = _backend.create_engine(settings.database_url)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# FastAPI dependency — use with `Depends(get_session)` in route handlers
async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# Background task / CLI context manager — use `async with db_session() as session:` in tasks
from contextlib import asynccontextmanager

@asynccontextmanager
async def db_session():
    """Direct async context manager for background tasks and CLI (not a FastAPI dependency)."""
    async with AsyncSessionLocal() as session:
        yield session
```

### Alembic `env.py` — batch mode + dialect awareness

```python
# alembic/env.py (critical additions)
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

def do_run_migrations(connection):
    is_sqlite = connection.dialect.name == "sqlite"
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=is_sqlite,   # required for SQLite ALTER TABLE
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()
```

> **Note**: Migration scripts that use `op.alter_column` or `op.add_column` MUST use `with op.batch_alter_table("table_name") as batch_op:` syntax to remain SQLite-compatible. This is enforced by Alembic's autogenerate when `render_as_batch=True`.

### Adding a new backend (future extensibility)

1. Create `backend/manifold/database/backends/newdb.py` implementing `DatabaseBackend`
2. Register in `_BACKENDS` dict in `factory.py` with the URL scheme prefix
3. No other application code changes required

### Driver installation notes

| Backend    | Driver      | Install                                                           |
| ---------- | ----------- | ----------------------------------------------------------------- |
| SQLite     | `aiosqlite` | `uv add aiosqlite` — always installed (default)                   |
| PostgreSQL | `asyncpg`   | `uv add asyncpg` — optional; listed as extras in `pyproject.toml` |
| MariaDB    | `asyncmy`   | `uv add asyncmy` — optional; listed as extras in `pyproject.toml` |

Optional drivers are declared in `pyproject.toml` as:

```toml
[project.optional-dependencies]
postgresql = ["asyncpg"]
mariadb = ["asyncmy"]
all-backends = ["asyncpg", "asyncmy"]
```

---

## 11. API Surface Design

### Base URL and versioning

All API endpoints are versioned: `/api/v1/...`

> **URL path naming convention**: Multi-word path **segments** use **kebab-case** (hyphens), e.g., `/sync-runs`, `/auth-url`, `/direct-debits`. This is the idiomatic REST convention and is used consistently throughout. JSON **field names** in request and response bodies use **snake_case**, e.g., `provider_type`, `account_id`, `sync_run_id`. Implementers and QA authors must follow both rules to avoid inconsistency.

### Authentication endpoints

```
POST   /api/v1/auth/login          # { username, password } → sets HttpOnly cookie; body: {"access_token":"<jwt>","token_type":"bearer","expires_in":900}
POST   /api/v1/auth/logout         # Clears cookie; revokes refresh_token row in DB
POST   /api/v1/auth/refresh        # Refreshes access token using refresh cookie (rotates token); body: {"access_token":"<jwt>","expires_in":900}
GET    /api/v1/auth/me             # Returns current session info: {id, username, role, mustChangePassword}; requires cookie OR Authorization: Bearer <token>
PATCH  /api/v1/auth/me/password    # { current_password, new_password } → changes own password; clears must_change_password flag
GET    /api/v1/auth/sessions       # List my active sessions/devices
DELETE /api/v1/auth/sessions/{id}  # Revoke one session/device (cannot delete others' sessions)
POST   /api/v1/auth/sessions/revoke-others  # Revoke all sessions except current
```

> All endpoints except `/auth/login`, `/auth/refresh`, `/health`, and OAuth callback routes require a valid JWT. When `must_change_password=true`, ALL endpoints
> except `PATCH /auth/me/password` return `403 {"error":"password_change_required"}`.

### User management endpoints (superadmin only)

```
GET    /api/v1/users               # List all users (superadmin only)
POST   /api/v1/users               # Create user {username, password, role, email?}; password Argon2id-hashed before storage
GET    /api/v1/users/{id}          # Get user detail (superadmin only)
PATCH  /api/v1/users/{id}          # Update user: {is_active, role, must_change_password}; PATCH {is_active:false} on last active superadmin → 409
DELETE /api/v1/users/{id}          # Soft-delete user (sets is_active=false; revokes all refresh_tokens)
```

### Delegation endpoints (account owner)

```
GET    /api/v1/users/me/access         # List access grants I've given (owner view)
POST   /api/v1/users/me/access         # Grant access: {grantee_user_id, role} — viewer or admin; self-grant → 422
DELETE /api/v1/users/me/access/{id}    # Revoke a specific grant
```

### Data access scoping

> All data endpoints (accounts, transactions, balances, alarms, notifiers, provider connections, etc.)
> filter through `get_accessible_scope(current_user)`, which returns the set of `user_id` values
> the current user may query (own ID + all IDs they have been granted access to).
>
> **Superadmin users receive `403 {"error":"financial_data_forbidden"}` on any endpoint that
> returns financial figures.** The forbidden field list:
>
> - `balances.*` (entire resource)
> - `cards.display_name`, `.partial_card_number`, `.currency`, `.credit_limit`
> - `transactions.amount`, `.currency`, `.transaction_category`, `.description`, `.merchant_name`, `.merchant_category`, `.running_balance`, `.transaction_date`, `.settled_date`
> - `pending_transactions.amount`, `.currency`, `.description`, `.merchant_name`, `.transaction_date`
> - `direct_debits.name`, `.amount`, `.currency`, `.reference`, `.next_payment_amount`, `.last_payment_date`, `.next_payment_date`
> - `standing_orders.reference`, `.currency`, `.*_amount` (all four), `.*_date` (all four)
> - `recurrence_profiles.*` (entire resource — amounts, predicted dates, and merchant patterns are all sensitive)
> - `accounts.account_type`, `.currency`, `.display_name`, `.iban`, `.sort_code`, `.account_number`
> - `provider_connections.provider_type`, `.display_name`, `.credentials_encrypted`, `.config`
> - `alarm_definitions.name`, `.condition`
> - `alarm_definition_versions.condition`  -- condition tree at each version  [encrypted]
> - `alarm_evaluation_results.context_snapshot`, `.explanation`
> - `alarm_firing_events.condition_snapshot`, `.context_snapshot`, `.explanation`
> - `notifier_configs.name`, `.type`, `.config`
> - `notification_deliveries.rendered_subject`, `.rendered_body`, `.request_payload`, `.response_detail`
> - `events.payload`, `.explanation` (all event types — always encrypted under owner DEK)

### Provider endpoints

```
GET    /api/v1/providers                         # List registered provider types
GET    /api/v1/connections                       # List user's provider connections
POST   /api/v1/connections                       # Create new connection (initiate auth)
GET    /api/v1/connections/{id}                  # Connection detail + status
PATCH  /api/v1/connections/{id}                  # Update config
DELETE /api/v1/connections/{id}                  # Remove connection

GET    /api/v1/connections/{id}/auth-url         # Get OAuth URL (provider-specific)
GET    /api/v1/providers/{type}/callback         # OAuth callback handler
POST   /api/v1/connections/{id}/sync             # Trigger manual sync
GET    /api/v1/connections/{id}/sync-runs        # List sync run history
```

> **Naming rule**: `providers` refers to the adapter registry / provider types (`/api/v1/providers`, OAuth callback by provider type). `connections` refers to persisted user-owned connection resources (`/api/v1/connections/...`). Use these terms consistently in code, docs, and QA.

### Account and financial data endpoints

```
GET    /api/v1/accounts                          # List all accounts
# NOTE: The accounts list response includes a `current_balance` projected field derived from
# the most recent `balances` row for each account. It is NOT a column on the `accounts` table.
# For full balance history, use GET /api/v1/accounts/{id}/balances.
GET    /api/v1/accounts/{id}                     # Account detail
GET    /api/v1/accounts/{id}/balances            # Balance history (with ?from=&to=)
GET    /api/v1/accounts/{id}/transactions        # Transactions (paginated, filterable)
GET    /api/v1/accounts/{id}/pending             # Pending transactions
GET    /api/v1/accounts/{id}/direct-debits       # Direct debit mandates
GET    /api/v1/accounts/{id}/standing-orders     # Standing orders
GET    /api/v1/accounts/{id}/recurrence-profiles # Detected recurring patterns

GET    /api/v1/cards                             # List all cards
GET    /api/v1/cards/{id}                        # Card detail
GET    /api/v1/cards/{id}/balances               # Card balance history when provider supplies card-scoped balances
GET    /api/v1/cards/{id}/transactions           # Card-scoped transactions when provider supplies them
```

### Sync and events endpoints

```
GET    /api/v1/sync-runs                         # All sync runs (filterable)
GET    /api/v1/sync-runs/{id}                    # Sync run detail
GET    /api/v1/events                            # Event log (filterable by type, source, account)
GET    /api/v1/events/{id}
```

### Alarm endpoints

```
GET    /api/v1/alarms                            # List alarm definitions
POST   /api/v1/alarms                            # Create alarm
GET    /api/v1/alarms/{id}                       # Alarm detail + current state
PATCH  /api/v1/alarms/{id}                       # Update alarm
DELETE /api/v1/alarms/{id}                       # Archive alarm
POST   /api/v1/alarms/{id}/mute                  # Mute for duration
POST   /api/v1/alarms/{id}/unmute                # Clear mute
GET    /api/v1/alarms/{id}/history               # State transition history
GET    /api/v1/alarms/{id}/firings               # Firing events
POST   /api/v1/alarms/evaluate                   # Manually trigger evaluation (debug)
```

`POST /api/v1/alarms` and `PATCH /api/v1/alarms/{id}` MUST accept an explicit `account_ids: UUID[]` field (non-empty). The backend persists these bindings in `alarm_account_assignments`. Alarm evaluation is performed only against those linked accounts; there is no implicit "all accounts" default in v1.

### Notifier endpoints

```
GET    /api/v1/notifiers                         # List configured notifiers
POST   /api/v1/notifiers                         # Add notifier
GET    /api/v1/notifiers/{id}
PATCH  /api/v1/notifiers/{id}
DELETE /api/v1/notifiers/{id}
POST   /api/v1/notifiers/{id}/test               # Send test notification
GET    /api/v1/notifiers/{id}/deliveries         # Delivery history
```

### Dashboard summary endpoint

```
GET    /api/v1/dashboard/summary                 # Aggregated summary for dashboard
# Returns keys: accounts_total, active_alarms_count, last_sync_at, recent_events, upcoming_debits
```

### Recurrence profiles endpoint

```
GET    /api/v1/recurrence-profiles                    # List detected recurring transaction patterns
GET    /api/v1/recurrence-profiles/{id}               # Profile detail + next predicted occurrences
```

### Notification deliveries endpoint

```
GET    /api/v1/notification-deliveries                # List deliveries (filterable by ?alarm_id=, ?notifier_id=)
GET    /api/v1/notification-deliveries/{id}           # Delivery detail (status, attempts, error)
```

### Settings endpoint

```
GET    /api/v1/settings                               # Read-only operational metadata (app_version, scheduler_running, connection counts, notifier counts, etc.)
# NOTE: Settings are env-var-backed and read-only via API in v1. PATCH /settings is not supported.
# To change sync intervals or other cron config, update environment variables and restart.
```

### Admin job trigger endpoints

> Internal endpoints requiring standard JWT authentication (`Authorization: Bearer <token>`).
> The bearer token must belong to a user with `role == 'superadmin'` (checked via `require_superadmin()` dependency).
> Used in QA scenarios and integration tests to force-run background jobs without waiting for the scheduler cycle.

```
GET    /api/v1/admin/jobs                             # List available background jobs and their last-run status
POST   /api/v1/admin/jobs/detect-recurrence/trigger   # Force-run recurrence detection job immediately (asynchronous; returns 202 immediately, job runs in background)
POST   /api/v1/admin/jobs/evaluate-alarms/trigger     # Force-run alarm evaluation job immediately (asynchronous; returns 202 immediately, job runs in background)
```

### API response conventions

- All list endpoints support: `?page=1&page_size=50&sort_by=created_at&sort_dir=desc`
  > **Note on encrypted fields**: Columns annotated `[encrypted]` in §10 (e.g., `transaction_date`, `settled_date`, `amount`, `currency`, `description`, `merchant_name`, `transaction_category`) **cannot be sorted or filtered at the database level** — AES-GCM ciphertext has no meaningful sort order. `sort_by` and range-filter parameters that reference encrypted fields are applied at the **application layer** in Python after decryption. **For such requests, the operation order is: load scoped candidate set → decrypt → filter/sort in memory → paginate the final result.** `sort_by=created_at` and other plaintext columns are sorted in SQL as normal.
- All list responses: `{ "items": [...], "total": N, "page": N, "page_size": N }`
- All error responses: `{ "error": "error_code", "message": "...", "details": {...} }`
- Timestamps: ISO 8601 with timezone
- Monetary amounts: strings with currency code (e.g., `{ "amount": "285.00", "currency": "GBP" }`)
- Enum values: lowercase snake_case strings

---

## 12. Background Jobs and Sync Engine

### Task queue: Taskiq + Redis

Manifold uses **Taskiq** as its task queue with a **Redis Streams broker**. The API enqueues tasks; a dedicated `manifold-tasker` container runs four processes via **supervisord**: one Taskiq scheduler (fires periodic tasks) and three Taskiq workers (each consuming both queues). Redis is the shared broker and result backend.

```
manifold-api     →  calls .kiq()  →  Redis (manifold-redis)
                                          ↓
manifold-tasker (supervisord):
  ├── taskiq scheduler              →  fires periodic tasks → Redis
  ├── taskiq worker --queues manual,sync  ←  worker-1
  ├── taskiq worker --queues manual,sync  ←  worker-2
  └── taskiq worker --queues manual,sync  ←  worker-3
```

**Why two queues, three shared workers?**

- `sync`: bulk periodic work — cron syncs, alarm evaluation, recurrence detection, maintenance.
- `manual`: time-sensitive work — user-triggered syncs and alarm notification dispatch.

All three workers consume **both queues**, with `manual` listed first. Taskiq checks queues in declaration order, so each worker always drains `manual` before pulling `sync` work. Time-sensitive tasks are never starved by bulk cron work, and idle capacity is never wasted on an empty queue.

### Broker setup

```python
# manifold/tasks/broker.py
from taskiq import SmartRetryMiddleware
from taskiq_redis import RedisStreamBroker, RedisAsyncResultBackend
from manifold.config import settings

broker = (
    RedisStreamBroker(url=settings.redis_url)
    .with_result_backend(
        RedisAsyncResultBackend(
            redis_url=settings.redis_url,
            result_ex_time=settings.taskiq_result_ttl,
        )
    )
    .with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=3,
            use_jitter=True,
            use_delay_exponent=True,
        )
    )
)
```

### Periodic schedule

```python
# manifold/tasks/scheduler.py
from taskiq.scheduler import TaskiqScheduler
from taskiq.scheduler.schedulers import AsyncScheduler
from manifold.tasks.broker import broker

scheduler = TaskiqScheduler(broker=broker)
```

Schedules are declared inline on each task with `schedule=[...]` (see task definitions below).

### Task definitions

```python
# manifold/tasks/sync.py
from manifold.tasks.broker import broker
from manifold.config import settings

@broker.task(
    queue="sync",
    retry_on_error=True,
    schedule=[{"cron": settings.sync_cron}],  # default: "0 * * * *"
)
async def sync_all_connections() -> None:
    """Periodic: sync all active provider connections."""
    from manifold.domain.sync_engine import SyncEngine
    from manifold.database import db_session
    async with db_session() as session:
        engine = SyncEngine(session)
        # SyncEngine.sync_all_active() must use the same per-connection Redis lock contract
        # as manual sync: reserve `lock:sync:{connection_id}` before processing each connection,
        # skip already-locked connections, and release only locks acquired by that loop iteration.
        await engine.sync_all_active()

@broker.task(queue="manual", retry_on_error=True)
async def sync_connection(connection_id: str, sync_run_id: str | None = None) -> dict:
    """On-demand: sync a single connection, triggered by API or scheduler.
    If sync_run_id is provided, reuses the pre-created SyncRun row (created by the API
    before enqueueing so callers can poll status immediately).
    """
    from manifold.domain.sync_engine import SyncEngine
    from manifold.database import db_session

    lock_key = f"lock:sync:{connection_id}"
    try:
        async with db_session() as session:
            engine = SyncEngine(session)
            run = await engine.sync_connection_by_id(connection_id, existing_run_id=sync_run_id)
            return {"sync_run_id": str(run.id), "status": run.status}
    finally:
        await _release_lock(lock_key)
```

```python
# manifold/tasks/alarms.py
from manifold.tasks.broker import broker
from manifold.config import settings

@broker.task(
    queue="sync",
    retry_on_error=True,
    schedule=[{"cron": settings.alarm_eval_cron}],  # default: "*/5 * * * *"
)
async def evaluate_all_alarms() -> None:
    from manifold.domain.alarm_evaluator import AlarmEvaluatorService
    from manifold.database import db_session
    async with db_session() as session:
        evaluator = AlarmEvaluatorService(session)
        await evaluator.evaluate_all_active()
        # evaluate_all_active() enqueues dispatch_alarm_notifications tasks
        # for any state transitions — it does NOT call NotifierDispatcher directly.
```

```python
# manifold/tasks/notifications.py
from manifold.tasks.broker import broker

@broker.task(queue="manual", retry_on_error=True)
async def dispatch_alarm_notifications(alarm_firing_event_id: str) -> None:
    """
    Dispatches notifications for a single alarm firing event.
    Enqueued by evaluate_all_alarms when an alarm transitions to FIRING or RESOLVED.
    Runs on the 'manual' queue so it is prioritised over bulk cron work.
    NotifierDispatcher handles per-notifier retries with exponential backoff.
    """
    from manifold.notifiers.dispatcher import NotifierDispatcher
    from manifold.database import db_session
    async with db_session() as session:
        dispatcher = NotifierDispatcher(session)
        await dispatcher.dispatch_for_firing_event(alarm_firing_event_id)


@broker.task(queue="manual", retry_on_error=True)
async def dispatch_system_notification(
    notification_type: str,
    notifier_ids: list[str],
    owner_user_id: str,
    payload_dict: dict,
) -> None:
    """Send a non-alarm notification (system_event, informational, test).
    notification_type: 'system_event' | 'informational' | 'test'
    owner_user_id: used to resolve the owner DEK for encrypted notifier config fields.
    Enqueued manually (e.g. POST /notifiers/{id}/test, system health events).
    """
    from manifold.notifiers.dispatcher import NotifierDispatcher
    from manifold.notifiers.base import NotificationPayload
    from manifold.database import db_session
    async with db_session() as session:
        dispatcher = NotifierDispatcher(session)
        payload = NotificationPayload(**payload_dict)
        await dispatcher.dispatch_system_notification(
            notification_type=notification_type,
            notifier_ids=notifier_ids,
            owner_user_id=owner_user_id,
            payload=payload,
        )
```

```python
# manifold/tasks/maintenance.py
from manifold.tasks.broker import broker
from manifold.config import settings

@broker.task(
    queue="sync",
    schedule=[{"cron": settings.recurrence_detect_cron}],  # default: "0 3 * * *"
)
async def detect_recurrence() -> None: ...

@broker.task(
    queue="sync",
    schedule=[{"cron": settings.cleanup_cron}],  # default: "0 4 * * *"
)
async def run_data_retention_jobs() -> None: ...
# Responsibilities:
# - delete old pending transactions past retention window
# - compact old balance snapshots to one-per-day after 90 days
# - purge expired oauth_states rows
```

> **DEK iteration requirement for background jobs**: Any domain method called by these tasks that reads or writes encrypted fields (`EncryptedText`, `EncryptedJSON`, `EncryptedDecimal`) MUST iterate by owner user. For each user:
>
> 1. Load the user row and decrypt their DEK using the master key.
> 2. Set `_current_dek.set(plaintext_dek)` via ContextVar token.
> 3. Load and process that user's encrypted rows (the TypeDecorators decrypt transparently).
> 4. Reset the ContextVar via `token`.
>
> **Affected methods**: `SyncEngine.sync_all_active()` (iterates connections by user), `SyncEngine.sync_connection_by_id()` / `SyncEngine.sync_connection()` (single-connection sync — resolves user from `connection.user_id`; DEK must be set before `sync_connection()` is called, whether invoked directly or via `sync_connection_by_id()`), `AlarmEvaluatorService.evaluate_all_active()` (iterates alarms by user), `detect_recurrence` (iterates recurrence profiles by user), `NotifierDispatcher.dispatch_for_firing_event()` (resolves user via alarm → alarm_definition). Failure to set the DEK ContextVar before accessing encrypted columns will raise `RuntimeError("No encryption context set")`.

### DB concurrency safety

With the API running `--workers 2` and three Taskiq workers, five processes share the database. The engine creation is backend-aware: SQLite uses `NullPool` (serialized file I/O, no pool overhead), while PostgreSQL and MariaDB use `QueuePool` with pre-ping and bounded pool sizes to prevent exhaustion.

**Backend-aware engine factory** (`manifold/database/__init__.py`):

```python
# manifold/database/__init__.py  (simplified illustration; §10a documents the full package layout)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from sqlalchemy.pool import NullPool, StaticPool
from manifold.config import settings

def _make_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        # SQLite: no connection pool — serialized file I/O
        # Use StaticPool for :memory: (tests), NullPool for file-based URLs
        poolclass = StaticPool if ":memory:" in url else NullPool
        engine = create_async_engine(
            url,
            poolclass=poolclass,
            connect_args={"check_same_thread": False},
        )
        @event.listens_for(engine.sync_engine, "connect")
        def _on_connect(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")    # concurrent readers
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")  # safe + fast
            dbapi_conn.execute("PRAGMA foreign_keys=ON")     # enforce FK constraints
    else:
        # PostgreSQL / MariaDB: bounded pool with stale-connection detection
        engine = create_async_engine(
            url,
            pool_size=settings.db_pool_size,            # default: 3
            max_overflow=settings.db_pool_max_overflow,  # default: 2
            pool_timeout=settings.db_pool_timeout,       # default: 30s
            pool_pre_ping=True,                          # detect stale connections
        )
    return engine

engine = _make_engine()
# PostgreSQL / MariaDB: max total = (api_workers × 5) + (taskiq_workers × 5)
# Default: (2 × 5) + (3 × 5) = 25 connections — well under PG max_connections=100
# SQLite: serialized via NullPool — no connection limit applies
```

**Distributed lock** (prevents duplicate concurrent syncs for the same connection):

```python
# manifold/tasks/_locks.py
import redis.asyncio as aioredis
from manifold.config import settings

_redis: aioredis.Redis | None = None

async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(settings.redis_url)
    return _redis

async def _acquire_lock(key: str, ttl: int = 600) -> bool:
    r = await _get_redis()
    return await r.set(key, "1", nx=True, ex=ttl)

async def _release_lock(key: str) -> None:
    r = await _get_redis()
    await r.delete(key)
```

**Duplicate task prevention** (reserve lock before enqueuing from API routes):

```python
# manifold/api/sync.py
@router.post("/connections/{id}/sync", status_code=202)
async def trigger_sync(id: str, session: AsyncSession = Depends(get_session)):
    lock_key = f"lock:sync:{id}"
    acquired = await _acquire_lock(lock_key, ttl=600)
    if not acquired:
        raise HTTPException(409, detail="Sync already in flight for this connection")
    try:
        # Create SyncRun row before enqueueing so callers can poll its status immediately
        run = SyncRun(provider_connection_id=id, status="queued")
        session.add(run)
        await session.commit()
        await sync_connection.kiq(connection_id=id, sync_run_id=str(run.id))
        return {"sync_run_id": str(run.id), "status": "queued"}
    except Exception:
        await _release_lock(lock_key)
        raise
```

### supervisord configuration

```ini
# backend/supervisord.conf
[supervisord]
nodaemon=true
logfile=/dev/stdout
logfile_maxbytes=0

[program:worker-1]
command=taskiq worker manifold.tasks.broker:broker --queues manual,sync
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:worker-2]
command=taskiq worker manifold.tasks.broker:broker --queues manual,sync
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:worker-3]
command=taskiq worker manifold.tasks.broker:broker --queues manual,sync
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:scheduler]
command=taskiq scheduler manifold.tasks.scheduler:scheduler
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
```

### Stale SyncRun recovery

On worker startup (lifespan startup in the worker process), before accepting tasks:

```python
# Portable stale SyncRun recovery — runs on worker startup via lifespan hook
from datetime import datetime, timezone, timedelta
from sqlalchemy import update as sa_update

stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
await session.execute(
    sa_update(SyncRun)
    .where(SyncRun.status == "running", SyncRun.started_at < stale_cutoff)
    .values(status="failed", error_code="interrupted", completed_at=datetime.now(timezone.utc))
)
await session.commit()
```

This ensures a crash mid-sync does not leave perpetually-`running` records in the UI.

### Testing

In tests, swap the real broker for an in-memory broker — tasks execute synchronously inline, no Redis needed:

```python
# backend/tests/conftest.py
from taskiq import InMemoryBroker
from manifold.tasks.broker import broker

@pytest.fixture(autouse=True)
def use_in_memory_broker():
    broker._broker = InMemoryBroker()
    broker.is_worker_process = True
    yield
    broker.is_worker_process = False
```

### Sync job architecture

The `sync_all_connections` job:

1. Loads all `ProviderConnection` records with `status=active`
2. For each connection, calls `SyncEngine.sync_connection(connection)`
3. `SyncEngine` creates or adopts a `SyncRun` record, calls provider adapter, normalizes data, upserts records
4. Generates `Event` records for notable changes (new transaction, balance change, direct debit detected)
5. Updates `SyncRun` and the owning `ProviderConnection` (`status`, `auth_status`, `last_sync_at`) with final outcome

```python
# manifold/domain/sync_engine.py
class SyncEngine:
    async def sync_connection(self, connection: ProviderConnection, existing_run_id: str | None = None) -> SyncRun:
        if existing_run_id:
            # Load the pre-created queued row and transition it to running
            run = await self._session.get(SyncRun, existing_run_id)
            run.status = "running"
            run.started_at = utcnow()
            await save(run)
        else:
            run = SyncRun(provider_connection_id=connection.id, status="running", started_at=utcnow())
            await save(run)
        try:
            provider = registry.get(connection.provider_type)
            await provider.refresh_if_needed(connection)
            accounts = await provider.get_accounts(connection)
            await self._upsert_accounts(accounts, connection)
            for account in accounts:
                await self._sync_account(provider, connection, account, run)
            run.status = "success"
            connection.status = "active"
            connection.auth_status = "connected"
            connection.last_sync_at = utcnow()
        except ProviderAuthError as e:
            run.status = "failed"
            run.error_code = "auth_error"
            run.error_detail = {"message": str(e)}
            connection.status = "error"
            connection.auth_status = "refresh_failed"
            await self._generate_auth_failure_event(connection, e)
        except Exception as e:
            run.status = "failed"
            run.error_code = "unknown"
            run.error_detail = {"message": str(e)}
            connection.status = "error"
        finally:
            run.completed_at = utcnow()
            await save(connection)
            await save(run)
        return run

    async def sync_connection_by_id(self, connection_id: str, existing_run_id: str | None = None) -> SyncRun:
        connection = await self._session.get(ProviderConnection, connection_id)
        return await self.sync_connection(connection, existing_run_id=existing_run_id)
```

### Recurrence detection algorithm

The recurrence detector runs daily and:

1. Groups transactions by `(account_id, merchant_name_normalized)` over a 90-day window
2. Filters groups with ≥3 occurrences
3. Computes inter-arrival times (days between consecutive transactions in the group)
4. If mean inter-arrival is within common cadence bands (7, 14, 28-31, 90, 365 ± 20%) and coefficient of variation < 0.15, marks as recurring
5. Computes `confidence` score based on: count, CV of inter-arrival, amount consistency
6. Creates or updates `RecurrenceProfile`
7. Sets `next_predicted_at` = last occurrence + mean cadence
8. Generates `Event(event_type="debit_predicted", source_type="predicted")` for near-term predictions (within 7 days)

### Alarm evaluation job

The `evaluate_all_alarms` job:

1. Loads all `AlarmDefinition` records with `status=active`
2. For each alarm, builds an evaluation context from current DB state
3. Calls `AlarmEvaluator.evaluate(alarm.condition, context)`
4. Determines new state based on result + current state + `repeat_count` config
5. Saves `AlarmEvaluationResult` and updates `AlarmState`
6. If state transition triggers notification, calls `dispatch_alarm_notifications.kiq(alarm_firing_event_id)` — enqueues onto the `manual` queue and returns immediately

The evaluation job never makes HTTP calls. It is a fast read-evaluate-write-enqueue loop.

### Idempotency

All sync operations use upsert semantics (`INSERT ... ON CONFLICT DO UPDATE`). Re-running a sync for the same date range produces no duplicate records. `SyncRun` records are always created to maintain a full audit log of sync attempts.

---

## 13. Notification and Alerting Architecture

### Notification lifecycle

```
Financial event occurs (sync completes, alarm evaluates)
       ↓
AlarmEvaluator produces evaluation result
       ↓
State machine determines state transition
       ↓
AlarmEvaluationResult + AlarmState saved to DB
       ↓
IF state transition requires notification:
    dispatch_alarm_notifications.kiq(alarm_firing_event_id)
    → enqueued on "manual" queue; evaluate_all_alarms returns immediately
       ↓ (picked up by next available worker, typically within seconds)
dispatch_alarm_notifications task:
    For each notifier_id in alarm.notifier_assignments (resolved from alarm_notifier_assignments join table):
        NotificationDelivery record created (status=pending)
            ↓
        NotifierDispatcher.dispatch(payload, config)
            ↓
        Notifier.send() called (with retry up to MAX_ATTEMPTS)
            ↓
        NotificationDelivery updated (status=delivered|failed)
```

### Notification triggers

| Trigger          | Condition                                        | Default behavior                                           |
| ---------------- | ------------------------------------------------ | ---------------------------------------------------------- |
| Alarm fires      | State → FIRING                                   | Notify via all linked notifiers                            |
| Alarm resolves   | State → RESOLVED                                 | Optional when `alarm_definitions.notify_on_resolve = true` |
| Sync failure     | SyncRun.status = failed                          | System notifier (if configured)                            |
| Auth failure     | ProviderConnection.auth_status = refresh_failed  | System notifier                                            |
| Consent expiring | consent_expires_at within 7 days                 | System notifier                                            |
| Predicted debit  | RecurrenceProfile generates near-term prediction | Informational notifier                                     |

### System notifier

A "system notifier" is a special notifier designated to receive system-level events (sync failures, auth failures, consent expiry) regardless of alarm routing. It is configured in Settings:

```bash
SYSTEM_NOTIFIER_ID=uuid-of-configured-notifier
```

`SYSTEM_NOTIFIER_ID` **must point to a valid `notifier_configs` row owned by a real user** (typically the first-run admin). It is not a global non-user-owned entity; it is simply a user-created notifier that the system uses for platform events. For system-event dispatch, the notifier config is always decrypted using the **notifier owner's** DEK (the owner of `SYSTEM_NOTIFIER_ID`). The `notification_deliveries.user_id` field, however, is set to the user who owns the **affected resource** (e.g., the owner of the failing connection). This deliberately separates **config ownership/decryption** from **event ownership/audit visibility**.

---

## 14. Docker and Local Development Strategy

### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Install uv
RUN pip install uv

# Copy full source (needed so uv can install the local package itself)
COPY . .

# Install dependencies (including local package and all optional DB drivers)
# all-backends extra installs asyncpg (PostgreSQL) and asyncmy (MariaDB) in addition to core deps.
# SQLite requires no extra driver; it is always available.
RUN uv sync --frozen --no-dev --extra all-backends

FROM python:3.12-slim AS final
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Install uv in final image (needed for manifold CLI commands e.g. alembic, manifold)
RUN pip install uv

# Install supervisor (required by manifold-tasker container to manage worker + scheduler processes)
RUN apt-get update && apt-get install -y --no-install-recommends supervisor && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -u 1000 manifold
USER manifold

# Copy installed venv and source from builder
COPY --from=builder --chown=manifold:manifold /app/.venv /app/.venv
COPY --chown=manifold:manifold . /app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "manifold.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:alpine AS final
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**`frontend/nginx.conf`**:

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # React SPA: all unknown paths → index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy /api to backend (Docker Compose network)
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Root docker-compose.yml

```yaml
# docker-compose.yml
services:
  https-proxy:
    image: nginx:alpine
    profiles: ["https"]
    ports:
      - "3443:443"
    depends_on:
      frontend:
        condition: service_started
      backend:
        condition: service_healthy
    volumes:
      - ./ops/https/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - manifold-certs:/etc/nginx/certs
    command: >-
      /bin/sh -c '
      if [ ! -f /etc/nginx/certs/manifold.crt ] || [ ! -f /etc/nginx/certs/manifold.key ]; then
        apk add --no-cache openssl >/dev/null 2>&1 &&
        openssl req -x509 -nodes -newkey rsa:2048 -days 365
          -keyout /etc/nginx/certs/manifold.key
          -out /etc/nginx/certs/manifold.crt
          -subj "/CN=localhost";
      fi &&
      nginx -g "daemon off;"'
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: /api
    ports:
      - "3000:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  migrate:
    build:
      context: ./backend
    command: ["uv", "run", "alembic", "upgrade", "head"]
    env_file:
      - .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
    volumes:
      - manifold-data:/app/data
    restart: "no"

  backend:
    build:
      context: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - REDIS_URL=redis://manifold-redis:6379/0
    depends_on:
      manifold-redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    volumes:
      - manifold-data:/app/data  # SQLite database file; shared with manifold-tasker
    extra_hosts:
      - "host.docker.internal:host-gateway"  # Linux host resolution; macOS/Windows Docker Desktop resolves this automatically
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    restart: unless-stopped

  manifold-tasker:
    build:
      context: ./backend
    # supervisord starts: worker-1, worker-2, worker-3 (all --queues manual,sync), scheduler
    command: ["supervisord", "-c", "/app/supervisord.conf"]
    env_file:
      - .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - REDIS_URL=redis://manifold-redis:6379/0
    depends_on:
      manifold-redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    volumes:
      - manifold-data:/app/data  # SQLite database file; shared with backend
    extra_hosts:
      - "host.docker.internal:host-gateway"  # Linux host resolution; macOS/Windows Docker Desktop resolves this automatically
    restart: unless-stopped

  manifold-redis:
    image: redis:7-alpine
    command: redis-server --save "" --appendonly no  # no persistence needed — queue is ephemeral
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped

volumes:
  manifold-data:  # Persistent named volume for SQLite database; shared between backend and manifold-tasker
  manifold-certs:  # Self-signed TLS cert/key for optional HTTPS reverse proxy
  # For PostgreSQL or MariaDB: set DATABASE_URL to an external host; manifold-data is unused.
```

**Optional HTTPS termination container**:

- Enabled with `docker compose --profile https up`
- Generates a self-signed certificate on first start into the `manifold-certs` volume
- Terminates TLS and reverse-proxies:
  - `/` → `frontend:80`
  - `/api` → `backend:8000`
- Intended for local/self-hosted HTTPS testing; production deployments may replace the self-signed cert flow with managed certificates while keeping the same reverse-proxy shape.

**`ops/https/nginx.conf`**:

```nginx
server {
    listen 443 ssl;
    server_name localhost;

    ssl_certificate     /etc/nginx/certs/manifold.crt;
    ssl_certificate_key /etc/nginx/certs/manifold.key;

    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Development override** — `docker-compose.dev.yml`:

```yaml
services:
  backend:
    build:
      context: ./backend
      target: builder  # Stop at builder stage for dev
    volumes:
      - ./backend:/app  # Live reload via bind mount
      - venv-data:/app/.venv  # Named volume so bind mount doesn't shadow the installed venv
    command: uv run uvicorn manifold.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      - APP_ENV=development
      - REDIS_URL=redis://manifold-redis:6379/0

  manifold-tasker:
    build:
      context: ./backend
      target: builder
    volumes:
      - ./backend:/app
      - venv-data:/app/.venv  # Named volume so bind mount doesn't shadow the installed venv
    # Run both workers + scheduler in one command for dev convenience
    command: >
      sh -c "uv run taskiq worker manifold.tasks.broker:broker --queues manual,sync &
               uv run taskiq worker manifold.tasks.broker:broker --queues manual,sync &
               uv run taskiq worker manifold.tasks.broker:broker --queues manual,sync &
               uv run taskiq scheduler manifold.tasks.scheduler:scheduler &
               wait"
    environment:
      - APP_ENV=development
      - REDIS_URL=redis://manifold-redis:6379/0

  frontend:
    build: ./frontend
    volumes:
      - ./frontend:/app
      - /app/node_modules  # Exclude node_modules from bind mount
    command: npm run dev -- --host 0.0.0.0
    ports:
      - "5173:5173"

  mailpit:
    image: axllent/mailpit:latest
    ports:
      - "1025:1025"   # SMTP — set SMTP_HOST=localhost SMTP_PORT=1025 in dev .env
      - "8025:8025"   # Web UI — verify email delivery at http://localhost:8025
    restart: unless-stopped

volumes:
  venv-data:
```

Run with: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`

### Local development without Docker

See Makefile section. Requires:

- Python 3.12, uv
- Node 20+, npm
- Redis 7+ running locally (`redis-server`)
- SQLite is sufficient for local dev (default `DATABASE_URL`); PostgreSQL or MariaDB are optional for testing those backends

**Optional backend extras (install before using non-SQLite backends):**

```bash
# PostgreSQL support
uv sync --extra postgresql

# MariaDB support
uv sync --extra mariadb

# All backends (matches Docker image)
uv sync --extra all-backends
```

Backend API: `cd backend && uv run uvicorn manifold.main:app --reload`
Worker 1: `cd backend && uv run taskiq worker manifold.tasks.broker:broker --queues manual,sync`
Worker 2: `cd backend && uv run taskiq worker manifold.tasks.broker:broker --queues manual,sync`
Worker 3: `cd backend && uv run taskiq worker manifold.tasks.broker:broker --queues manual,sync`
Scheduler: `cd backend && uv run taskiq scheduler manifold.tasks.scheduler:scheduler`
Frontend: `cd frontend && npm run dev`

---

## 15. Makefile Strategy

```makefile
# Manifold root Makefile

.PHONY: help setup install dev build test lint format clean docker-up docker-down ci-check

# ──────────────────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────────────────
help:
 @echo "Manifold development targets:"
 @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
  awk 'BEGIN {FS = ":.*?## "}; {printf "  %-25s %s\n", $$1, $$2}'

# ──────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────
setup: install-backend install-frontend ## Install all dependencies
 @cp -n .env.example .env || true
 @cp -n backend/.env.example backend/.env || true
 @echo "✓ Setup complete. Edit .env and backend/.env before starting."

install-backend: ## Install backend dependencies (uv)
 cd backend && uv sync

install-frontend: ## Install frontend dependencies (npm)
 cd frontend && npm ci

# ──────────────────────────────────────────────────────────
# Development servers
# ──────────────────────────────────────────────────────────
dev-backend: ## Start backend dev server (hot reload)
 cd backend && uv run uvicorn manifold.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend dev server
 cd frontend && npm run dev

dev: ## Start all services (requires tmux or parallel; shows combined log)
 @echo "Run in separate terminals: make dev-backend / make dev-frontend"
 @echo "Or: docker compose -f docker-compose.yml -f docker-compose.dev.yml up"

# ──────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────
db-migrate: ## Run Alembic migrations
 cd backend && uv run alembic upgrade head

db-revision: ## Create a new Alembic migration revision
 cd backend && uv run alembic revision --autogenerate -m "$(MSG)"

db-downgrade: ## Rollback one migration
 cd backend && uv run alembic downgrade -1

# ──────────────────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────────────────
test-backend: ## Run backend tests
 cd backend && uv run pytest tests/ -v

test-frontend: ## Run frontend tests
 cd frontend && npm run test

test: test-backend test-frontend ## Run all tests

test-cov: ## Backend tests with coverage report
 cd backend && uv run pytest tests/ --cov=manifold --cov-report=html

ci-check: lint typecheck-backend typecheck-frontend test ## Full CI gate: lint + type-check + tests (mirrors GitHub Actions pipelines)

# ──────────────────────────────────────────────────────────
# Linting
# ──────────────────────────────────────────────────────────
lint-backend: ## Lint backend (ruff)
 cd backend && uv run ruff check manifold/ tests/

lint-frontend: ## Lint frontend (eslint)
 cd frontend && npm run lint

lint: lint-backend lint-frontend ## Lint everything

# ──────────────────────────────────────────────────────────
# Formatting
# ──────────────────────────────────────────────────────────
format-backend: ## Format backend (ruff format)
 cd backend && uv run ruff format manifold/ tests/

format-frontend: ## Format frontend (prettier)
 cd frontend && npm run format

format: format-backend format-frontend ## Format everything

# ──────────────────────────────────────────────────────────
# Type checking
# ──────────────────────────────────────────────────────────
typecheck-backend: ## Type check backend (mypy)
 cd backend && uv run mypy manifold/

typecheck-frontend: ## Type check frontend (tsc)
 cd frontend && npm run typecheck

# ──────────────────────────────────────────────────────────
# Build
# ──────────────────────────────────────────────────────────
build-frontend: ## Build frontend for production
 cd frontend && npm run build

build-backend: ## Build backend wheel/sdist
 cd backend && uv build

build: build-frontend build-backend ## Build everything

# ──────────────────────────────────────────────────────────
# Docker
# ──────────────────────────────────────────────────────────
docker-build: ## Build Docker images
 docker compose build

docker-up: ## Start Docker Compose stack
 docker compose up -d

docker-up-dev: ## Start Docker Compose dev stack
 docker compose -f docker-compose.yml -f docker-compose.dev.yml up

docker-down: ## Stop Docker Compose stack
 docker compose down

docker-logs: ## Follow Docker Compose logs
 docker compose logs -f

# ──────────────────────────────────────────────────────────
# Release helpers
# ──────────────────────────────────────────────────────────
release-dry-run: ## Preview release changes (requires git tags)
 @echo "Current version: $$(git describe --tags --abbrev=0 2>/dev/null || echo 'no tags')"
 @echo "Commits since last tag:"
 @git log $$(git describe --tags --abbrev=0 2>/dev/null)..HEAD --oneline 2>/dev/null || git log --oneline -10

# ──────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────
clean: ## Remove build artifacts
 rm -rf backend/dist/ backend/.venv/ backend/htmlcov/
 rm -rf frontend/dist/ frontend/node_modules/
 find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
 find . -name "*.pyc" -delete 2>/dev/null || true
```

---

## 16. Environment Variable Strategy

### Root `.env.example` (for Docker Compose)

```bash
# ──────────────────────────────────────────────────────────
# Manifold — Environment Configuration
# Copy to .env and fill in values before starting
# ──────────────────────────────────────────────────────────

# ── Application ──────────────────────────────────────────
APP_ENV=development                 # development | production
SECRET_KEY=replace-with-64-char-random-string  # openssl rand -hex 32
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
TIMEZONE=UTC                        # IANA timezone, e.g. Europe/London

# ── First-run bootstrap ──────────────────────────────────
# Required ONLY when the users table is empty (fresh database).
# On first startup, a superadmin is created from these values.
# ADMIN_PASSWORD is plaintext here; it is Argon2id-hashed before storage.
# must_change_password is set to true — the user is forced to change on first login.
# After the first login + password change, these vars can be removed from .env.
ADMIN_USERNAME=admin
ADMIN_PASSWORD=                     # temporary plaintext; Argon2id-hashed immediately on seed
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Database (user-managed; SQLite by default) ───────────
# SQLite (default — zero-ops, file-based; data persisted in Docker volume):
DATABASE_URL=sqlite+aiosqlite:///data/manifold.db
# PostgreSQL (production, high concurrency):
# DATABASE_URL=postgresql+asyncpg://manifold:password@host:5432/manifold
# MariaDB (existing MariaDB setup):
# DATABASE_URL=mysql+asyncmy://manifold:password@host:3306/manifold

# ── Background job schedules (cron, UTC) ─────────────────
SYNC_CRON=0 * * * *                 # hourly sync of all connections
ALARM_EVAL_CRON=*/5 * * * *         # alarm evaluation every 5 minutes
RECURRENCE_DETECT_CRON=0 3 * * *    # recurrence detection at 3 AM daily
CLEANUP_CRON=0 4 * * *              # pending transaction cleanup at 4 AM daily

# ── Redis (Taskiq broker + distributed locks) ─────────────
REDIS_URL=redis://manifold-redis:6379/0
TASKIQ_RESULT_TTL=3600              # seconds to keep task results in Redis

# ── DB connection pool (PostgreSQL / MariaDB only) ───────
DB_POOL_SIZE=3                      # connections per process (api workers + task workers)
DB_POOL_MAX_OVERFLOW=2              # burst headroom per process
# SQLite uses NullPool — pool settings do not apply to SQLite
# Max total (PG/MariaDB): (api_workers × (pool_size + max_overflow)) + (task_workers × same)
# Default (2 API + 3 task workers): (2×5) + (3×5) = 25 — well under PG max_connections=100

# ── Logging ──────────────────────────────────────────────
LOG_LEVEL=INFO                      # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json                     # json | text (use 'text' for local dev)

# ── TrueLayer provider ───────────────────────────────────
TRUELAYER_CLIENT_ID=
TRUELAYER_CLIENT_SECRET=
TRUELAYER_REDIRECT_URI=https://localhost:3443/api/v1/providers/truelayer/callback
TRUELAYER_SANDBOX=true             # true for TrueLayer sandbox environment

# ── JSON provider ────────────────────────────────────────
# JSON provider configuration is per-connection (stored in DB).
# The API key value can reference an env var name instead of a literal value:
JSON_PROVIDER_API_KEY=              # Referenced by provider config as header_value_env

# ── System notifier ──────────────────────────────────────
SYSTEM_NOTIFIER_ID=                 # UUID of the notifier to receive system events

# ── Email notifier (SMTP) ────────────────────────────────
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_ADDRESS=manifold@example.com
SMTP_USE_TLS=true

# ── Slack notifier ───────────────────────────────────────
SLACK_WEBHOOK_URL=                  # Slack Incoming Webhook URL

# ── Telegram notifier ────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── WhatsApp notifier (Twilio) — v2 only ─────────────────
# TWILIO_ACCOUNT_SID=
# TWILIO_AUTH_TOKEN=
# TWILIO_WHATSAPP_FROM=

# ── CORS / Frontend ──────────────────────────────────────
FRONTEND_URL=http://localhost:3000
```

### Frontend `.env.example`

```bash
# frontend/.env.example
VITE_API_BASE_URL=
VITE_APP_ENV=development
```

### Backend `.env.example`

```bash
# backend/.env.example
# Same vars as root .env.example — backend-specific copy for non-Docker development
# Non-Docker setup copies this to backend/.env because local backend commands run from ./backend
# and Settings loads .env from the current working directory.
APP_ENV=development
SECRET_KEY=dev-secret-key-not-for-production
DATABASE_URL=sqlite+aiosqlite:///data/manifold.db
LOG_LEVEL=DEBUG
LOG_FORMAT=text
...
```

---

## 17. GitHub Actions / CI-CD Strategy

### Workflow files

```
.github/workflows/
├── frontend-ci.yml     # Lint, type check, test, build — triggered on frontend/** changes
├── backend-ci.yml      # Lint, type check, test — triggered on backend/** changes
├── docker-build.yml    # Build Docker images — on PRs and main push
└── release.yml         # Full release pipeline — on version tags
```

### `frontend-ci.yml`

```yaml
name: Frontend CI
on:
  push:
    paths: ["frontend/**", ".github/workflows/frontend-ci.yml"]
  pull_request:
    paths: ["frontend/**"]

jobs:
  ci:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run typecheck
      - run: npm run lint
      - run: npm run test -- --run
      - run: npm run build
        env:
          VITE_API_BASE_URL: /api  # Use /api path prefix; never set to http://localhost:8000 (breaks cookie auth)
      - uses: actions/upload-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist/
```

### `backend-ci.yml`

```yaml
name: Backend CI
on:
  push:
    paths: ["backend/**", ".github/workflows/backend-ci.yml"]
  pull_request:
    paths: ["backend/**"]

jobs:
  ci:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: manifold_test
          POSTGRES_USER: manifold
          POSTGRES_PASSWORD: manifold
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      mariadb:
        image: mariadb:11
        env:
          MARIADB_DATABASE: manifold_test
          MARIADB_USER: manifold
          MARIADB_PASSWORD: manifold
          MARIADB_ROOT_PASSWORD: rootpass
        ports:
          - 3306:3306
        options: >-
          --health-cmd "mariadb-admin ping -h 127.0.0.1 -uroot -prootpass"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 10
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
      - run: uv sync --extra all-backends
      - run: uv run alembic upgrade head
        env:
          DATABASE_URL: sqlite+aiosqlite:///:memory:
          SECRET_KEY: test-secret-key
          APP_ENV: test
      - run: uv run alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://manifold:manifold@localhost:5432/manifold_test
          SECRET_KEY: test-secret-key
          APP_ENV: test
      - run: uv run alembic upgrade head
        env:
          DATABASE_URL: mysql+asyncmy://manifold:manifold@127.0.0.1:3306/manifold_test
          SECRET_KEY: test-secret-key
          APP_ENV: test
      - run: uv run ruff check manifold/ tests/
      - run: uv run ruff format --check manifold/ tests/
      - run: uv run mypy manifold/
      - run: uv run pytest tests/ -v --tb=short
        env:
          DATABASE_URL: sqlite+aiosqlite:///:memory:
          SECRET_KEY: test-secret-key
          APP_ENV: test
      - run: uv run pytest tests/ -v --tb=short
        env:
          DATABASE_URL: postgresql+asyncpg://manifold:manifold@localhost:5432/manifold_test
          SECRET_KEY: test-secret-key
          APP_ENV: test
      - run: uv run pytest tests/ -v --tb=short
        env:
          DATABASE_URL: mysql+asyncmy://manifold:manifold@127.0.0.1:3306/manifold_test
          SECRET_KEY: test-secret-key
          APP_ENV: test
```

### `docker-build.yml`

```yaml
name: Docker Build
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: false
          cache-from: type=gha
          cache-to: type=gha,mode=max
          tags: ghcr.io/${{ github.repository }}/backend:${{ github.sha }}

  build-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: false
          build-args: |
            VITE_API_BASE_URL=/api
          cache-from: type=gha
          cache-to: type=gha,mode=max
          tags: ghcr.io/${{ github.repository }}/frontend:${{ github.sha }}
```

### `release.yml`

```yaml
name: Release
on:
  push:
    tags:
      - "v*.*.*"

permissions:
  contents: write
  packages: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Extract version
        id: version
        run: echo "version=${GITHUB_REF_NAME#v}" >> $GITHUB_OUTPUT

      # ── Build frontend ────────────────────────────────────────────
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
        env:
          VITE_API_BASE_URL: /api
      - run: |
          cd frontend && tar -czf ../manifold-frontend-${{ steps.version.outputs.version }}.tar.gz dist/

      # ── Build backend wheel ───────────────────────────────────────
      - uses: astral-sh/setup-uv@v3
      - run: uv build
        working-directory: backend
        env:
          SETUPTOOLS_SCM_PRETEND_VERSION: ${{ steps.version.outputs.version }}
      - run: |
          mv backend/dist/manifold-*.whl ./manifold-backend-${{ steps.version.outputs.version }}.whl

      # ── Build and push Docker images ──────────────────────────────
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/backend:${{ github.ref_name }}
            ghcr.io/${{ github.repository }}/backend:latest

      - uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          build-args: VITE_API_BASE_URL=/api
          tags: |
            ghcr.io/${{ github.repository }}/frontend:${{ github.ref_name }}
            ghcr.io/${{ github.repository }}/frontend:latest

      # ── Create GitHub Release ─────────────────────────────────────
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            manifold-frontend-${{ steps.version.outputs.version }}.tar.gz
            manifold-backend-${{ steps.version.outputs.version }}.whl
          generate_release_notes: true
          body: |
            ## Docker images
            ```
            docker pull ghcr.io/${{ github.repository }}/backend:${{ github.ref_name }}
            docker pull ghcr.io/${{ github.repository }}/frontend:${{ github.ref_name }}
            ```
```

### Versioning strategy

- Git tags: `v1.0.0`, `v1.1.0`, `v2.0.0` (semver)
- Backend: `setuptools-scm` reads the tag and injects version at build time via `pyproject.toml`:

  ```toml
  [tool.setuptools_scm]
  ```

- Frontend: version in `package.json` is updated as part of the release process (or derived from `GITHUB_REF_NAME` at build time)
- Release branches: tags are created from `main`; no separate release branches in v1

---

## 18. Security Considerations

### Secret management

- **No secrets in code or Docker images**. All secrets via environment variables / `.env` files.
- `.env` files are `.gitignore`'d. Only `.env.example` is committed.
- `SECRET_KEY` derives two independent keys via HKDF-SHA256 with distinct `info` labels:
  - JWT signing key: `HKDF(SECRET_KEY, info=b"manifold-jwt-signing", length=32)`
  - Master encryption key for per-user DEKs: `HKDF(SECRET_KEY, info=b"manifold-dek-master", length=32)`
  - The raw `SECRET_KEY` is never used directly for signing or encryption
- Never log access tokens, refresh tokens, or credential values at any log level

### Encryption at rest

All financial data and sensitive configuration/credential fields are encrypted at the database level using
AES-256-GCM (authenticated encryption via Python `cryptography` library). Encrypted columns are annotated
`[encrypted]` in §10. Login identifiers (`username`, `email`) used for lookup and uniqueness enforcement
remain in plaintext in v1; encrypting lookup columns would require HMAC-blind-index schemes outside scope.
Operational metadata (UUIDs, status fields, timestamps, counts) is stored in plaintext.

**Scheme**:

- **Master key**: Derived from `SECRET_KEY` env var using HKDF-SHA256. The raw `SECRET_KEY` is never used
  directly for data encryption.
- **Per-user Data Encryption Key (DEK)**: Each `users` row contains an `encrypted_dek LargeBinary NOT NULL`
  column — a randomly generated 32-byte key, encrypted under the master key. One compromised user's DEK
  does not expose other users' data.
- **DEK access pattern**: When a service function reads/writes encrypted fields it: (1) loads the user row,
  (2) decrypts the DEK in-memory using the master key, (3) sets a `contextvars.ContextVar` (`_current_dek`)
  to the plaintext DEK, (4) performs the ORM operation, (5) resets the ContextVar via token. The DEK is
  never cached or persisted in decrypted form. For multi-user delegation queries (where one request reads
  rows owned by multiple users), the service iterates per-owner: set DEK → fetch + decrypt rows → reset DEK.
  Background jobs (sync, alarm evaluation, notification dispatch) iterate users explicitly: for each user,
  set the ContextVar to that user's DEK before processing their rows.
- **ORM integration**: SQLAlchemy `TypeDecorator` subclasses (`EncryptedText`, `EncryptedJSON`,
  `EncryptedDecimal`) handle field-level encryption transparently. `process_bind_param` reads the active DEK
  from the ContextVar to encrypt; `process_result_value` reads it to decrypt. If no DEK is set and the
  ContextVar is `None`, the TypeDecorators raise `RuntimeError("No encryption context set")` as a
  programming-error guard. Application code reads/writes plain Python values; the ORM layer handles
  AES-256-GCM encrypt/decrypt.
- **Date/sort semantics**: Date fields encrypted as ISO-8601 `EncryptedText` (`transaction_date`,
  `settled_date`, `*_payment_date`) cannot be sorted or range-filtered at the database level (AES-GCM
  produces random ciphertext). Sorting and date-range filtering for these fields is performed at the
  **application layer** after decryption. For encrypted-field queries, the order of operations is explicit:
  scope in SQL first, then decrypt, then apply filter/sort in memory, and only then apply `page` /
  `page_size` pagination to the filtered result set. This is acceptable for the expected single-user /
  small-group deployment scale.

### Service-layer enforcement

In addition to HTTP-level 403 blocks on financial endpoints, all domain service functions that load
financial data (`domain/accounts.py`, `domain/transactions.py`, `domain/sync_engine.py`, etc.) include
two explicit guards as defense-in-depth:

```python
# Guard 1: superadmin block (HTTP-scoped calls only)
if current_user is not None and current_user.role == "superadmin":
    raise PermissionError("superadmin cannot access financial data")

# Guard 2: owner/delegation scope (prevents cross-user data leaks if a route forgets scope)
if current_user is not None:
    if resource.user_id not in get_accessible_scope(current_user):
        raise PermissionError("access denied")
```

> **Ownership-resolution rules**: Not all resource models carry a direct `user_id` column. The guard resolves ownership via the shortest join path to `users`:
>
> | Resource | Join path to `user_id` |
> |---|---|
> | `direct_debits`, `standing_orders` | `→ accounts → user_id` |
> | `transactions` | `→ accounts → user_id` if `account_id NOT NULL`, else `→ card_id → cards → provider_connections → user_id` |
> | `pending_transactions` | `→ accounts → user_id` (account_id is always non-null; no card_id column) |
> | `balances` | `→ accounts → user_id` if `account_id NOT NULL`, else `→ card_id → cards → provider_connections → user_id` |
> | `cards` | `→ provider_connections → user_id` (via non-nullable `provider_connection_id`) |
> | `accounts` | `→ user_id` (direct — accounts.user_id FK) |
> | `provider_connections` | `→ user_id` (direct) |
> | `alarm_evaluation_results`, `alarm_firing_events` | `→ alarm_definitions → user_id` |
> | `alarm_notifier_assignments` | `→ alarm_definitions → user_id` |
> | `notification_deliveries` | `→ alarm_firing_events → alarm_definitions → user_id` if `alarm_firing_event_id NOT NULL`; otherwise `→ user_id` (direct column set at creation for both system and test notifications) |
> | `events` | `→ user_id` (direct — added in §10) |
> | `alarm_definitions`, `notifier_configs` | `→ user_id` (direct) |
> | `alarm_states` | `→ alarm_definitions → user_id` |
> | `alarm_definition_versions` | `→ alarm_definition_id → alarm_definitions → user_id` |
> | `recurrence_profiles` | `→ accounts → user_id` |
> | `sync_runs` | `→ account_id → accounts → user_id` if `account_id NOT NULL`, else `→ provider_connection_id → provider_connections → user_id` |
>
> Service functions must resolve this path before calling the guard. Helpers such as `resolve_owner_user_id(resource, session)` should be implemented in `manifold/domain/ownership.py`.
> Any encrypted read/write path must also use a centralized helper such as `with_user_dek(user_id, fn)` (or equivalent context manager) so DEK scoping is never performed ad hoc in route/task code.

Background jobs (`sync_all_connections`, `evaluate_all_alarms`, `detect_recurrence`,
`dispatch_alarm_notifications`) pass `current_user=None` (system context). Guard 1 is skipped for
`None`; Guard 2 is also skipped — these jobs process all users intentionally and set the ContextVar
DEK per-user as they iterate. The system context must never be used in HTTP request handlers.

**What the superadmin CAN see** (unencrypted operational metadata only):

- `provider_connections`: `id`, `user_id`, `status`, `auth_status`, `last_sync_at`, `created_at`
- `accounts`: `id`, `user_id`, `provider_connection_id`, `is_active`, `created_at` *(`provider_account_id`, `display_name`, `iban`, `sort_code`, `account_number`, and `currency` are explicitly excluded — these are either encrypted financial identifiers or provider-native identifiers the superadmin must not see)*
- `cards`: `id`, `provider_connection_id`, `account_id`, `provider_card_id`, `card_network`, `created_at`
- `alarm_definitions`: `id`, `user_id`, `condition_version`, `status`, `cooldown_minutes`, `created_at`
- `alarm_evaluation_results`: `id`, `alarm_id`, `evaluated_at`, `result`, `previous_state`, `new_state`, `condition_version`
- `alarm_firing_events`: `id`, `alarm_id`, `fired_at`, `resolved_at`, `notifications_sent`
- `notifier_configs`: `id`, `user_id`, `is_enabled`, `created_at`
- `notification_deliveries`: `id`, `alarm_firing_event_id`, `notifier_id`, `notification_type`, `status`, `attempt_count`, `created_at`, `delivered_at`
- `events`: `id`, `event_type`, `source_type`, `confidence`, `account_id`, `occurred_at`, `recorded_at`
- All operational tables: `sync_runs`, `alarm_states`, `users` (non-financial metadata only)

The superadmin does **not** see encrypted provider/notifier classification fields such as `provider_connections.provider_type` or `notifier_configs.type` in v1. "Structural metadata" in this plan means IDs, ownership edges, statuses, timestamps, counts, and lifecycle state — not encrypted adapter/channel labels.

**v1 `SECRET_KEY` rotation procedure** (manual, until `manifold rotate-key` CLI is added in v2):

1. **Export encrypted DEKs**: `SELECT id, encrypted_dek FROM users;` → save to a secure offline file.
2. **Decrypt DEKs with old master key**: Use a one-off script to re-derive the old master key
   (HKDF-SHA256 from the old `SECRET_KEY`) and decrypt each `encrypted_dek`.
3. **Re-encrypt DEKs with new master key**: Derive the new master key from the new `SECRET_KEY`
   and re-encrypt each DEK. Field data itself is NOT re-encrypted — only the DEK wrapper changes.
4. **Update DB**: `UPDATE users SET encrypted_dek = '<new_encrypted_dek>' WHERE id = '<user_id>';`
   for each row.
5. **Rotate the key**: Replace `SECRET_KEY` in `.env` / secrets manager.
6. **Restart the app**: Verify connections are still functional by triggering a manual sync.

> ⚠️ Only `users.encrypted_dek` needs updating during key rotation — all other encrypted data is
> protected by the per-user DEK, which itself is re-wrapped (not the field data). Always run this
> procedure transactionally in a maintenance window. A CLI helper (`manifold rotate-key`) is planned for v2.

### Application auth (multi-user)

- **First-run bootstrap**: If the `users` table is empty at startup, Manifold seeds a `superadmin` account
  from the `ADMIN_USERNAME` + `ADMIN_PASSWORD` env vars. The plaintext password is Argon2id-hashed
  (m=65536, t=3, p=4) before storage; the plaintext value is never persisted. `must_change_password=True`
  is set on the seeded account — the user must change their password before any other action is permitted.
  Startup fails loudly if either var is missing and the table is empty.
- **Password hashing**: Argon2id (m=65536, t=3, p=4) via `passlib[argon2]`. No bcrypt support; greenfield system.
- **Access token**: JWT, 15-minute expiry, signed with the HKDF-derived JWT signing key (`HKDF(SECRET_KEY, info=b"manifold-jwt-signing", length=32)` — see §18 "Secret management"; the raw `SECRET_KEY` is never used directly for signing)
  - JWT payload: `{"sub": "<user_id>", "role": "superadmin|regular", "exp": ...}`
  - **Browser clients**: delivered as an `HttpOnly` cookie in local development and an `HttpOnly; Secure` cookie in production (set automatically on login response)
  - **API / script clients**: also returned in the JSON response body as `{"access_token":"...","token_type":"bearer","expires_in":900}`; callers may send it via `Authorization: Bearer <token>` header
  - The backend auth middleware accepts either a valid cookie OR a valid Bearer token; cookie takes precedence when both are present
- **Refresh token**: JWT, 7-day expiry, always `HttpOnly` cookie (not returned in body); `Secure` flag added in production → `HttpOnly; Secure` in production, `HttpOnly` only in local development
  - Server-side tracking: each refresh token is stored as a SHA-256 hash in the `refresh_tokens` table
  - Each refresh token is linked to a `user_sessions` row representing a single browser/device session
  - Deactivating a user instantly revokes all their active sessions (sets `revoked_at = datetime.now(timezone.utc)` on all matching rows at the Python layer before flush)
  - Token rotation: each use of a refresh token issues a new one and revokes the old row
- **Device binding**: Browser sessions are hard-bound to an opaque device cookie.
  - On login, the backend creates a `user_sessions` row and sets a long-lived `device_binding` cookie.
  - Only the SHA-256 hash of that cookie is stored (`user_sessions.device_cookie_hash`).
  - `POST /api/v1/auth/refresh` requires both a valid refresh token and a matching device-binding cookie.
  - If the refresh token is valid but the device-binding cookie is missing/mismatched, the session is revoked and refresh fails.
  - IP and user-agent changes are recorded as soft anomaly signals (`ip_last`, `user_agent`) but do not hard-fail by themselves.
- **`must_change_password` enforcement**: Server-side. All endpoints except `PATCH /api/v1/auth/me/password`
  return `403 {"error":"password_change_required"}` when the flag is set. The flag is cleared when the
  password is successfully changed.
- **CSRF**: Same-origin deployment is the primary defense (`/api` served behind the same frontend origin), cookies use `SameSite=Lax`, and all mutating operations require explicit `Content-Type: application/json`. Manifold v1 does **not** rely on JSON-only requests as a sole CSRF mitigation; if cross-origin browser access is introduced later, add an explicit CSRF token mechanism.
  (not form submissions); acceptable risk for self-hosted household use.
- All API routes behind authentication middleware; `/auth/login`, `/auth/refresh`, `/health`, and OAuth callback routes are exempt

### HTTPS / reverse proxy

- Manifold does **not** terminate TLS. Deploy behind a reverse proxy (nginx, Caddy, Traefik) that handles HTTPS.
- Document this requirement clearly in README.
- HttpOnly cookies must be set with `Secure` flag in production; Manifold checks `APP_ENV` and sets cookie flags accordingly.

### Database least privilege

- **SQLite** (default): database file is owned by the process user; restrict OS-level file permissions to `600`
- **PostgreSQL**: create a dedicated `manifold` user with access only to the `manifold` database — no superuser; grant `CONNECT`, `CREATE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE` on the manifold schema only; migration runs under the same user (Alembic needs `CREATE TABLE` / `ALTER TABLE`)
- **MariaDB**: same principle — dedicated `manifold` user with `GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX ON manifold.*`
- Migration runs under the same user for all backends; no elevated privileges required beyond schema DDL

### Financial data logging

- `DEBUG` level: may include additional control-flow detail (which handler/service ran, retry count, branch decisions) but MUST NOT log balances, transaction descriptions, amounts, raw provider responses, tokens, secrets, or decrypted financial fields
- `INFO` level: includes request IDs, user IDs, connection IDs, alarm IDs, notifier IDs, sync run IDs, and high-level outcomes — never balances or transaction details
- `WARNING/ERROR` level: no financial data — only operation names, entity IDs, error codes, and failure summaries
- Log redaction middleware in the `structlog` pipeline strips known sensitive field names before emission

### v1 structured logging policy

Use **structlog** for structured application logging.

**Recommended stack**:

- `structlog` — structured event logging / processors / JSON rendering
- Python stdlib `logging` — transport/handler integration
- `contextvars` — request-scoped correlation fields (`request_id`, `user_id`, `session_id`, `sync_run_id` where applicable)

**Format policy**:

- Default runtime format: JSON (`LOG_FORMAT=json`)
- Local development may use `LOG_FORMAT=text`
- Every emitted event should be a structured event, not interpolated free text

**Required common fields** (when applicable):

- `event` — machine-readable event name (`auth.login_success`, `sync.run_failed`, etc.)
- `level`
- `timestamp`
- `request_id`
- `user_id`
- `session_id`
- `path`
- `method`
- `provider_connection_id`
- `alarm_id`
- `notifier_id`
- `sync_run_id`
- `error_code`

**v1 event naming guidance**:

- `auth.login_success`
- `auth.login_failed`
- `auth.password_change_required`
- `auth.refresh_rotated`
- `auth.refresh_device_mismatch`
- `auth.session_revoked`
- `sync.run_started`
- `sync.run_succeeded`
- `sync.run_failed`
- `provider.auth_refresh_failed`
- `provider.consent_expiring`
- `alarm.evaluated`
- `alarm.fired`
- `alarm.resolved`
- `notifier.dispatch_succeeded`
- `notifier.dispatch_failed`

**Redaction policy**:

- Never log raw values for:
  - access tokens
  - refresh tokens
  - device-binding cookies
  - provider credentials (access tokens, refresh tokens, client secrets)
  - notifier secrets (webhook URLs, bot tokens, API keys)
  - decrypted financial fields (balances, transaction amounts, transaction descriptions)
  - account identifiers: IBAN, sort code, account number, card PAN, card number
  - raw provider response bodies
  - rendered notification subjects or bodies
- If a secret must be referenced operationally, log only a boolean presence flag or a stable hash prefix where strictly necessary for debugging
- The `structlog` processor pipeline MUST include a `drop_sensitive_fields` processor that redacts any log event key matching the list above before emission (matched by field name — e.g., `access_token`, `refresh_token`, `iban`, `account_number`, `sort_code`, `pan`, `card_number`, `rendered_subject`, `rendered_body`, `credentials`, `config` when the value resembles a secret)

**Audit vs log split**:

- Logs are for operational tracing and debugging
- Durable business/security history belongs in DB-backed records:
  - `sync_runs`
  - `events`
  - `alarm_*`
  - `notification_deliveries`
  - `user_sessions`
- Do not treat logs as the sole audit trail

**Retention policy**:

- App/container logs: operational retention outside the app (Docker/log collector policy), recommended 7–30 days depending on environment
- Database-backed audit/observability tables: retained according to their own product/data-retention rules, not tied to log retention

### Token refresh rotation

- When a refresh token is used, it is rotated: a new `refresh_tokens` row is inserted and the old one has `revoked_at` set
- Server-side revocation: deactivating a user via `PATCH /api/v1/users/{id} {is_active: false}` bulk-revokes all their `refresh_tokens` rows; subsequent refresh attempts return 401
- Device-binding mismatch on refresh revokes the associated `user_sessions` row and all linked refresh tokens for that session
- TrueLayer access tokens are encrypted before storage; decrypted in-memory only when needed
- Consent expiry (TrueLayer 90-day window) is tracked and alarmed proactively

---

## 19. Testing Strategy

### Backend testing

**Framework**: `pytest` + `pytest-asyncio` + `httpx` (async test client for FastAPI)

**Test structure**:

```
backend/tests/
├── unit/
│   ├── test_alarm_evaluator.py          # Alarm condition tree evaluation
│   ├── test_recurrence_detector.py      # Pattern detection logic
│   ├── test_provider_mappers/           # TrueLayer + JSON mapper tests
│   │   ├── test_truelayer_mappers.py
│   │   └── test_json_provider_mappers.py
│   ├── test_notifier_dispatcher.py      # Retry + delivery logic
│   └── test_dedup_hash.py               # Deduplication hash generation
├── integration/
│   ├── test_sync_engine.py             # Full sync pipeline (real test DB)
│   ├── test_alarm_lifecycle.py         # Alarm state transitions
│   ├── test_api_accounts.py            # API endpoint tests
│   ├── test_api_alarms.py
│   └── test_api_auth.py
├── fixtures/
│   ├── truelayer_responses/           # Saved TrueLayer API response fixtures
│   ├── json_provider_responses/        # JSON provider fixture payloads
│   └── factory.py                      # SQLModel test data factories
└── conftest.py                         # Shared fixtures (test DB, async client)
```

**Testing principles**:

- Unit tests mock all I/O (HTTP calls, DB writes); test pure business logic
- Integration tests use real databases across SQLite, PostgreSQL, and MariaDB. SQLite remains the default local path; PostgreSQL and MariaDB are both required validation targets for v1.
- Provider adapter tests use fixture JSON responses (never hit real APIs in CI)
- Alarm evaluator has exhaustive unit tests for all operator types and edge cases
- `conftest.py` provides: `async_client`, `test_db_session`, `mock_provider_registry`

**Coverage target**: 80% for `manifold/alarm_engine/`, `manifold/domain/`, `manifold/providers/`

### Frontend testing

**Framework**: `Vitest` + `@testing-library/react` + `@testing-library/user-event`

**Test structure**:

```
frontend/src/**tests**/
├── features/
│   ├── alarms/AlarmRuleBuilder.test.tsx   # Rule builder interaction tests
│   ├── auth/useAuth.test.ts               # Auth hook tests
│   └── transactions/TransactionTable.test.tsx
├── api/
│   └── client.test.ts                      # Axios interceptor tests (token refresh)
└── lib/
    └── utils.test.ts
```

**Testing principles**:

- Component tests use `@testing-library/react`; test behavior, not implementation
- API layer tests use `msw` (Mock Service Worker) to mock backend responses
- No Playwright tests in v1 CI (E2E reserved for manual testing); add in v2

### Provider adapter testing approach

Provider adapters are tested with **fixture files** (saved JSON responses from real or sandbox API calls). Tests assert that given a specific raw API response, the mapper produces the expected canonical model. This:

- Requires no network access in CI
- Documents expected provider response shapes
- Catches breaking changes in provider APIs early

---

## 20. Phased Delivery Roadmap

### Phase 1: Foundation + Database Backends (Weeks 1–4)

**Goal**: Greenfield monorepo bootstrap, full database backend abstraction, auth/RBAC foundation, and v1-grade infrastructure.

- Bootstrap greenfield monorepo structure (`frontend/`, `backend/`, `Makefile`, `docker-compose.yml`, `.github/`)
- Backend: FastAPI app factory, database setup, Alembic migrations, multi-user auth endpoints (login, logout, refresh, me, change-password), first-run bootstrap seeding, RBAC deps
- Frontend: Vite app, TanStack Router, shadcn/ui setup, login page, forced change-password page
- Database: `DatabaseBackend` abstraction + factory + SQLite/PostgreSQL/MariaDB implementations + initial foundational migrations
- Multi-user auth/RBAC: users, delegation, refresh tokens, superadmin guards, encryption-at-rest scaffolding
- **Structured logging**: `structlog` pipeline setup, redaction processor, JSON rendering, and correlation context injection (§18 v1 structured logging policy) — required from day one, not added later
- Docker: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`
- Makefile: all standard targets
- CI: `frontend-ci.yml`, `backend-ci.yml`

**Milestone**: `docker compose up` → login page → authenticated API calls

**Phase QA**:

```bash
# Preconditions:
#   docker compose up with valid .env (SECRET_KEY set; DATABASE_URL defaults to SQLite)
#   ADMIN_USERNAME=admin ADMIN_PASSWORD=bootstrap-pass (bootstrap seeds superadmin, must_change_password=true)
#
# NOTE: The bootstrap user has must_change_password=true and cannot call most endpoints until
# the password is changed. QA uses a fixture user created via CLI:
#   docker compose exec backend uv run manifold create-user fixture-user testpass123

# 1. Health check
curl -s http://localhost:8000/health
# → HTTP 200; body: {"status": "ok"}

# 2. Seed fixture user (no must_change_password)
docker compose exec backend uv run manifold create-user fixture-user testpass123 --role regular

# 3. Login with fixture user
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"fixture-user","password":"testpass123"}' | jq -r '.access_token')
# → HTTP 200; body contains {"access_token": "<jwt>", "token_type": "bearer"}

# 4. Authenticated me endpoint
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq .
# → HTTP 200; body: {"username": "fixture-user", "role": "regular", "mustChangePassword": false}

# 5. Unauthenticated request rejected
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/auth/me
# → 401

# 6. Bootstrap admin forced password change
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"bootstrap-pass"}' | jq -r '.access_token')
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# → 403 (must_change_password=true; only PATCH /auth/me/password is allowed)

# 7. Change admin password clears flag
curl -s -X PATCH http://localhost:8000/api/v1/auth/me/password \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password":"bootstrap-pass","new_password":"newSecurePass!1"}' | jq .
# → HTTP 200; body: {"message":"password updated"}
NEW_ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"newSecurePass!1"}' | jq -r '.access_token')
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $NEW_ADMIN_TOKEN" | jq .role
# → "superadmin" (must_change_password now false)

# 8. Frontend reachable and redirects unauthenticated user to /login
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard
# → 200 (SPA serves index.html for all routes — client-side routing handles /login redirect)
# Executable redirect verification (Playwright):
#   npx playwright open http://localhost:3000/dashboard
#   → browser should land on /login (TanStack Router beforeLoad guard / ProtectedRoute redirects unauthenticated users)
#   Assert: document.location.pathname === '/login'
#   Alternatively: npx playwright codegen http://localhost:3000/dashboard
#   Evidence: screenshot saved to .sisyphus/evidence/phase1-frontend-redirect.png
```

### Phase 2: Connectors + Core Sync (Weeks 5–7)

**Goal**: Deliver the v1 ingestion path with both JSON and TrueLayer connectors, manual/cron sync, and canonical financial data views across SQLite, PostgreSQL, and MariaDB.

- `ProviderRegistry` + `BaseProvider` interface
- `JsonProvider` adapter
- `TrueLayerProvider` adapter + OAuth callback + encrypted token storage
- `SyncEngine`, `sync_runs`, `events`, and idempotent upsert flow
- Taskiq + Redis + 3 shared workers + scheduler
- Provider connection CRUD + accounts/transactions/balances APIs
- Frontend connections/accounts/transactions views

**Milestone**: Both JSON and TrueLayer connections sync successfully and surface data in the app. Full cross-backend execution is validated by backend CI across SQLite, PostgreSQL, and MariaDB.

### Phase 3: Alarms (Weeks 7–8)

**Goal**: Ship observed-data alarming on synced financial data.

- Alarm models + evaluator + state machine
- Alarm CRUD API
- Alarm evaluation jobs
- Frontend alarm rule builder + history/detail

**Milestone**: User creates an account-bound alarm and sees it transition correctly.

### Phase 4: Notifications (Week 9)

**Goal**: Ship notification delivery for alerts and system messages.

- `EmailNotifier`
- `WebhookNotifier`
- Delivery history / metadata endpoints
- Notifier CRUD + test endpoint
- Per-alarm routing + system notifications
- Optional HTTPS reverse-proxy verification (`https-proxy` profile; implementation already lands in Phase 1 infrastructure)

**Milestone**: Alerts and test/system messages deliver through email and generic webhooks with recorded history.

### Phase 5: Predictions + Expanded Integrations (Weeks 10+)

**Goal**: Complete remaining v1 features: predictions, expanded notifier channels, and release/polish work.

- Recurrence detection + `debit_predicted` events
- Slack / Telegram notifiers
- Release polish, settings/dashboard polish, release workflow

**Milestone**: v1 feature set complete and releasable across SQLite, PostgreSQL, and MariaDB.

### Phase 6: Post-v1 (future)

- WhatsApp notifier (post-v1)
- Additional providers (Nordigen/GoCardless, Plaid)
- Balance projection charts
- Mobile-optimized frontend
- Alternative HTTPS/cert-management options beyond the self-signed proxy profile

---

## 21. Risks and Mitigations

| Risk                                                   | Probability           | Impact   | Mitigation                                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------ | --------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TrueLayer API breaking changes                         | Medium                | High     | Fixture-based adapter tests; monitor TrueLayer changelog; version detection in adapter                                                                                                                                                                                                                |
| TrueLayer OAuth consent expiry disrupting sync         | High                  | Medium   | Track `consent_expires_at`; alarm when within 7 days; clear re-auth UX in frontend                                                                                                                                                                                                                    |
| Redis unavailable on startup                           | Low                   | High     | `manifold-tasker` and `backend` depend on `manifold-redis` health check in Docker Compose; tasks are not lost — Redis Streams are durable; API returns 503 on enqueue failure                                                                                                                         |
| Duplicate concurrent syncs                             | Low                   | Medium   | Redis `SETNX` lock per `connection_id`; API returns 409 if sync already in flight                                                                                                                                                                                                                     |
| DB connection pool exhaustion                          | Low                   | High     | `pool_size` + `max_overflow` capped per process; default 25 total connections (2 API workers × 5 + 3 task workers × 5); configurable via `DB_POOL_SIZE` env var; SQLite is exempt (NullPool); PostgreSQL: monitor via `SHOW pg_stat_activity`; `pool_pre_ping=True` prevents silent stale connections |
| Encrypted credential loss if SECRET_KEY changes        | High (if not managed) | Critical | Document key rotation process; backup encrypted credentials before key change; provide `manifold rotate-key` CLI command in v2                                                                                                                                                                        |
| False alarm fatigue                                    | Medium                | Medium   | `repeat_count`, `for_duration_minutes`, `cooldown_minutes` defaults; mute functionality                                                                                                                                                                                                               |
| JSON provider misconfiguration silently fails          | Medium                | Medium   | Strict validation on provider config at creation time; test notifier endpoint (`/notifiers/{id}/test`) to verify delivery independently of sync                                                                                                                                                       |
| Complex alarm condition tree causes performance issues | Low                   | Low      | Evaluation is in-process; trees are bounded by user intent; add depth limit guard                                                                                                                                                                                                                     |
| Frontend API URL misconfigured in Docker               | Medium                | Medium   | Clear documentation; `/health` endpoint confirms backend is reachable; nginx proxy config serves `/api` from the same origin                                                                                                                                                                          |

---

## 22. Suggested Initial Backlog / Milestone Breakdown

### Milestone 1: "Hello Manifold" (Phase 1)

- [x] Bootstrap greenfield monorepo structure: create `frontend/`, `backend/`, root `Makefile`, `docker-compose.yml`, `.github/workflows/`, `README.md`
- [x] Brand: Manifold logo — SVG (vector, light + dark variants) + PNG (512×512 raster); financial observability theme; saved as `frontend/public/logo.svg`, `frontend/public/logo-dark.svg`, `frontend/public/logo.png`
- [x] `backend/`: `DatabaseBackend` ABC + `DatabaseBackendFactory` in `manifold/database/`
- [x] `backend/`: `SQLiteBackend` (WAL pragma, FK pragma, NullPool)
- [x] `backend/`: `PostgreSQLBackend` (QueuePool, pre_ping, native ON CONFLICT upsert)
- [x] `backend/`: `MariaDBBackend` (QueuePool, native ON DUPLICATE KEY UPDATE)
- [x] `backend/`: Alembic `env.py` with `render_as_batch=True` + dialect-conditional DDL
- [x] `backend/`: FastAPI app, Pydantic settings, `manifold/database/__init__.py` (engine factory entry point)
- [x] `backend/`: Initial Alembic migration for foundational auth/session/core tables with backend-portable types
- [x] `backend/`: Auth endpoints (login, logout, refresh, me, change-password) + Argon2id hashing + JWT with role in payload
- [x] `backend/`: Device-bound session model (`user_sessions` + device-binding cookie + refresh-token/session linkage)
- [x] `backend/`: First-run bootstrap: seed superadmin from `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars on empty `users` table; must_change_password=True
- [x] `backend/`: `manifold/models/user.py` — `User`, `AccountAccess`, `RefreshToken` SQLModel ORM models
- [x] `backend/`: `manifold/api/users.py` — user management router (superadmin CRUD) + delegation sub-routes (`/users/me/access`)
- [x] `backend/`: `get_accessible_scope(current_user)` + superadmin guards + last-superadmin protection + self-grant prevention
- [x] `backend/`: `manifold/security/` package — `EncryptionService` + `EncryptedText` / `EncryptedJSON` / `EncryptedDecimal`
- [x] `backend/`: encryption-at-rest migration + service-layer superadmin financial-data guard
- [x] `backend/`: Health endpoint
- [x] `frontend/`: Vite + React + TypeScript + Tailwind + shadcn/ui + TanStack Router
- [x] `frontend/`: Login page with auth flow (logo displayed on login screen)
- [x] `frontend/`: Protected route wrapper
- [x] `frontend/`: `/change-password`, `/settings/users`, `/settings/access`, role-aware AuthContext and route guards
- [x] `frontend/`: `/settings/sessions` page — user-visible session inventory with per-session revoke
- [x] `Makefile`: All standard targets working
- [x] `docker-compose.yml`: Backend + Frontend + Redis containers (SQLite default via volume; `.env` overrides to PG/MariaDB)
- [x] `ops/https/nginx.conf` + optional `https-proxy` compose profile: self-signed TLS termination reverse-proxying both website and `/api`
- [x] `backend/Dockerfile`, `frontend/Dockerfile`
- [x] CI: `frontend-ci.yml` + `backend-ci.yml` passing
- [x] `.env.example` root, backend, frontend files

**Milestone QA**:

```bash
# Preconditions: docker compose up; .env populated with SECRET_KEY, ADMIN_USERNAME=admin, ADMIN_PASSWORD=bootstrap-pass

# Seed fixture user (no must_change_password)
docker compose exec backend uv run manifold create-user fixture-user testpass123 --role regular

# Login succeeds with fixture user
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"fixture-user","password":"testpass123"}' | jq -r '.access_token')
[ -n "$TOKEN" ] && echo "PASS: login returned token" || echo "FAIL: no token"

# Health endpoint responds
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
[ "$STATUS" = "200" ] && echo "PASS: health ok" || echo "FAIL: health returned $STATUS"

# Authenticated /me returns username + role
RESP=$(curl -s http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN")
USERNAME=$(echo $RESP | jq -r '.username')
ROLE=$(echo $RESP | jq -r '.role')
[ "$USERNAME" = "fixture-user" ] && echo "PASS: me endpoint" || echo "FAIL: me returned $USERNAME"
[ "$ROLE" = "regular" ] && echo "PASS: role correct" || echo "FAIL: role returned $ROLE"

# Unauthenticated request rejected
UNAUTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/auth/me)
[ "$UNAUTH" = "401" ] && echo "PASS: 401 on unauthenticated" || echo "FAIL: got $UNAUTH"

# Bootstrap admin forced to change password
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"bootstrap-pass"}' | jq -r '.access_token')
MCP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $ADMIN_TOKEN")
[ "$MCP_STATUS" = "403" ] && echo "PASS: bootstrap admin blocked until password changed" || echo "FAIL: got $MCP_STATUS"

# CI check — frontend passes and backend GitHub Actions cover SQLite, PostgreSQL, and MariaDB
make ci-check
# → exit code 0

# Change bootstrap admin password (satisfies must_change_password constraint)
CHANGE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH http://localhost:8000/api/v1/auth/me/password \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password":"bootstrap-pass","new_password":"newSecurePass!1"}')
[ "$CHANGE_STATUS" = "204" ] && echo "PASS: admin password changed" || echo "FAIL: password change returned $CHANGE_STATUS"

# Re-authenticate after password change
NEW_ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"newSecurePass!1"}' | jq -r '.access_token')

# Create a regular user via API
ALICE_ID=$(curl -s -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $NEW_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"alicePass1","role":"regular"}' | jq -r '.id')
[ -n "$ALICE_ID" ] && echo "PASS: user created" || echo "FAIL: no user id"

# Alice cannot access /api/v1/users
ALICE_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"alicePass1"}' | jq -r '.access_token')
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $ALICE_TOKEN")
[ "$STATUS" = "403" ] && echo "PASS: superadmin-only user list enforced" || echo "FAIL: got $STATUS"

# Verify encryption-at-rest scaffolding exists
docker compose exec backend uv run python -c "
import asyncio
from sqlalchemy import text
from manifold.database import engine
async def check():
    async with engine.connect() as conn:
        row = (await conn.execute(text(\"SELECT encrypted_dek FROM users WHERE username = 'alice'\"))).fetchone()
        print('PASS' if row and row[0] else 'FAIL')
asyncio.run(check())
"
```

### Milestone 2: "Data In" (Phase 2)

- [x] `BaseProvider` interface + `ProviderRegistry`
- [x] `BaseProviderAuth` hierarchy (OAuth2, ApiKey, Bearer, Basic, None)
- [x] `JsonProvider` adapter with all auth modes
- [x] `TrueLayerProvider` adapter with OAuth2 flow
- [x] `SyncEngine` with `SyncRun` logging and idempotent upserts
- [x] Taskiq broker + Redis setup (`manifold/tasks/broker.py`, `manifold/tasks/scheduler.py`)
- [x] `manifold-tasker` container with `supervisord.conf` (worker-1, worker-2, worker-3 — all `--queues manual,sync` — and scheduler)
- [x] Distributed sync lock via Redis SETNX (`manifold/tasks/_locks.py`)
- [x] `manifold-redis` service in `docker-compose.yml`
- [x] Provider connection CRUD API
- [x] Accounts + transactions + balances API
- [x] Provider and accounts pages in frontend
- [x] Alembic migration for provider connection + account/balance/transaction/sync/event tables needed by JSON + TrueLayer sync
- [x] OAuth callback handling + encrypted token storage
- [x] Consent expiry tracking
- [x] Cards, pending transactions, direct debits, standing orders endpoints + frontend pages

**Milestone QA**:

```bash
# Precondition: Start fixture HTTP server before running QA:
#   python -m http.server 9000 --directory backend/tests/fixtures/ &
# Preconditions: admin password changed to newSecurePass!1 (Phase 1 QA); fixture-user/testpass123 created (Phase 1 QA)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"username":"fixture-user","password":"testpass123"}' | jq -r '.access_token')

# JSON provider: create connection, sync, verify data
CONN=$(curl -s -X POST http://localhost:8000/api/v1/connections \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Fixture","provider_type":"json","config":{"url":"http://localhost:9000/manifold-fixture.json","auth_type":"none","mapping":{}}}' | jq -r '.id')
# NOTE: mapping: {} uses the default canonical field mapping
# NOTE: If running in Docker, replace 'localhost:9000' with 'host.docker.internal:9000' above.
curl -s -X POST "http://localhost:8000/api/v1/connections/$CONN/sync" \
  -H "Authorization: Bearer $TOKEN" > /dev/null
sleep 5

ACCOUNT_COUNT=$(curl -s http://localhost:8000/api/v1/accounts \
  -H "Authorization: Bearer $TOKEN" | jq '.items | length')
[ "$ACCOUNT_COUNT" -ge 1 ] && echo "PASS: accounts loaded" || echo "FAIL: no accounts"

# Sync run status — no errors
SYNC_STATUS=$(curl -s "http://localhost:8000/api/v1/connections/$CONN/sync-runs?page=1&page_size=1" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.items[0].status')
[ "$SYNC_STATUS" = "success" ] && echo "PASS: sync completed" || echo "FAIL: sync status=$SYNC_STATUS"

# Idempotency: re-sync does not duplicate accounts
curl -s -X POST "http://localhost:8000/api/v1/connections/$CONN/sync" \
  -H "Authorization: Bearer $TOKEN" > /dev/null
sleep 5
ACCOUNT_COUNT_2=$(curl -s http://localhost:8000/api/v1/accounts \
  -H "Authorization: Bearer $TOKEN" | jq '.items | length')
[ "$ACCOUNT_COUNT_2" = "$ACCOUNT_COUNT" ] && echo "PASS: idempotent" || echo "FAIL: duplicates detected"

# TrueLayer OAuth flow is part of v1.
# Preconditions: TRUELAYER_CLIENT_ID + TRUELAYER_CLIENT_SECRET set; TRUELAYER_SANDBOX=true
TL_CONN_ID=$(curl -s -X POST http://localhost:8000/api/v1/connections \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"My Bank","provider_type":"truelayer"}' | jq -r '.id')
[ -n "$TL_CONN_ID" ] && echo "PASS: TrueLayer connection created ($TL_CONN_ID)" || echo "FAIL: connection not created"

REDIRECT=$(curl -s "http://localhost:8000/api/v1/connections/$TL_CONN_ID/auth-url" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.redirect_url')
echo "Navigate to: $REDIRECT"
# → URL starting with https://auth.truelayer-sandbox.com/...
# Manual step: navigate to $REDIRECT in browser → log in with sandbox credentials → approve consent
# → browser is redirected to https://localhost:3443/api/v1/providers/truelayer/callback?code=...&state=...
# After OAuth callback completes:
curl -s "http://localhost:8000/api/v1/connections/$TL_CONN_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '{status, consent_expires_at}'
# → {"status": "active", "consent_expires_at": "<ISO8601 ~90 days out>"}
TL_STATUS=$(curl -s "http://localhost:8000/api/v1/connections/$TL_CONN_ID" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.status')
[ "$TL_STATUS" = "active" ] && echo "PASS: TrueLayer connection active" || echo "FAIL: TL status=$TL_STATUS"
 
# Backend abstraction verification across all supported databases
docker compose exec backend uv run python -c "from manifold.database.factory import DatabaseBackendFactory; print(DatabaseBackendFactory.create('sqlite+aiosqlite:///data/manifold.db').__class__.__name__)"
# → SQLiteBackend

docker compose exec backend uv run python -c "from manifold.database.factory import DatabaseBackendFactory; print(DatabaseBackendFactory.create('postgresql+asyncpg://user:pass@db/manifold').__class__.__name__)"
# → PostgreSQLBackend

docker compose exec backend uv run python -c "from manifold.database.factory import DatabaseBackendFactory; print(DatabaseBackendFactory.create('mysql+asyncmy://user:pass@db/manifold').__class__.__name__)"
# → MariaDBBackend
```

### Milestone 3: "Alarms" (Phase 3)

- [x] `AlarmDefinition` + `AlarmState` + evaluation result models
- [x] `AlarmEvaluator` (observed-data contexts first)
- [x] Alarm state machine
- [x] Alarm evaluation scheduled job
- [x] Alarm CRUD API
- [x] Alarm explanation text generation
- [x] Frontend alarm list + rule builder + detail view

**Milestone QA**:

```bash
# Preconditions: admin password changed to newSecurePass!1 (Phase 1 QA); fixture-user/testpass123 created (Phase 1 QA)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"username":"fixture-user","password":"testpass123"}' | jq -r '.access_token')
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"username":"admin","password":"newSecurePass!1"}' | jq -r '.access_token')

# Preconditions: Milestone 2 complete
ACCOUNT_ID=$(curl -s http://localhost:8000/api/v1/accounts \
  -H "Authorization: Bearer $TOKEN" | jq -r '.items[0].id')

# Create simple threshold alarm
ALARM_ID=$(curl -s -X POST http://localhost:8000/api/v1/alarms \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Low Balance\",\"account_ids\":[\"$ACCOUNT_ID\"],\"condition\":{\"op\":\"LT\",\"field\":\"account.balance\",\"value\":10000},\"for_duration_minutes\":0}" | jq -r '.id')
[ -n "$ALARM_ID" ] && echo "PASS: alarm created" || echo "FAIL: alarm creation failed"

# Trigger evaluation
curl -s -X POST http://localhost:8000/api/v1/admin/jobs/evaluate-alarms/trigger \
  -H "Authorization: Bearer $ADMIN_TOKEN" > /dev/null
sleep 3

# Alarm state transitions to firing
STATE=$(curl -s "http://localhost:8000/api/v1/alarms/$ALARM_ID" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.state')
[ "$STATE" = "firing" ] && echo "PASS: alarm firing" || echo "FAIL: state=$STATE"
```

### Milestone 4: "Notifications" (Phase 4)

- [x] `BaseNotifier` + `NotifierRegistry` + `NotifierDispatcher` + retry logic
- [x] `EmailNotifier` (SMTP, Jinja2 templates)
- [x] `WebhookNotifier` (generic HTTP POST message sender)
- [x] Delivery log + history endpoints for triggered jobs / attempts / payload + response metadata
- [x] Notifier CRUD API + test endpoint
- [x] Per-alarm notifier routing
- [x] System notifier for sync failures + auth expiry
- [x] Frontend notifier management page
- [x] Optional HTTPS reverse-proxy path verified (`https-proxy` profile)

**Milestone QA**:

```bash
# Preconditions:
#   - admin password changed to newSecurePass!1 (Phase 1 QA); fixture-user/testpass123 created (Phase 1 QA)
#   - Full dev compose is running: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
#     (Mailpit SMTP sink starts automatically; verify: curl -s http://localhost:8025/api/v1/messages | jq '.messages | length')
#   - Clear Mailpit inbox before this QA run: curl -s -X DELETE http://localhost:8025/api/v1/messages

# Start webhook capture server on port 9010 (Docker containers reach it via host.docker.internal:9010)
python3 -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        l = int(self.headers.get('Content-Length', 0))
        self.rfile.read(l)
        self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
    def log_message(self, *a): pass
HTTPServer(('0.0.0.0', 9010), H).serve_forever()
" &
WEBHOOK_PID=$!
sleep 1
[ -n "$WEBHOOK_PID" ] && echo "PASS: webhook receiver started (pid=$WEBHOOK_PID)" || echo "FAIL: webhook receiver not started"

TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"username":"fixture-user","password":"testpass123"}' | jq -r '.access_token')

# 1. Email notifier test delivery
EMAIL_ID=$(curl -s -X POST http://localhost:8000/api/v1/notifiers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Email","type":"email","config":{"smtp_host":"localhost","smtp_port":1025,"smtp_use_tls":false,"from_address":"manifold@localhost","to_address":"test@example.com"}}' | jq -r '.id')
[ -n "$EMAIL_ID" ] && echo "PASS: email notifier created" || echo "FAIL: no email notifier id"

# Test email delivery via notifier /test endpoint
EMAIL_DELIVERED=$(curl -s -X POST "http://localhost:8000/api/v1/notifiers/$EMAIL_ID/test" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.delivered')
[ "$EMAIL_DELIVERED" = "true" ] && echo "PASS: email test delivery accepted" || echo "FAIL: email test delivered=$EMAIL_DELIVERED"

# Verify email landed in Mailpit SMTP sink
sleep 2
MAIL_COUNT=$(curl -s http://localhost:8025/api/v1/messages | jq '.messages | length')
[ "$MAIL_COUNT" -ge 1 ] && echo "PASS: email received in Mailpit" || echo "FAIL: no email found in Mailpit (is Mailpit running?)"
MAIL_TO=$(curl -s http://localhost:8025/api/v1/messages | jq -r '.messages[0].To[0].Address')
[ "$MAIL_TO" = "test@example.com" ] && echo "PASS: email addressed to test@example.com" || echo "FAIL: wrong recipient=$MAIL_TO"

# 2. Generic webhook notifier test delivery
WEBHOOK_ID=$(curl -s -X POST http://localhost:8000/api/v1/notifiers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Generic Webhook","type":"webhook","config":{"url":"http://host.docker.internal:9010/alerts","method":"POST","headers":{"X-Manifold-Test":"1"}}}' | jq -r '.id')
[ -n "$WEBHOOK_ID" ] && echo "PASS: webhook notifier created" || echo "FAIL: no webhook notifier id"

WEBHOOK_DELIVERED=$(curl -s -X POST "http://localhost:8000/api/v1/notifiers/$WEBHOOK_ID/test" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.delivered')
[ "$WEBHOOK_DELIVERED" = "true" ] && echo "PASS: webhook delivered" || echo "FAIL: webhook not delivered"

# 3. Delivery log records webhook metadata/history
DELIVERY_COUNT=$(curl -s "http://localhost:8000/api/v1/notification-deliveries?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN" | jq '.items | length')
[ "$DELIVERY_COUNT" -ge 1 ] && echo "PASS: delivery history present" || echo "FAIL: no delivery history"

# 4. Optional HTTPS reverse proxy responds when enabled
HTTPS_STATUS=$(curl -k -s -o /dev/null -w "%{http_code}" https://localhost:3443/)
[ "$HTTPS_STATUS" = "200" ] && echo "PASS: https proxy reachable" || echo "FAIL: https proxy status=$HTTPS_STATUS"

# Cleanup webhook receiver
kill $WEBHOOK_PID 2>/dev/null
```

### Milestone 5: "Predictions + Expanded Channels + Release" (Phase 5)

- [x] `SlackNotifier`
- [x] `TelegramNotifier`
- [x] Recurrence detection algorithm
- [x] `RecurrenceProfile` model + daily detection job
- [x] Predicted event generation
- [x] Dashboard summary polish
- [x] Settings page
- [x] `release.yml` GitHub Actions workflow
- [x] First `v1.0.0` tag + GitHub Release

**Milestone QA**:

```bash
# Preconditions:
#   - Milestone 4 complete; dev compose is running
#   - Slack credential: export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
#   - Telegram credentials: export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
#   - release.yml committed to .github/workflows/ and pushed to default branch
#   - Fixture data (backend/tests/fixtures/manifold-fixture.json) contains >=3 monthly
#     recurring transactions so the recurrence detection job can produce a profile.
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"username":"fixture-user","password":"testpass123"}' | jq -r '.access_token')
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"username":"admin","password":"newSecurePass!1"}' | jq -r '.access_token')
EMAIL_ID=$(curl -s "http://localhost:8000/api/v1/notifiers?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.items[] | select(.type=="email") | .id' | head -n 1)
ACCOUNT_ID=$(curl -s http://localhost:8000/api/v1/accounts \
  -H "Authorization: Bearer $TOKEN" | jq -r '.items[0].id')

# 1. Slack notifier test delivery
SLACK_ID=$(curl -s -X POST http://localhost:8000/api/v1/notifiers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Slack\",\"type\":\"slack\",\"config\":{\"webhook_url\":\"$SLACK_WEBHOOK_URL\",\"channel\":\"#manifold-alerts\"}}" | jq -r '.id')
[ -n "$SLACK_ID" ] && echo "PASS: slack notifier created" || echo "FAIL: no slack notifier id"
SLACK_DELIVERED=$(curl -s -X POST "http://localhost:8000/api/v1/notifiers/$SLACK_ID/test" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.delivered')
[ "$SLACK_DELIVERED" = "true" ] && echo "PASS: slack test delivered" || echo "FAIL: slack not delivered"

# 2. Telegram notifier test delivery
TELEGRAM_ID=$(curl -s -X POST http://localhost:8000/api/v1/notifiers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Telegram\",\"type\":\"telegram\",\"config\":{\"bot_token\":\"$TELEGRAM_BOT_TOKEN\",\"chat_id\":\"$TELEGRAM_CHAT_ID\"}}" | jq -r '.id')
[ -n "$TELEGRAM_ID" ] && echo "PASS: telegram notifier created" || echo "FAIL: no telegram notifier id"
TELEGRAM_DELIVERED=$(curl -s -X POST "http://localhost:8000/api/v1/notifiers/$TELEGRAM_ID/test" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.delivered')
[ "$TELEGRAM_DELIVERED" = "true" ] && echo "PASS: telegram test delivered" || echo "FAIL: telegram not delivered"

# 3. Predicted debit events appear after recurrence detection
# Trigger detect-recurrence job (analyses transaction history for recurring patterns)
DETECT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/admin/jobs/detect-recurrence/trigger \
  -H "Authorization: Bearer $ADMIN_TOKEN")
[ "$DETECT_STATUS" = "202" ] && echo "PASS: recurrence detect triggered" || echo "FAIL: trigger returned $DETECT_STATUS"
sleep 10

# Verify at least one RecurrenceProfile was persisted
PROFILE_COUNT=$(curl -s "http://localhost:8000/api/v1/recurrence-profiles?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN" | jq '.items | length')
[ "$PROFILE_COUNT" -ge 1 ] && echo "PASS: recurrence profile created (count=$PROFILE_COUNT)" || echo "FAIL: no recurrence profiles (fixture must contain >=3 monthly recurring transactions)"

# Trigger evaluate-alarms to generate debit_predicted events from detected profiles
curl -s -X POST http://localhost:8000/api/v1/admin/jobs/evaluate-alarms/trigger \
  -H "Authorization: Bearer $ADMIN_TOKEN" > /dev/null
sleep 5

PREDICTED_COUNT=$(curl -s "http://localhost:8000/api/v1/events?type=debit_predicted&page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN" | jq '.items | length')
[ "$PREDICTED_COUNT" -ge 1 ] && echo "PASS: debit_predicted events generated (count=$PREDICTED_COUNT)" || echo "FAIL: no debit_predicted events"

# 4. Release pipeline dry-run succeeds
[ -f ".github/workflows/release.yml" ] && echo "PASS: release.yml exists" || echo "FAIL: .github/workflows/release.yml missing"
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" \
  && echo "PASS: release.yml is valid YAML" || echo "FAIL: invalid YAML in release.yml"
# Verify workflow references the v1.0.0 tag pattern
grep -q 'tags:' .github/workflows/release.yml \
  && echo "PASS: release workflow is tag-triggered" || echo "FAIL: release workflow missing tags trigger"
ALARM_ID=$(curl -s -X POST http://localhost:8000/api/v1/alarms \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"E2E Test\",\"account_ids\":[\"$ACCOUNT_ID\"],\"condition\":{\"op\":\"LT\",\"field\":\"account.balance\",\"value\":99999999},\"notifier_ids\":[\"$EMAIL_ID\"],\"for_duration_minutes\":0,\"cooldown_minutes\":0}" | jq -r '.id')
# notifier_ids in the request/response is an API convenience field; the server writes to alarm_notifier_assignments join table
curl -s -X POST http://localhost:8000/api/v1/admin/jobs/evaluate-alarms/trigger \
  -H "Authorization: Bearer $ADMIN_TOKEN" > /dev/null
sleep 5
AUTO_DELIVERY=$(curl -s "http://localhost:8000/api/v1/notification-deliveries?alarm_id=$ALARM_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '[.items[] | select(.status=="delivered")] | length')
[ "$AUTO_DELIVERY" -ge 1 ] && echo "PASS: auto-delivery on alarm fire" || echo "FAIL: no auto-delivery"

# 6. Dashboard summary endpoint returns complete shape
curl -s http://localhost:8000/api/v1/dashboard/summary \
  -H "Authorization: Bearer $TOKEN" | jq 'keys | sort'
# → ["accounts_total","active_alarms_count","last_sync_at","recent_events","upcoming_debits"]

# 7. Docker image builds and passes config check
docker build -t manifold-backend:milestone-5-test ./backend
docker run --rm \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@localhost/manifold" \
  -e SECRET_KEY="test-secret-key-32-chars-minimum!" \
  manifold-backend:milestone-5-test python -m manifold.cli check-config
# → exit code 0; output "Configuration OK"

# 8. MariaDB backend abstraction path resolves correctly
docker run --rm manifold-backend:milestone-5-test python -c "from manifold.database.factory import DatabaseBackendFactory; print(DatabaseBackendFactory.create('mysql+asyncmy://user:pass@localhost/manifold').__class__.__name__)"
# → MariaDBBackend
```

---

*End of Manifold Implementation Plan v1.0*
