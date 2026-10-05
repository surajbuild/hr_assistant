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

export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  roles: readonly Role[];
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: LayoutDashboard, roles: ALL_ROLES },
  { label: "My Profile", path: "/my-profile", icon: UserCircle, roles: ALL_ROLES },
  { label: "Employees", path: "/employees", icon: Users, roles: STAFF_ROLES },
  { label: "Departments", path: "/departments", icon: Building2, roles: STAFF_ROLES },
  { label: "Attendance", path: "/attendance", icon: CalendarCheck, roles: ALL_ROLES },
  { label: "Leave", path: "/leave", icon: CalendarDays, roles: ALL_ROLES },
  { label: "Payroll", path: "/payroll", icon: Wallet, roles: ALL_ROLES },
  { label: "Documents", path: "/documents", icon: FileText, roles: ALL_ROLES },
  { label: "Reports", path: "/reports", icon: BarChart3, roles: HR_ROLES },
  { label: "AI Assistant", path: "/assistant", icon: Bot, roles: ALL_ROLES },
  { label: "Settings", path: "/settings", icon: Settings, roles: ["admin"] },
];

export function navForRole(role: Role | null): NavItem[] {
  if (!role) return [];
  return NAV_ITEMS.filter((n) => n.roles.includes(role));
}

/** Whether `pathname` belongs to nav item `path` (prefix match on segments). */
export function isActivePath(pathname: string, path: string): boolean {
  return pathname === path || pathname.startsWith(path + "/");
}
