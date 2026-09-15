/**
 * Overview screen.
 *
 * Release 1 delivers the foundation: identity, roles, company configuration and
 * the audit trail. Quotation and order figures are not shown here because there
 * are no quotations yet - an empty chart implying otherwise would be worse than
 * saying plainly what is and is not in place.
 */

import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useResource } from "../api/hooks";
import type { SystemStatus } from "../api/types";
import { useSession } from "../auth/SessionProvider";
import { Badge, Banner, Card, DateTime, LoadingState, PageHeader } from "../components/primitives";

export function DashboardPage() {
  const { session, can } = useSession();
  const canSeeStatus = can("settings.view");
  const status = useResource<SystemStatus | null>(
    (signal) => (canSeeStatus ? api.get<SystemStatus>("/api/system/status/", undefined, signal) : Promise.resolve(null)),
    [canSeeStatus],
  );

  if (!session) return null;

  return (
    <>
      <PageHeader
        title={`Welcome, ${session.user.full_name.split(" ")[0]}`}
        description={`${session.company.legal_name} · ${session.company.currency_code} · ${session.company.timezone}`}
      />

      {session.must_change_password ? (
        <Banner tone="warning" title="Change your password">
          This account is still using the password it was created with.{" "}
          <Link to="/account/password">Set a new one now</Link>.
        </Banner>
      ) : null}

      <Card title="Your access" hint="What this account may do in this environment.">
        <dl className="definition">
          <dt>Signed in as</dt>
          <dd>
            {session.user.full_name} &lt;{session.user.email}&gt;
          </dd>
          <dt>Roles</dt>
          <dd>
            {session.user.roles.length === 0
              ? "No roles assigned"
              : session.user.roles.map((role) => (
                  <span key={role.id} style={{ marginInlineEnd: 8 }}>
                    <Badge tone="info">{role.name}</Badge>
                  </span>
                ))}
          </dd>
          <dt>Permissions held</dt>
          <dd>{session.permissions.length}</dd>
          <dt>Last signed in</dt>
          <dd>
            <DateTime value={session.user.last_login} />
          </dd>
          <dt>Approval authority</dt>
          <dd>
            {session.permissions.includes("approval.decide") ? (
              <Badge tone="success">Yes</Badge>
            ) : (
              <Badge tone="neutral">No</Badge>
            )}
          </dd>
        </dl>
      </Card>

      {canSeeStatus ? (
        <Card title="Deployment status" hint="Reported as configured, not as assumed.">
          {status.loading ? (
            <LoadingState />
          ) : status.data ? (
            <dl className="definition">
              <dt>Client</dt>
              <dd>{status.data.client_code}</dd>
              <dt>Release</dt>
              <dd>{status.data.release}</dd>
              <dt>Database</dt>
              <dd>
                <Badge tone={status.data.database.connected ? "success" : "danger"}>
                  {status.data.database.engine} {status.data.database.connected ? "connected" : "unreachable"}
                </Badge>
              </dd>
              <dt>Outbound email</dt>
              <dd>
                <Badge tone={status.data.email.status === "configured" ? "success" : "warning"}>
                  {status.data.email.status.replace("_", " ")}
                </Badge>
                <div className="field__hint">{status.data.email.detail}</div>
              </dd>
              <dt>Attachment scanning</dt>
              <dd>
                <Badge tone={status.data.attachment_scanning.status === "configured" ? "success" : "warning"}>
                  {status.data.attachment_scanning.adapter}
                </Badge>
                <div className="field__hint">{status.data.attachment_scanning.detail}</div>
              </dd>
            </dl>
          ) : (
            <Banner tone="error">Could not read the deployment status.</Banner>
          )}
        </Card>
      ) : null}

      <Card title="What is in this release" hint="Stated plainly so nobody plans around something that is not here yet.">
        <p>
          This build delivers the foundation the sales workflow is built on: sign-in, roles and permissions,
          company configuration, the audit trail, private attachment storage and the background worker.
        </p>
        <p>
          Customers, the product catalog, quotations, approvals, customer documents, email delivery and
          reporting arrive in the increments that follow. Nothing above pretends those exist yet.
        </p>
      </Card>
    </>
  );
}
