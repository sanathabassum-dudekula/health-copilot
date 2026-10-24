# CuraMind frontend — backend compatibility notes

This package is based on the latest frontend source supplied for this task. `next.config.ts` proxies browser requests from `/api/*` to `BACKEND_URL`; the local backend default is `http://127.0.0.1:8000`.

## Routes exposed by the backend

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`
- `GET/PUT/DELETE /profile`
- `GET /profile/timeline`
- `GET /profile/fhir`
- `POST/GET /documents`
- `GET /documents/{doc_id}`
- `GET /documents/{doc_id}/file`
- `GET /documents/{doc_id}/summary`
- `GET/POST/DELETE /family` and `DELETE /family/{oid}`
- `/assistant/*`, `/reminders/*`, `/insights`, and `/vitals`
- `POST /abha/link`, `/abha/verify`, `/abha/import`

## Known family API mismatch

The frontend calls `/family/active`, profile lookup/update, PIN management, profile switching, and invitation endpoints. Those routes are not implemented by the current backend family router, so the corresponding UI flows will fail until the backend support is restored or the frontend is adapted. Do not enable these flows in production until authorization behavior has been reviewed and tested.

## Run locally

1. Install Node.js 20.9 or newer.
2. In this folder run `npm install`.
3. Ensure the FastAPI backend is running at `http://127.0.0.1:8000`.
4. Run `npm run dev`.

Do not put real credentials in `.env.example`; create a local `.env.local` if needed and keep it private.
