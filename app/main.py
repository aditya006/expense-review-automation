from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.db import close_db, init_db
from app.routers import admin, auth, health, ingest, review, telegram
from app.security import validate_runtime_config

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_config()
    init_db()
    yield
    close_db()


is_prod = settings.app_env.lower() == "production"
docs_disabled = is_prod and settings.disable_docs_in_production

app = FastAPI(
    title="Expense Review Automation",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if docs_disabled else "/docs",
    redoc_url=None if docs_disabled else "/redoc",
    openapi_url=None if docs_disabled else "/openapi.json",
)

if settings.allowed_hosts != "*":
    hosts = [h.strip() for h in settings.allowed_hosts.split(",") if h.strip()]
    if hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(telegram.router)
app.include_router(review.router)
app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "expense-review-automation", "status": "ok"}
