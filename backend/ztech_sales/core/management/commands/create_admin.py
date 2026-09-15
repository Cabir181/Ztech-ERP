"""Create the first administrator account for a deployment.

Intended to be run once, immediately after ``bootstrap_client``. The password is
read from the environment or prompted for; it is never accepted as a command
line argument, because arguments end up in shell history and in process
listings.
"""

from __future__ import annotations

import getpass
import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ztech_sales.core.context import request_context
from ztech_sales.core.models import Company, Role, User, UserRole
from ztech_sales.core.permissions import SYSTEM_ADMINISTRATOR
from ztech_sales.core.services.audit import record_audit


class Command(BaseCommand):
    help = "Create the first administrator account. Password comes from ZTECH_ADMIN_PASSWORD or a prompt."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--full-name", required=True)
        parser.add_argument(
            "--allow-existing",
            action="store_true",
            help="Do nothing instead of failing when the account already exists.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        email = options["email"].strip().lower()

        try:
            company = Company.objects.default()
        except Company.DoesNotExist as exc:
            raise CommandError("Run `manage.py bootstrap_client` before creating the administrator.") from exc

        if User.objects.filter(email=email).exists():
            if options["allow_existing"]:
                self.stdout.write(self.style.WARNING(f"{email} already exists; nothing to do."))
                return
            raise CommandError(f"A user with the email address {email} already exists.")

        password = os.environ.get("ZTECH_ADMIN_PASSWORD")
        if not password:
            password = getpass.getpass("Password for the new administrator: ")
            if password != getpass.getpass("Repeat the password: "):
                raise CommandError("The two passwords do not match.")
        if not password:
            raise CommandError("A password is required.")

        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("Password rejected: " + " ".join(exc.messages)) from exc

        with request_context(source="command"):
            user = User.objects.create_administrator(
                email=email, full_name=options["full_name"], password=password
            )
            user.must_change_password = True
            user.save(update_fields=["must_change_password"])

            role = Role.objects.filter(company=company, code=SYSTEM_ADMINISTRATOR).first()
            if role is not None:
                UserRole.objects.get_or_create(user=user, role=role)

            record_audit(
                company=company,
                action="user.created",
                entity_type="core.user",
                entity_id=user.id,
                entity_label=user.full_name,
                summary=f"Created the initial administrator account {user.email} from the command line.",
                actor=user,
                source="command",
            )

        self.stdout.write(self.style.SUCCESS(f"Created administrator {email}."))
        self.stdout.write("The account is flagged to change its password at first sign-in.")
        self.stdout.write(
            self.style.WARNING(
                "Approval authority is NOT granted by the administrator flag. Assign the Approver "
                "role to the people who are allowed to decide discount approvals."
            )
        )
