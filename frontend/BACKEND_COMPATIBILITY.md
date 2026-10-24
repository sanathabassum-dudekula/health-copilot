# CuraMind frontend — backend compatibility notes

This package is based on the latest frontend source supplied for this task. `next.config.ts` proxies browser requests from `/api/*` to `BACKEND_URL`. Local development defaults to `http://127.0.0.1:8000`; on Vercel, the default backend is `https://curamind-backend.vercel.app`. Set `BACKEND_URL` to override either default.

## Routes exposed by the backend

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`
- `GET/PUT/DELETE /profile`
- `GET /profile/timeline`
- `GET /profile/fhir`
- `POST/GET /documents`
- `GET /documents/{doc_id}`
- `GET /documents/{doc_id}/file`
- `GET /documents/{doc_id}/summary`
- `GET/POST /family`, `GET/PUT/DELETE /family/{oid}`, and `/family/active`
- `/family/{oid}/set-pin`, `/family/{oid}/unlock`, `/family/{oid}/reset-pin`
- `/family/switch-to-owner` and `/family/invitations`
- `/assistant/*`, `/reminders/*`, `/insights`, and `/vitals`
- `POST /abha/link`, `/abha/verify`, `/abha/import`

Family profile management, PIN protection, profile switching, and pending invitation records require a signed-in account. Invitations are saved to the backend as pending records; no SMS is sent and phone verification is not enabled.

The guest experience remains available for non-family workflows. Do not use this prototype with real health information until production access controls, storage, backups, and privacy/security controls are independently verified.

## Run locally

1. Install Node.js 20.9 or newer.
2. In this folder run `npm install`.
3. Ensure the FastAPI backend is running at `http://127.0.0.1:8000`.
4. Run `npm run dev`.

Do not put real credentials in `.env.example`; create a local `.env.local` if needed and keep it private.
