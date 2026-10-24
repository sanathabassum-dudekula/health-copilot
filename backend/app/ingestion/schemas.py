from typing import Literal

from pydantic import BaseModel, Field


class Medication(BaseModel):
    name: str
    strength: str | None = None
    form: str | None = None
    dose_pattern: str | None = None  # exactly as written: "1-0-1", "BD", "सुबह-शाम"
    timing: str | None = None  # "after food"
    duration: str | None = None  # "5 days", "continue"
    source_text: str
    confidence: float = Field(ge=0, le=1)


class LabResult(BaseModel):
    test_name: str
    value: str  # string: "<0.5", "Positive", "7.8"
    unit: str | None = None
    ref_range: str | None = None
    flag_on_report: str | None = None
    source_text: str
    confidence: float = Field(ge=0, le=1)


class Diagnosis(BaseModel):
    name: str
    source_text: str
    confidence: float = Field(ge=0, le=1)




class FractureInjury(BaseModel):
    """Structured injury facts extracted from a source; not an automated diagnosis."""
    body_site: str | None = None
    side: Literal["left", "right", "bilateral", "not_stated"] = "not_stated"
    injury_type: str | None = None  # fracture, dislocation, sprain, other; keep source wording
    fracture_pattern: str | None = None
    displacement: str | None = None
    open_or_closed: Literal["open", "closed", "not_stated"] = "not_stated"
    date_of_injury: str | None = None
    date_of_report: str | None = None
    imaging_modality: str | None = None
    reported_findings: str | None = None
    treatment_or_procedure: str | None = None
    immobilization: str | None = None
    weight_bearing_instruction: str | None = None
    follow_up_plan: str | None = None
    source_text: str
    confidence: float = Field(ge=0, le=1)


class WomensHealthExtraction(BaseModel):
    """Optional, consent-sensitive reproductive-health facts; unknown values stay null."""
    pregnancy_status: Literal["pregnant", "not_pregnant", "postpartum", "unknown"] = "unknown"
    last_menstrual_period: str | None = None
    estimated_due_date: str | None = None
    gestational_age: str | None = None
    trimester: Literal["first", "second", "third", "unknown"] = "unknown"
    gravida: int | None = Field(default=None, ge=0)
    para: int | None = Field(default=None, ge=0)
    pregnancy_complications: list[str] = Field(default_factory=list)
    prenatal_visits_or_tests: list[str] = Field(default_factory=list)
    delivery_date: str | None = None
    postpartum_notes: list[str] = Field(default_factory=list)
    menstrual_history: str | None = None
    reproductive_health_notes: list[str] = Field(default_factory=list)
    cervical_screening: list[str] = Field(default_factory=list)
    breast_health_notes: list[str] = Field(default_factory=list)
    menopause_or_fertility_notes: list[str] = Field(default_factory=list)
    source_text: str | None = None
    needs_clinician_review: bool = True


class DocumentExtraction(BaseModel):
    doc_type: Literal["prescription", "lab_report", "discharge_summary", "diagnostic_report", "fracture_or_injury_report", "antenatal_record", "womens_health_report", "other"]
    doc_date: str | None = None
    patient_name: str | None = None
    facility: str | None = None
    practitioner: str | None = None
    admission_date: str | None = None
    discharge_date: str | None = None
    diagnoses: list[Diagnosis] = []
    medications: list[Medication] = []
    lab_results: list[LabResult] = []
    allergies: list[str] = []
    impression: str | None = None  # imaging findings
    follow_up: str | None = None
    languages_detected: list[str] = []
    handwritten: bool = False
    fractures_or_injuries: list[FractureInjury] = Field(default_factory=list)
    womens_health: WomensHealthExtraction | None = None
    needs_human_review: bool = True


class AbnormalExplanation(BaseModel):
    test: str
    value: str
    status: str
    what_it_means: str
    common_reasons: str
    question_for_doctor: str


class MedicineExplained(BaseModel):
    name: str
    general_purpose: str
    how_to_take: str


class Summary(BaseModel):
    headline: str
    key_points: list[str]
    urgent_actions: list[str] = Field(default_factory=list)
    abnormal_explanations: list[AbnormalExplanation] = Field(default_factory=list)
    medicines_explained: list[MedicineExplained] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
