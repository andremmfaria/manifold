from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from taskiq_fastapi import init as taskiq_init

from manifold.api.auth import router as auth_router
from manifold.api.users import router as users_router
from manifold.config import settings
from manifold.database import AsyncSessionLocal, engine
from manifold.domain.users import create_user_record
from manifold.logging import configure_logging, request_id_var
from manifold.models.user import User
from manifold.tasks.broker import broker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    return app


app = create_app()
