# Contributing to Manifold

Thanks for contributing! This guide covers how the repo is laid out, the day-to-day
workflow, and the **best practices for each component** (Python/FastAPI backend,
React/TypeScript frontend). Following these keeps CI green and the codebase consistent.

> **TL;DR:** Backend uses **absolute `manifold.*` imports** + `ruff`/`mypy`/`pytest`.
> Frontend uses **explicit named imports** + the `@/` alias + `eslint`/`tsc`/`vitest`.
> Commits follow **Conventional Commits**. Run `make ci-check` before you push.

---

## 1. Repository layout

Manifold is a **monorepo**:

```
manifold/
├── backend/              # Python / FastAPI API + background worker
│   ├── src/manifold/     # application package (imported as `manifold.*`)
│   ├── tests/            # unit/ + integration/ + fixtures/
│   └── migrations/       # Alembic migrations
├── frontend/             # React + Vite single-page app
│   └── src/              # @/ alias points here
├── samples/              # JSON fixtures for the file-based provider
├── docs/                 # architecture.md, providers.md, alarm-engine.md, deployment.md
├── ops/                  # deployment helpers
├── .github/workflows/    # CI (backend-ci, frontend-ci, release)
├── Makefile              # task automation — start here
├── docker-compose.yml / docker-compose.dev.yml
└── README.md
```

The root **`Makefile`** is the single entry point for every common task. Prefer its
targets over remembering raw commands.

---

## 2. Prerequisites & setup

- **Python 3.12+** with [`uv`](https://github.com/astral-sh/uv) (the backend package manager)
- **Node.js 20+** with `npm`
- **Docker** (optional, for the full stack / alternate databases)

```bash
make setup            # install backend + frontend deps and copy .env files
```

Or individually:

```bash
make install-backend  # cd backend && uv sync
make install-frontend # cd frontend && npm ci
```

---

## 3. Development workflow

Run the pieces you need in separate terminals:

```bash
make dev-backend      # uvicorn (FastAPI) on :8000, --reload
make dev-frontend     # vite dev server on :5173 (proxies /api -> :8000)
make dev-worker       # taskiq worker + scheduler (background sync / alarms)
```

### Before you push — mirror CI locally

```bash
make ci-check         # lint + typecheck + test for both backend and frontend
```

Individual gates:

| Concern    | Backend                         | Frontend                          |
| ---------- | ------------------------------- | --------------------------------- |
| Lint       | `make lint-backend` (ruff)      | `make lint-frontend` (eslint)     |
| Format     | `make format-backend` (ruff)    | `make format-frontend` (prettier) |
| Type-check | `make typecheck-backend` (mypy) | `make typecheck-frontend` (tsc)   |
| Tests      | `make test-backend` (pytest)    | `make test-frontend` (vitest)     |

> CI runs on changes under `backend/**` and `frontend/**` separately. The backend job
> additionally runs `ruff format --check` and executes the full test suite against
> **SQLite, PostgreSQL, and MariaDB**. The frontend job runs typecheck → lint → test →
> build. Keep these green.

---

## 4. Branching, commits & pull requests

- **Branch** off `main`; never commit directly to `main`.
- **Commit messages** follow [Conventional Commits](https://www.conventionalcommits.org/):

  ```
  <type>(<scope>): <subject>
  ```

  - `type`: `feat`, `fix`, `refactor`, `docs`, `test`, `perf`, `chore`, `ci`
  - `scope`: the affected area, e.g. `connections`, `backend`, `frontend`, `json-provider`, `ci`
  - `subject`: imperative, lowercase, no trailing period

  Examples (from the real history):

  ```
  feat(connections): credential inputs per auth mode in connect/edit dialogs
  fix(transactions): set per-user DEK before query so encrypted columns decrypt
  test(json-provider): expand fixture + add multi-currency fixtures
  ```

- **Keep PRs focused.** One logical change per PR. Update tests and docs in the same PR.
- **A PR is ready when** `make ci-check` passes, new behavior has tests, and any schema
  change ships with an Alembic migration (see §6).

### Automated style enforcement (pre-commit)

Style is enforced by tooling, not by hand. A [`pre-commit`](https://pre-commit.com/)
config (`.pre-commit-config.yaml`) runs **ruff** (lint + format) on the backend and
**prettier** on the frontend, auto-fixing what it can before each commit. Set it up once:

```bash
pip install pre-commit            # or: pipx install pre-commit
pre-commit install                # install the git hook
cd frontend && npm ci             # so the prettier hook finds ./node_modules/.bin
pre-commit run --all-files        # optional: scan/fix the whole tree now
```

Cross-editor whitespace defaults live in `.editorconfig`. The hooks cover formatting and
fast lint only; heavier gates (mypy, tsc, eslint, tests) still run in CI / `make ci-check`,
so run those yourself before pushing.

---

## 5. Backend — Python / FastAPI best practices

Stack: **FastAPI**, **SQLAlchemy 2.0 (async)** + **SQLModel**, **Pydantic v2**, **Alembic**,
**taskiq** (background jobs), **structlog**. Tooling: `ruff` (lint + format, line length **100**,
rules `E,F,I,UP`) and `mypy`.

### Imports — use full-path absolute imports, never relative

The application package is importable as `manifold.*`. **Always** import from the full
path; do **not** use relative imports (`from ..deps import ...`).

```python
# ✅ Do
from manifold.api.deps import get_session, get_current_user
from manifold.models.user import User
from manifold.config import settings

# ❌ Don't
from ..deps import get_session
from .models.user import User
```

`ruff` rule `I` enforces import sorting — let `make format-backend` order them for you.

### API routers & dependency injection

- One `APIRouter` per resource module under `manifold/api/` (e.g. `users.py`, `accounts.py`).
- Use FastAPI **`Depends`** for cross-cutting concerns; the factories live in
  `manifold/api/deps.py` (`get_session`, `get_current_user`, `require_superadmin`, …).
- Give every route an explicit `operation_id` and a `response_model`.
- Declare a path with a static segment (e.g. `/by-username/{username}`) **before** a
  catch-all `/{id}` route, or order routes so the static one isn't shadowed.

```python
@router.get("/{user_id}", operation_id="getUser", response_model=UserResponse)
async def get_user(
    user_id: str,
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    ...
```

### Schemas vs models

- **Request/response shapes** are Pydantic v2 models in `manifold/schemas/`. Validate and
  serialize at the API boundary — don't return ORM objects directly.
- **Database models** live in `manifold/models/`, using SQLAlchemy 2.0 typed columns
  (`Mapped[...]` + `mapped_column(...)`) and the shared mixins (`UUIDPrimaryKeyMixin`,
  `TimestampMixin`).
- Sensitive columns use the encrypted field types from `manifold.security` — keep secrets
  encrypted at rest; never add a plaintext column for credential/PII data.

### Async & database access

- Everything I/O is **async**. Handlers and helpers that touch the DB take an
  `AsyncSession` and `await` their queries (`await session.execute(select(...))`).
- Prefer application-level logic inside the handler's transaction over extra round-trips.

### Migrations

Any change to a model needs an Alembic migration:

```bash
make db-revision MSG="add grantee_username to access grant"   # autogenerate
make db-migrate                                                # apply (upgrade head)
```

Review the generated migration by hand (autogenerate isn't perfect), and make sure it
works across SQLite/PostgreSQL/MariaDB — CI tests all three. Use batch mode for SQLite
alterations where required.

### Tests

- `pytest` with `pytest-asyncio` in **auto** mode (no `@pytest.mark.asyncio` needed for
  async tests). Layout: `tests/unit/`, `tests/integration/`, shared fixtures in
  `tests/conftest.py`, data in `tests/fixtures/`.
- Integration tests hit the app via `httpx.AsyncClient`. Add a test for every new
  endpoint and every bug fix (a failing test first, then the fix).

```bash
cd backend && uv run pytest tests/integration/test_users.py -q
```

---

## 6. Frontend — React / TypeScript best practices

Stack: **React 18** + **Vite**, **TypeScript (strict)**, **TanStack Router** (file-based)

- **TanStack Query**, **Tailwind CSS v4**, **shadcn/ui** (Radix primitives),
  **lucide-react** icons, **axios**. Tooling: `eslint` + `prettier`, tests via **vitest**.

### Imports — explicit named imports, not wildcards; use the `@/` alias

```ts
// ✅ Do — named imports via the @/ alias
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/useAuth";
import { Home, Bell, CreditCard } from "lucide-react";

// ❌ Don't — wildcard namespace imports or deep relative chains
import * as UI from "@/components/ui/button";
import { useAuth } from "../../../features/auth/useAuth";
```

- The `@/` alias maps to `frontend/src/` (configured in `tsconfig.json` and `vite.config.ts`).
- Import only what you use; pull individual icons from `lucide-react`, not the whole module.
- **Exception:** the generated shadcn/ui primitives in `src/components/ui/` use the
  library idiom `import * as React from "react"` / namespaced Radix imports. Leave those
  as the generator produces them; the "no wildcard" rule is for application code.

### Components & files

- **Function components only**, named in **PascalCase**; the file matches the component
  name (`ConnectionCard.tsx`).
- Reusable UI primitives live in `src/components/ui/` (shadcn). Feature code is grouped
  under `src/features/<feature>/` (component + its API calls + hooks). No barrel
  `index.ts` re-export files.
- Style with **Tailwind utility classes**; compose conditional classes with the `cn()`
  helper from `@/lib/utils`. Don't hand-roll components that shadcn already provides.

### Routing (TanStack Router)

- Routes are **file-based** under `src/routes/`, mirroring the URL. Each route file
  exports a `createRoute({...})`; routes are registered in `src/main.tsx`.
- Guard protected routes in `beforeLoad` (e.g. redirect unauthenticated users to
  `/login`). Use `params`/typed `Link`s rather than string-concatenated paths.

### Data fetching (TanStack Query)

- Fetch through **`useQuery`/`useMutation`**, not ad-hoc `useEffect` + `axios`. Use stable
  `queryKey`s and `invalidateQueries` after mutations to refresh the cache.
- The shared axios instance is `@/api/client`; per-resource calls live in `src/api/*.ts`.

### TypeScript

- `strict` is on — **type everything**; avoid `any`. Prefer precise prop types and
  discriminated unions over loose objects.
- Build must typecheck: `npm run build` runs `tsc -b` first.

### Formatting & lint

- Format with **Prettier** (`make format-frontend` / `npm run format`). The style is pinned
  in `frontend/.prettierrc.json`: **single quotes, no semicolons, 100-char width,
  2-space indent, trailing commas**. Let Prettier own these — don't style by hand. (Some
  older files predate the config; running `npm run format` normalizes them.)
- `eslint` enforces the React Hooks rules (`rules-of-hooks: error`,
  `exhaustive-deps: warn`). Fix warnings you introduce; don't add new ones.

### Tests

- **Vitest** + Testing Library. Co-locate tests in `__tests__/` next to the code
  (`src/features/alarms/__tests__/AlarmRuleBuilder.test.tsx`).

```bash
cd frontend && npm run test         # watch
cd frontend && npm run test -- --run # one-shot (as CI runs it)
```

---

## 7. Sample data

The file-based provider reads JSON fixtures from `samples/`. Generate bogus test data
of varying sizes with:

```bash
python samples/generate_samples.py            # writes samples/generated/*.json
python samples/generate_samples.py --help
```

The generated files conform to the JSON provider schema (see
`backend/src/manifold/providers/json_provider/`), so they can be used directly as a
file-connection source.

---

## 8. Docker & databases

```bash
make docker-up-dev    # full dev stack (build + up)
make docker-up        # production-style stack
make docker-down
```

The default dev database is SQLite. PostgreSQL and MariaDB are supported (and tested in
CI); install the drivers with `uv sync --extra all-backends` when working against them.

---

## 9. Further reading

- `docs/architecture.md` — system design and layer responsibilities
- `docs/providers.md` — adding a new data provider
- `docs/alarm-engine.md` — alarm rule evaluation
- `docs/deployment.md` — hosting / deployment

---

## 10. Quick reference

```bash
make setup            # one-time install
make dev-backend      # API   :8000
make dev-frontend     # SPA   :5173
make dev-worker       # background jobs
make db-revision MSG="..."   # new migration
make db-migrate              # apply migrations
make ci-check         # everything CI checks — run before pushing
```

Happy hacking! 🛠️
