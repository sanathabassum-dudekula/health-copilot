
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import update

from .db import SessionLocal, init_db
from .models import Document
from .routers import (
    abha,
    assistant,
    auth,
    documents,
    family,
    insights,
    profile,
    reminders,
    vitals,
)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        db.execute(
            update(Document)
            .where(Document.status == "processing")
            .values(
                status="failed",
                extraction={"_error": "interrupted by server restart"},
            )
        )
        db.execute(
            update(Document)
            .where(Document.status == "summarizing")
            .values(status="done")
        )
        db.commit()
    yield


app = FastAPI(title="Health Copilot", lifespan=lifespan)

for r in (
    abha.router,
    assistant.router,
    auth.router,
    documents.router,
    family.router,
    insights.router,
    profile.router,
    reminders.router,
    vitals.router,
):
    app.include_router(r)
