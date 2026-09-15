import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, api } from "../api/client";
import { useResource } from "../api/hooks";
import type { Company } from "../api/types";
import { useSession } from "../auth/SessionProvider";
import { useToast } from "../components/Toast";
import { TextAreaField, TextField } from "../components/form";
import { Banner, Button, Card, LoadingState, PageHeader } from "../components/primitives";
import { useUnsavedChanges } from "../components/useUnsavedChanges";

const EDITABLE = [
  "legal_name",
  "trade_name",
  "timezone",
  "tax_registration_number",
  "commercial_registration_number",
  "address_line1",
  "address_line2",
  "city",
  "region",
  "postal_code",
  "country_code",
  "phone",
  "email",
  "website",
  "brand_primary_color",
  "brand_accent_color",
  "document_footer",
] as const;

type EditableField = (typeof EDITABLE)[number];
type FormState = Record<EditableField, string>;

export function CompanySettingsPage() {
  const toast = useToast();
  const { can, refresh } = useSession();
  const readOnly = !can("settings.manage");

  const company = useResource<Company>((signal) => api.get<Company>("/api/company/", undefined, signal), []);
  const [form, setForm] = useState<FormState | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  useUnsavedChanges(dirty);

  useEffect(() => {
    if (!company.data) return;
    const record = company.data;
    setForm(
      Object.fromEntries(EDITABLE.map((field) => [field, String(record[field] ?? "")])) as FormState,
    );
    setVersion(record.version);
    setDirty(false);
  }, [company.data]);

  function update(field: EditableField, value: string) {
    setForm((current) => (current ? { ...current, [field]: value } : current));
    setDirty(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form || version === null) return;
    setSaving(true);
    setFormError(null);
    setConflict(false);
    setFieldErrors({});
    try {
      await api.patch<Company>("/api/company/", { ...form, version });
      setDirty(false);
      toast.success("Company settings saved.");
      // Branding colours are applied from the session payload.
      await refresh();
      company.reload();
    } catch (caught) {
      if (caught instanceof ApiError) {
        setFieldErrors(caught.fieldErrors());
        if (caught.isConflict) setConflict(true);
        else setFormError(caught.message);
      } else {
        setFormError("Could not save. Check your connection and try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (company.loading || !form) return <LoadingState label="Loading company settings" />;
  if (company.error) return <Banner tone="error">{company.error.message}</Banner>;

  return (
    <form onSubmit={handleSubmit} noValidate>
      <PageHeader
        title="Company"
        description="The legal entity that owns every record in this environment."
        actions={
          !readOnly ? (
            <Button type="submit" variant="primary" busy={saving} disabled={!dirty}>
              Save changes
            </Button>
          ) : null
        }
      />

      {conflict ? (
        <Banner tone="warning" title="These settings were changed by someone else">
          Nothing was saved. Reload and reapply your changes.{" "}
          <Button size="sm" onClick={() => company.reload()}>
            Reload
          </Button>
        </Banner>
      ) : null}
      {formError ? <Banner tone="error">{formError}</Banner> : null}
      {readOnly ? <Banner tone="info">You have read-only access to company settings.</Banner> : null}

      <Card title="Identity">
        <div className="grid-2">
          <TextField
            label="Legal name"
            required
            value={form.legal_name}
            errors={fieldErrors.legal_name}
            disabled={readOnly}
            onChange={(event) => update("legal_name", event.target.value)}
          />
          <TextField
            label="Trading name"
            hint="Shown on documents and in the interface when set."
            value={form.trade_name}
            errors={fieldErrors.trade_name}
            disabled={readOnly}
            onChange={(event) => update("trade_name", event.target.value)}
          />
          <TextField
            label="Tax registration number"
            value={form.tax_registration_number}
            errors={fieldErrors.tax_registration_number}
            disabled={readOnly}
            onChange={(event) => update("tax_registration_number", event.target.value)}
          />
          <TextField
            label="Commercial registration number"
            value={form.commercial_registration_number}
            errors={fieldErrors.commercial_registration_number}
            disabled={readOnly}
            onChange={(event) => update("commercial_registration_number", event.target.value)}
          />
        </div>
      </Card>

      <Card
        title="Currency and time zone"
        hint="Monetary precision follows the currency. Date-sensitive rules such as quotation expiry are evaluated in this time zone, not in the viewer's."
      >
        <dl className="definition">
          <dt>Currency</dt>
          <dd>
            {company.data?.currency.code} — {company.data?.currency.name} (
            {company.data?.currency.decimal_places} decimal places, {company.data?.currency.rounding_mode})
          </dd>
        </dl>
        <TextField
          label="Time zone"
          required
          hint="IANA name, for example Asia/Muscat."
          value={form.timezone}
          errors={fieldErrors.timezone}
          disabled={readOnly}
          onChange={(event) => update("timezone", event.target.value)}
        />
      </Card>

      <Card title="Address and contact">
        <div className="grid-2">
          <TextField
            label="Address line 1"
            value={form.address_line1}
            disabled={readOnly}
            onChange={(event) => update("address_line1", event.target.value)}
          />
          <TextField
            label="Address line 2"
            value={form.address_line2}
            disabled={readOnly}
            onChange={(event) => update("address_line2", event.target.value)}
          />
          <TextField
            label="City"
            value={form.city}
            disabled={readOnly}
            onChange={(event) => update("city", event.target.value)}
          />
          <TextField
            label="Region"
            value={form.region}
            disabled={readOnly}
            onChange={(event) => update("region", event.target.value)}
          />
          <TextField
            label="Postal code"
            value={form.postal_code}
            disabled={readOnly}
            onChange={(event) => update("postal_code", event.target.value)}
          />
          <TextField
            label="Country code"
            hint="Two-letter ISO code, for example OM."
            maxLength={2}
            value={form.country_code}
            errors={fieldErrors.country_code}
            disabled={readOnly}
            onChange={(event) => update("country_code", event.target.value.toUpperCase())}
          />
          <TextField
            label="Phone"
            value={form.phone}
            disabled={readOnly}
            onChange={(event) => update("phone", event.target.value)}
          />
          <TextField
            label="Email"
            type="email"
            value={form.email}
            errors={fieldErrors.email}
            disabled={readOnly}
            onChange={(event) => update("email", event.target.value)}
          />
        </div>
        <TextField
          label="Website"
          value={form.website}
          disabled={readOnly}
          onChange={(event) => update("website", event.target.value)}
        />
      </Card>

      <Card title="Branding" hint="Applied to the interface and to customer documents.">
        <div className="grid-2">
          <TextField
            label="Primary colour"
            type="color"
            value={form.brand_primary_color}
            errors={fieldErrors.brand_primary_color}
            disabled={readOnly}
            onChange={(event) => update("brand_primary_color", event.target.value)}
          />
          <TextField
            label="Accent colour"
            type="color"
            value={form.brand_accent_color}
            errors={fieldErrors.brand_accent_color}
            disabled={readOnly}
            onChange={(event) => update("brand_accent_color", event.target.value)}
          />
        </div>
        <TextAreaField
          label="Document footer"
          hint="Printed at the foot of customer documents. Never put internal notes or approval policy here - customers see it."
          value={form.document_footer}
          errors={fieldErrors.document_footer}
          disabled={readOnly}
          onChange={(event) => update("document_footer", event.target.value)}
        />
      </Card>
    </form>
  );
}
