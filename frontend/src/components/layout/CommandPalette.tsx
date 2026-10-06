/**
 * Ctrl/⌘+K command palette (Radix Dialog, no cmdk).
 * Lists ONLY what the current role may open: nav pages, "Add employee" (hr/admin), theme and sign-out actions,
 * and — for staff roles — an employee search backed by GET /employees?search= (server-side scoped, so managers
 * only find their team). Keyboard: ↑/↓ move, Enter runs, Esc closes (Radix).
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { CornerDownLeft, LogOut, Monitor, Moon, Search, Sun, UserPlus, Users, type LucideIcon } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { navForRole } from "@/lib/nav";
import { navigate } from "@/lib/router";
import { useTheme } from "@/lib/theme";
import type { Employee } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Cmd {
  id: string;
  group: "Pages" | "Actions" | "Employees";
  label: string;
  hint?: string;
  icon?: LucideIcon;
  avatar?: string;
  run: () => void;
}

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { role, logout } = useAuth();
  const { resolved, setMode } = useTheme();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [people, setPeople] = useState<Employee[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const staff = role === "admin" || role === "hr" || role === "manager";
  const canAdd = role === "admin" || role === "hr";

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setPeople([]);
    }
  }, [open]);

  // employee search (staff only), debounced
  useEffect(() => {
    const q = query.trim();
    if (!open || !staff || q.length < 2) {
      setPeople([]);
      return;
    }
    let cancelled = false;
    const t = setTimeout(() => {
      api
        .get<Employee[]>(`/employees?search=${encodeURIComponent(q)}`)
        .then((res) => !cancelled && setPeople(res.slice(0, 6)))
        .catch(() => !cancelled && setPeople([]));
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query, open, staff]);

  const go = (path: string) => () => navigate(path);

  const commands = useMemo<Cmd[]>(() => {
    const all: Cmd[] = navForRole(role).map((n) => ({ id: `page:${n.path}`, group: "Pages", label: n.label, hint: n.group, icon: n.icon, run: go(n.path) }));
    if (canAdd) all.push({ id: "act:add-employee", group: "Actions", label: "Add employee", hint: "People", icon: UserPlus, run: go("/employees/add") });
    all.push({
      id: "act:theme",
      group: "Actions",
      label: resolved === "dark" ? "Switch to light theme" : "Switch to dark theme",
      icon: resolved === "dark" ? Sun : Moon,
      run: () => setMode(resolved === "dark" ? "light" : "dark"),
    });
    all.push({ id: "act:system", group: "Actions", label: "Use system theme", icon: Monitor, run: () => setMode("system") });
    all.push({
      id: "act:logout",
      group: "Actions",
      label: "Sign out",
      icon: LogOut,
      run: () => {
        logout();
        navigate("/login", { replace: true });
      },
    });
    const q = query.trim().toLowerCase();
    const filtered = q ? all.filter((c) => c.label.toLowerCase().includes(q) || c.hint?.toLowerCase().includes(q)) : all;
    const emps: Cmd[] = people.map((p) => ({
      id: `emp:${p.id}`,
      group: "Employees",
      label: p.name,
      hint: [p.designation, p.department].filter(Boolean).join(" · ") || p.employee_code,
      avatar: p.name,
      icon: Users,
      run: go(`/employees/${p.id}`),
    }));
    return [...filtered, ...emps];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, canAdd, resolved, query, people]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function run(cmd: Cmd | undefined) {
    if (!cmd) return;
    onOpenChange(false);
    cmd.run();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (commands.length ? (i + 1) % commands.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (commands.length ? (i - 1 + commands.length) % commands.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(commands[active]);
    }
  }

  const groups: { name: Cmd["group"]; items: { cmd: Cmd; index: number }[] }[] = [];
  commands.forEach((cmd, index) => {
    let g = groups.find((x) => x.name === cmd.group);
    if (!g) groups.push((g = { name: cmd.group, items: [] }));
    g.items.push({ cmd, index });
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md" className="max-h-[70dvh] overflow-hidden sm:mb-[12vh] sm:self-start" onOpenAutoFocus={(e) => {
        e.preventDefault();
        (e.currentTarget as HTMLElement).querySelector<HTMLElement>("input")?.focus();
      }}>
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">Search pages, actions and people. Use the arrow keys and Enter.</DialogDescription>
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={staff ? "Search pages, actions or people…" : "Search pages and actions…"}
            role="combobox"
            aria-expanded="true"
            aria-controls="cmdk-list"
            aria-activedescendant={commands[active] ? `cmdk-${commands[active]!.id}` : undefined}
            aria-label="Search commands"
            className="h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
          <kbd className="hidden shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:block">Esc</kbd>
        </div>
        <div ref={listRef} id="cmdk-list" role="listbox" className="flex-1 overflow-y-auto p-2">
          {commands.length === 0 ? (
            <div className="flex flex-col items-center gap-1.5 px-4 py-10 text-center">
              <span className="flex size-10 items-center justify-center rounded-xl bg-surface-muted text-muted-foreground">
                <Search className="size-5" />
              </span>
              <p className="text-sm font-medium text-foreground">No results for “{query.trim()}”</p>
              <p className="text-xs text-muted-foreground">{staff ? "Try a page name, an action, or an employee's name." : "Try a page name or an action."}</p>
            </div>
          ) : (
            groups.map((g) => (
              <div key={g.name} className="mb-1 last:mb-0">
                <p className="px-2.5 pt-2 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">{g.name}</p>
                {g.items.map(({ cmd, index }) => {
                  const Icon = cmd.icon;
                  const isActive = index === active;
                  const lead: ReactNode = cmd.avatar ? (
                    <Avatar name={cmd.avatar} size="sm" />
                  ) : Icon ? (
                    <span className="flex size-7 items-center justify-center rounded-md bg-surface-muted text-muted-foreground">
                      <Icon className="size-4" />
                    </span>
                  ) : null;
                  return (
                    <div
                      key={cmd.id}
                      id={`cmdk-${cmd.id}`}
                      role="option"
                      aria-selected={isActive}
                      data-index={index}
                      onMouseMove={() => setActive(index)}
                      onClick={() => run(cmd)}
                      className={cn("flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors", isActive ? "bg-accent text-foreground" : "text-foreground")}
                    >
                      {lead}
                      <span className="min-w-0 flex-1 truncate font-medium">{cmd.label}</span>
                      {cmd.hint && <span className="hidden truncate text-xs text-muted-foreground sm:block">{cmd.hint}</span>}
                      {isActive && <CornerDownLeft className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />}
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
