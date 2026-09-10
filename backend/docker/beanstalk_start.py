"""Console-upload startup: provision optionally, serialize release, then serve.

Selected by the Beanstalk Dockerrun file only. ECS/Compose keep their normal CMD.
Startup migrations require compatible schema changes or a maintenance window.
"""

import os
from pathlib import Path
import signal
import subprocess
import sys

APP_DIR = Path(__file__).resolve().parents[1]


def run_release():
    os.chdir(APP_DIR)
    sys.path.insert(0, str(APP_DIR))
    if os.getenv("DJANGO_PROVISION_DATABASE", "false").lower() == "true":
        subprocess.run(
            [sys.executable, "docker/provision_database.py", "--if-missing"], check=True
        )
    # The Gunicorn process does not need bootstrap credentials.
    for key in ("DB_ADMIN_USER", "DB_ADMIN_PASSWORD"):
        os.environ.pop(key, None)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connection

    if connection.vendor != "postgresql":
        raise SystemExit("Beanstalk startup requires PostgreSQL.")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '120s'")
            cursor.execute("SELECT pg_advisory_lock(718204032)")
            # Hold this dedicated session open until both child commands finish.
            subprocess.run(["sh", "docker/release.sh"], check=True)
            subprocess.run([sys.executable, "manage.py", "bootstrap_admin"], check=True)
    finally:
        # PostgreSQL releases the session advisory lock even on failure.
        connection.close()
    for key in (
        "DJANGO_SUPERUSER_USERNAME", "DJANGO_SUPERUSER_EMAIL", "DJANGO_SUPERUSER_PASSWORD"
    ):
        os.environ.pop(key, None)


def stop(signum, frame):
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    try:
        run_release()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from None
    except Exception:
        # Connection errors may contain identifying data; no environment dumps.
        raise SystemExit("Startup failed. Check database settings, connectivity and release logs.") from None
    os.execvp("gunicorn", ["gunicorn", "--config", "gunicorn.conf.py", "config.wsgi:application"])
