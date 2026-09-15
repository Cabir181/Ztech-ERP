import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { useResource } from "../api/hooks";
import type { Paginated, Role, User, UserWrite } from "../api/types";
import { useSession } from "../auth/SessionProvider";
import { useToast } from "../components/Toast";
import { CheckboxField, TextField } from "../components/form";
import { Banner, Button, Card, LoadingState, PageHeader } from "../components/primitives";
import { confirmDiscard, useUnsavedChanges } from "../components/useUnsavedChanges";

interface FormState {
  email: string;
  full_name: string;
  job_title: string;
  phone: string;
  is_active: boolean;
  is_system_administrator: boolean;
  role_ids: string[];
  initial_password: string;
}

const BLANK: FormState = {
  email: "",
  full_name: "",
  job_title: "",
  phone: "",
  is_active: true,
  is_system_administrator: false,
  role_ids: [],
  initial_password: "",
};

export function UserFormPage() {
  const { userId } = useParams<{ userId: string }>();
  const isNew = !userId || userId === "new";
  const navigate = useNavigate();
  const toast = useToast();
  const { can, refresh, session } = useSession();
  const readOnly = !can("user.manage");

  const [form, setForm] = useState<FormState>(BLANK);
  const [version, setVersion] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  useUnsavedChanges(dirty);

  const roles = useResource<Paginated<Role>>(
    (signal) => api.get<Paginated<Role>>("/api/roles/", { page_size: 200 }, signal),
    [],
  );
  const existing = useResource<User | null>(
    (signal) => (isNew ? Promise.resolve(null) : api.get<User>(`/api/users/${userId}/`, undefined, signal)),
    [userId, isNew],
  );

  useEffect(() => {
    if (!existing.data) return;
    const user = existing.data;
    setForm({
      email: user.email,
      full_name: user.full_name,
      job_title: user.job_title,
      phone: user.phone,
      is_active: user.is_active,
      is_system_administrator: user.is_system_administrator,
      role_ids: user.roles.map((role) => role.id),
      initial_password: "",
    });
    setVersion(user.version);
    setDirty(false);
  }, [existing.data]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setDirty(true);
  }

  function toggleRole(roleId: string, checked: boolean) {
    update(
      "role_ids",
      checked ? [...form.role_ids, roleId] : form.role_ids.filter((id) => id !== roleId),
    );
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    setConflict(false);
    setFieldErrors({});

    const payload: UserWrite = {
      email: form.email,
      full_name: form.full_name,
      job_title: form.job_title,
      phone: form.phone,
      is_active: form.is_active,
      is_system_administrator: form.is_system_administrator,
      role_ids: form.role_ids,
    };
    if (isNew && form.initial_password) payload.initial_password = form.initial_password;
    if (!isNew && version !== null) payload.version = version;

    try {
      const saved = isNew
        ? await api.post<User>("/api/users/", payload)
        : await api.patch<User>(`/api/users/${userId}/`, payload);
      setDirty(false);
      toast.success(isNew ? `Created ${saved.full_name}.` : `Saved ${saved.full_name}.`);
      // The signed-in user's own roles may have just changed.
      if (session && saved.id === session.user.id) await refresh();
      navigate(`/users/${saved.id}`, { replace: true });
      if (!isNew) existing.reload();
    } catch (caught) {
      if (caught instanceof ApiError) {
        setFieldErrors(caught.fieldErrors());
        if (caught.isConflict) {
          setConflict(true);
        } else {
          setFormError(caught.message);
        }
      } else {
        setFormError("Could not save. Check your connection and try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (!isNew && existing.loading) return <LoadingState label="Loading user" />;
  if (!isNew && existing.error) return <Banner tone="error">{existing.error.message}</Banner>;

  return (
    <form onSubmit={handleSubmit} noValidate>
      <PageHeader
        title={isNew ? "Add user" : form.full_name || "User"}
        description={isNew ? "Create an account for a named person." : form.email}
        actions={
          <>
            <Button
              onClick={() => {
                if (confirmDiscard(dirty)) navigate("/users");
              }}
            >
              Back to users
            </Button>
            {!readOnly ? (
              <Button type="submit" variant="primary" busy={saving}>
                {isNew ? "Create user" : "Save changes"}
              </Button>
            ) : null}
          </>
        }
      />

      {conflict ? (
        <Banner tone="warning" title="This user was changed by someone else">
          Your copy is out of date, so nothing was saved. Reload to see the current values, then reapply your
          changes.{" "}
          <Button size="sm" onClick={() => existing.reload()}>
            Reload
          </Button>
        </Banner>
      ) : null}
      {formError ? <Banner tone="error">{formError}</Banner> : null}
      {readOnly ? (
        <Banner tone="info">You have read-only access to user administration.</Banner>
      ) : null}

      <Card title="Details">
        <div className="grid-2">
          <TextField
            label="Full name"
            required
            autoComplete="off"
            value={form.full_name}
            errors={fieldErrors.full_name}
            disabled={readOnly}
            onChange={(event) => update("full_name", event.target.value)}
          />
          <TextField
            label="Email address"
            type="email"
            required
            autoComplete="off"
            hint="Used to sign in. Must be unique."
            value={form.email}
            errors={fieldErrors.email}
            disabled={readOnly}
            onChange={(event) => update("email", event.target.value)}
          />
          <TextField
            label="Job title"
            value={form.job_title}
            errors={fieldErrors.job_title}
            disabled={readOnly}
            onChange={(event) => update("job_title", event.target.value)}
          />
          <TextField
            label="Phone"
            value={form.phone}
            errors={fieldErrors.phone}
            disabled={readOnly}
            onChange={(event) => update("phone", event.target.value)}
          />
        </div>

        {isNew ? (
          <TextField
            label="Initial password"
            type="password"
            autoComplete="new-password"
            hint="The user is asked to change this the first time they sign in. Leave blank to create the account without a usable password."
            value={form.initial_password}
            errors={fieldErrors.initial_password}
            onChange={(event) => update("initial_password", event.target.value)}
          />
        ) : null}

        <CheckboxField
          label="Active"
          hint="An inactive account cannot sign in and loses access immediately, including on a session that is already open."
          checked={form.is_active}
          disabled={readOnly}
          onChange={(checked) => update("is_active", checked)}
        />
        <CheckboxField
          label="System administrator"
          hint="Grants every permission except approval authority, which is granted by the Approver role."
          checked={form.is_system_administrator}
          disabled={readOnly}
          onChange={(checked) => update("is_system_administrator", checked)}
        />
      </Card>

      <Card title="Roles" hint="Roles decide what this person may do. Saving replaces the whole set.">
        {roles.loading ? (
          <LoadingState label="Loading roles" />
        ) : (
          (roles.data?.results ?? []).map((role) => (
            <CheckboxField
              key={role.id}
              label={role.name}
              hint={role.description}
              checked={form.role_ids.includes(role.id)}
              disabled={readOnly}
              onChange={(checked) => toggleRole(role.id, checked)}
            />
          ))
        )}
        {fieldErrors.role_ids ? <span className="field__error">{fieldErrors.role_ids.join(" ")}</span> : null}
      </Card>
    </form>
  );
}
