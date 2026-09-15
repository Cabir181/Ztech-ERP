import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useResource } from "../api/hooks";
import type { Paginated, Role } from "../api/types";
import { useSession } from "../auth/SessionProvider";
import { DataTable } from "../components/DataTable";
import type { Column } from "../components/DataTable";
import { Badge, Banner, Button, PageHeader } from "../components/primitives";

export function RolesPage() {
  const { can } = useSession();
  const navigate = useNavigate();
  const roles = useResource<Paginated<Role>>(
    (signal) => api.get<Paginated<Role>>("/api/roles/", { page_size: 200 }, signal),
    [],
  );

  const columns: Column<Role>[] = [
    {
      key: "name",
      header: "Role",
      render: (role) => (
        <>
          <Link to={`/roles/${role.id}`}>{role.name}</Link>
          <div className="field__hint">{role.description}</div>
        </>
      ),
    },
    {
      key: "kind",
      header: "Type",
      render: (role) =>
        role.is_system ? <Badge tone="info">Built in</Badge> : <Badge tone="neutral">Custom</Badge>,
    },
    { key: "permissions", header: "Permissions", numeric: true, render: (role) => role.permissions.length },
    { key: "users", header: "Users", numeric: true, render: (role) => role.assigned_user_count },
    {
      key: "status",
      header: "Status",
      render: (role) =>
        role.is_active ? <Badge tone="success">Active</Badge> : <Badge tone="neutral">Inactive</Badge>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Roles"
        description="A role is a named bundle of permissions. Changing a role changes what everyone holding it may do."
        actions={
          can("role.manage") ? (
            <Button variant="primary" onClick={() => navigate("/roles/new")}>
              Add role
            </Button>
          ) : null
        }
      />
      {roles.error ? <Banner tone="error">{roles.error.message}</Banner> : null}
      <DataTable
        caption="Roles defined for this company"
        columns={columns}
        rows={roles.data?.results ?? []}
        rowKey={(role) => role.id}
        loading={roles.loading}
        emptyTitle="No roles defined"
      />
    </>
  );
}
