from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from taskiq_fastapi import init as taskiq_init

from manifold.api.accounts import router as accounts_router
from manifold.api.admin import router as admin_router
from manifold.api.alarms import router as alarms_router
from manifold.api.auth import router as auth_router
from manifold.api.cards import router as cards_router
from manifold.api.connections import router as connections_router
from manifold.api.dashboard import router as dashboard_router
from manifold.api.events import router as events_router
from manifold.api.notification_deliveries import router as notification_deliveries_router
from manifold.api.notifiers import router as notifiers_router
from manifold.api.providers import router as providers_router
from manifold.api.recurrence_profiles import router as recurrence_profiles_router
from manifold.api.settings import router as settings_router
from manifold.api.sync import router as sync_router
from manifold.api.transactions import router as transactions_router
from manifold.api.users import router as users_router
from manifold.config import settings
from manifold.database import AsyncSessionLocal, engine
from manifold.domain.users import create_user_record
from manifold.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from manifold.exceptions import (
    ValidationError as DomainValidationError,
)
from manifold.logging import configure_logging, request_id_var
from manifold.models.user import User
from manifold.notifiers.registry import register_all as register_notifiers
from manifold.providers.registry import register_all as register_providers
from manifold.schemas.common import HealthResponse
from manifold.tasks.broker import broker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    register_providers()
    register_notifiers()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count()).select_from(User))
        if int(result.scalar_one()) == 0:
            if not settings.admin_username or not settings.admin_password:
                raise RuntimeError(
                    "ADMIN_USERNAME and ADMIN_PASSWORD must be set when users table is empty"
                )
            await create_user_record(
                username=settings.admin_username,
                password=settings.admin_password,
                role="superadmin",
                must_change_password=True,
                session=session,
            )

    if not broker.is_worker_process:
        try:
            await broker.startup()
        except Exception as exc:  # noqa: BLE001
            import structlog

            structlog.get_logger().warning(
                "broker.startup_failed",
                error=str(exc),
                detail=(
                    "Background tasks unavailable — Redis unreachable. "
                    "Auth and API endpoints are functional."
                ),
            )
    try:
        yield
    finally:
        if not broker.is_worker_process:
            try:
                await broker.shutdown()
            except Exception:  # noqa: BLE001
                pass


def create_app() -> FastAPI:
    app = FastAPI(title="Manifold", lifespan=lifespan)
    taskiq_init(broker, app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request, call_next):
        import uuid

        token = request_id_var.set(str(uuid.uuid4()))
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id_var.get() or ""
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AuthorizationError)
    async def authz_handler(_request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(DomainValidationError)
    async def validation_handler(_request: Request, exc: DomainValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health", operation_id="healthCheck", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return {"status": "ok"}

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    app.include_router(providers_router, prefix="/api/v1/providers", tags=["providers"])
    app.include_router(connections_router, prefix="/api/v1/connections", tags=["connections"])
    app.include_router(accounts_router, prefix="/api/v1/accounts", tags=["accounts"])
    app.include_router(alarms_router, prefix="/api/v1/alarms", tags=["alarms"])
    app.include_router(sync_router, prefix="/api/v1", tags=["sync"])
    app.include_router(transactions_router, prefix="/api/v1/transactions", tags=["transactions"])
    app.include_router(cards_router, prefix="/api/v1/cards", tags=["cards"])
    app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])
    app.include_router(settings_router, prefix="/api/v1", tags=["settings"])
    app.include_router(events_router, prefix="/api/v1", tags=["events"])
    app.include_router(
        recurrence_profiles_router,
        prefix="/api/v1/recurrence-profiles",
        tags=["recurrence"],
    )
    app.include_router(notifiers_router, prefix="/api/v1/notifiers", tags=["notifiers"])
    app.include_router(
        notification_deliveries_router,
        prefix="/api/v1/notification-deliveries",
        tags=["notifications"],
    )
    app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
    return app


app = create_app()
