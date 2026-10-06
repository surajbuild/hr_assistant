/**
 * Login: split screen — calm brand panel (desktop) + sign-in form.
 * Email/password (POST /auth/login via AuthProvider), Google (redirect flow), demo-account quick-fill chips.
 * Behaviour unchanged: generic backend error ("Invalid email or password."), network errors, redirect to /dashboard.
 */
import { useRef, useState, type FormEvent } from "react";
import { AlertCircle, BarChart3, Bot, CalendarCheck, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { BrandMark } from "@/components/layout/BrandMark";
import { ThemeMenu } from "@/components/layout/ThemeMenu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ApiError, NETWORK_ERROR_MESSAGE } from "@/lib/api";
import { GOOGLE_LOGIN_URL, useAuth } from "@/lib/auth";
import { navigate } from "@/lib/router";
import { cn } from "@/lib/utils";

const DEMO_ACCOUNTS = [
  { email: "admin@company.com", role: "Admin", name: "Admin", tone: "bg-brand-subtle text-brand-subtle-foreground" },
  { email: "neha.hr@company.com", role: "HR", name: "Neha", tone: "bg-status-leave-bg text-status-leave-fg" },
  { email: "priya.mgr@company.com", role: "Manager", name: "Priya", tone: "bg-status-half-bg text-status-half-fg" },
  { email: "aman@company.com", role: "Employee", name: "Aman", tone: "bg-status-present-bg text-status-present-fg" },
  { email: "rahul@company.com", role: "Employee", name: "Rahul", tone: "bg-status-present-bg text-status-present-fg" },
];

const FEATURES = [
  { icon: Bot, title: "Ask in plain English", text: "Answers come from live HR data and your policy documents, with sources." },
  { icon: CalendarCheck, title: "Attendance & leave", text: "Check-ins, overtime and approvals in one place." },
  { icon: BarChart3, title: "Payroll & reports", text: "Monthly payroll and Excel exports for HR teams." },
  { icon: ShieldCheck, title: "Role-based access", text: "Employees, managers, HR and admins each see only what they should." },
];

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.4-.18-2.05H12v3.87h5.38a4.6 4.6 0 0 1-2 3.02v2.5h3.24c1.9-1.75 2.98-4.32 2.98-7.34z" />
      <path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.43l-3.24-2.5c-.9.6-2.04.95-3.38.95-2.6 0-4.8-1.76-5.59-4.12H3.07v2.58A10 10 0 0 0 12 22z" />
      <path fill="#FBBC05" d="M6.41 13.9a6 6 0 0 1 0-3.8V7.52H3.07a10 10 0 0 0 0 8.96l3.34-2.58z" />
      <path fill="#EA4335" d="M12 5.98c1.47 0 2.79.5 3.83 1.5l2.87-2.87C16.95 2.99 14.7 2 12 2a10 10 0 0 0-8.93 5.52l3.34 2.58C7.2 7.74 9.4 5.98 12 5.98z" />
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
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const passwordRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const errs: { email?: string; password?: string } = {};
    if (!email.trim()) errs.email = "Enter your email address.";
    if (!password) errs.password = "Enter your password.";
    setFieldErrors(errs);
    if (errs.email || errs.password) {
      setError("");
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
    setFieldErrors({});
    setTimeout(() => passwordRef.current?.focus(), 0);
  }

  return (
    <TooltipProvider>
      <div className="flex min-h-screen bg-background">
        {/* Brand panel (desktop) */}
        <aside className="relative hidden w-[44%] max-w-[640px] flex-col justify-between overflow-hidden bg-brand-panel p-12 text-brand-panel-foreground lg:flex">
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.35]"
            style={{
              backgroundImage: "radial-gradient(color-mix(in srgb, currentColor 18%, transparent) 1px, transparent 1px)",
              backgroundSize: "22px 22px",
              maskImage: "linear-gradient(180deg, transparent, black 30%, black 70%, transparent)",
            }}
            aria-hidden="true"
          />
          <div className="relative flex items-center gap-3">
            <BrandMark className="size-9 bg-brand-panel-foreground text-brand-panel" />
            <span className="text-base font-semibold tracking-tight">AI HR Assistant</span>
          </div>

          <div className="relative">
            <h1 className="max-w-md text-[34px] leading-[1.15] font-semibold tracking-tight text-brand-panel-foreground">HR that answers back.</h1>
            <p className="mt-3 max-w-md text-[15px] leading-relaxed opacity-80">
              Attendance, leave, payroll and policies in one workspace — with an assistant that answers from your own company data.
            </p>
            <ul className="mt-10 space-y-5">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <li key={title} className="flex items-start gap-3.5">
                  <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-panel-foreground/10 text-brand-panel-foreground">
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-brand-panel-foreground">{title}</p>
                    <p className="text-sm opacity-70">{text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <p className="relative text-xs opacity-60">Answers are computed from your database — never guessed by the model.</p>
        </aside>

        {/* Sign-in */}
        <main className="relative flex flex-1 flex-col">
          <div className="flex items-center justify-between px-5 pt-4 sm:px-8 sm:pt-6">
            <div className="flex items-center gap-2.5 lg:invisible">
              <BrandMark />
              <span className="text-[15px] font-semibold tracking-tight text-foreground">AI HR Assistant</span>
            </div>
            <ThemeMenu />
          </div>

          <div className="flex flex-1 items-center justify-center px-5 py-8 sm:px-8">
            <div className="w-full max-w-[400px] animate-page-in">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">Sign in</h2>
              <p className="mt-1 text-sm text-muted-foreground">Welcome back. Enter your details to continue.</p>

              <form onSubmit={handleSubmit} className="mt-7 space-y-4" noValidate>
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
                    aria-invalid={!!fieldErrors.email}
                    aria-describedby={fieldErrors.email ? "email-error" : undefined}
                    className="h-10"
                  />
                  {fieldErrors.email && (
                    <p id="email-error" role="alert" className="text-xs text-status-absent-fg">
                      {fieldErrors.email}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      ref={passwordRef}
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      disabled={loading}
                      aria-invalid={!!fieldErrors.password}
                      aria-describedby={fieldErrors.password ? "password-error" : undefined}
                      className="h-10 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((s) => !s)}
                      className="absolute top-1/2 right-1.5 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      aria-pressed={showPassword}
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                  {fieldErrors.password && (
                    <p id="password-error" role="alert" className="text-xs text-status-absent-fg">
                      {fieldErrors.password}
                    </p>
                  )}
                </div>

                {error && (
                  <div role="alert" className="flex items-start gap-2 rounded-lg border border-status-absent/25 bg-status-absent-bg px-3 py-2.5 text-sm text-status-absent-fg">
                    <AlertCircle className="mt-0.5 size-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <Button type="submit" size="lg" className="w-full" loading={loading}>
                  {loading ? "Signing in…" : "Sign in"}
                </Button>
              </form>

              <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
                <span className="h-px flex-1 bg-border" />
                or
                <span className="h-px flex-1 bg-border" />
              </div>

              <Button asChild variant="outline" size="lg" className="w-full">
                <a href={GOOGLE_LOGIN_URL}>
                  <GoogleIcon /> Continue with Google
                </a>
              </Button>

              {/* Demo accounts: quick-fill the email, then type the seeded password */}
              <div className="mt-8 rounded-xl border border-dashed border-border-strong p-4">
                <p className="text-xs font-medium text-foreground">Demo accounts</p>
                <p className="mt-0.5 text-xs text-muted-foreground">Pick one to fill the email, then enter the seeded demo password.</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {DEMO_ACCOUNTS.map((a) => (
                    <button
                      key={a.email}
                      type="button"
                      onClick={() => pickDemo(a.email)}
                      title={a.email}
                      aria-label={`Fill ${a.role} demo account ${a.email}`}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-[filter,transform] duration-150 hover:brightness-95 active:scale-95",
                        a.tone,
                      )}
                    >
                      {a.role}
                      {a.role !== "Admin" && <span className="font-normal">· {a.name}</span>}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </TooltipProvider>
  );
}
