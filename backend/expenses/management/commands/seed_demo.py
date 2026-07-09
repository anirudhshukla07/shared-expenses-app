from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from expenses.models import ExpenseGroup, GroupMembership, Person
from expenses.services.importer import canonical_key

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo flatmates and membership windows for the assignment."

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(username="demo", defaults={"email": "demo@example.com"})
        if not user.has_usable_password():
            user.set_password("demo12345")
            user.save()

        group, _ = ExpenseGroup.objects.get_or_create(name="Flatmates Feb-Apr 2026", created_by=user)
        people = {}
        for name in ["Aisha", "Rohan", "Priya", "Meera", "Dev", "Sam", "Kabir"]:
            people[name], _ = Person.objects.get_or_create(canonical_name=canonical_key(name), defaults={"name": name})

        windows = [
            ("Aisha", date(2026, 2, 1), None, "member"),
            ("Rohan", date(2026, 2, 1), None, "member"),
            ("Priya", date(2026, 2, 1), None, "member"),
            ("Meera", date(2026, 2, 1), date(2026, 3, 31), "member"),
            ("Dev", date(2026, 3, 8), date(2026, 3, 13), "guest"),
            ("Sam", date(2026, 4, 15), None, "member"),
        ]
        for person_name, starts, ends, role in windows:
            GroupMembership.objects.get_or_create(
                group=group,
                person=people[person_name],
                starts_on=starts,
                defaults={"ends_on": ends, "role": role},
            )
        self.stdout.write(self.style.SUCCESS("Seeded demo user demo/demo12345 and assignment group."))
