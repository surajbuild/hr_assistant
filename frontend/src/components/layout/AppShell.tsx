/**
 * HRMS app shell: sticky white 52px top navbar (brand · scrollable nav · role pill + profile menu),
 * hamburger dropdown below 1280px (xl), and a #f1f5f9 content area (max-w 1400px, 24px padding).
 *
 * Desktop nav density: 1280–1535px shows text-only links (11 admin items must fit at 1400px);
 * ≥1536px (2xl) adds icons and the user's name. If items still overflow, scroll arrows appear so
 * no menu item is ever hidden without a visible cue.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, LogOut, Menu, UserCircle, X } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { RoleBadge } from "@/components/StatusBadge";
import { displayName, useAuth } from "@/lib/auth";
import { isActivePath, navForRole } from "@/lib/nav";
import { Link, navigate, useRoute } from "@/lib/router";
import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "relative inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-navy text-sm font-bold text-white",
        className,
      )}
      aria-hidden="true"
    >
      HR
      <span className="absolute -top-0.5 -right-0.5 size-2.5 rounded-full border-2 border-white bg-brand" />
    </span>
  );
}

function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const name = displayName(user);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function handleLogout() {
    setOpen(false);
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-lg px-1.5 py-1 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-brand"
      >
        <Avatar name={name} size="sm" />
        <span className="hidden max-w-[140px] truncate text-sm font-medium text-ink sm:block xl:hidden 2xl:block">{name}</span>
        <ChevronDown className="hidden size-4 text-ink-muted sm:block" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 mt-2 w-60 overflow-hidden rounded-lg border border-border bg-white shadow-lg">
          <div className="border-b border-border px-4 py-3">
            <p className="truncate text-sm font-semibold text-ink">{name}</p>
            <p className="truncate text-xs text-ink-muted">{user?.email}</p>
            {user?.employee?.designation && <p className="mt-0.5 truncate text-xs text-ink-muted">{user.employee.designation}</p>}
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              navigate("/my-profile");
            }}
            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-ink hover:bg-slate-50"
          >
            <UserCircle className="size-4 text-ink-muted" /> My Profile
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={handleLogout}
            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-danger hover:bg-danger-light"
          >
            <LogOut className="size-4" /> Logout
          </button>
        </div>
      )}
    </div>
  );
}

function DesktopNav({ items, pathname }: { items: ReturnType<typeof navForRole>; pathname: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () =>
      setEdges({
        left: el.scrollLeft > 2,
        right: el.scrollLeft + el.clientWidth < el.scrollWidth - 2,
      });
    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, [items.length]);

  // Keep the active item in view (e.g. after navigating to Settings via the profile menu)
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [pathname]);

  const scrollBy = (dx: number) => ref.current?.scrollBy({ left: dx, behavior: "smooth" });

  return (
    <div className="relative ml-4 hidden min-w-0 flex-1 items-center xl:flex">
      {edges.left && (
        <button
          type="button"
          onClick={() => scrollBy(-240)}
          aria-label="Scroll menu left"
          className="absolute left-0 z-10 flex h-full items-center bg-gradient-to-r from-white via-white to-transparent pr-3 text-ink-muted hover:text-ink"
        >
          <ChevronLeft className="size-4" />
        </button>
      )}
      <nav ref={ref} aria-label="Main" className="scrollbar-none flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto">
        {items.map((item) => {
          const active = isActivePath(pathname, item.path);
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors",
                active ? "bg-brand-light text-brand" : "text-slate-600 hover:bg-slate-100 hover:text-ink",
              )}
            >
              <Icon className="hidden size-4 2xl:block" aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      {edges.right && (
        <button
          type="button"
          onClick={() => scrollBy(240)}
          aria-label="Scroll menu right"
          className="absolute right-0 z-10 flex h-full items-center bg-gradient-to-l from-white via-white to-transparent pl-3 text-ink-muted hover:text-ink"
        >
          <ChevronRight className="size-4" />
        </button>
      )}
    </div>
  );
}

export function AppShell({ children, fullHeight }: { children: ReactNode; fullHeight?: boolean }) {
  const { role } = useAuth();
  const { pathname } = useRoute();
  const [mobileOpen, setMobileOpen] = useState(false);
  const items = navForRole(role);

  useEffect(() => setMobileOpen(false), [pathname]);

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <header className="sticky top-0 z-40 border-b border-border bg-white">
        <div className="flex h-[52px] items-center gap-3 px-3 sm:px-4">
          <button
            type="button"
            onClick={() => setMobileOpen((o) => !o)}
            className="rounded-md p-1.5 text-ink hover:bg-slate-100 xl:hidden"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>

          <Link to="/dashboard" className="flex shrink-0 items-center gap-2.5" aria-label="AI HR Assistant home">
            <BrandMark />
            <span className="hidden text-[15px] font-bold tracking-tight text-navy sm:block">AI HR Assistant</span>
          </Link>

          <DesktopNav items={items} pathname={pathname} />

          <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
            <RoleBadge role={role} />
            <ProfileMenu />
          </div>
        </div>

        {mobileOpen && (
          <nav aria-label="Mobile" className="max-h-[calc(100vh-52px)] overflow-y-auto border-t border-border bg-white px-3 py-2 shadow-md xl:hidden">
            {items.map((item) => {
              const active = isActivePath(pathname, item.path);
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium",
                    active ? "bg-brand-light text-brand" : "text-slate-700 hover:bg-slate-50",
                  )}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        )}
      </header>

      <main
        className={cn(
          "mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 sm:p-6",
          fullHeight && "flex min-h-0 flex-col",
        )}
      >
        {children}
      </main>
    </div>
  );
}
