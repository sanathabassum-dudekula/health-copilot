# CuraMind frontend — backend compatibility notes

This package is based on the latest frontend source supplied for this task. `next.config.ts` proxies browser requests from `/api/*` to `BACKEND_URL`; the local backend default is `http://127.0.0.1:8000`.

## Routes exposed by the supplied backend snapshot

- `GET/PUT/DELETE /profile`
- `GET /profile/timeline`
- `GET /profile/fhir`
- `POST/GET /documents`
- `GET /documents/{doc_id}`
- `GET /documents/{doc_id}/file`
- `GET /documents/{doc_id}/summary`
- `GET/POST/DELETE /family` and `DELETE /family/{oid}` (see backend route definitions for exact request models)
- `POST /abha/link`, `/abha/verify`, `/abha/import`

## Known mismatch to resolve later

The supplied frontend API client also calls `/auth/*`, `/assistant/*`, `/reminders/*`, `/insights`, `/vitals`, and several family endpoints for active profile, PINs, and invitations. Those routes are not registered in the supplied backend `main.py` snapshot. Their UI may therefore show request errors until the matching backend endpoints are restored or the frontend is adapted. This package does not claim those flows are integrated or tested.

## Run locally

1. Install Node.js 20.9 or newer.
2. In this folder run `npm install`.
3. Ensure the FastAPI backend is running at `http://127.0.0.1:8000`.
4. Run `npm run dev`.

Do not put real credentials in `.env.example`; create a local `.env.local` if needed and keep it private.
