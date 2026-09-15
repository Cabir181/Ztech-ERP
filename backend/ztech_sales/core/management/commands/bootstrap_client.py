"""Prepare a fresh client environment.

Creates the currencies, the legal company, the built-in roles and the document
sequences a new deployment needs. The command is idempotent: running it again
updates what it owns and leaves everything else alone, so it is safe to run as
part of a release.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ztech_sales.core.models import Company, Currency, DocumentSequence, ResetPeriod, Role
from ztech_sales.core.permissions import BUILTIN_ROLES

# Precision follows ISO 4217. The Omani rial has three decimal places; getting
# this wrong would silently change every total on every document.
SEED_CURRENCIES = [
    {"code": "OMR", "name": "Omani Rial", "symbol": "OMR", "decimal_places": 3},
    {"code": "AED", "name": "UAE Dirham", "symbol": "AED", "decimal_places": 2},
    {"code": "SAR", "name": "Saudi Riyal", "symbol": "SAR", "decimal_places": 2},
    {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2},
    {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2},
    {"code": "GBP", "name": "Pound Sterling", "symbol": "£", "decimal_places": 2},
]

SEED_SEQUENCES = [
    {"key": "quotation", "name": "Quotation", "prefix": "QT-", "padding": 5},
    {"key": "sales_order", "name": "Sales order", "prefix": "SO-", "padding": 5},
    {"key": "customer", "name": "Customer", "prefix": "CUS-", "padding": 5},
]


class Command(BaseCommand):
    help = "Create or update the company, built-in roles and document sequences for this deployment."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--code", required=True, help="Short client code, for example acme.")
        parser.add_argument("--legal-name", required=True, help="Registered legal name of the company.")
        parser.add_argument("--trade-name", default="", help="Trading name shown on documents.")
        parser.add_argument("--currency", default="OMR", help="ISO 4217 code of the company currency.")
        parser.add_argument("--timezone", default="Asia/Muscat", help="IANA time zone of the company.")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        self.verbosity = options.get("verbosity", 1)
        currencies = self._seed_currencies()

        currency_code = options["currency"].upper()
        currency = currencies.get(currency_code)
        if currency is None:
            raise CommandError(
                f"Currency {currency_code} is not seeded. Add it to SEED_CURRENCIES or pick one of "
                f"{', '.join(sorted(currencies))}."
            )

        company, created = Company.objects.get_or_create(
            code=options["code"],
            defaults={
                "legal_name": options["legal_name"],
                "trade_name": options["trade_name"],
                "currency": currency,
                "timezone": options["timezone"],
            },
        )
        if not created:
            company.legal_name = options["legal_name"]
            company.trade_name = options["trade_name"]
            company.currency = currency
            company.timezone = options["timezone"]
            company.full_clean(exclude=["currency"])
            company.save()

        self._say(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} company {company.legal_name} "
                f"({company.code}, {currency.code}, {company.timezone})."
            )
        )

        self._seed_roles(company)
        self._seed_sequences(company)
        self._say(self.style.SUCCESS("Client environment is ready."))

    def _say(self, message: str) -> None:
        if self.verbosity:
            self.stdout.write(message)

    def _seed_currencies(self) -> dict[str, Currency]:
        result: dict[str, Currency] = {}
        for spec in SEED_CURRENCIES:
            currency, created = Currency.objects.get_or_create(code=spec["code"], defaults=spec)
            if not created and currency.decimal_places != spec["decimal_places"]:
                # Changing precision after amounts exist would restate history.
                self._say(
                    self.style.WARNING(
                        f"{currency.code} is configured with {currency.decimal_places} decimal places "
                        f"but ISO 4217 specifies {spec['decimal_places']}. Left unchanged - review it "
                        f"before recording further amounts."
                    )
                )
            result[currency.code] = currency
        return result

    def _seed_roles(self, company: Company) -> None:
        for code, spec in BUILTIN_ROLES.items():
            role, created = Role.objects.get_or_create(
                company=company,
                code=code,
                defaults={"name": spec["name"], "description": spec["description"], "is_system": True},
            )
            if not created:
                role.name = spec["name"]
                role.description = spec["description"]
                role.is_system = True
                role.save()
            role.set_permissions(list(spec["permissions"]))
            self._say(
                f"  {'created' if created else 'updated'} role {role.name} "
                f"({len(spec['permissions'])} permissions)"
            )

    def _seed_sequences(self, company: Company) -> None:
        for spec in SEED_SEQUENCES:
            _, created = DocumentSequence.objects.get_or_create(
                company=company,
                key=spec["key"],
                defaults={
                    "name": spec["name"],
                    "prefix": spec["prefix"],
                    "padding": spec["padding"],
                    "reset_period": ResetPeriod.YEARLY,
                },
            )
            if created:
                self._say(f"  created sequence {spec['key']} ({spec['prefix']})")
