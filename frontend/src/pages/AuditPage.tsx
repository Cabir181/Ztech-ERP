import { useState } from "react";
import { api } from "../api/client";
import { useResource } from "../api/hooks";
import type { AuditEvent, Paginated } from "../api/types";
import { DataTable, Pagination } from "../components/DataTable";
import type { Column } from "../components/DataTable";
import { Banner, DateTime, PageHeader } from "../components/primitives";

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function AuditPage() {
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [page, setPage] = useState(1);

  const events = useResource<Paginated<AuditEvent>>(
    (signal) =>
      api.get<Paginated<AuditEvent>>(
        "/api/audit-events/",
        { action: action || undefined, entity_type: entityType || undefined, page },
        signal,
      ),
    [action, entityType, page],
  );

  const columns: Column<AuditEvent>[] = [
    { key: "when", header: "When", render: (event) => <DateTime value={event.occurred_at} /> },
    { key: "who", header: "Who", render: (event) => event.actor_label || "system" },
    {
      key: "what",
      header: "What",
      render: (event) => (
        <>
          <code>{event.action}</code>
          <div className="field__hint">{event.summary}</div>
        </>
      ),
    },
    {
      key: "record",
      header: "Record",
      render: (event) => (
        <>
          {event.entity_label || "—"}
          <div className="field__hint">{event.entity_type}</div>
        </>
      ),
    },
    {
      key: "changes",
      header: "Changes",
      render: (event) => {
        const entries = Object.entries(event.changes ?? {});
        if (entries.length === 0) return "—";
        return (
          <span className="changes">
            {entries.map(([field, change]) => (
              <span className="changes__row" key={field}>
                {field}: <span className="changes__from">{renderValue(change.from)}</span> {"→"}{" "}
                <span className="changes__to">{renderValue(change.to)}</span>
              </span>
            ))}
          </span>
        );
      },
    },
  ];

  return (
    <>
      <PageHeader
        title="Audit trail"
        description="Every recorded action, in order. Entries cannot be edited or deleted, by anyone, through any route."
      />

      {events.error ? <Banner tone="error">{events.error.message}</Banner> : null}

      <div className="toolbar">
        <div className="toolbar__search">
          <label className="visually-hidden" htmlFor="audit-action">
            Filter by action
          </label>
          <input
            id="audit-action"
            className="control"
            placeholder="Action, for example user.created"
            value={action}
            onChange={(event) => {
              setAction(event.target.value.trim());
              setPage(1);
            }}
          />
        </div>
        <div className="toolbar__search">
          <label className="visually-hidden" htmlFor="audit-entity">
            Filter by record type
          </label>
          <input
            id="audit-entity"
            className="control"
            placeholder="Record type, for example core.user"
            value={entityType}
            onChange={(event) => {
              setEntityType(event.target.value.trim());
              setPage(1);
            }}
          />
        </div>
      </div>

      <DataTable
        caption="Audit trail"
        columns={columns}
        rows={events.data?.results ?? []}
        rowKey={(event) => event.id}
        loading={events.loading}
        emptyTitle="No matching audit entries"
        emptyDescription="Clear the filters to see the whole trail."
      />
      {events.data ? (
        <Pagination
          page={events.data.page}
          totalPages={events.data.total_pages}
          count={events.data.count}
          onPageChange={setPage}
        />
      ) : null}
    </>
  );
}
