"""Non-destructive sample budgets. Safe to run repeatedly."""

from datetime import date
from django.core.management.base import BaseCommand
from core.models import Plan, Member


class Command(BaseCommand):
    help = "Add labeled demo budgets and a volunteer without deleting existing records."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=date.today().year)

    def handle(self, *args, **options):
        year = options["year"]
        for title, category, budget in [
            ("[DEMO] Mandap and decoration", "Decoration", "60000"),
            ("[DEMO] Prasadam and annadanam", "Food & prasadam", "45000"),
            ("[DEMO] Cultural evening", "Cultural programs", "25000"),
        ]:
            Plan.objects.get_or_create(
                title=title,
                target_date=date(year, 9, 1),
                defaults={"category": category, "budget": budget},
            )
        Member.objects.get_or_create(
            email="volunteer@example.test",
            defaults={"name": "[DEMO] Festival volunteer", "position": "Volunteer"},
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Labeled sample budgets added. No financial entries or existing data were changed."
            )
        )
