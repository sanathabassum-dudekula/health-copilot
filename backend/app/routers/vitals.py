from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..access import profile_for_owner
from ..auth import current_profile
from ..db import get_db
from ..models import Profile, VitalSign

router = APIRouter(prefix="/vitals", tags=["vitals"])

VitalMetric = Literal["heart_rate", "oxygen_saturation", "body_temperature"]
VitalSource = Literal["bluetooth", "manual"]
UNITS = {
    "heart_rate": "bpm",
    "oxygen_saturation": "%",
    "body_temperature": "°C",
}
RANGES = {
    "heart_rate": (20, 250),
    "oxygen_saturation": (40, 100),
    "body_temperature": (25, 45),
}


class VitalSignCreate(BaseModel):
    metric: VitalMetric
    value: float = Field(ge=0, le=300)
    source: VitalSource
    device_name: str | None = Field(default=None, max_length=120)
    captured_at: datetime | None = None


def _vital_json(record: VitalSign) -> dict:
    captured_at = record.captured_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)

    return {
        "id": record.id,
        "metric": record.metric,
        "value": record.value,
        "unit": record.unit,
        "source": record.source,
        "device_name": record.device_name,
        "captured_at": captured_at.isoformat(),
    }


@router.get("")
def list_vitals(
    profile_oid: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    target = profile_for_owner(owner, db, profile_oid)
    records = db.scalars(
        select(VitalSign)
        .where(VitalSign.profile_id == target.id)
        .order_by(desc(VitalSign.captured_at), desc(VitalSign.id))
        .limit(limit)
    )
    return [_vital_json(record) for record in records]


@router.post("", status_code=201)
def create_vital(
    body: VitalSignCreate,
    profile_oid: str | None = None,
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    target = profile_for_owner(owner, db, profile_oid)
    lower, upper = RANGES[body.metric]
    if not lower <= body.value <= upper:
        raise HTTPException(
            status_code=422,
            detail=f"{body.metric.replace('_', ' ').capitalize()} must be between {lower} and {upper}.",
        )
    if body.metric == "heart_rate" and not body.value.is_integer():
        raise HTTPException(
            status_code=422,
            detail="Heart rate must be a whole number of beats per minute.",
        )

    captured_at = body.captured_at or datetime.now(timezone.utc)
    if captured_at.tzinfo is not None:
        captured_at = captured_at.astimezone(timezone.utc).replace(tzinfo=None)

    record = VitalSign(
        profile_id=target.id,
        metric=body.metric,
        value=body.value,
        unit=UNITS[body.metric],
        source=body.source,
        device_name=body.device_name.strip()[:120] if body.device_name else None,
        captured_at=captured_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _vital_json(record)
