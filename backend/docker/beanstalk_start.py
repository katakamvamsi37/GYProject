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


def log_stage(message):
    print(f"[startup] {message}", flush=True)


def run_release():
    stage = "initializing"
    try:
        os.chdir(APP_DIR)
        sys.path.insert(0, str(APP_DIR))

        if os.getenv("DJANGO_PROVISION_DATABASE", "false").lower() == "true":
            stage = "database provisioning"
            log_stage(stage)
            subprocess.run(
                [
                    sys.executable,
                    "docker/provision_database.py",
                    "--if-missing",
                    "--sync-existing",
                ],
                check=True,
            )

        # The Gunicorn process does not need database-admin credentials.
        for key in ("DB_ADMIN_USER", "DB_ADMIN_PASSWORD"):
            os.environ.pop(key, None)

        stage = "loading Django settings"
        log_stage(stage)
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django

        django.setup()
        from django.db import connection

        if connection.vendor != "postgresql":
            raise RuntimeError("Beanstalk startup requires PostgreSQL")

        stage = "connecting to PostgreSQL"
        log_stage(stage)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '120s'")
                cursor.execute("SELECT pg_advisory_lock(718204032)")
                log_stage("PostgreSQL connection established")

                stage = "running release commands"
                log_stage(stage)
                subprocess.run(["sh", "docker/release.sh"], check=True)

                stage = "bootstrapping admin"
                log_stage(stage)
                subprocess.run(
                    [sys.executable, "manage.py", "bootstrap_admin"], check=True
                )
        finally:
            # PostgreSQL releases the session advisory lock even on failure.
            connection.close()

        for key in (
            "DJANGO_SUPERUSER_USERNAME",
            "DJANGO_SUPERUSER_EMAIL",
            "DJANGO_SUPERUSER_PASSWORD",
        ):
            os.environ.pop(key, None)

        log_stage("release completed")
    except subprocess.CalledProcessError as error:
        print(
            f"[startup] stage={stage} child_exit={error.returncode}",
            file=sys.stderr,
            flush=True,
        )
        raise
    except Exception as error:
        # Do not print exception messages: database drivers can include identifying
        # connection data. The type and stage are sufficient for diagnostics.
        print(
            f"[startup] stage={stage} error_type={type(error).__name__}",
            file=sys.stderr,
            flush=True,
        )
        raise


def stop(signum, frame):
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    try:
        run_release()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from None
    except Exception:
        raise SystemExit(1) from None

    log_stage("starting Gunicorn")
    os.execvp(
        "gunicorn",
        ["gunicorn", "--config", "gunicorn.conf.py", "config.wsgi:application"],
    )
