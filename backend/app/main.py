
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import update

from .db import SessionLocal, init_db
from .models import Document
from .routers import abha, auth, documents, profile, family

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    auth.router,
    documents.router,
    profile.router,
    abha.router,
    family.router,
):
    app.include_router(r)
