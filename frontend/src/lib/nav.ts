/** Menu definition + role gating (same role sets the backend enforces; UI gating is UX only). */
import {
  BarChart3,
  Bot,
  Building2,
  CalendarCheck,
  CalendarDays,
  FileText,
  LayoutDashboard,
  Settings,
  UserCircle,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "./types";

export const ALL_ROLES: readonly Role[] = ["employee", "manager", "hr", "admin"];
export const HR_ROLES: readonly Role[] = ["admin", "hr"];
export const STAFF_ROLES: readonly Role[] = ["admin", "hr", "manager"];

export type NavGroup = "Overview" | "People" | "Workspace" | "Insights" | "Admin";

export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  roles: readonly Role[];
  group: NavGroup;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", group: "Overview", icon: LayoutDashboard, roles: ALL_ROLES },
  { label: "My Profile", path: "/my-profile", group: "Overview", icon: UserCircle, roles: ALL_ROLES },
  { label: "Employees", path: "/employees", group: "People", icon: Users, roles: STAFF_ROLES },
  { label: "Departments", path: "/departments", group: "People", icon: Building2, roles: STAFF_ROLES },
  { label: "Attendance", path: "/attendance", group: "Workspace", icon: CalendarCheck, roles: ALL_ROLES },
  { label: "Leave", path: "/leave", group: "Workspace", icon: CalendarDays, roles: ALL_ROLES },
  { label: "Payroll", path: "/payroll", group: "Workspace", icon: Wallet, roles: ALL_ROLES },
  { label: "Documents", path: "/documents", group: "Workspace", icon: FileText, roles: ALL_ROLES },
  { label: "Reports", path: "/reports", group: "Insights", icon: BarChart3, roles: HR_ROLES },
  { label: "AI Assistant", path: "/assistant", group: "Insights", icon: Bot, roles: ALL_ROLES },
  { label: "Settings", path: "/settings", group: "Admin", icon: Settings, roles: ["admin"] },
];

export function navForRole(role: Role | null): NavItem[] {
  if (!role) return [];
  return NAV_ITEMS.filter((n) => n.roles.includes(role));
}

/** Whether `pathname` belongs to nav item `path` (prefix match on segments). */
export function isActivePath(pathname: string, path: string): boolean {
  return pathname === path || pathname.startsWith(path + "/");
}

/** Nav items grouped for the sidebar, preserving the global menu order. */
export function groupedNavForRole(role: Role | null): { group: NavGroup; items: NavItem[] }[] {
  const out: { group: NavGroup; items: NavItem[] }[] = [];
  for (const item of navForRole(role)) {
    const last = out[out.length - 1];
    if (last && last.group === item.group) last.items.push(item);
    else out.push({ group: item.group, items: [item] });
  }
  return out;
}
