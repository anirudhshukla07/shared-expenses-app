from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from expenses.models import ExpenseGroup, GroupMembership, Person
from expenses.services.importer import canonical_key

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo flatmates and membership windows for the assignment."

    @transaction.atomic
    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={"email": "demo@example.com", "is_active": True},
        )

        # get_or_create() does not call create_user(), so a newly created user may
        # not have the expected encoded password. Set it deterministically every
        # time so demo/demo12345 always works after a database reset.
        user.email = user.email or "demo@example.com"
        user.is_active = True
        user.set_password("demo12345")
        user.save(update_fields=["email", "is_active", "password"])

        group, _ = ExpenseGroup.objects.get_or_create(
            name="Flatmates Feb-Apr 2026",
            created_by=user,
        )

        people = {}
        for name in ["Aisha", "Rohan", "Priya", "Meera", "Dev", "Sam", "Kabir"]:
            person, _ = Person.objects.get_or_create(
                canonical_name=canonical_key(name),
                defaults={"name": name},
            )
            if person.name != name:
                person.name = name
                person.save(update_fields=["name", "updated_at"])
            people[name] = person

        windows = [
            ("Aisha", date(2026, 2, 1), None, "member"),
            ("Rohan", date(2026, 2, 1), None, "member"),
            ("Priya", date(2026, 2, 1), None, "member"),
            ("Meera", date(2026, 2, 1), date(2026, 3, 31), "member"),
            ("Dev", date(2026, 3, 8), date(2026, 3, 13), "guest"),
            ("Sam", date(2026, 4, 15), None, "member"),
        ]

        for person_name, starts, ends, role in windows:
            GroupMembership.objects.update_or_create(
                group=group,
                person=people[person_name],
                starts_on=starts,
                defaults={"ends_on": ends, "role": role},
            )

        action = "Created" if created else "Reset"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} demo user demo/demo12345 and seeded assignment group."
            )
        )