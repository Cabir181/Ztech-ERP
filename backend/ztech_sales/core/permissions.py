"""Application permission catalogue and permission-checking helpers.

Permissions are declared in code, not in the database, so that an upgrade can
add or retire a permission without a data migration. Roles are stored in the
database and reference these codes; a role holding a code that is no longer in
the catalogue is simply ignored at resolution time and reported by the
``check_roles`` management command.

Every protected operation - list, detail, report, export, file download and
state transition - is gated on a code from this catalogue. Nothing relies on an
identifier being hard to guess or on a button being hidden in the interface.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PermissionDef:
    code: str
    module: str
    label: str
    description: str


def _p(code: str, module: str, label: str, description: str) -> PermissionDef:
    return PermissionDef(code=code, module=module, label=label, description=description)


PERMISSIONS: tuple[PermissionDef, ...] = (
    # -- administration -----------------------------------------------------
    _p(
        "settings.view",
        "administration",
        "View settings",
        "Read company profile, branding and system settings.",
    ),
    _p(
        "settings.manage",
        "administration",
        "Manage settings",
        "Change company profile, branding and system settings.",
    ),
    _p("user.view", "administration", "View users", "List and open user accounts."),
    _p(
        "user.manage",
        "administration",
        "Manage users",
        "Create, edit, activate and deactivate user accounts.",
    ),
    _p("role.view", "administration", "View roles", "List roles and the permissions they grant."),
    _p("role.manage", "administration", "Manage roles", "Create and edit roles and assign roles to users."),
    _p("audit.view", "administration", "View audit trail", "Read the immutable audit trail."),
    # -- customers ----------------------------------------------------------
    _p("customer.view", "customers", "View customers", "List and open customer records and their addresses."),
    _p(
        "customer.manage",
        "customers",
        "Manage customers",
        "Create and edit customers, contacts and addresses.",
    ),
    # -- catalog ------------------------------------------------------------
    _p("catalog.view", "catalog", "View catalog", "List and open products, units of measure and taxes."),
    _p(
        "catalog.manage", "catalog", "Manage catalog", "Create and edit products, units of measure and taxes."
    ),
    # -- pricing ------------------------------------------------------------
    _p(
        "pricing.view",
        "pricing",
        "View pricing",
        "List and open pricelists, payment terms and quotation templates.",
    ),
    _p(
        "pricing.manage",
        "pricing",
        "Manage pricing",
        "Create and edit pricelists, payment terms and quotation templates.",
    ),
    # -- sales --------------------------------------------------------------
    _p("quotation.view.own", "sales", "View own quotations", "Read quotations the user owns."),
    _p(
        "quotation.view.all", "sales", "View all quotations", "Read every quotation belonging to the company."
    ),
    _p("quotation.create", "sales", "Create quotations", "Create new quotations and revisions."),
    _p("quotation.edit.own", "sales", "Edit own quotations", "Edit draft quotations the user owns."),
    _p(
        "quotation.edit.all",
        "sales",
        "Edit all quotations",
        "Edit any draft quotation belonging to the company.",
    ),
    _p("quotation.issue", "sales", "Issue quotations", "Issue a quotation revision to the customer."),
    _p(
        "quotation.record_acceptance",
        "sales",
        "Record acceptance",
        "Record customer acceptance of an issued revision.",
    ),
    _p(
        "quotation.confirm",
        "sales",
        "Confirm sales orders",
        "Confirm an accepted quotation into a sales order.",
    ),
    _p("quotation.cancel", "sales", "Cancel quotations", "Cancel a quotation or a confirmed sales order."),
    _p(
        "quotation.override_price",
        "sales",
        "Override unit prices",
        "Enter a unit price other than the pricelist price.",
    ),
    _p("order.view.own", "sales", "View own sales orders", "Read sales orders the user owns."),
    _p(
        "order.view.all", "sales", "View all sales orders", "Read every sales order belonging to the company."
    ),
    # -- approvals ----------------------------------------------------------
    _p("approval.request", "approvals", "Request approval", "Submit a quotation for internal approval."),
    _p(
        "approval.decide",
        "approvals",
        "Decide approvals",
        "Approve or reject a quotation submitted for approval.",
    ),
    _p(
        "approval.reassign",
        "approvals",
        "Reassign approvals",
        "Reassign a pending approval to another approver.",
    ),
    _p("approval.view", "approvals", "View approvals", "Read approval requests and their decision history."),
    # -- communications -----------------------------------------------------
    _p("document.download", "communications", "Download documents", "Download generated customer documents."),
    _p("attachment.view", "communications", "View attachments", "List and download attachments on a record."),
    _p(
        "attachment.manage",
        "communications",
        "Manage attachments",
        "Upload and remove attachments on a record.",
    ),
    _p("email.send", "communications", "Send email", "Queue a customer document for delivery by email."),
    _p(
        "email.view_status",
        "communications",
        "View delivery status",
        "Read the delivery status of queued email.",
    ),
    _p(
        "activity.manage",
        "communications",
        "Manage activities",
        "Create, reassign and complete follow-up activities.",
    ),
    # -- reporting ----------------------------------------------------------
    _p("report.view", "reports", "View reports", "Open the reporting screens and drill through to records."),
    _p("report.export", "reports", "Export reports", "Export report results to CSV."),
    # -- integrations -------------------------------------------------------
    _p(
        "integration.view",
        "integrations",
        "View integration events",
        "Read the outbound integration event log.",
    ),
    _p(
        "integration.manage",
        "integrations",
        "Manage integrations",
        "Configure consumers and replay integration events.",
    ),
)

PERMISSIONS_BY_CODE: dict[str, PermissionDef] = {p.code: p for p in PERMISSIONS}
ALL_PERMISSION_CODES: frozenset[str] = frozenset(PERMISSIONS_BY_CODE)


def is_known_permission(code: str) -> bool:
    return code in ALL_PERMISSION_CODES


def validate_permission_codes(codes: list[str]) -> list[str]:
    """Return the unknown codes in ``codes`` (empty when all are valid)."""
    return sorted({code for code in codes if code not in ALL_PERMISSION_CODES})


# ---------------------------------------------------------------------------
# Built-in roles
#
# These are seeded into a new client environment and can be edited afterwards by
# a user holding ``role.manage``. They are a starting point, not a hard-coded
# authorisation model: every check in the application reads the database.
# ---------------------------------------------------------------------------

SYSTEM_ADMINISTRATOR = "system_administrator"
SALES_MANAGER = "sales_manager"
SALES_REPRESENTATIVE = "sales_representative"
APPROVER = "approver"
READ_ONLY = "read_only"

BUILTIN_ROLES: dict[str, dict[str, object]] = {
    SYSTEM_ADMINISTRATOR: {
        "name": "System Administrator",
        "description": "Full access to configuration, users and roles. Does not grant approval authority.",
        "permissions": sorted(ALL_PERMISSION_CODES - {"approval.decide"}),
    },
    SALES_MANAGER: {
        "name": "Sales Manager",
        "description": "Full visibility of the sales pipeline, including other users' quotations.",
        "permissions": [
            "settings.view",
            "user.view",
            "role.view",
            "audit.view",
            "customer.view",
            "customer.manage",
            "catalog.view",
            "pricing.view",
            "pricing.manage",
            "quotation.view.all",
            "quotation.create",
            "quotation.edit.all",
            "quotation.issue",
            "quotation.record_acceptance",
            "quotation.confirm",
            "quotation.cancel",
            "quotation.override_price",
            "order.view.all",
            "approval.request",
            "approval.view",
            "document.download",
            "attachment.view",
            "attachment.manage",
            "email.send",
            "email.view_status",
            "activity.manage",
            "report.view",
            "report.export",
            "integration.view",
        ],
    },
    SALES_REPRESENTATIVE: {
        "name": "Sales Representative",
        "description": "Works on their own quotations and customers.",
        "permissions": [
            "customer.view",
            "customer.manage",
            "catalog.view",
            "pricing.view",
            "quotation.view.own",
            "quotation.create",
            "quotation.edit.own",
            "quotation.issue",
            "quotation.record_acceptance",
            "quotation.confirm",
            "quotation.cancel",
            "quotation.override_price",
            "order.view.own",
            "approval.request",
            "approval.view",
            "document.download",
            "attachment.view",
            "attachment.manage",
            "email.send",
            "email.view_status",
            "activity.manage",
            "report.view",
        ],
    },
    APPROVER: {
        "name": "Approver",
        "description": (
            "Decides discount and price-concession approvals. Held in addition to a sales role; "
            "the holder can never approve a request they raised themselves."
        ),
        "permissions": [
            "quotation.view.all",
            "order.view.all",
            "customer.view",
            "catalog.view",
            "pricing.view",
            "approval.view",
            "approval.decide",
            "approval.reassign",
            "document.download",
            "attachment.view",
            "report.view",
        ],
    },
    READ_ONLY: {
        "name": "Read Only",
        "description": "Read-only visibility of customers, catalog, quotations and reports.",
        "permissions": [
            "settings.view",
            "customer.view",
            "catalog.view",
            "pricing.view",
            "quotation.view.all",
            "order.view.all",
            "approval.view",
            "document.download",
            "attachment.view",
            "report.view",
        ],
    },
}
