"""Точка входа FastAPI."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import redirect as redirect_routes
from app.api.v1 import account_prep, auth, bots, campaigns, health, jobs, prepared_accounts, settings
from app.config import Config
from app.core import (
    LoggingMiddleware,
    SecurityHeadersMiddleware,
    init_logging,
    register_error_handlers,
)
from app.core.logging import get_logger
from app.infrastructure.cache.redis_client import close_redis, init_redis
from app.infrastructure.database.pool import close_pool, init_pool
from app.infrastructure.database.schema_patches import apply_startup_schema_patches

init_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=Config.APP_NAME,
    description="API автоматического создания Telegram-ботов",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=Config.CORS_SUPPORTS_CREDENTIALS,
    allow_methods=Config.CORS_METHODS,
    allow_headers=["*", "Authorization", "Content-Type", "Idempotency-Key"],
    expose_headers=["*"],
)

register_error_handlers(app)

app.include_router(redirect_routes.router)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(campaigns.router, prefix="/api/v1", tags=["campaigns"])
app.include_router(bots.router, prefix="/api/v1", tags=["bots"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(account_prep.router, prefix="/api/v1", tags=["account-prep"])
app.include_router(prepared_accounts.router, prefix="/api/v1", tags=["prepared-accounts"])
app.include_router(settings.router, prefix="/api/v1", tags=["settings"])


@app.on_event("startup")
async def startup() -> None:
    Config.validate()
    await init_pool()
    await apply_startup_schema_patches()
    await init_redis(Config.REDIS_URL)
    from app.domain.services import maintenance_service

    await maintenance_service.run_maintenance_cycle()
    logger.info(
        "API started (env=%s, admin_password_len=%d)",
        os.getenv("ENVIRONMENT", "development"),
        len(Config.ADMIN_PASSWORD),
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_pool()
    await close_redis()
    logger.info("API stopped")


@app.get("/")
async def root():
    return {"message": Config.APP_NAME, "version": "0.1.0"}


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": Config.APP_NAME}


if __name__ == "__main__":
    import uvicorn

    is_prod = os.getenv("ENVIRONMENT", "development") == "production"
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        reload=not is_prod,
    )
