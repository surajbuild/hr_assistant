/** Login: navy brand panel + sign-in card (email/password, Google, demo accounts helper). */
import { useState, type FormEvent } from "react";
import {
  AlertCircle,
  BarChart3,
  Bot,
  CalendarCheck,
  ChevronDown,
  Eye,
  EyeOff,
  LogIn,
  ShieldCheck,
  Users,
} from "lucide-react";
import { BrandMark } from "@/components/layout/AppShell";
import { Spinner } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, NETWORK_ERROR_MESSAGE } from "@/lib/api";
import { GOOGLE_LOGIN_URL, useAuth } from "@/lib/auth";
import { navigate } from "@/lib/router";
import { cn } from "@/lib/utils";

const DEMO_ACCOUNTS = [
  { email: "admin@company.com", role: "Admin" },
  { email: "neha.hr@company.com", role: "HR" },
  { email: "priya.mgr@company.com", role: "Manager" },
  { email: "aman@company.com", role: "Employee" },
  { email: "rahul@company.com", role: "Employee" },
];

const FEATURES = [
  { icon: Bot, text: "Ask questions in plain English — answers come from live HR data and policy documents" },
  { icon: CalendarCheck, text: "Attendance, leave and overtime tracking with approvals" },
  { icon: BarChart3, text: "Dashboards and Excel reports for HR teams" },
  { icon: ShieldCheck, text: "Role-based access for employees, managers, HR and admins" },
];

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.24 1.4-1.66 4.1-5.5 4.1-3.31 0-6-2.74-6-6.2s2.69-6.2 6-6.2c1.88 0 3.15.8 3.87 1.49l2.64-2.54C16.82 3.2 14.62 2.2 12 2.2 6.6 2.2 2.2 6.6 2.2 12s4.4 9.8 9.8 9.8c5.66 0 9.41-3.98 9.41-9.58 0-.64-.07-1.13-.16-1.62H12z" />
    </svg>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [demoOpen, setDemoOpen] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await login(email.trim(), password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 0 || err.status >= 500) setError(NETWORK_ERROR_MESSAGE);
        else if (err.status === 401) setError(err.message || "Invalid email or password.");
        else setError(err.message);
      } else {
        setError(NETWORK_ERROR_MESSAGE);
      }
    } finally {
      setLoading(false);
    }
  }

  function pickDemo(addr: string) {
    setEmail(addr);
    setPassword("");
    setError("");
    setTimeout(() => document.getElementById("password")?.focus(), 0);
  }

  return (
    <div className="flex min-h-screen bg-page">
      {/* Brand panel */}
      <aside className="relative hidden w-[46%] max-w-[640px] flex-col justify-between overflow-hidden bg-gradient-to-br from-navy via-navy to-navy-dark p-10 text-white lg:flex">
        <div className="pointer-events-none absolute -top-24 -right-24 size-80 rounded-full bg-brand/25 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-white/5 blur-2xl" />
        <div className="relative flex items-center gap-3">
          <BrandMark className="size-10 bg-white text-navy" />
          <span className="text-lg font-bold tracking-tight">AI HR Assistant</span>
        </div>
        <div className="relative">
          <h1 className="text-3xl leading-tight font-bold xl:text-4xl">
            Smart HR management with an AI assistant that answers from your company data
          </h1>
          <ul className="mt-8 space-y-4">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-sm text-blue-100">
                <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-white/10">
                  <Icon className="size-4 text-white" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative flex items-center gap-2 text-xs text-blue-200">
          <Users className="size-3.5" /> Employees · Attendance · Leave · Payroll · Documents · Reports
        </p>
      </aside>

      {/* Sign-in */}
      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-[400px]">
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <BrandMark className="size-10" />
            <div>
              <p className="text-lg font-bold text-navy">AI HR Assistant</p>
              <p className="text-xs text-ink-muted">Smart HR management with an AI assistant</p>
            </div>
          </div>

          <div className="hr-card p-6 sm:p-8">
            <h2 className="text-xl font-bold text-navy">Welcome back</h2>
            <p className="mt-1 text-sm text-ink-muted">Sign in to your account to continue</p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  className="h-10 bg-white"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                    className="h-10 bg-white pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-brand"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-200 bg-danger-light px-3 py-2.5 text-sm text-red-700">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <Button type="submit" className="h-10 w-full" disabled={loading}>
                {loading ? <Spinner /> : <LogIn className="size-4" />}
                {loading ? "Signing in..." : "Sign in"}
              </Button>
            </form>

            <div className="my-5 flex items-center gap-3 text-xs text-ink-muted">
              <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
            </div>

            <Button asChild variant="outline" className="h-10 w-full bg-white">
              <a href={GOOGLE_LOGIN_URL}>
                <GoogleIcon /> Sign in with Google
              </a>
            </Button>
          </div>

          {/* Demo accounts */}
          <div className="hr-card mt-4 overflow-hidden">
            <button
              type="button"
              onClick={() => setDemoOpen((o) => !o)}
              aria-expanded={demoOpen}
              className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-ink hover:bg-slate-50"
            >
              Demo accounts
              <ChevronDown className={cn("size-4 text-ink-muted transition-transform", demoOpen && "rotate-180")} />
            </button>
            {demoOpen && (
              <div className="border-t border-border px-2 pb-3">
                <p className="px-2 pt-3 pb-2 text-xs text-ink-muted">
                  Click an account to fill the email, then use the seeded password.
                </p>
                <ul>
                  {DEMO_ACCOUNTS.map((a) => (
                    <li key={a.email}>
                      <button
                        type="button"
                        onClick={() => pickDemo(a.email)}
                        className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm hover:bg-brand-light focus-visible:outline-2 focus-visible:outline-brand"
                      >
                        <span className="truncate text-ink">{a.email}</span>
                        <span className="ml-2 shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-ink-muted">
                          {a.role}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
