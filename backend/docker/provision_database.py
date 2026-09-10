"""One-time RDS setup task: grant a dedicated app login access to an empty DB.

Inject the RDS master credentials into this task only. Never run in the web service.
Existing roles are rejected so this script cannot silently change their passwords.
"""

import argparse
import os

import psycopg
from psycopg import sql


def provision(*, if_missing=False):
    app_user = os.environ["POSTGRES_USER"]
    database = os.environ["POSTGRES_DB"]
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=database,
        user=os.environ["DB_ADMIN_USER"],
        password=os.environ["DB_ADMIN_PASSWORD"],
        sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
        connect_timeout=10,
    ) as connection:
        # Serialize first-start provisioning when several instances launch together.
        connection.execute("SET LOCAL lock_timeout = '120s'")
        connection.execute("SELECT pg_advisory_xact_lock(718204031)")
        if connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,)
        ).fetchone():
            if if_missing:
                print("Application database role already exists; no changes made.")
                return
            raise SystemExit("Application role already exists; no changes made.")
        connection.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                sql.Identifier(app_user), sql.Literal(os.environ["POSTGRES_PASSWORD"])
            )
        )
        connection.execute(
            sql.SQL("GRANT CONNECT, CREATE ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(app_user)
            )
        )
        connection.execute(
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(sql.Identifier(app_user))
        )
    print("Application database role created.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--if-missing", action="store_true")
    arguments = parser.parse_args()
    try:
        provision(if_missing=arguments.if_missing)
    except (psycopg.Error, KeyError):
        # PostgreSQL errors can include SQL containing credentials. Keep logs clean.
        raise SystemExit("Database setup failed. Check injected settings, connectivity and privileges.") from None
