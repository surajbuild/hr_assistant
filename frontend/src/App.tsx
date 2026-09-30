import { useState } from "react";
import { LoginView } from "./LoginView";
import { ChatView } from "./ChatView";
import { DashboardView } from "./DashboardView";
import { Button } from "@/components/ui/button";
import { MessageSquare, LayoutDashboard, LogOut } from "lucide-react";
import "./index.css";

// ── Simple JWT Decode Helper ───────────────────────────────────────────────────

function decodeTokenPayload(token: string): { sub?: string; role?: string } {
  try {
    const payload = token.split(".")[1];
    if (!payload) return {};
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as { sub?: string; role?: string };
  } catch {
    return {};
  }
}

export function App() {
  // Initialise from localStorage so page refreshes keep the user logged in
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("hr_token")
  );

  // Active view tab: "dashboard" for HR/Admin, "chat" for Employee/Manager
  const [activeTab, setActiveTab] = useState<"chat" | "dashboard">(() => {
    const raw = localStorage.getItem("hr_token");
    if (!raw) return "chat";
    const payload = decodeTokenPayload(raw);
    return ["hr", "admin"].includes(payload.role || "") ? "dashboard" : "chat";
  });

  function handleLoginSuccess(newToken: string) {
    localStorage.setItem("hr_token", newToken);
    setToken(newToken);
    const payload = decodeTokenPayload(newToken);
    setActiveTab(["hr", "admin"].includes(payload.role || "") ? "dashboard" : "chat");
  }

  function handleLogout() {
    localStorage.removeItem("hr_token");
    setToken(null);
  }

  if (!token) {
    return <LoginView onLoginSuccess={handleLoginSuccess} />;
  }

  const { role } = decodeTokenPayload(token);

  return (
    <div className="flex flex-col h-screen w-full bg-background overflow-hidden">
      {/* ── Global Top Navbar ── */}
      <header className="flex items-center justify-between px-6 py-3 border-b bg-card shrink-0 z-10">
        {/* Brand & Active Role */}
        <div className="flex items-center gap-3">
          <span className="font-bold text-base tracking-tight text-foreground">
            AI HR Assistant
          </span>
          {role && (
            <span className="text-[11px] font-semibold uppercase px-2.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
              {role}
            </span>
          )}
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center bg-muted/60 p-1 rounded-lg border">
          <Button
            variant={activeTab === "dashboard" ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("dashboard")}
            className="gap-2 text-xs h-8 px-3.5"
          >
            <LayoutDashboard className="size-3.5" />
            HR Dashboard
          </Button>

          <Button
            variant={activeTab === "chat" ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("chat")}
            className="gap-2 text-xs h-8 px-3.5"
          >
            <MessageSquare className="size-3.5" />
            AI Assistant
          </Button>
        </nav>

        {/* User actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="gap-1.5 text-xs text-muted-foreground hover:text-destructive"
          >
            <LogOut className="size-3.5" />
            Logout
          </Button>
        </div>
      </header>

      {/* ── Main View Area ── */}
      <main className="flex-1 overflow-y-auto">
        {activeTab === "dashboard" ? (
          <DashboardView token={token} />
        ) : (
          <div className="h-full">
            <ChatView token={token} onLogout={handleLogout} showHeader={false} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
