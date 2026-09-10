# Deploy the existing Render backend

Backend source: `GYProject/backend`. The frontend is maintained in the separate
`GYFrontEnd/GYProjectFrontEnd/frontend` checkout.

The login failure `relation "auth_user" does not exist` means the connected
PostgreSQL database lacks Django's user table. The committed migrations already
create the required tables. `build.sh` now applies them on every deploy and stops
on failure. It does not create accounts or import local data.

## Existing Render web service: gyproject

Push these backend changes to the repository/branch used by the existing service.
Configure that service (do not create a replacement PostgreSQL database):

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Build Command | `bash build.sh` |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |
| Health Check Path | `/health/` |
| `DATABASE_URL` | Existing Render PostgreSQL service's **Internal Database URL** |
| `DJANGO_SECRET_KEY` | A stable, private random secret |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | `gyproject.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `https://gy-project-frontend.onrender.com` |

If the Git repository itself starts at `backend` (manage.py is at its root),
leave Root Directory blank and use `bash build.sh` as Build Command. If the
service is rooted at the parent Git repository, use `bash backend/build.sh` as
Build Command and `gunicorn --chdir backend config.wsgi:application --bind
0.0.0.0:$PORT` as Start Command. Do not combine `pip install` with the
`collectstatic` command; each must be a separate shell command, as already
implemented in `build.sh`.

Creating PostgreSQL on Render does not automatically populate DATABASE_URL in a
manually configured web service. Set it in the backend service's Environment tab;
do not put it in the frontend or commit it. Existing CORS environment values now
actually take effect, so include the exact frontend origin without `/signin`.

`render.yaml` records these settings. A manually configured service does not adopt
this file automatically. If using a Blueprint, set its path to
`backend/render.yaml` and use your existing database connection.

Deploy and check the build log for successful `auth`, `core`, and token blacklist
migrations. On an existing database with valuable data, take a backup before
applying pending migrations. If the build reports no pending migrations but
`auth_user` is missing, inspect DATABASE_URL and migration history rather than
using fake migrations or deleting data.

## First administrator without Render Shell

Signup in this application is administrator-only. Configure these three values
as **secret environment variables** on the Render web service before deploying:

| Variable | Example | Purpose |
| --- | --- | --- |
| `DJANGO_SUPERUSER_USERNAME` | `festival-admin` | Login username |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Administrator email |
| `DJANGO_SUPERUSER_PASSWORD` | Use a unique password of at least 10 characters | Initial password |

Deploy after saving the variables. `build.sh` runs migrations and then the
idempotent `bootstrap_admin` command. The first successful deploy creates the
superuser in the Render PostgreSQL database and its application `admin`
profile. A later deploy does not change the password or create a duplicate.

After confirming that login works, remove all three bootstrap variables from
Render and deploy once more. The command then safely skips. Do not put the
password in Git, `render.yaml`, build output, or frontend variables.

If the username already exists as a non-superuser, the deployment stops instead
of changing that account. Choose another username or promote the account using
an authenticated administrator workflow.

## Frontend

In the frontend Render service, set
`VITE_API_URL=https://gyproject.onrender.com/api` and rebuild/redeploy.
Login must POST to `https://gyproject.onrender.com/api/login/`.
The `/health/` response checks that Django responds; it is not a database check.

## Local verification

Install `requirements.lock.txt`, then run from this backend directory:

```bash
python manage.py test core.tests
python manage.py makemigrations --check --dry-run
```

Tests use a separate test database. Never point a local test run at production.
