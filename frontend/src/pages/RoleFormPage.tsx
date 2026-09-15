import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { useResource } from "../api/hooks";
import type { PermissionDef, Role } from "../api/types";
import { useSession } from "../auth/SessionProvider";
import { useToast } from "../components/Toast";
import { CheckboxField, TextAreaField, TextField } from "../components/form";
import { Badge, Banner, Button, Card, LoadingState, PageHeader } from "../components/primitives";
import { confirmDiscard, useUnsavedChanges } from "../components/useUnsavedChanges";

export function RoleFormPage() {
  const { roleId } = useParams<{ roleId: string }>();
  const isNew = !roleId || roleId === "new";
  const navigate = useNavigate();
  const toast = useToast();
  const { can, refresh } = useSession();
  const readOnly = !can("role.manage");

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSystem, setIsSystem] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [version, setVersion] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  useUnsavedChanges(dirty);

  const catalogue = useResource<PermissionDef[]>(
    (signal) => api.get<PermissionDef[]>("/api/system/permissions/", undefined, signal),
    [],
  );
  const existing = useResource<Role | null>(
    (signal) => (isNew ? Promise.resolve(null) : api.get<Role>(`/api/roles/${roleId}/`, undefined, signal)),
    [roleId, isNew],
  );

  useEffect(() => {
    if (!existing.data) return;
    const role = existing.data;
    setCode(role.code);
    setName(role.name);
    setDescription(role.description);
    setIsActive(role.is_active);
    setIsSystem(role.is_system);
    setSelected(new Set(role.permissions));
    setVersion(role.version);
    setDirty(false);
  }, [existing.data]);

  const modules = useMemo(() => {
    const grouped = new Map<string, PermissionDef[]>();
    for (const permission of catalogue.data ?? []) {
      const bucket = grouped.get(permission.module) ?? [];
      bucket.push(permission);
      grouped.set(permission.module, bucket);
    }
    return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [catalogue.data]);

  function togglePermission(permissionCode: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(permissionCode);
      else next.delete(permissionCode);
      return next;
    });
    setDirty(true);
  }

  function toggleModule(permissions: PermissionDef[], checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const permission of permissions) {
        if (checked) next.add(permission.code);
        else next.delete(permission.code);
      }
      return next;
    });
    setDirty(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    setConflict(false);
    setFieldErrors({});

    const payload: Record<string, unknown> = {
      code,
      name,
      description,
      is_active: isActive,
      permissions: [...selected].sort(),
    };
    if (!isNew && version !== null) payload.version = version;

    try {
      const saved = isNew
        ? await api.post<Role>("/api/roles/", payload)
        : await api.patch<Role>(`/api/roles/${roleId}/`, payload);
      setDirty(false);
      toast.success(isNew ? `Created the ${saved.name} role.` : `Saved the ${saved.name} role.`);
      // Editing a role the signed-in user holds changes their own menu.
      await refresh();
      navigate(`/roles/${saved.id}`, { replace: true });
      if (!isNew) existing.reload();
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

  if (!isNew && existing.loading) return <LoadingState label="Loading role" />;
  if (!isNew && existing.error) return <Banner tone="error">{existing.error.message}</Banner>;

  return (
    <form onSubmit={handleSubmit} noValidate>
      <PageHeader
        title={isNew ? "Add role" : name || "Role"}
        description={`${selected.size} permission${selected.size === 1 ? "" : "s"} selected`}
        actions={
          <>
            <Button
              onClick={() => {
                if (confirmDiscard(dirty)) navigate("/roles");
              }}
            >
              Back to roles
            </Button>
            {!readOnly ? (
              <Button type="submit" variant="primary" busy={saving}>
                {isNew ? "Create role" : "Save changes"}
              </Button>
            ) : null}
          </>
        }
      />

      {conflict ? (
        <Banner tone="warning" title="This role was changed by someone else">
          Nothing was saved. Reload to see the current permissions, then reapply your changes.{" "}
          <Button size="sm" onClick={() => existing.reload()}>
            Reload
          </Button>
        </Banner>
      ) : null}
      {formError ? <Banner tone="error">{formError}</Banner> : null}
      {isSystem ? (
        <Banner tone="info">
          This is a built-in role. Its permissions can be changed, but its code cannot, and it cannot be
          deactivated.
        </Banner>
      ) : null}

      <Card title="Details">
        <div className="grid-2">
          <TextField
            label="Name"
            required
            value={name}
            errors={fieldErrors.name}
            disabled={readOnly}
            onChange={(event) => {
              setName(event.target.value);
              setDirty(true);
            }}
          />
          <TextField
            label="Code"
            required
            hint="Lower-case identifier used in filters and reports. Cannot be changed on a built-in role."
            value={code}
            errors={fieldErrors.code}
            disabled={readOnly || isSystem}
            onChange={(event) => {
              setCode(event.target.value);
              setDirty(true);
            }}
          />
        </div>
        <TextAreaField
          label="Description"
          hint="Say what this role is for, so the next administrator does not have to guess."
          value={description}
          errors={fieldErrors.description}
          disabled={readOnly}
          onChange={(event) => {
            setDescription(event.target.value);
            setDirty(true);
          }}
        />
        <CheckboxField
          label="Active"
          checked={isActive}
          disabled={readOnly || isSystem}
          onChange={(checked) => {
            setIsActive(checked);
            setDirty(true);
          }}
        />
      </Card>

      <Card title="Permissions" hint="Every permission is enforced on the server for every request.">
        {fieldErrors.permissions ? (
          <Banner tone="error">{fieldErrors.permissions.join(" ")}</Banner>
        ) : null}
        {catalogue.loading ? (
          <LoadingState label="Loading permissions" />
        ) : (
          modules.map(([module, permissions]) => {
            const allSelected = permissions.every((permission) => selected.has(permission.code));
            const someSelected = permissions.some((permission) => selected.has(permission.code));
            return (
              <div className="permission-module" key={module}>
                <div className="permission-module__head">
                  <span className="permission-module__title">{module}</span>
                  <span className="page-header__actions">
                    <Badge tone={someSelected ? "info" : "neutral"}>
                      {permissions.filter((permission) => selected.has(permission.code)).length} of{" "}
                      {permissions.length}
                    </Badge>
                    {!readOnly ? (
                      <Button size="sm" onClick={() => toggleModule(permissions, !allSelected)}>
                        {allSelected ? "Clear all" : "Select all"}
                      </Button>
                    ) : null}
                  </span>
                </div>
                <div className="permission-module__body">
                  {permissions.map((permission) => (
                    <CheckboxField
                      key={permission.code}
                      label={permission.label}
                      hint={permission.description}
                      checked={selected.has(permission.code)}
                      disabled={readOnly}
                      onChange={(checked) => togglePermission(permission.code, checked)}
                    />
                  ))}
                </div>
              </div>
            );
          })
        )}
      </Card>
    </form>
  );
}
