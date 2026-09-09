"""Create a consistent SQLite backup before migrations or maintenance."""

import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Back up local SQLite to backups/. Use pg_dump for PostgreSQL deployments."

    def handle(self, *args, **options):
        config = settings.DATABASES["default"]
        if config["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Use pg_dump for a consistent PostgreSQL backup.")
        source = Path(config["NAME"])
        if not source.exists():
            raise CommandError("No SQLite database exists yet.")
        target_dir = settings.BASE_DIR.parent / "backups"
        target_dir.mkdir(exist_ok=True)
        target = target_dir / (
            "ganesh-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3.bak"
        )
        with sqlite3.connect(source) as original, sqlite3.connect(target) as backup:
            original.backup(backup)
        self.stdout.write(self.style.SUCCESS(f"Backup created: {target}"))
