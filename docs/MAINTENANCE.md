# Maintenance and troubleshooting

## Before editing

1. Make a source-control commit or source backup.
2. Back up the database before changing models or doing data maintenance.
3. Locate the feature using ARCHITECTURE.md.
4. Edit the smallest relevant module.
5. Run the relevant tests, then build.

There was no usable Git command in the initial environment. Set up Git locally so you can review diffs and restore earlier versions.

## Backend checks

```powershell
.\.venv\Scripts\python.exe backend/manage.py test core.tests
.\.venv\Scripts\python.exe backend/manage.py check
.\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run
```

After intentionally editing a model:

```powershell
.\.venv\Scripts\python.exe backend/manage.py makemigrations core
.\.venv\Scripts\python.exe backend/manage.py backup_database
.\.venv\Scripts\python.exe backend/manage.py migrate
```

Inspect the generated migration before applying it. Never remove old migrations to fix an error.

## Frontend checks

```powershell
cd frontend
npm run format
npm run lint
npm run build
npm test
```

Browser tests start the API on 8011 and Vite on 5179, use a temporary SQLite database and launch headless Microsoft Edge. No live festival data is read.
On non-Windows machines, adjust the Python executable in playwright.config.js and use an installed Playwright Chromium browser instead of channel msedge.
Screenshots and failed-test traces are written to frontend/test-results and are ignored by Git.

## Troubleshooting map

| Symptom | Check |
|---|---|
| Cannot reach server | Start backend on 8000; inspect API proxy in vite.config.js |
| Unsupported Django/Python error | Use root .venv, not backend/.venv |
| Login fails after update | Sign in again; old browser sessions and signing key are retired |
| Blank page | Browser console, ErrorBoundary message, npm run lint/build |
| No data for selected year | Check dates and status filters; empty records are never replaced by samples |
| Entry missing from totals | Pending/rejected/void entries are excluded; inspect review state |
| Cannot approve own record | Ask another admin/treasurer; this is intentional |
| Duplicate transaction error | Search collections for the bank reference before retrying |
| Retry says different details | Check whether the original entry was saved; close and reopen only for a genuinely new entry |
| CSV/XLSX fails | Inspect authenticated /api/export request; confirm management role |
| Profile role did not change | Use Access management; self-edit does not grant roles |
| Existing record lacks evidence | Review source documents; reject/replace if the entry cannot be supported |
| Frontend route 404 after deployment | Configure web server SPA rewrite to index.html |
| Admin page cannot edit business entries | Use the application so changes receive audit snapshots |

## Backups and restore

Local SQLite backup:

```powershell
.\.venv\Scripts\python.exe backend/manage.py backup_database
```

Backups go to backups/ with timestamps. Keep a separate protected copy outside this machine.
To restore, stop the backend, keep a backup of the current database, then replace backend/db.sqlite3 with the chosen backup.
After restore, run `showmigrations` and verify records before accepting new entries.
For PostgreSQL, use pg_dump/pg_restore and regularly test restoration.

## Dependency updates

backend/requirements.txt defines supported ranges; requirements.lock.txt records tested exact versions.
frontend/package-lock.json records the frontend dependency tree.
After updating, run backend and browser tests and review production checks.
Keep the root Python and project-local Node runtimes supported.

## Current boundaries

- Manual payment reconciliation; no live payment provider or OTP delivery.
- Evidence URLs, not file uploads.
- Application audit trail, not cryptographically sealed or externally immutable storage.
- Local SQLite and local-memory rate limiting are development defaults; PostgreSQL/shared rate limiting still need hosting configuration.
- No statutory ledger, bank statement import, expense tax treatment, carry-forward fund balance, or multi-organization isolation.
- Legacy records are preserved without inventing historical approval/actor evidence.

## Python formatting

Install backend/requirements-dev.txt, then run from the project root:

```powershell
.\.venv\Scripts\ruff.exe check backend scripts
.\.venv\Scripts\ruff.exe format backend scripts
```

VS Code uses the root Python environment through .vscode/settings.json.
The optional Django debug configuration is in .vscode/launch.json.
