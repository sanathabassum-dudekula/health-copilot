

import io
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_profile
from ..config import settings
from ..db import get_db
from ..ingestion.classify import classify_document
from ..ingestion.graph import run_ingest
from ..ingestion.summarize import LANGS, translate_summary
from ..models import Document, Profile
from ..storage import get_s3_client, upload_file as store_file, delete_file

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
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    # Check the supplied MIME type.
    if file.content_type not in EXT:
        raise HTTPException(
            415, "Only JPG, PNG or PDF files are accepted"
        )

    data = await file.read()

    if not data:
        raise HTTPException(400, "The uploaded file is empty")

    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 15 MB")

    # Screen the actual document before creating a database record
    # or uploading it to permanent storage.
    try:
        classification = classify_document(data, file.content_type)
    except Exception:
        log.exception("Could not screen uploaded document")
        raise HTTPException(
            503,
            "We couldn't verify this document right now. Please try again.",
        )

    # An uncertain result is not treated as proof that a document
    # is non-medical. Ask the user to retry with a clearer document.
    if classification.confidence < 0.80:
        raise HTTPException(
            422,
            "We couldn't confidently identify this as a medical document. "
            "Please upload a clearer medical report or image.",
        )

    if not classification.is_medical:
        raise HTTPException(
            422,
            "This doesn't appear to be a medical document. "
            "Please upload a prescription, medical report, test result, "
            "or another document related to your health.",
        )

    # Only create and store the document after screening passes.
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
    except Exception:
        log.exception("Could not save uploaded document %s", doc.id)
        db.rollback()
        try:
            delete_file(key)
        except Exception:
            log.exception("Could not clean up failed upload for document %s", doc.id)
        raise HTTPException(
            502, "Could not save the document to secure storage"
        )

    bg.add_task(run_ingest, doc.id, p.id)
    return doc_brief(doc)


@router.get("")
def list_documents(
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    docs = db.scalars(
        select(Document)
        .where(Document.profile_id == p.id)
        .order_by(Document.created_at.desc())
    )
    return [doc_brief(d) for d in docs]


@router.get("/{doc_id}")
def get_document(
    doc_id: int,
    p: Profile = Depends(current_profile),
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
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    d = _own(db, p, doc_id)

    if not d.file_path:
        raise HTTPException(404, "No original file for this document")

    try:
        obj = get_s3_client().get_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=d.file_path,
        )
        data = obj["Body"].read()
    except Exception:
        raise HTTPException(
            404, "Original document not found in storage"
        )

    filename = Path(d.file_path).name

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
    p: Profile = Depends(current_profile),
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
