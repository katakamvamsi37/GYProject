"""One-time RDS setup task for the dedicated application database login.

Inject RDS master credentials into this task only. The normal web process must use
POSTGRES_USER/POSTGRES_PASSWORD. Existing-role password synchronization is opt-in
and is intended only for controlled credential repair/rotation.
"""

import argparse
import os

import psycopg
from psycopg import sql


def grant_app_access(connection, *, database, app_user):
    connection.execute(
        sql.SQL("GRANT CONNECT, CREATE ON DATABASE {} TO {}").format(
            sql.Identifier(database), sql.Identifier(app_user)
        )
    )
    connection.execute(
        sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
            sql.Identifier(app_user)
        )
    )


def provision(*, if_missing=False, sync_existing=False):
    app_user = os.environ["POSTGRES_USER"]
    database = os.environ["POSTGRES_DB"]
    app_password = os.environ["POSTGRES_PASSWORD"]

    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=database,
        user=os.environ["DB_ADMIN_USER"],
        password=os.environ["DB_ADMIN_PASSWORD"],
        sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
        connect_timeout=10,
    ) as connection:
        # Serialize provisioning/credential repair if multiple instances start.
        connection.execute("SET LOCAL lock_timeout = '120s'")
        connection.execute("SELECT pg_advisory_xact_lock(718204031)")

        role_exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,)
        ).fetchone()

        if role_exists:
            if not sync_existing:
                if if_missing:
                    print("Application database role already exists; no changes made.")
                    return
                raise SystemExit("Application role already exists; no changes made.")

            connection.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(app_user), sql.Literal(app_password)
                )
            )
            grant_app_access(connection, database=database, app_user=app_user)
            print("Application database role credentials synchronized.")
            return

        connection.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE"
            ).format(sql.Identifier(app_user), sql.Literal(app_password))
        )
        grant_app_access(connection, database=database, app_user=app_user)
        print("Application database role created.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--if-missing", action="store_true")
    parser.add_argument(
        "--sync-existing",
        action="store_true",
        help="Synchronize the password and grants for an existing application role.",
    )
    arguments = parser.parse_args()
    try:
        provision(
            if_missing=arguments.if_missing,
            sync_existing=arguments.sync_existing,
        )
    except (psycopg.Error, KeyError):
        # PostgreSQL errors can include SQL containing credentials. Keep logs clean.
        raise SystemExit(
            "Database setup failed. Check injected settings, connectivity and privileges."
        ) from None
