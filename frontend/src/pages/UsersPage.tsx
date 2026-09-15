import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useDebounced, useResource } from "../api/hooks";
import type { Paginated, User } from "../api/types";
import { useSession } from "../auth/SessionProvider";
import { DataTable, Pagination } from "../components/DataTable";
import type { Column } from "../components/DataTable";
import { Badge, Banner, Button, DateTime, PageHeader } from "../components/primitives";

export function UsersPage() {
  const { can } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [activeOnly, setActiveOnly] = useState<"" | "true" | "false">("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);

  const users = useResource<Paginated<User>>(
    (signal) =>
      api.get<Paginated<User>>(
        "/api/users/",
        { search: debouncedSearch, is_active: activeOnly || undefined, page },
        signal,
      ),
    [debouncedSearch, activeOnly, page],
  );

  const columns: Column<User>[] = [
    {
      key: "name",
      header: "Name",
      render: (user) => (
        <>
          <Link to={`/users/${user.id}`}>{user.full_name}</Link>
          <div className="field__hint">{user.email}</div>
        </>
      ),
    },
    { key: "job_title", header: "Job title", render: (user) => user.job_title || "—" },
    {
      key: "roles",
      header: "Roles",
      render: (user) =>
        user.roles.length === 0 ? (
          <Badge tone="warning">No roles</Badge>
        ) : (
          user.roles.map((role) => (
            <span key={role.id} style={{ marginInlineEnd: 6 }}>
              <Badge tone="info">{role.name}</Badge>
            </span>
          ))
        ),
    },
    {
      key: "status",
      header: "Status",
      render: (user) => {
        if (!user.is_active) return <Badge tone="neutral">Inactive</Badge>;
        if (user.is_locked) return <Badge tone="danger">Locked</Badge>;
        if (user.must_change_password) return <Badge tone="warning">Must change password</Badge>;
        return <Badge tone="success">Active</Badge>;
      },
    },
    { key: "last_login", header: "Last sign-in", render: (user) => <DateTime value={user.last_login} /> },
  ];

  return (
    <>
      <PageHeader
        title="Users"
        description="People who can sign in to this environment."
        actions={
          can("user.manage") ? (
            <Button variant="primary" onClick={() => navigate("/users/new")}>
              Add user
            </Button>
          ) : null
        }
      />

      {users.error ? <Banner tone="error">{users.error.message}</Banner> : null}

      <div className="toolbar">
        <div className="toolbar__search">
          <label className="visually-hidden" htmlFor="user-search">
            Search users by name or email
          </label>
          <input
            id="user-search"
            type="search"
            className="control"
            placeholder="Search by name or email"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </div>
        <label className="visually-hidden" htmlFor="user-status">
          Filter by status
        </label>
        <select
          id="user-status"
          className="control"
          style={{ width: "auto" }}
          value={activeOnly}
          onChange={(event) => {
            setActiveOnly(event.target.value as "" | "true" | "false");
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="true">Active only</option>
          <option value="false">Inactive only</option>
        </select>
      </div>

      <DataTable
        caption="Users in this environment"
        columns={columns}
        rows={users.data?.results ?? []}
        rowKey={(user) => user.id}
        loading={users.loading}
        emptyTitle={search ? "No users match that search" : "No users yet"}
        emptyDescription={
          search ? "Try a different name or email address." : "Add the first user to get started."
        }
      />
      {users.data ? (
        <Pagination
          page={users.data.page}
          totalPages={users.data.total_pages}
          count={users.data.count}
          onPageChange={setPage}
        />
      ) : null}
    </>
  );
}
