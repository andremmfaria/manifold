# Deployment Guide

Manifold is designed for reliability and ease of self-hosting. This guide covers everything from basic Docker setup to advanced production configurations.

## Production Requirements

Before deploying, ensure your environment meets these minimum specifications:

- **Operating System**: Linux (Ubuntu 22.04+ recommended)
- **Memory**: 1GB RAM minimum (2GB recommended if running many syncs)
- **Disk**: 5GB available space (SQLite databases can grow over time)
- **Network**: Public IP or a tunnel (like Cloudflare Tunnel) if using Open Banking callbacks.
- **Tools**: Docker and Docker Compose installed.

## Docker Compose Deployment

This is the recommended path for most users.

### 1. Prepare Environment

```bash
git clone https://github.com/your-org/manifold.git
cd manifold
cp .env.example .env
```

### 2. Generate Secrets

Set a strong, unique `SECRET_KEY`.

```bash
# Generate 64-character hex string
openssl rand -hex 32
# Paste into .env as SECRET_KEY
```

### 3. Configure Database

By default, Manifold uses SQLite. To use an external database, update `DATABASE_URL` in `.env`:

- **PostgreSQL**: `postgresql+asyncpg://user:pass@db-host:5432/manifold`
- **MariaDB**: `mysql+asyncmy://user:pass@db-host:3306/manifold`

### 4. Start the Stack

```bash
docker compose up -d
```

### 5. Initialize the Superadmin

If this is a fresh install, initialize your first user:

```bash
docker compose exec backend uv run manifold create-user admin your-secure-password --role superadmin
```

## HTTPS and Reverse Proxy

Open Banking (TrueLayer) requires HTTPS for callbacks.

### Built-in Proxy

You can enable a basic self-signed HTTPS proxy for local testing:

```bash
docker compose --profile https up -d
```

Access at `https://localhost:3443`.

### External Reverse Proxy (Recommended)

For production, use a proper proxy like Caddy or Nginx with Let's Encrypt.
**Caddy Example**:

```text
manifold.example.com {
    reverse_proxy localhost:3000
}
```

## Database Setup

### PostgreSQL

1. Create a database: `CREATE DATABASE manifold;`
2. Create a user: `CREATE USER manifold WITH PASSWORD 'your_password';`
3. Grant permissions: `GRANT ALL PRIVILEGES ON DATABASE manifold TO manifold;`
4. Update `.env`: `DATABASE_URL=postgresql+asyncpg://manifold:your_password@localhost:5432/manifold`

### MariaDB

1. Create a database: `CREATE DATABASE manifold;`
2. Create a user: `CREATE USER 'manifold'@'%' IDENTIFIED BY 'your_password';`
3. Grant permissions: `GRANT ALL PRIVILEGES ON manifold.* TO 'manifold'@'%';`
4. Update `.env`: `DATABASE_URL=mysql+asyncmy://manifold:your_password@localhost:3306/manifold`

### Migration Sequence

Manifold uses Alembic. Migrations run automatically on startup (or manually via `alembic upgrade head`). The full ordered sequence is:

| Revision | Description |
|---|---|
| `0001_initial` | Core schema — users, connections, accounts, transactions |
| `0002_data_in` | Provider-specific data tables |
| `0003_alarms_notifiers` | Alarm engine and notifier configuration tables |
| `0004_user_names` | Display name columns on the users table |
| `0005_account_identity` | Account identity grouping — `account_identities` table and `accounts.identity_id` FK |
| `0006_txn_dedup` | Cross-connection transaction deduplication columns (`identity_dedup_hash`, `content_hash`, `is_cross_connection_duplicate`) |
| `0007_email_subsystem` | Email subsystem tables — `instance_email_settings`, `email_suppression`, `email_webhook_events` |

## Backup Strategy

Your financial data is valuable. Back it up regularly.

- **SQLite**: Simply back up the `/app/data/manifold.db` file (or the Docker volume).
- **PostgreSQL**:

  ```bash
  docker exec -t manifold-db pg_dump -U manifold manifold > backup.sql
  ```

- **MariaDB**:

  ```bash
  docker exec manifold-db mysqldump -u manifold -p manifold > backup.sql
  ```

## SECRET_KEY Rotation

If your `SECRET_KEY` is compromised, you must rotate it.
**Warning**: Rotating the key means all existing encrypted Data Encryption Keys (DEKs) will become unreadable. You will need to re-link all provider connections.

1. Generate a new key.
2. Update `.env`.
3. Restart the stack.
4. Users will need to re-authorize their bank connections.

## Email Transport Configuration

Manifold ships a pluggable email transport layer used for alarm notifications and system messages. The active provider and its credentials are stored encrypted in the database via the admin UI (`/settings/email`). The following adapters are supported: `smtp`, `ses`, `resend`, `postmark`, `mailgun`, `brevo`.

The SMTP adapter can also be seeded from environment variables as a convenience for first-run or self-hosted setups where a UI config step is undesirable:

| Variable | Default | Purpose |
|---|---|---|
| `SMTP_HOST` | _(empty)_ | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `SMTP_USER` | _(empty)_ | SMTP authentication username |
| `SMTP_PASSWORD` | _(empty)_ | SMTP authentication password |
| `SMTP_FROM_ADDRESS` | _(empty)_ | Envelope `From` address |

For API-based providers (SES, Resend, Postmark, Mailgun, Brevo), credentials and provider-specific keys (e.g. API keys, signing secrets) are stored exclusively in the encrypted `instance_email_settings` database row — they are not read from environment variables.

### Bounce and Complaint Webhook

To keep the suppression list up to date, register the following URL with your email provider's bounce/complaint webhook settings:

```
POST https://<your-domain>/api/v1/email/webhooks/{provider}
```

Replace `{provider}` with the lowercase adapter name (e.g. `ses`, `postmark`, `mailgun`, `resend`, `brevo`). The SMTP adapter does not support webhooks.

Each provider requires a signing secret or token to authenticate inbound webhook requests. Set this in the encrypted provider config via the admin UI — the field name varies by adapter (`webhook_secret`, `webhook_signing_key`, or `webhook_token`).

## Upgrade Procedure

1. Pull the latest code: `git pull origin main`
2. Pull new images: `docker compose pull`
3. Restart the stack: `docker compose up -d`
4. Run migrations: `docker compose exec backend uv run alembic upgrade head`
5. **If upgrading from a release prior to `0005_account_identity`**, run the identity backfill to assign existing accounts to identity groups:

   ```bash
   docker compose exec backend uv run manifold backfill-identities
   ```

   This command is idempotent — it is safe to run multiple times. A second run with no new unassigned accounts exits cleanly. It must be run after migrations complete and before the next sync cycle to ensure cross-connection deduplication (migration `0006_txn_dedup`) operates correctly.

   For more detail on the identity model, see `docs/account-identity.md`.

## Health Checks and Troubleshooting

### Health Check

Monitor the system status at:
`GET /health` -> Returns `{"status": "ok"}`

### Common Issues

- **Redis Connection**: If the worker fails to start, ensure `manifold-redis` is healthy.
- **CORS Errors**: Check `ALLOWED_ORIGINS` in `.env`. It must match the URL you use to access the frontend.
- **OAuth Callback Failure**: Ensure `TRUELAYER_REDIRECT_URI` matches exactly what is configured in the TrueLayer console and includes the correct protocol (https).
- **Migration Issues**: If migrations fail on SQLite, ensure no other process is holding a lock on the database file.

## Post-Deployment Optimization

### Tuning Redis

For larger deployments, consider these Redis optimizations:

- **Persistence**: While the task queue is transient, enabling RDB snapshots can help recover the schedule state after a full system reboot.
- **Memory Limit**: Set `maxmemory` to prevent Redis from consuming all system RAM if the task queue grows unexpectedly.

### Log Rotation

Docker logs can consume significant disk space. Ensure your `docker-compose.yml` or global Docker config includes log rotation:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### Monitoring the Stack

- **Dashboard**: The Manifold frontend includes a "System Health" view for administrators.
- **External Uptime**: Use a tool like Uptime Kuma to monitor the `/health` endpoint.
- **Resource Monitoring**: `docker stats` is a quick way to check CPU and RAM usage of the Manifold containers.

## Security Hardening

For production environments exposed to the internet:

1. **Strict CORS**: Limit `ALLOWED_ORIGINS` to the exact domain where the frontend is hosted.
2. **Firewall**: Only open ports `80` and `443` (or your chosen proxy ports) to the public internet. Keep Redis and the Database ports blocked.
3. **App Environment**: Ensure `APP_ENV=production` is set in your `.env`. This enables secure cookie flags and disables debug-level error responses.
4. **Updates**: Subscribe to the Manifold security advisory mailing list (or watch the GitHub repository) for updates.

## Migration from SQLite to PostgreSQL

If you start with SQLite and wish to upgrade as your data grows:

1. **Stop Services**: Stop the Manifold stack.
2. **Export Data**: Use a tool like `pgloader` or a custom script to migrate the `.db` file to a fresh PostgreSQL instance.
3. **Update Config**: Change the `DATABASE_URL` in your `.env`.
4. **Run Migrations**: Run `alembic upgrade head` to ensure the schema is synchronized.
5. **Restart**: Start the services.

## Advanced Deployment Configurations

### High-Availability Redis

For enterprise-grade self-hosting, you can point Manifold to a Redis Cluster or a managed Redis instance. Update your `REDIS_URL`:
`REDIS_URL=rediss://:password@your-redis-cluster:6380/0`
Ensure that your Redis version is 7.0 or higher to support the advanced locking and stream features used by Taskiq.

### Custom Python Packages

If you need to install additional Python packages (e.g., for a custom notifier), you can extend the backend image:

```dockerfile
FROM ghcr.io/your-org/manifold-backend:latest
RUN uv pip install some-custom-package
```

### Resource Limits and Quotas

In a shared hosting environment, it is good practice to limit the resources consumed by the Manifold containers. You can do this in your `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
```

## Troubleshooting and Debugging

### Accessing the Database Shell

- **SQLite**:

  ```bash
  docker compose exec backend sqlite3 /app/data/manifold.db
  ```

- **PostgreSQL**:

  ```bash
  docker compose exec backend psql $DATABASE_URL
  ```

### Manual Task Execution

Sometimes you may want to trigger a task manually from the CLI to see its output in real-time:

```bash
docker compose exec backend uv run taskiq run manifold.tasks.sync:sync_connection --args '["connection-uuid"]'
```

### Inspecting Redis

To see the current task queue or active locks:

```bash
docker compose exec manifold-redis redis-cli
> keys *
> LRANGE taskiq:queue 0 -1
```

## Monitoring and Alerting

We recommend setting up basic monitoring to ensure your Manifold instance is running smoothly.

### Log Management with Promtail/Loki

If you use Grafana, you can ship Manifold logs (which are in JSON format by default) to Loki. This allows you to create dashboards for:

- Sync success vs failure rates.
- Alarm firing frequency.
- API response time percentiles.

### Uptime Monitoring

Set up an external heartbeat check on the `/health` endpoint. If the endpoint returns anything other than `200 OK`, it indicates that either the backend is down or the database is unreachable.

## Migration and Disaster Recovery

### Full System Backup

To back up the entire Manifold state, you need two things:

1. **The Database**: As covered in the Backup Strategy section.
2. **The .env file**: This contains your `SECRET_KEY`, which is the only way to decrypt your data. **Store this file separately and securely.**

### Restore Procedure

1. Set up a fresh Manifold instance with the **same** `SECRET_KEY` as the original.
2. Restore the database from your backup.
3. The system should immediately recognize the existing data and encrypted keys.

## Deployment Checklist

Before going "live" with your Manifold instance, verify the following:

- [ ] `SECRET_KEY` is a strong, random 64-character string.
- [ ] `APP_ENV` is set to `production`.
- [ ] `ALLOWED_ORIGINS` is restricted to your exact frontend domain.
- [ ] `TRUELAYER_REDIRECT_URI` is set to your public HTTPS callback URL and matches the TrueLayer console.
- [ ] `TRUELAYER_SANDBOX` is set to `false` for production (default is `false`).
- [ ] Database is being backed up at least daily.
- [ ] `.env` file is stored in a secure backup location.
- [ ] HTTPS is correctly configured and the certificate is valid.
- [ ] If email notifications are required, the email transport is configured in the admin UI and the bounce/complaint webhook URL is registered with your provider.
- [ ] If upgrading from before `0005_account_identity`, the identity backfill (`manifold backfill-identities`) has been run after migrations.
- [ ] You have successfully performed a test sync and received a test notification.
