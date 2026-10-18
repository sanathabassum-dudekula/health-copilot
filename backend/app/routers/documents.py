

import io
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import owns_or_links_profile, profile_for_owner
from ..auth import current_profile
from ..config import settings
from ..db import get_db
from ..ingestion.classify import classify_document
from ..ingestion.graph import run_ingest
from ..ingestion.normalize import normalize_record
from ..ingestion.schemas import DocumentExtraction
from ..ingestion.summarize import (
    LANGS,
    summarize as summarize_document,
    translate_summary,
)
from ..models import Allergy, Condition, Document, Medication, Observation, Profile
from ..storage import get_s3_client, upload_file as store_file, delete_file

router = APIRouter(prefix="/documents", tags=["documents"])
log = logging.getLogger(__name__)


class DocumentReview(BaseModel):
    decision: Literal["confirmed", "rejected"]
    extraction: DocumentExtraction | None = None

    @model_validator(mode="after")
    def validate_extraction_content(self):
        if self.extraction is None:
            return self
        if any(
            not item.test_name.strip() or not item.value.strip()
            for item in self.extraction.lab_results
        ):
            raise ValueError("Test names and reported values cannot be blank")
        if any(not item.name.strip() for item in self.extraction.medications):
            raise ValueError("Medicine names cannot be blank")
        if any(not item.name.strip() for item in self.extraction.diagnoses):
            raise ValueError("Diagnosis names cannot be blank")
        if any(not item.strip() for item in self.extraction.allergies):
            raise ValueError("Allergy names cannot be blank")
        return self


EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}
MAX_BYTES = 15 * 1024 * 1024


def _own(db: Session, profile: Profile, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    target = db.get(Profile, doc.profile_id) if doc else None
    if not doc or target is None or not owns_or_links_profile(profile, target, db):
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
        "review_status": d.review_status,
        "reviewed_at": d.reviewed_at,
        "source": d.source,
        "created_at": d.created_at,
    }


@router.post("")
async def upload(
    file: UploadFile,
    bg: BackgroundTasks,
    profile_oid: str | None = None,
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    target = profile_for_owner(p, db, profile_oid)
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
        profile_id=target.id,
        mime=file.content_type,
        status="processing",
        source="upload",
    )
    db.add(doc)
    db.flush()

    key = f"uploads/{target.id}/{doc.id}/original{EXT[file.content_type]}"

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

    bg.add_task(run_ingest, doc.id, target.id)
    return doc_brief(doc)


@router.get("")
def list_documents(
    profile_oid: str | None = None,
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    target = profile_for_owner(p, db, profile_oid)
    docs = db.scalars(
        select(Document)
        .where(Document.profile_id == target.id)
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
        "extraction": d.extraction if d.review_status != "rejected" else None,
        "summary": d.summary if d.review_status == "confirmed" else None,
        "observations": [_row(o) for o in d.observations],
        "medications": [_row(m) for m in d.medications],
        "conditions": [_row(c) for c in d.conditions],
        "allergies": [_row(a) for a in d.allergies],
    }


@router.post("/{doc_id}/review")
def review_document(
    doc_id: int,
    body: DocumentReview,
    bg: BackgroundTasks,
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    doc = _own(db, p, doc_id)
    if doc.status != "done":
        raise HTTPException(409, "Document processing is not complete")
    if doc.review_status != "pending":
        raise HTTPException(409, "This document has already been reviewed")

    doc.review_status = body.decision
    doc.reviewed_at = datetime.now(timezone.utc)
    doc.reviewed_by_profile_id = p.id
    if body.decision == "rejected":
        doc.observations.clear()
        doc.medications.clear()
        doc.conditions.clear()
        doc.allergies.clear()
        doc.extraction = None
        doc.summary = None
        doc.summary_i18n = None
    elif body.extraction is not None:
        target = db.get(Profile, doc.profile_id)
        if target is None:
            raise HTTPException(404, "Document not found")
        extraction = body.extraction.model_dump()
        record, warnings = normalize_record(
            extraction, target.name, target.dob, target.sex
        )
        doc.doc_type = record["doc_type"]
        doc.doc_date = record["doc_date"]
        doc.facility = record["facility"]
        doc.practitioner = record["practitioner"]
        doc.admission_date = record["admission_date"]
        doc.discharge_date = record["discharge_date"]
        doc.extraction = {**extraction, "_warnings": warnings}
        doc.observations.clear()
        doc.medications.clear()
        doc.conditions.clear()
        doc.allergies.clear()
        ids = {"profile_id": target.id, "document_id": doc.id}
        db.add_all(Observation(**ids, **{
            key: value for key, value in item.items() if key != "explainer"
        }) for item in record["observations"])
        db.add_all(Medication(**ids, **{
            key: value for key, value in item.items() if key != "as_needed"
        }) for item in record["medications"])
        db.add_all(Condition(**ids, **item) for item in record["conditions"])
        db.add_all(Allergy(**ids, **item) for item in record["allergies"])
        doc.summary = None
        doc.summary_i18n = None
        doc.status = "summarizing"
        bg.add_task(
            summarize_document,
            {
                "record": record,
                "profile_id": target.id,
                "document_id": doc.id,
            },
        )
    db.commit()
    db.refresh(doc)
    return doc_brief(doc)


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

    if d.review_status != "confirmed":
        raise HTTPException(409, "Review this document before opening its summary")
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
