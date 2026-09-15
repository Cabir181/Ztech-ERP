import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { SessionProvider, useSession } from "./auth/SessionProvider";
import { ToastProvider } from "./components/Toast";
import { Banner, LoadingState } from "./components/primitives";
import { AppShell } from "./layout/AppShell";
import { AuditPage } from "./pages/AuditPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { CompanySettingsPage } from "./pages/CompanySettingsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RoleFormPage } from "./pages/RoleFormPage";
import { RolesPage } from "./pages/RolesPage";
import { UserFormPage } from "./pages/UserFormPage";
import { UsersPage } from "./pages/UsersPage";

/**
 * Gate a route on a permission.
 *
 * This decides what the interface shows. It is not the access control: the
 * server refuses an unauthorised request whether or not the interface offered
 * it, so removing this gate would change the wording of the refusal and nothing
 * else.
 */
function RequirePermission({ anyOf, children }: { anyOf: string[]; children: ReactNode }) {
  const { can } = useSession();
  if (!can(...anyOf)) {
    return (
      <Banner tone="error" title="You do not have access to this screen">
        Ask an administrator if you need it. Required: {anyOf.join(" or ")}.
      </Banner>
    );
  }
  return <>{children}</>;
}

function AuthenticatedRoutes() {
  const { session, ready } = useSession();

  if (!ready) return <LoadingState label="Starting" />;
  if (!session) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="account/password" element={<ChangePasswordPage />} />
        <Route
          path="users"
          element={
            <RequirePermission anyOf={["user.view"]}>
              <UsersPage />
            </RequirePermission>
          }
        />
        <Route
          path="users/:userId"
          element={
            <RequirePermission anyOf={["user.view", "user.manage"]}>
              <UserFormPage />
            </RequirePermission>
          }
        />
        <Route
          path="roles"
          element={
            <RequirePermission anyOf={["role.view"]}>
              <RolesPage />
            </RequirePermission>
          }
        />
        <Route
          path="roles/:roleId"
          element={
            <RequirePermission anyOf={["role.view", "role.manage"]}>
              <RoleFormPage />
            </RequirePermission>
          }
        />
        <Route
          path="company"
          element={
            <RequirePermission anyOf={["settings.view"]}>
              <CompanySettingsPage />
            </RequirePermission>
          }
        />
        <Route
          path="audit"
          element={
            <RequirePermission anyOf={["audit.view"]}>
              <AuditPage />
            </RequirePermission>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <SessionProvider>
          <AuthenticatedRoutes />
        </SessionProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
