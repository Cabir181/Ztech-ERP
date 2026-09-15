/**
 * The signed-in frame: navigation, the current user, and the routed screen.
 *
 * Navigation entries are filtered by permission so people are not shown
 * controls that would only refuse them. Entries for parts of the product that
 * Release 1 does not include are simply absent - there are no buttons here that
 * do nothing.
 */

import { NavLink, Outlet } from "react-router-dom";
import { useSession } from "../auth/SessionProvider";
import { Button } from "../components/primitives";

interface NavItem {
  to: string;
  label: string;
  permissions?: string[];
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Work",
    items: [{ to: "/", label: "Overview" }],
  },
  {
    label: "Administration",
    items: [
      { to: "/users", label: "Users", permissions: ["user.view"] },
      { to: "/roles", label: "Roles", permissions: ["role.view"] },
      { to: "/company", label: "Company", permissions: ["settings.view"] },
      { to: "/audit", label: "Audit trail", permissions: ["audit.view"] },
    ],
  },
];

export function AppShell() {
  const { session, signOut, can } = useSession();
  if (!session) return null;

  const initials = session.company.display_name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0] ?? "")
    .join("")
    .toUpperCase();

  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <nav className="nav" aria-label="Main">
        <div className="nav__brand">
          <span className="nav__mark" aria-hidden="true">
            {initials}
          </span>
          <span>
            <span className="nav__company">{session.company.display_name}</span>
            <span className="nav__client">
              {session.company.currency_code} · {session.company.timezone}
            </span>
          </span>
        </div>

        {NAV_GROUPS.map((group) => {
          const visible = group.items.filter((item) => !item.permissions || can(...item.permissions));
          if (visible.length === 0) return null;
          return (
            <div className="nav__group" key={group.label}>
              <div className="nav__group-label">{group.label}</div>
              {visible.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.to === "/"} className="nav__link">
                  {item.label}
                </NavLink>
              ))}
            </div>
          );
        })}

        <div className="nav__footer">
          <div className="nav__user">
            <div className="nav__user-name">{session.user.full_name}</div>
            <div className="nav__user-email">{session.user.email}</div>
          </div>
          <NavLink to="/account/password" className="nav__link">
            Change password
          </NavLink>
          <Button variant="ghost" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </nav>

      <div className="main">
        <main className="main__content" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
