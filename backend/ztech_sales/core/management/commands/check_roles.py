"""Report roles that reference permission codes this release no longer defines.

Run after an upgrade. A retired code is ignored at resolution time rather than
granting anything, so this is a housekeeping report, not an incident.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from ztech_sales.core.models import Role, RolePermission
from ztech_sales.core.permissions import ALL_PERMISSION_CODES


class Command(BaseCommand):
    help = "List role permissions that are no longer part of the application's permission catalogue."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--prune", action="store_true", help="Delete the stale rows instead of only reporting them."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        stale = RolePermission.objects.exclude(code__in=sorted(ALL_PERMISSION_CODES)).select_related("role")
        count = stale.count()
        if not count:
            self.stdout.write(self.style.SUCCESS("Every role permission is part of the current catalogue."))
        else:
            for row in stale:
                self.stdout.write(self.style.WARNING(f"  {row.role.code}: {row.code} (not in this release)"))
            if options["prune"]:
                stale.delete()
                self.stdout.write(self.style.SUCCESS(f"Removed {count} stale role permission(s)."))
            else:
                self.stdout.write(f"{count} stale role permission(s). Re-run with --prune to remove them.")

        empty = [role.code for role in Role.objects.filter(is_active=True) if not role.permission_codes]
        if empty:
            self.stdout.write(
                self.style.WARNING(f"Active roles granting no permissions: {', '.join(sorted(empty))}")
            )
