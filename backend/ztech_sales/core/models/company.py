"""Currency and company records."""

from __future__ import annotations

import zoneinfo

from django.core.validators import MaxValueValidator, MinLengthValidator, RegexValidator
from django.db import models
from django.utils import timezone as dj_timezone

from ztech_sales.core.models.base import BaseModel

CODE_VALIDATOR = RegexValidator(
    regex=r"^[a-z0-9][a-z0-9_-]*$",
    message="Use lower-case letters, digits, hyphen and underscore only, starting with a letter or digit.",
)


def validate_timezone(value: str) -> None:
    from django.core.exceptions import ValidationError

    if value not in zoneinfo.available_timezones():
        raise ValidationError(f"{value!r} is not a recognised IANA time zone name.")


class Currency(BaseModel):
    """An ISO 4217 currency and the precision its amounts are rounded to."""

    code = models.CharField(
        max_length=3,
        unique=True,
        validators=[
            MinLengthValidator(3),
            RegexValidator(r"^[A-Z]{3}$", "Use the three-letter ISO 4217 code."),
        ],
    )
    name = models.CharField(max_length=80)
    symbol = models.CharField(max_length=8, blank=True)
    decimal_places = models.PositiveSmallIntegerField(
        default=2,
        validators=[MaxValueValidator(6)],
        help_text="Number of decimal places amounts are rounded to. OMR uses 3, USD uses 2, JPY uses 0.",
    )
    rounding_mode = models.CharField(
        max_length=16,
        default="half_up",
        choices=[("half_up", "Half up"), ("half_even", "Half even (banker's)")],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "core_currency"
        ordering = ["code"]
        verbose_name_plural = "currencies"

    def __str__(self) -> str:
        return self.code


class CompanyQuerySet(models.QuerySet):
    def active(self) -> CompanyQuerySet:
        return self.filter(is_active=True)

    def default(self) -> Company:
        """Return the single company this deployment serves.

        Release 1 runs one legal company per environment. This raises rather
        than guessing if the environment has been configured with none or with
        more than one, because silently picking a company would mean writing a
        record against the wrong owner.

        Defined on the queryset rather than on the manager so that it still
        works after ``select_related`` or any other chained call.
        """
        companies = list(self.active()[:2])
        if not companies:
            raise Company.DoesNotExist(
                "No active company is configured. Run `manage.py bootstrap_client` to set one up."
            )
        if len(companies) > 1:
            raise Company.MultipleObjectsReturned(
                "More than one active company exists. Release 1 supports one legal company per "
                "environment; resolve the company explicitly instead of relying on the default."
            )
        return companies[0]


CompanyManager = models.Manager.from_queryset(CompanyQuerySet)


class Company(BaseModel):
    """The legal entity that owns every business record in this deployment."""

    code = models.SlugField(max_length=32, unique=True, validators=[CODE_VALIDATOR])
    legal_name = models.CharField(max_length=200)
    trade_name = models.CharField(max_length=200, blank=True)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="companies")
    timezone = models.CharField(
        max_length=64,
        default="Asia/Muscat",
        validators=[validate_timezone],
        help_text=(
            "IANA time zone of the legal entity. Date-sensitive business rules - notably "
            "quotation expiry - are evaluated in this zone, not in the viewer's zone."
        ),
    )

    tax_registration_number = models.CharField(max_length=40, blank=True)
    commercial_registration_number = models.CharField(max_length=40, blank=True)

    address_line1 = models.CharField(max_length=160, blank=True)
    address_line2 = models.CharField(max_length=160, blank=True)
    city = models.CharField(max_length=80, blank=True)
    region = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country_code = models.CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2 country code.")

    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=200, blank=True)

    # Branding is configuration, not code: the same tagged release serves every
    # client and each client supplies its own mark, colour and document footer.
    brand_primary_color = models.CharField(
        max_length=7,
        default="#1F3A5F",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use a hex colour such as #1F3A5F.")],
    )
    brand_accent_color = models.CharField(
        max_length=7,
        default="#2F7D6E",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use a hex colour such as #2F7D6E.")],
    )
    logo_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path within this client's private storage scope. Never served from a static URL.",
    )
    document_footer = models.TextField(
        blank=True,
        help_text="Shown at the foot of customer documents. Never include internal notes or approval policy.",
    )

    is_active = models.BooleanField(default=True)

    objects = CompanyManager()

    class Meta:
        db_table = "core_company"
        ordering = ["legal_name"]
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.trade_name or self.legal_name

    @property
    def display_name(self) -> str:
        return self.trade_name or self.legal_name

    @property
    def tzinfo(self) -> zoneinfo.ZoneInfo:
        return zoneinfo.ZoneInfo(self.timezone)

    def today(self):
        """Today's date in the company's own time zone."""
        return dj_timezone.now().astimezone(self.tzinfo).date()

    def localtime(self, value=None):
        """Convert an aware datetime (default: now) into the company's time zone."""
        return (value or dj_timezone.now()).astimezone(self.tzinfo)

    @property
    def decimal_places(self) -> int:
        return self.currency.decimal_places

    @property
    def rounding_mode(self) -> str:
        return self.currency.rounding_mode
