/**
 * The shared list table.
 *
 * Every list screen renders through this component so that loading, empty and
 * error states, pagination and keyboard-reachable row actions behave the same
 * way everywhere. The table itself scrolls horizontally rather than forcing the
 * whole page to, which keeps long product descriptions readable on a phone.
 */

import type { ReactNode } from "react";
import { Button, EmptyState, LoadingState } from "./primitives";

export interface Column<T> {
  key: string;
  header: string;
  /** Right-aligns and uses tabular figures. For quantities and money. */
  numeric?: boolean;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  caption?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  emptyTitle = "Nothing to show",
  emptyDescription,
  emptyAction,
  caption,
}: DataTableProps<T>) {
  if (loading) return <LoadingState />;
  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />;
  }

  return (
    <div className="table-wrap">
      <table className="table">
        {caption ? <caption className="visually-hidden">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={column.numeric ? "table__numeric" : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} className={column.numeric ? "table__numeric" : undefined}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  count,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  count: number;
  onPageChange: (page: number) => void;
}) {
  if (count === 0) return null;
  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="pagination__status" aria-live="polite">
        {count} record{count === 1 ? "" : "s"} · page {page} of {Math.max(totalPages, 1)}
      </span>
      <span className="page-header__actions">
        <Button size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <Button size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </span>
    </nav>
  );
}
