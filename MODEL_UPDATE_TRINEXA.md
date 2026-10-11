# TRINEXA additive model update — October 2026

## Preservation promise
This update is additive. It keeps the existing project folders, routes, database tables, sample reports, evaluation fixtures, FHIR code, and frontend layout in place. It does **not** replace the baseline or remove/rename download assets. Existing SQLAlchemy tables are intentionally unchanged in this package so it does not silently require a database migration. The extraction schema gains optional fields, so old extraction payloads remain valid.

## Keep the current layout
Keep the current Home → Upload → Document review → Timeline → ABHA navigation and visual language. Add new pages/sections inside that pattern rather than redesigning the shell:
- Home: selected patient/profile context and recent records.
- Upload: retain current file picker and supported formats.
- Document review: original document beside extracted fields; allow correction and explicit confirmation before adding extracted facts to the health record.
- Timeline: one date-sorted timeline for documents, labs, medication start/stop, diagnoses, fractures/injuries, pregnancy milestones, procedures, and follow-ups.
- Profile switcher/family profiles: introduce only when profile-scoped authorization is implemented end-to-end.
- Doctor workspace: a separate role-based area, not a patient profile masquerading as a doctor.
- Women's health: optional, private section shown only when relevant and consented to; do not assume every patient needs it.

## Existing core remains the source of truth
Current entities remain `User`, `Visit`, `Profile`, `Document`, `Observation`, `Medication`, `Condition`, and `Allergy`. Continue storing source document IDs, extraction confidence, original text and unknown dates. Never infer a missing date, dosage, pregnancy status, fracture side, or test value. Treat AI extraction as *suggested*, not verified clinical data.

## New optional extraction fields
`backend/app/ingestion/schemas.py` now supports:
- `FractureInjury`: body site, laterality, injury/fracture wording, pattern, displacement, open/closed when explicitly documented, injury/report dates, imaging modality and findings, treatment, immobilization, weight-bearing instructions, follow-up, source text and confidence.
- `WomensHealthExtraction`: pregnancy status (unknown by default), LMP, EDD, gestational age, trimester, gravida/para, pregnancy complications, prenatal tests/visits, delivery/postpartum, menstrual and reproductive history, cervical screening, breast health, menopause/fertility notes, source text and mandatory clinician-review default.
- Additional document categories for fracture/injury reports, antenatal records and women's-health reports.
- `needs_human_review=True` by default on the overall extraction.

These fields are optional and are not a diagnosis, medical-image interpretation, or substitute for clinician review. The application should show confidence/source text and ask the user to review sensitive fields before saving. Do not show pregnancy information in shared family views unless the profile owner explicitly permits it.

## Doctor identity and authorization — planned schema extension, not yet wired into DB
Add separate entities when implementing the doctor workflow:
- `DoctorProfile`: user_id, internal TRINEXA doctor ID, NMR ID (if applicable), HPR ID (if applicable), registration number, registration council/state, specialty/subspecialty, verification status, verified_at, professional contact and languages.
- `DoctorQualification`: degree, institution, year and verification status.
- `HealthcareFacility`: name, facility type, address and HFR ID when applicable.
- `Consultation`: doctor, patient profile, purpose, dates/status, consent record and access expiry.
- `ProfileMembership`: user_id, profile_id, role/permission, status, invited_by, accepted_at.
- `AuditEvent`: actor, affected profile, action, entity reference, timestamp and minimal before/after change summary.

NMR, HPR, HFR and ABHA are different identifiers. Store each in its own field; do not treat ABHA as a login credential. Never claim a registry check succeeded unless a real verification integration or documented manual verification has run. A doctor receives no patient access merely because they have a doctor account or a family member invites them; require explicit, revocable, profile-scoped consent and record access.

## Safe database rollout
Do not add columns to a live database by editing `models.py` alone. When these entities are implemented, use Alembic migrations, back up the database, test migration and rollback on a copy, then deploy. Keep current `Profile.user_id` one-to-one until a deliberate migration supports multiple family profiles. Family profiles are not safe to enable just by changing the ORM relationship; endpoints, ownership checks, deletion, FHIR export and all queries must be profile-scoped first.

## Women's health privacy and clinical safeguards
- All fields can be null/unknown. Do not calculate or fill LMP/EDD/gestational age unless the user requests a clearly labelled calculation and the required date is supplied.
- Ask permission before recording reproductive-health details. Provide a way to correct/delete them and avoid exposing them in notifications, audit logs or shared summaries unnecessarily.
- Pregnancy red flags should route to urgent clinician/emergency guidance, not an AI diagnosis.
- Cervical/breast screening and fertility notes are records, not recommendations to screen or treatment advice.
- Do not make medication-safety decisions in pregnancy from extraction alone; flag for qualified clinician/pharmacist review.

## Stage plan
1. **Stage 1 (existing goal):** upload → extract medicines/dosages/lab values/diagnoses/dates → summary → unified timeline, with review and source links. Completion must be established by end-to-end tests, not by this schema edit.
2. **Stage 1 model enhancement (this package):** optional fracture/injury and women's-health extraction shapes, preserving baseline.
3. **Next implementation stages:** verified review/save workflow; OCR for image/scanned/handwritten records; family profiles and permissions; doctor registry/consultation workflow; multilingual text/audio assistant; sync/audit; deployment and security review.
4. Treat OCR, voice, family sync, doctor access and live registry checks as incomplete until each is implemented and tested.

## Validation checklist before release
- Existing golden extraction fixtures and API/FHIR tests still pass.
- Old payloads without the new fields still validate.
- New fracture and women's-health examples validate with absent fields left unknown.
- Source document and profile ownership are enforced on every read/write.
- Timeline includes dates only when grounded and links each event to its source.
- Sensitive women's-health data is not included in unauthorized family/doctor views.
- Database migrations are separately reviewed and tested before adding any new persisted tables.
