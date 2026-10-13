<div align="center">

# CuraMind
### Your Personal Health Copilot

**Bringing medical records together so health history is easier to review and understand.**

[![Status](https://img.shields.io/badge/status-in%20development-0F766E)](#project-status)
[![Frontend](https://img.shields.io/badge/frontend-Next.js%20%2F%20TypeScript-111827)](#technology-stack)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](#technology-stack)
[![Privacy](https://img.shields.io/badge/health%20data-sensitive-7C3AED)](#privacy-safety-and-limitations)

*Hackathon prototype · Not for diagnosis or emergency care*

</div>

---

## The problem

Prescriptions, laboratory reports, discharge summaries, and other health documents often live in separate places. This makes it difficult to see what happened over time or prepare a clear overview for a healthcare visit.

**CuraMind is being developed to help people organise medical documents, review information extracted from them, and build a clearer health history.**

The goal is to make health information easier to navigate—not to replace a clinician or make medical decisions.

## What we're building

- **One place for health records** — bring supported medical documents and health information into a more organised experience.
- **Document understanding** — extract medicine names, dosages, lab/test values, diagnoses, and dates where those details are present.
- **Human review first** — let people inspect and correct extracted details before treating them as confirmed.
- **Plain-language summaries** — summarise reviewed information while making uncertainty clear.
- **A unified health timeline** — organise confirmed events by date when reliable dates are available.
- **Broader health history (planned)** — support injury and fracture history, plus pregnancy and women's-health records, with additional privacy care.
- **Existing baseline preservation** — retain existing download/export behaviour while the project evolves.

> **Important:** These are the product goals. See [Project status](#project-status) for what is present in the repository and what still needs end-to-end verification.

## Project status

CuraMind is an active prototype. The repository contains a Next.js/TypeScript web frontend and a Python/FastAPI backend. A separate Flutter patient-app workstream has also been developed locally; it is **not included** in the repository structure shown below unless it is added to this repository.

| Area | Current status |
|---|---|
| Web interface and navigation | Present in `frontend/`; routes include health, upload, timeline, profile, and ABHA-related screens. Test all routes after changes. |
| FastAPI backend | Present in `backend/app/`, including document, profile, and ABHA-related routers. |
| Medical document processing | Backend ingestion and extraction modules are present; extraction accuracy and full UI-to-API integration still require validation. |
| Review, summary, and timeline | Intended core workflow; do not assume every step is fully integrated without end-to-end tests. |
| ABHA and doctor-related functionality | Verify the actual integration, permissions, and availability before describing it as live. |
| Fracture and injury history | Planned broader health-history area. |
| Pregnancy and women's health | Planned; requires careful design and stronger privacy protections. |
| Authentication and access controls | Require security review and tests before use with real users or sensitive records. |
| Downloads/exports | Preserve existing behaviour and test it after changes. |
| Production deployment | Not complete. Production database, persistent file storage, access controls, and privacy/security checks remain deployment prerequisites. |

### Stage 1: the end-to-end health-record workflow

Stage 1 is considered complete only when this entire flow works and has been tested:

1. Upload a supported medical document.
2. Extract medicines, dosages, test values, diagnoses, and dates.
3. Show extracted details for review, correction, confirmation, or rejection.
4. Create a summary from reviewed information.
5. Display confirmed information in a unified health timeline.

A file picker or individual screen alone does not complete Stage 1. Update this README's status only after the complete workflow has passed end-to-end tests using synthetic sample documents.

## Technology stack

| Component | Technology |
|---|---|
| Web frontend | Next.js, React, TypeScript |
| Backend API | Python, FastAPI |
| Data and document processing | Backend models and ingestion modules; check current configuration for active storage and database |
| Testing | Python test suite under `backend/tests/` |
| Mobile workstream | Flutter/Dart patient app maintained separately at present |

The dependency files and source code in the repository are the source of truth. PostgreSQL and other production storage options must not be assumed active until the deployed backend configuration has been verified.

## Repository structure

```text
health-copilot/
├── backend/
│   ├── app/
│   │   ├── fhir/           # FHIR import/serialization helpers
│   │   ├── ingestion/      # Document ingestion and extraction workflow
│   │   ├── routers/        # API routes, including documents and profile
│   │   ├── rules/          # Dosage, lab catalogue, formulary and safety rules
│   │   ├── auth.py         # Current request/session access logic
│   │   ├── config.py       # Backend configuration
│   │   ├── db.py           # Database setup
│   │   ├── main.py         # FastAPI application entry point
│   │   └── models.py       # Data models
│   ├── data/               # Reference catalogues and mock ABHA/ABDM data
│   ├── eval/
│   │   ├── gold/           # Synthetic evaluation documents and labels
│   │   └── make_samples.py # Sample-data generator
│   ├── tests/              # Backend tests
│   ├── .env.example        # Safe configuration template
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js route pages
│   │   ├── components/     # Shared UI components
│   │   ├── i18n/            # English, Hindi, Tamil and Telugu strings
│   │   ├── Shell.tsx       # Shared navigation/layout
│   │   └── api.ts          # Frontend API client
│   ├── next.config.ts      # Local API proxy configuration
│   ├── package.json
│   └── .env.example
├── MODEL_UPDATE_TRINEXA.md
├── README.md
└── .gitignore
```

The Flutter patient app is currently maintained in a separate local folder and is not shown above.

## Run locally

These commands are for local development on Windows PowerShell. Open **separate terminal windows** for the frontend and backend. Use synthetic test documents only.

### Prerequisites

- Git
- Node.js and npm
- Python compatible with `backend/requirements.txt`
- A configured model-provider API key only if you intend to test an LLM-backed extraction path
- Additional system tools only if required by the enabled OCR/document-processing path

### 1. Clone the repository

```powershell
git clone https://github.com/sanathabassum-dudekula/health-copilot.git
Set-Location .\health-copilot
```

### 2. Configure and start the backend

In a new PowerShell terminal:

```powershell
Set-Location ".\backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `backend\.env` locally and configure the model/provider settings and S3-compatible storage settings required for document uploads. Keep real keys in `.env`; never commit that file.

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

If the backend reports a missing setting, database dependency, or external service, check `backend/app/config.py`, `backend/app/db.py`, and the current README/configuration before changing the database. **Do not delete or recreate an existing database to troubleshoot startup.**

### 3. Configure and start the frontend

In a second PowerShell terminal:

```powershell
Set-Location "C:\path\to\health-copilot\frontend"
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open the URL printed by Next.js. This workspace has used `http://localhost:5173`; use the actual URL printed by the dev server if it differs.

**Check the API proxy before testing API-dependent pages.** `frontend/next.config.ts` has been configured for local development and the backend runs on port `8001` in the current setup. The example environment file may specify a different default (`BACKEND_URL=http://localhost:8000`). Do not assume these values agree: inspect `frontend/next.config.ts` and `frontend/.env.example`, then make the local proxy target and backend port consistent. Keep local overrides in `.env.local` rather than hard-coding deployment secrets.

### 4. Run backend tests

From the repository root:

```powershell
Set-Location ".\backend"
.\.venv\Scripts\python.exe -m pytest
```

If the repository has a `requirements-dev.txt` file and pytest is not installed, install those development dependencies first. Do not assume that file exists; check the `backend` directory.

### 5. Build the frontend

In a separate terminal:

```powershell
Set-Location "C:\path\to\health-copilot\frontend"
npm ci
npm run build
```

A successful build is useful, but it does not prove the full medical-document workflow, access control, or production deployment is safe.

## Demo guidance

For a hackathon demo:

- Use only the fictional evaluation documents under `backend/eval/gold/`.
- Explain which capabilities are implemented, which are mocked, and which are planned.
- Show extraction as unconfirmed until a person reviews it.
- Demonstrate the full upload → extraction → review → summary → timeline flow only if it is connected and has passed testing.
- Do not use real patient records, credentials, or identifiable health information in public demos, screenshots, issues, or commits.

## Deployment overview

**The web frontend and FastAPI backend need separate deployment configuration.** Vercel can host the Next.js frontend; the Python API must be hosted on a service that supports the backend process and its runtime needs.

### Frontend on Vercel

1. Import the GitHub repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Keep the detected Next.js framework and build settings unless the project configuration requires otherwise.
4. Configure the production backend URL using the environment variable/rewrite mechanism supported by the current `frontend/next.config.ts`.
5. Redeploy after changing environment variables and verify API calls against the deployed backend.

### Backend and persistent data

Before connecting a public frontend to the API:

- Deploy FastAPI separately and configure the start command for the selected host.
- Set API keys and other secrets through the hosting provider's secret/environment settings—not in source code.
- Configure a production database and persistent file storage. Do not rely on an ephemeral server filesystem or an unverified local SQLite database for persistent real-user medical records.
- Configure HTTPS, CORS/proxy behaviour, request limits, and access controls for the deployed domains.
- Test uploads, document processing, review, summaries, timeline, downloads, error handling, and permissions after deployment.
- Confirm backup and recovery procedures without exposing health information in logs.

Do not point a public deployment at your local machine or assume that a successful Vercel build means the backend is deployed.

## Roadmap

### Stage 1 — Medical-record foundation
- Complete document upload for supported PDFs and images.
- Extract medicines, dosages, test values, diagnoses, and dates.
- Add review actions to edit, confirm, and reject extracted items.
- Generate a summary from reviewed information.
- Build a unified health timeline.
- Verify the full workflow and preserve baseline/download behaviour.

### Stage 2 — Reliable APIs, accounts, and storage
- Finalise authentication and authorisation.
- Test that one user cannot access another user's records.
- Confirm database and persistent file-storage configuration.
- Validate API contracts and frontend integration.
- Improve loading, error, and unsupported-file handling.

### Stage 3 — Broader health history
- Add structured fracture and injury history.
- Design pregnancy and women's-health records with additional privacy protections.
- Review doctor-facing support, identity verification, and user-controlled sharing.
- Verify ABHA-related integration requirements.
- Improve extraction quality and preserve download/export features.

### Stage 4 — Quality and release preparation
- Expand automated frontend, backend, and integration tests.
- Improve accessibility and responsive behaviour.
- Review authentication, permissions, secrets, encryption, logs, backups, and retention.
- Document deployment and recovery.
- Complete appropriate privacy, legal, security, and clinical review before real-world use.

## Privacy, safety, and limitations

Medical records are sensitive. This project is under development and should not be treated as a production medical-record service.

- Never commit `.env` files, API keys, access tokens, private certificates, or real patient records.
- Use synthetic or properly de-identified test documents.
- Treat extracted information as unconfirmed until reviewed.
- Do not invent missing values or dates; communicate uncertainty.
- Do not present generated summaries as diagnoses or treatment plans.
- Require appropriate authentication, authorisation, and explicit consent before sharing records.
- Give pregnancy, fertility, and other women's-health information additional privacy protection.
- Complete a security and privacy review before allowing real users to upload sensitive health information.

## Contributing

1. Check the current branch and repository status before making changes.
2. Coordinate with teammates before changing shared backend, database, or API files.
3. Keep changes focused and preserve existing baseline/download behaviour unless a change is agreed and tested.
4. Use mock/synthetic data while integration is incomplete.
5. Run relevant tests and describe what changed, how it was tested, and what remains unfinished.

## Disclaimer

CuraMind is a software prototype intended to help organise and review health information. It does not replace a qualified healthcare professional, provide emergency care, or independently diagnose conditions or prescribe treatment. Extracted data and generated summaries can be incomplete or incorrect. Medical decisions should be made with an appropriate healthcare professional.
