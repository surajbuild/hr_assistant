/**
 * App shell (design system v2): collapsible left sidebar (desktop), icon-only rail (tablet), slide-over drawer
 * with focus trap (phone), and a slim 56px top bar with breadcrumb, Ctrl+K search, notifications (approvers only),
 * theme toggle and profile menu. Content area: max 1400px, 16/24/32px gutters, page-in motion.
 *
 * Breakpoints: <768px drawer · 768–1279px rail · ≥1280px expanded (user can collapse; remembered in localStorage).
 */
import { useEffect, useState, type ReactNode } from "react";
import { ChevronRight, Menu, Search } from "lucide-react";
import { CloseButton, Dialog, DialogDescription, DialogTitle, DrawerContent } from "@/components/ui/dialog";
import { Hint } from "@/components/ui/tooltip";
import { TooltipProvider } from "@/components/ui/tooltip";
import { navForRole } from "@/lib/nav";
import { useAuth } from "@/lib/auth";
import { useRoute } from "@/lib/router";
import { useMediaQuery } from "@/lib/useMediaQuery";
import { cn } from "@/lib/utils";
import { BrandMark } from "./BrandMark";
import { CommandPalette } from "./CommandPalette";
import { NotificationBell } from "./NotificationBell";
import { ProfileMenu } from "./ProfileMenu";
import { Sidebar, SidebarNav } from "./Sidebar";
import { ThemeMenu } from "./ThemeMenu";

export { BrandMark };

const SIDEBAR_KEY = "hr_sidebar";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "collapsed";
  } catch {
    return false;
  }
}

/** Breadcrumb trail derived from the route + role-filtered nav (so it never names a page the role can't open). */
function useBreadcrumb(pathname: string): string[] {
  const { role } = useAuth();
  const items = navForRole(role);
  const base = items.filter((n) => pathname === n.path || pathname.startsWith(n.path + "/")).sort((a, b) => b.path.length - a.path.length)[0];
  if (!base) return ["Not found"];
  const trail = [base.group, base.label];
  if (pathname === "/employees/add") trail.push("New");
  else if (/^\/employees\/[^/]+\/edit$/.test(pathname)) trail.push("Edit");
  else if (/^\/employees\/[^/]+$/.test(pathname)) trail.push("Profile");
  return trail;
}

export function AppShell({ children, fullHeight }: { children: ReactNode; fullHeight?: boolean }) {
  const { pathname } = useRoute();
  const wide = useMediaQuery("(min-width: 1280px)");
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [drawer, setDrawer] = useState(false);
  const [palette, setPalette] = useState(false);
  const trail = useBreadcrumb(pathname);
  const rail = !wide || collapsed;
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

  useEffect(() => setDrawer(false), [pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function toggleCollapsed() {
    setCollapsed((c) => {
      try {
        localStorage.setItem(SIDEBAR_KEY, c ? "expanded" : "collapsed");
      } catch {
        /* ignore */
      }
      return !c;
    });
  }

  return (
    <TooltipProvider>
      <div className="flex min-h-screen bg-background">
        <a
          href="#main"
          className="sr-only z-[90] rounded-md bg-brand px-3 py-2 text-sm font-medium text-brand-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
        >
          Skip to content
        </a>
        <Sidebar rail={rail} canToggle={wide} onToggle={toggleCollapsed} />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-surface/85 px-3 backdrop-blur-sm sm:gap-3 sm:px-6">
            <button
              type="button"
              onClick={() => setDrawer(true)}
              className="inline-flex size-9 items-center justify-center rounded-lg text-foreground transition-colors hover:bg-accent md:hidden"
              aria-label="Open navigation menu"
            >
              <Menu className="size-5" />
            </button>
            <span className="flex items-center gap-2 md:hidden" aria-hidden="true">
              <BrandMark className="size-7 text-xs" />
            </span>

            <nav aria-label="Breadcrumb" className="hidden min-w-0 items-center gap-1.5 text-sm md:flex">
              {trail.map((t, i) => (
                <span key={`${t}-${i}`} className="flex min-w-0 items-center gap-1.5">
                  {i > 0 && <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/60" aria-hidden="true" />}
                  <span className={cn("truncate", i === trail.length - 1 ? "font-medium text-foreground" : "text-muted-foreground")} aria-current={i === trail.length - 1 ? "page" : undefined}>
                    {t}
                  </span>
                </span>
              ))}
            </nav>
            <span className="min-w-0 truncate text-sm font-semibold text-foreground md:hidden">{trail[trail.length - 1]}</span>

            <div className="ml-auto flex items-center gap-1 sm:gap-1.5">
              <button
                type="button"
                onClick={() => setPalette(true)}
                aria-label="Search (Ctrl+K)"
                className="hidden h-9 items-center gap-2 rounded-lg border border-border bg-surface-muted/60 px-3 text-sm text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground sm:flex sm:w-56 lg:w-64"
              >
                <Search className="size-4" />
                <span className="flex-1 text-left">Search…</span>
                <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 text-[10px] font-medium">{isMac ? "⌘K" : "Ctrl K"}</kbd>
              </button>
              <Hint label="Search">
                <button
                  type="button"
                  onClick={() => setPalette(true)}
                  aria-label="Search"
                  className="inline-flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground sm:hidden"
                >
                  <Search className="size-[18px]" />
                </button>
              </Hint>
              <NotificationBell />
              <ThemeMenu />
              <span className="mx-1 hidden h-5 w-px bg-border sm:block" aria-hidden="true" />
              <ProfileMenu />
            </div>
          </header>

          <main id="main" tabIndex={-1} className={cn("mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 outline-none sm:px-6 sm:py-6 lg:px-8", fullHeight && "flex min-h-0 flex-col")}>
            <div key={pathname} className={cn("animate-page-in", fullHeight && "flex min-h-0 flex-1 flex-col")}>
              {children}
            </div>
          </main>
        </div>

        <Dialog open={drawer} onOpenChange={setDrawer}>
          <DrawerContent side="left">
            <DialogTitle className="sr-only">Navigation</DialogTitle>
            <DialogDescription className="sr-only">Main navigation menu</DialogDescription>
            <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-border px-4">
              <BrandMark />
              <span className="text-[15px] font-semibold tracking-tight text-foreground">AI HR Assistant</span>
              <CloseButton className="ml-auto" />
            </div>
            <SidebarNav onNavigate={() => setDrawer(false)} />
          </DrawerContent>
        </Dialog>

        <CommandPalette open={palette} onOpenChange={setPalette} />
      </div>
    </TooltipProvider>
  );
}
