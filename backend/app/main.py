"""Точка входа FastAPI."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import account_prep, auth, campaigns, health, jobs, prepared_accounts
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
    allow_headers=["*", "Authorization", "Content-Type"],
    expose_headers=["*"],
)

register_error_handlers(app)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(campaigns.router, prefix="/api/v1", tags=["campaigns"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(account_prep.router, prefix="/api/v1", tags=["account-prep"])
app.include_router(prepared_accounts.router, prefix="/api/v1", tags=["prepared-accounts"])


@app.on_event("startup")
async def startup() -> None:
    Config.validate()
    await init_pool()
    await init_redis(Config.REDIS_URL)
    logger.info("API started (env=%s)", os.getenv("ENVIRONMENT", "development"))


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
