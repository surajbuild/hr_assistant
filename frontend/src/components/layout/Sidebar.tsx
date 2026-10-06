/**
 * Sidebar navigation: grouped, role-filtered links with an active indicator.
 * - `rail` = icon-only (tablet, or desktop when collapsed) with tooltips; otherwise icon + label.
 * - `SidebarNav` is shared by the desktop sidebar and the mobile drawer.
 */
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Hint } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth";
import { groupedNavForRole, isActivePath } from "@/lib/nav";
import { Link, useRoute } from "@/lib/router";
import { cn } from "@/lib/utils";
import { BrandMark } from "./BrandMark";

export function SidebarNav({ rail, onNavigate }: { rail?: boolean; onNavigate?: () => void }) {
  const { role } = useAuth();
  const { pathname } = useRoute();
  const groups = groupedNavForRole(role);

  return (
    <nav aria-label="Main" className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4">
      {groups.map(({ group, items }) => (
        <div key={group} className="flex flex-col gap-0.5">
          {rail ? (
            <div className="mx-2 mb-1 h-px bg-border first:hidden" aria-hidden="true" />
          ) : (
            <p className="px-2.5 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">{group}</p>
          )}
          {items.map((item) => {
            const active = isActivePath(pathname, item.path);
            const Icon = item.icon;
            const link = (
              <Link
                key={item.path}
                to={item.path}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                aria-label={rail ? item.label : undefined}
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors duration-150",
                  rail && "justify-center px-0",
                  active ? "bg-brand-subtle text-brand-subtle-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                {active && <span className="absolute top-1/2 -left-3 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand" aria-hidden="true" />}
                <Icon className="size-[18px] shrink-0" aria-hidden="true" />
                {!rail && <span className="truncate">{item.label}</span>}
              </Link>
            );
            return rail ? (
              <Hint key={item.path} label={item.label} side="right">
                {link}
              </Hint>
            ) : (
              link
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function Sidebar({ rail, canToggle, onToggle }: { rail: boolean; canToggle: boolean; onToggle: () => void }) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-200 ease-out md:flex",
        rail ? "w-[68px]" : "w-[248px]",
      )}
    >
      <div className={cn("flex h-14 shrink-0 items-center gap-2.5 border-b border-border px-4", rail && "justify-center px-0")}>
        <Link to="/dashboard" aria-label="AI HR Assistant home" className="flex items-center gap-2.5 rounded-md">
          <BrandMark />
          {!rail && <span className="text-[15px] font-semibold tracking-tight text-foreground">AI HR Assistant</span>}
        </Link>
      </div>
      <SidebarNav rail={rail} />
      {canToggle && (
        <div className="border-t border-border p-3">
          <Hint label={rail ? "Expand sidebar" : "Collapse sidebar"} side="right">
            <button
              type="button"
              onClick={onToggle}
              aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                rail && "justify-center px-0",
              )}
            >
              {rail ? <PanelLeftOpen className="size-[18px]" /> : <PanelLeftClose className="size-[18px]" />}
              {!rail && <span>Collapse</span>}
            </button>
          </Hint>
        </div>
      )}
    </aside>
  );
}
