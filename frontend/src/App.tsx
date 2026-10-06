/**
 * Root component: providers + client-side routes with auth/role guards.
 * Unauthenticated → /login · role not allowed → /dashboard · "/" → /dashboard.
 */
import { Fragment, useEffect, type ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, LoadingState } from "@/components/States";
import { ToastProvider } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { AuthProvider, hasRole, useAuth } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { ALL_ROLES, HR_ROLES, STAFF_ROLES } from "@/lib/nav";
import { matchPath, navigate, useRoute } from "@/lib/router";
import type { Role } from "@/lib/types";
import { AttendancePage } from "@/pages/AttendancePage";
import { ChatPage } from "@/pages/ChatPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { DepartmentsPage } from "@/pages/DepartmentsPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { EmployeeDetailPage } from "@/pages/EmployeeDetailPage";
import { EmployeeFormPage } from "@/pages/EmployeeFormPage";
import { EmployeesPage } from "@/pages/EmployeesPage";
import { LeavePage } from "@/pages/LeavePage";
import { LoginPage } from "@/pages/LoginPage";
import { PayrollPage } from "@/pages/PayrollPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { Compass } from "lucide-react";
import "./index.css";

function Redirect({ to }: { to: string }) {
  useEffect(() => {
    navigate(to, { replace: true });
  }, [to]);
  return null;
}

interface RouteDef {
  pattern: string;
  roles: readonly Role[];
  render: (params: Record<string, string>) => ReactNode;
  fullHeight?: boolean;
}

const ROUTES: RouteDef[] = [
  { pattern: "/dashboard", roles: ALL_ROLES, render: () => <DashboardPage /> },
  { pattern: "/my-profile", roles: ALL_ROLES, render: () => <EmployeeDetailPage self /> },
  { pattern: "/employees", roles: STAFF_ROLES, render: () => <EmployeesPage /> },
  { pattern: "/employees/add", roles: HR_ROLES, render: () => <EmployeeFormPage /> },
  { pattern: "/employees/:id/edit", roles: HR_ROLES, render: (p) => <EmployeeFormPage id={Number(p.id)} /> },
  { pattern: "/employees/:id", roles: STAFF_ROLES, render: (p) => <EmployeeDetailPage id={Number(p.id)} /> },
  { pattern: "/departments", roles: STAFF_ROLES, render: () => <DepartmentsPage /> },
  { pattern: "/attendance", roles: ALL_ROLES, render: () => <AttendancePage /> },
  { pattern: "/leave", roles: ALL_ROLES, render: () => <LeavePage /> },
  { pattern: "/payroll", roles: ALL_ROLES, render: () => <PayrollPage /> },
  { pattern: "/documents", roles: ALL_ROLES, render: () => <DocumentsPage /> },
  { pattern: "/reports", roles: HR_ROLES, render: () => <ReportsPage /> },
  { pattern: "/assistant", roles: ALL_ROLES, render: () => <ChatPage />, fullHeight: true },
  { pattern: "/settings", roles: ["admin"], render: () => <SettingsPage /> },
];

function NotFound() {
  return (
    <div className="hr-card">
      <EmptyState
        icon={<Compass className="size-6" />}
        title="Page not found"
        description="The page you are looking for does not exist or has moved."
        action={<Button onClick={() => navigate("/dashboard")}>Go to Dashboard</Button>}
      />
    </div>
  );
}

function Routes() {
  const { pathname } = useRoute();
  const { token, user, role, loading } = useAuth();

  if (pathname === "/login") {
    if (token && user) return <Redirect to="/dashboard" />;
    return <LoginPage />;
  }

  if (!token) return <Redirect to="/login" />;

  if (loading || !user) {
    return (
      <div className="mx-auto flex min-h-screen max-w-md items-center justify-center bg-background">
        <LoadingState label="Loading your workspace..." className="w-full" />
      </div>
    );
  }

  if (pathname === "/") return <Redirect to="/dashboard" />;

  for (const route of ROUTES) {
    const params = matchPath(route.pattern, pathname);
    if (!params) continue;
    if (!hasRole(role, route.roles)) return <Redirect to="/dashboard" />;
    return (
      <AppShell fullHeight={route.fullHeight}>
        <Fragment key={pathname}>{route.render(params)}</Fragment>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <NotFound />
    </AppShell>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <Routes />
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
