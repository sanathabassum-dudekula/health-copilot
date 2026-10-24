
import io
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..access import is_requested_profile
from ..auth import active_profile
from ..db import get_db
from ..ingestion.graph import run_ingest
from ..ingestion.summarize import LANGS, translate_summary
from ..models import Document, Profile
from ..storage import delete_file, download_file, upload_file as store_file

router = APIRouter(prefix="/documents", tags=["documents"])
log = logging.getLogger(__name__)

EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}
MAX_BYTES = 15 * 1024 * 1024


def _own(db: Session, profile: Profile, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if not doc or doc.profile_id != profile.id:
        raise HTTPException(404, "Document not found")
    return doc


def _row(o):
    return {
        c.name: getattr(o, c.name)
        for c in o.__table__.columns
        if c.name != "profile_id"
    }


def doc_brief(d: Document) -> dict:
    return {
        "id": d.id,
        "doc_type": d.doc_type,
        "doc_date": d.doc_date,
        "facility": d.facility,
        "status": d.status,
        "source": d.source,
        "created_at": d.created_at,
    }


@router.post("")
async def upload(
    file: UploadFile,
    bg: BackgroundTasks,
    profile_oid: str | None = None,
    p: Profile = Depends(active_profile),
    db: Session = Depends(get_db),
):
    if not is_requested_profile(p, profile_oid):
        raise HTTPException(404, "Profile not found")

    if file.content_type not in EXT:
        raise HTTPException(415, "Only JPG, PNG or PDF files are accepted")

    data = await file.read()

    if not data:
        raise HTTPException(400, "The uploaded file is empty")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 15 MB")

    doc = Document(
        profile_id=p.id,
        mime=file.content_type,
        status="processing",
        source="upload",
    )
    db.add(doc)
    db.flush()

    key = f"uploads/{p.id}/{doc.id}/original{EXT[file.content_type]}"

    try:
        store_file(key, data, file.content_type)
        doc.file_path = key
        db.commit()
        db.refresh(doc)
    except (BotoCoreError, OSError, SQLAlchemyError, ValueError):
        db.rollback()
        try:
            delete_file(key)
        except (BotoCoreError, OSError, ValueError):
            log.exception("Could not clean up a failed document upload")
        log.exception("Could not persist an uploaded document")
        raise HTTPException(
            502, "Could not save the document to secure storage"
        )

    bg.add_task(run_ingest, doc.id, p.id)
    return doc_brief(doc)


@router.get("")
def list_documents(
    profile_oid: str | None = None,
    p: Profile = Depends(active_profile),
    db: Session = Depends(get_db),
):
    if not is_requested_profile(p, profile_oid):
        raise HTTPException(404, "Profile not found")

    docs = db.scalars(
        select(Document)
        .where(Document.profile_id == p.id)
        .order_by(Document.created_at.desc())
    )
    return [doc_brief(d) for d in docs]


@router.get("/{doc_id}")
def get_document(
    doc_id: int,
    p: Profile = Depends(active_profile),
    db: Session = Depends(get_db),
):
    d = _own(db, p, doc_id)

    return {
        **doc_brief(d),
        "practitioner": d.practitioner,
        "admission_date": d.admission_date,
        "discharge_date": d.discharge_date,
        "extraction": d.extraction,
        "summary": d.summary,
        "observations": [_row(o) for o in d.observations],
        "medications": [_row(m) for m in d.medications],
        "conditions": [_row(c) for c in d.conditions],
        "allergies": [_row(a) for a in d.allergies],
    }


@router.get("/{doc_id}/file")
def get_file(
    doc_id: int,
    p: Profile = Depends(active_profile),
    db: Session = Depends(get_db),
):
    d = _own(db, p, doc_id)

    if not d.file_path:
        raise HTTPException(404, "No original file for this document")

    filename = Path(d.file_path).name
    try:
        with TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / filename
            download_file(d.file_path, str(destination))
            data = destination.read_bytes()
    except FileNotFoundError:
        raise HTTPException(404, "Original document not found in storage")
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            raise HTTPException(404, "Original document not found in storage") from exc
        raise

    return StreamingResponse(
        io.BytesIO(data),
        media_type=d.mime or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        },
    )


@router.get("/{doc_id}/summary")
def get_summary(
    doc_id: int,
    lang: str = "en",
    p: Profile = Depends(active_profile),
    db: Session = Depends(get_db),
):
    d = _own(db, p, doc_id)

    if not d.summary:
        raise HTTPException(409, "Summary not ready")

    if lang == "en":
        return d.summary

    if lang not in LANGS:
        raise HTTPException(
            422, f"Supported languages: en, {', '.join(LANGS)}"
        )

    cached = d.summary_i18n or {}

    if lang not in cached:
        cached = {
            **cached,
            lang: translate_summary(d.summary, lang),
        }
        d.summary_i18n = cached
        db.commit()

    return cached[lang]
