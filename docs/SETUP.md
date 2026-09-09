# Setup and deployment

## Local Windows setup

Use Python 3.12. The project already has a compatible root `.venv`.
On a fresh checkout:

```powershell
py -3.12 -m venv .venv
 .\.venv\Scripts\python.exe -m pip install -r backend/backend/requirements.lock.txt
 Copy-Item backend/backend/.env.example backend/backend/.env
 .\.venv\Scripts\python.exe backend/backend/manage.py migrate
 .\.venv\Scripts\python.exe backend/backend/manage.py createsuperuser
 .\.venv\Scripts\python.exe backend/backend/manage.py runserver
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Use Node 22 for system-wide development tooling. A Node 22 binary is also pinned as a frontend dev dependency so npm scripts can use it locally; `npm run runtime` prints the effective version. An older global Node may emit an engine warning during installation.

Use http://localhost:5173. The frontend development proxy forwards /api to http://127.0.0.1:8000.
No separate frontend Django server is needed.

Existing users and passwords remain valid; old browser sessions must sign in again.
The previously embedded secret was replaced with a generated local key ignored by Git. Production requires an explicit environment secret.

## Optional samples

```powershell
 .\.venv\Scripts\python.exe backend/backend/manage.py seed_demo --year 2026
```

This adds labeled budgets and one volunteer, never deletes records, and creates no financial receipts.

## Existing data migration

Back up before schema changes:

```powershell
 .\.venv\Scripts\python.exe backend/backend/manage.py backup_database
 .\.venv\Scripts\python.exe backend/backend/manage.py migrate
```

Migrations retain users, members, budgets, expenses and collections.
Existing expenses enter the pending-review workflow. Old dummy collections retain their label and are excluded from confirmed totals.
Existing manually entered `Plan.spent` values remain in the DB for reference but are no longer used as the current actual spend.
Older records have no submitter identity; the app does not invent one. Historical events cannot be reconstructed automatically.

## Production configuration

Set `DJANGO_DEBUG=false`, a new random `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, and the frontend origin in `CORS_ALLOWED_ORIGINS`.
For Render, create a PostgreSQL database and link it to the backend Web Service.
Render then provides `DATABASE_URL`; the application parses it automatically and
uses SSL in production. Set these Web Service environment variables:

```text
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_ALLOWED_HOSTS=<your-backend-service>.onrender.com
CORS_ALLOWED_ORIGINS=https://<your-frontend-domain>
```

Use these Render Web Service settings from the repository root:

```text
Build Command: pip install -r backend/requirements.lock.txt && python backend/manage.py collectstatic --noinput
Start Command: gunicorn --chdir backend config.wsgi:application
```

Run the database migration once after the service is connected:

```text
python backend/manage.py migrate
```

For local PostgreSQL, provide the split connection variables shown in
backend/.env.example instead.
Store secrets outside source control. Use a trusted HTTPS reverse proxy and a supported WSGI/ASGI server; Django runserver and Vite's dev server are for local work.

Generate a key locally without printing or committing it unnecessarily; configure it through your hosting secret manager.

```powershell
 .\.venv\Scripts\python.exe backend/backend/manage.py migrate
 .\.venv\Scripts\python.exe backend/backend/manage.py collectstatic --noinput
 .\.venv\Scripts\python.exe backend/backend/manage.py check --deploy
cd frontend
npm run build
```

Serve frontend/dist and rewrite frontend routes to index.html. Route /api and /admin to Django.
If serving behind a TLS-terminating proxy, configure forwarded HTTPS trust only for a proxy that strips spoofed client headers.
Default production settings enable SSL redirect, secure cookies and HSTS; validate your domain/proxy setup before launch.

For multiple backend workers, configure a shared Django cache and edge-level request limits. The default local-memory throttle cache is only process-local and is not a complete brute-force defense.
Protect receipt storage separately; a shared URL may be visible to committee users.

## Supported foundations

The backend uses Django 5.2 LTS on Python 3.12 ([Django release notes](https://docs.djangoproject.com/en/5.2/releases/5.2/)).
The frontend build uses the Vite 6.4 security-maintained line ([Vite releases](https://vite.dev/releases)).
Use the lockfiles for reproducible installs and review updates deliberately.
