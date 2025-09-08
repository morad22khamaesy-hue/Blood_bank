# blood/management/commands/seed_inventory.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from blood.models import Donor, DonationUnit, BLOOD_TYPES

class Command(BaseCommand):
    help = "Seed initial inventory: create N AVAILABLE units per blood type (default 1000)."

    def add_arguments(self, parser):
        parser.add_argument("--per-type", type=int, default=1000,
                            help="Target units per blood type (default: 1000)")
        parser.add_argument("--expiry-days", type=int, default=42,
                            help="Expiry offset in days for seeded units (default: 42)")
        parser.add_argument("--reset", action="store_true",
                            help="Delete all DonationUnit records before seeding")

    def handle(self, *args, **opts):
        per_type = opts["per_type"]
        expiry_days = opts["expiry_days"]
        do_reset = opts["reset"]

        if do_reset:
            self.stdout.write(self.style.WARNING("Deleting ALL DonationUnit records..."))
            DonationUnit.objects.all().delete()

        # Seed donor (technical)
        seed_donor, _ = Donor.objects.get_or_create(
            national_id="000000001",
            defaults={"full_name": "Seed Stock"},
        )

        now = timezone.now()
        exp = now + timedelta(days=expiry_days)

        created_total = 0
        for bt, _ in BLOOD_TYPES:
            current = DonationUnit.objects.filter(blood_type=bt).count()
            to_add = max(0, per_type - current)
            if to_add == 0:
                self.stdout.write(f"{bt}: already has {current}, skipping.")
                continue

            batch = [
                DonationUnit(
                    donor=seed_donor,
                    blood_type=bt,
                    status=DonationUnit.Status.AVAILABLE,
                    expiry_at=exp,
                )
                for _ in range(to_add)
            ]
            DonationUnit.objects.bulk_create(batch, batch_size=2000)
            created_total += to_add
            self.stdout.write(self.style.SUCCESS(f"{bt}: added {to_add} units (now target={per_type})."))

        self.stdout.write(self.style.SUCCESS(f"Done. Created {created_total} unit(s) total."))
