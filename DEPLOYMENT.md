# Deployment Guide

This guide covers deploying the DevOps Incident Agent to a cloud host. The
examples use [Render](https://render.com) (generous free tier), but the same
env vars apply to Railway, Fly.io, or any Docker host.

> This project ships with Docker images for every service, so anywhere that can
> run `docker-compose up` (a VPS, for example) will also work directly.

## Components to deploy

1. **PostgreSQL** — a managed database.
2. **Backend** — the FastAPI app (built from `backend/Dockerfile`).
3. **Frontend** — the static React build (from `frontend/`), served by any static host.

## 1. Database

Create a managed PostgreSQL instance and copy its connection string.

> ⚠️ **Important:** this app uses the async `asyncpg` driver, so the
> `DATABASE_URL` scheme must be `postgresql+asyncpg://...`, **not** the
> `postgres://...` that most hosts hand you. Rewrite the scheme:
>
> ```
> postgres://user:pass@host:5432/db
> →  postgresql+asyncpg://user:pass@host:5432/db
> ```

## 2. Backend (Docker web service)

- **Dockerfile path:** `backend/Dockerfile`
- **Docker context:** `backend`
- **Port:** `8000` (the container listens here; the host maps it to a public URL)

Environment variables:

| Variable             | Required | Notes                                                        |
| -------------------- | -------- | ------------------------------------------------------------ |
| `GEMINI_API_KEY`     | ✅       | Google Gemini API key                                        |
| `DATABASE_URL`       | ✅       | Must use the `postgresql+asyncpg://` scheme (see above)      |
| `PUBLIC_API_URL`     | ✅       | The backend's own public URL (used to build webhook URLs)    |
| `CORS_ORIGINS`       | ✅       | The frontend's public URL, comma-separated if more than one  |
| `GITHUB_TOKEN`       | ➖       | Optional — enables GitHub issue/PR creation                  |
| `GITHUB_REPO`        | ➖       | `owner/repo`                                                 |
| `TELEGRAM_BOT_TOKEN` | ➖       | Optional — enables Telegram alerts                           |
| `TELEGRAM_CHAT_ID`   | ➖       | Optional                                                     |
| `SLACK_WEBHOOK_URL`  | ➖       | Optional — enables Slack alerts                              |

## 3. Frontend (static site)

- **Build command:** `npm ci && npm run build`
- **Publish directory:** `frontend/dist`

> ⚠️ The frontend reads the backend URL at runtime from
> `frontend/public/config.js` (`window.APP_CONFIG.API_BASE_URL`). Before
> building, set it to your deployed backend URL:
>
> ```js
> window.APP_CONFIG = { API_BASE_URL: "https://your-backend.onrender.com" };
> ```
>
> This file is copied verbatim into the build, so it is the single source of
> truth for where the frontend sends API requests.

## 4. Log simulator (optional)

To generate demo data in the deployed environment, run the simulator container
(`log-simulator/`) with `BACKEND_URL` pointing at your deployed backend. It will
auto-create an app and start streaming logs.

## Post-deploy checklist

- [ ] `GET /health` on the backend returns `"status": "healthy"`.
- [ ] The frontend dashboard loads and can reach the API (check the browser
      console for CORS errors — if you see them, fix `CORS_ORIGINS`).
- [ ] Register an app, send a webhook/simulator log, and confirm an incident
      appears on the dashboard.
