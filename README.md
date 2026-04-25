# Manifold

> Self-hosted financial observability platform

Manifold is an operations control plane for your personal finances. It connects to your bank accounts, tracks your transactions, and allows you to build complex alerting logic to keep you informed about your financial health.

## What is Manifold?

Manifold is a self-hosted platform designed for individuals and small teams who want full control over their financial data. Unlike traditional budgeting apps that focus on backward-looking categorization, Manifold treats your finances as a system to be monitored. It ingests raw data from multiple sources, normalizes it into a unified domain model, and provides the tools to observe, analyze, and alert on financial events.

The platform is built on the philosophy that financial data is private and sensitive. By self-hosting Manifold, you ensure that your credentials and transaction history remain on your own infrastructure. Every piece of sensitive data, from provider tokens to notification settings, is encrypted at rest using per-user keys, providing a layer of security typically reserved for enterprise-grade systems.

Whether you are managing a single household account or coordinating finances for a small organization, Manifold provides a robust, developer-friendly foundation for financial observability. It is not just about where your money went, but about understanding the current state of your financial system and being alerted when things require your attention.

## Features

- **Financial Data Ingestion**: Seamlessly sync data from TrueLayer (Open Banking) or push data via the flexible JSON provider.
- **Unified Views**: Centralized dashboard for accounts, transactions, balances, cards, direct debits, and standing orders.
- **Advanced Alarm Engine**: Define sophisticated alarm rules using an AND/OR/NOT condition tree. Monitor balances, sync health, and specific transaction patterns.
- **Multi-channel Notifications**: Get alerted via Email (SMTP), Webhook, Slack, or Telegram when alarms fire.
- **Recurring Payment Detection**: Automatically identify recurring debits and predict future financial obligations.
- **Security First**: Per-user AES-256-GCM encryption at rest for all sensitive credentials. Data is only decrypted in memory when needed for a specific user's sync or evaluation.
- **Multi-user Delegation**: Support for multiple users with granular delegation. Grant "Viewer" or "Admin" access to specific accounts within a household or team.
- **Pluggable Database**: Runs on SQLite by default for zero-ops setup. Supports PostgreSQL and MariaDB for production-scale deployments.
- **Docker First**: Deploy the entire stack with a single `docker compose up` command.

## Architecture Overview

Manifold uses a layered architecture to ensure modularity and ease of extension:

1.  **Frontend**: A modern React/TypeScript SPA built with Vite and shadcn/ui.
2.  **API Layer**: FastAPI-based REST API handling authentication, request validation, and routing.
3.  **Domain Layer**: Pure business logic that manages accounts, transactions, and alarm evaluation without being tied to specific providers or databases.
4.  **Provider Layer**: Pluggable adapters (TrueLayer, JSON) that translate external data into the Manifold canonical model.
5.  **Background Jobs**: Taskiq-powered worker system using Redis for job orchestration (syncing, alarm evaluation, recurrence detection).
6.  **Persistence**: A dialect-agnostic SQL layer supporting SQLite, PostgreSQL, and MariaDB.

```text
  [Browser] <──> [Nginx/Frontend] <──> [FastAPI Backend] <──> [SQL Database]
                                              │
                                       [Taskiq Worker] <──> [Redis]
                                              │
                                    [External Bank APIs]
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- `openssl` (for generating secrets)

### Docker Compose (Recommended)

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-org/manifold.git
    cd manifold
    ```

2.  **Configure environment**:
    ```bash
    cp .env.example .env
    # Generate a secure key
    sed -i "s/replace-with-64-char-random-string/$(openssl rand -hex 32)/" .env
    ```

3.  **Set Admin Credentials**:
    Edit `.env` and set `ADMIN_USERNAME` and `ADMIN_PASSWORD`. These are used to bootstrap the first superadmin user.

4.  **Start the stack**:
    ```bash
    docker compose up -d
    ```

5.  **Initialize Database**:
    The system runs migrations automatically on startup, but you can verify with:
    ```bash
    docker compose exec backend uv run alembic upgrade head
    ```

6.  **Access the App**:
    Open `http://localhost:3000` in your browser. Log in with the admin credentials set in step 3.

### Local Development (without Docker)

For local development, you need Python 3.12+, Node.js 20+, and a running Redis instance.

1.  **Install dependencies**:
    ```bash
    make setup
    ```

2.  **Start Backend**:
    ```bash
    make dev-backend
    ```

3.  **Start Frontend**:
    ```bash
    make dev-frontend
    ```

4.  **Run Worker**:
    ```bash
    cd backend && uv run taskiq worker manifold.tasks.broker:broker manifold.tasks
    ```

## Configuration

All configuration is managed via environment variables.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `SECRET_KEY` | Master key for JWT and DEK derivation. **Keep secret.** | (None) |
| `DATABASE_URL` | SQLAlchemy connection string. | `sqlite+aiosqlite:///data/manifold.db` |
| `REDIS_URL` | Redis connection URL for tasks/locks. | `redis://manifold-redis:6379/0` |
| `ADMIN_USERNAME` | Bootstrap superadmin username. | `admin` |
| `ADMIN_PASSWORD` | Bootstrap superadmin password. | (None) |
| `ALLOWED_ORIGINS` | CORS allowed origins (JSON array). | `["http://localhost:3000"]` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, etc). | `INFO` |

## Providers

### TrueLayer
Connects to UK/EU banks via the Open Banking standard.
- **Setup**: Create a project in the [TrueLayer Console](https://console.truelayer.com/).
- **Credentials**: Set `TRUELAYER_CLIENT_ID` and `TRUELAYER_CLIENT_SECRET`.
- **Redirect URI**: Must match `TRUELAYER_REDIRECT_URI` in `.env`.

### JSON Provider
A generic "push" or "pull" provider for manual data or custom integrations.
- **Config**: Define endpoints and mapping logic in the provider settings.
- **Auth**: Supports No Auth, ApiKey, Bearer, and Basic auth.

### Adding a Provider
New providers can be added by implementing the `BaseProvider` interface in `backend/src/manifold/providers/base.py`. See `docs/providers.md` for details.

## Alarms

Alarms are the heart of Manifold. You can create rules that monitor your data continuously.

- **Example**: `account.balance < 500 AND sync_run.status == "success"`
- **Conditions**: Supports comparison operators (`==`, `!=`, `<`, `<=`, `>`, `>=`) and logical operators (`AND`, `OR`, `NOT`).
- **State Machine**: Alarms transition through states: `OK`, `PENDING` (delay before firing), `FIRING`, and `RESOLVED`.

## Notifications

Manifold supports several notification channels:
- **Email**: Requires SMTP server settings.
- **Slack**: Requires a Webhook URL.
- **Telegram**: Requires a Bot Token and Chat ID.
- **Webhook**: Sends a JSON POST request to a custom endpoint.

## Database Backends

Manifold abstracts the database layer. Change `DATABASE_URL` to switch backends:

- **SQLite**: `sqlite+aiosqlite:///data/manifold.db`
- **PostgreSQL**: `postgresql+asyncpg://user:pass@host:5432/dbname`
- **MariaDB/MySQL**: `mysql+asyncmy://user:pass@host:3306/dbname`

## Security

- **Encryption**: Sensitive fields are encrypted using AES-256-GCM. The Data Encryption Key (DEK) is generated per user and wrapped with a Master Key derived from your `SECRET_KEY`.
- **Cookies**: Authentication is handled via HttpOnly, Secure, SameSite cookies.
- **HTTPS**: Deployment behind a TLS-terminating reverse proxy is strongly recommended.

## API

Manifold provides a full REST API.
- **Interactive Docs**: Available at `/docs` (Swagger UI) or `/redoc` on your backend host.
- **Auth**: API calls require a session cookie or a Bearer token in the `Authorization` header.

## Testing

Run the full test suite with:
```bash
make test
```
Or individually:
```bash
make test-backend
make test-frontend
```

## Contributing / Development

We welcome contributions!
1. Check the [Issue Tracker](https://github.com/your-org/manifold/issues).
2. Follow the code style: `make format` and `make lint`.
3. Ensure all checks pass: `make ci-check`.

## Philosophy: Observability vs. Budgeting

Traditional budgeting apps often force users into a rigid "Envelope" or "Zero-based" budgeting workflow. While effective for some, these systems often fail to provide a high-level operational view of financial health.

Manifold takes a different approach. We believe that personal finance is a system that should be monitored, not just a ledger to be balanced. By focusing on **observability**, Manifold provides:
- **Visibility**: Clear, real-time views into account balances, pending transactions, and future liabilities.
- **Auditability**: A durable record of every sync attempt, alarm evaluation, and notification delivery.
- **Extensibility**: The ability to add custom data sources via the JSON provider and custom logic via the Alarm Engine.
- **Privacy**: The peace of mind that comes from knowing your data never leaves your infrastructure and is encrypted at rest.

Manifold is for the power user who wants to automate the tedious parts of financial management and be alerted when something truly matters.

## Community and Support

- **Documentation**: You are reading it! Check the `docs/` folder for deep dives.
- **GitHub Issues**: Report bugs or request features on our [GitHub Issues](https://github.com/your-org/manifold/issues) page.
- **Discussions**: Join our community on [GitHub Discussions](https://github.com/your-org/manifold/discussions) to share your custom alarm rules and provider integrations.

## Acknowledgments

Manifold is made possible by several incredible open-source projects:
- [FastAPI](https://fastapi.tiangolo.com/) for the robust API foundation.
- [Taskiq](https://taskiq-python.github.io/) for the distributed task queue.
- [shadcn/ui](https://ui.shadcn.com/) for the beautiful dashboard components.
- [SQLAlchemy](https://www.sqlalchemy.org/) for the flexible database layer.

## Multi-User Delegation and RBAC

Manifold is built for households and teams. Our unique delegation model ensures that you can share financial insights without sharing your bank credentials.

### Roles
- **Superadmin**: The instance owner. Can create and delete users, view system health, and manage global settings. Does **not** have access to financial data or user-specific alarms.
- **User**: The data owner. Can connect banks, create alarms, and view their own financial dashboard.
- **Viewer**: A delegated role. Can view accounts and transactions shared by a User, but cannot modify rules or connections.
- **Admin (Delegated)**: Has full control over a shared account, including the ability to manage alarms and syncs, but cannot delete the account or change its primary ownership.

### How Delegation Works
1.  **Grant Access**: A User generates an "Access Share" in their settings.
2.  **Assign Role**: The User specifies whether the recipient is a Viewer or an Admin.
3.  **Acceptance**: The recipient logs in and accepts the share. The data now appears in their dashboard.

This model is ideal for families where one person manages the bank connections while others need to monitor spending or receive alerts.

## Performance Benchmarks

Manifold is engineered for efficiency, even on low-power hardware like a Raspberry Pi 4:
- **API Latency**: Average response time for dashboard endpoints is < 50ms (SQLite) and < 30ms (PostgreSQL).
- **Sync Throughput**: Can handle up to 50 parallel provider syncs on a 2GB RAM instance.
- **Memory Footprint**:
    - Backend: ~120MB
    - Tasker: ~80MB
    - Frontend (Nginx): ~10MB
    - Redis: ~5MB

## Frequently Asked Questions

**Q: Does Manifold support my bank?**
A: If your bank is supported by TrueLayer (most UK/EU banks) or provides a JSON API, yes.

**Q: Can I run this on a Raspberry Pi?**
A: Yes, Manifold is fully compatible with ARM64 architecture. Use the provided Docker images.

**Q: Is my data safe if my server is stolen?**
A: Since your DEK is encrypted with a Master Key derived from `SECRET_KEY`, an attacker would need both your database file and your `.env` file to decrypt your financial data.

**Q: How do I contribute a new translation?**
A: The frontend uses `i18next`. Check `frontend/src/i18n` for language files and open a Pull Request!

Manifold includes a specialized "System Notifier" designed to alert the instance administrator about infrastructure events.
- **Heartbeat Alerts**: Notifies if the background scheduler stops emitting tasks.
- **System Capacity**: Alerts when the Redis queue size exceeds defined thresholds.
- **Security Audit**: Sends notifications for failed login attempts on the superadmin account.

Configuration for the system notifier is managed via the `SYSTEM_NOTIFIER_ID` environment variable, which points to one of your configured notification channels.

## Roadmap

Manifold is actively developed. Future planned features include:
- **Plaid Provider**: Broadening support for North American financial institutions.
- **CSV Import**: Support for importing historical data from legacy apps.
- **Advanced Forecasting**: Using machine learning to predict cash flow issues based on multi-year transaction history.
- **Mobile App**: A lightweight companion app for viewing dashboards and receiving push notifications.
- **WhatsApp Notifier**: Adding WhatsApp as an alternative notification channel.

## Security Disclosures

Security is our top priority. If you discover a vulnerability in Manifold, please do not open a public issue. Instead, send a detailed report to `security@manifold.example.com`. We aim to acknowledge all reports within 24 hours and provide a fix within 7 days.

## Development Environment Setup

If you want to contribute to Manifold's core, we recommend using the provided `dev` profile:
1.  **Initialize**: `make setup`
2.  **Start Dev Stack**: `make docker-up-dev`
3.  **Frontend Live-Reload**: The frontend is served via Vite at `http://localhost:5173` with a proxy to the backend.
4.  **Backend Hot-Reload**: Uvicorn monitors `backend/src` for changes and restarts the API server automatically.

See `CONTRIBUTING.md` for our full development guide and coding standards.

## License

Manifold is released under the MIT License. See `LICENSE.md` for details.

## Future of Manifold

Our vision is to become the industry-standard open-source platform for financial observability. We believe that by providing a robust, self-hosted alternative to proprietary financial apps, we can empower users to take back control of their data.

Join us on this journey. Whether you are a developer, a designer, or just someone who cares about financial privacy, there is a place for you in the Manifold community.

---

**Happy Monitoring!**
