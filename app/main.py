from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import close_db, init_db
from app.routers import auth, health, ingest, review, telegram


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    close_db()


app = FastAPI(title="Expense Review Automation", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(telegram.router)
app.include_router(review.router)
app.include_router(auth.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "expense-review-automation", "status": "ok"}
