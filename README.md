# Ganesh Youth — Festival Management & Audit

A committee workspace for Ganesh festival budgets, expenses, collections, volunteer responsibilities, and review history.

**Start here:** [Setup](docs/SETUP.md) · [Folder map](docs/ARCHITECTURE.md) · [Daily workflow](docs/WORKFLOWS.md) · [Maintenance](docs/MAINTENANCE.md)

## What works

- Password sign-in, session refresh, logout, profile updates and password changes.
- Administrator-created accounts with role and active/inactive controls.
- A festival-year overview with actual reviewed totals and clear empty/error states.
- Paginated, searchable budgets, expenses, collections and member records.
- Independent financial review: approve, reject, or void with a required reason.
- CSV and XLSX downloads using the same year/search/status/category filters.
- Actor/timestamp/before/after snapshots for application changes.
- Responsive desktop and mobile navigation.
- Database constraints and retry-safe financial submission identifiers.

## Run from this project directory

Backend (PowerShell):

```powershell
 .\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
 .\.venv\Scripts\python.exe backend/manage.py migrate
 .\.venv\Scripts\python.exe backend/manage.py createsuperuser
 .\.venv\Scripts\python.exe backend/manage.py runserver
```

Frontend (second terminal):

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. Vite proxies API calls to port 8000.

The canonical Python environment is the **root `.venv` (Python 3.12)**.
The old `backend/.venv` uses Python 3.9 and cannot run the updated Django dependency.
Frontend npm scripts use the project-local Node 22 dependency. See setup notes for fresh machines.

## Before real festival use

1. Create at least two independent authorized reviewers (administrator/treasurer).
2. Review migrated expenses and legacy records. Historical dummy collections are excluded from confirmed totals.
3. Take a database backup; store receipt evidence in committee-controlled storage.
4. Set production environment variables and use HTTPS and PostgreSQL for a shared deployment.

No payment gateway is connected. Collections are manually recorded contributions and require human reconciliation.
No OTP is issued. Recovery is administrator-managed until a delivery integration is built.
The ledger is an operational festival record, not a statutory accounting or bank-reconciliation system.

## Verify changes

```powershell
 .\.venv\Scripts\python.exe backend/manage.py test core.tests
 .\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run
cd frontend
npm run lint
npm run format:check
npm run build
npm test
```

Browser tests use a temporary database and headless Microsoft Edge. They never use your festival database.
