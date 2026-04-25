# Manifold

Self-hosted financial observability platform.

## Milestone 1

Foundation monorepo with:

- FastAPI backend
- React + Vite frontend
- SQLite / PostgreSQL / MariaDB database backend abstraction
- Cookie-based auth with bootstrap superadmin flow
- Docker Compose stack
- GitHub Actions workflows

## Quick start

1. Copy `.env.example` to `.env`
2. Fill `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`
3. Start stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Local backend verification

```bash
cd backend
uv sync --extra all-backends
uv run alembic upgrade head
uv run python -c "from manifold.main import create_app; app = create_app(); print('OK')"
```

## Security notes

- Same-origin cookie auth required for browser flows
- In production, run behind HTTPS reverse proxy
- `SECRET_KEY` derives separate JWT-signing and DEK-master keys via HKDF-SHA256
- Per-user DEKs are wrapped with AES-256-GCM

## License

See `LICENSE.md`.
