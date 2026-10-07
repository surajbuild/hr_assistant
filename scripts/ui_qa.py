"""
scripts/ui_qa.py
----------------
Browser QA harness (dev tool, not part of the app). Drives the real UI with
Playwright using the locally installed Microsoft Edge (no browser download) —
see PROJECT_DECISIONS.md D-020.

For every role × viewport it logs in through the login form, visits every page
the role may open (plus a forbidden one), and records:
  - console errors / uncaught page errors
  - failed API calls (HTTP >= 400 on /api/*)
  - horizontal page overflow (document wider than the viewport)
  - layout invariants from AGENTS.md §7 (design system v2: sticky top bar, left sidebar >= 768px
    [expanded >= 1280px, icon rail 768-1279px], drawer + hamburger on phones, menu items match the role)
  - a full-page screenshot per page

Usage (servers must be running: backend :8000, frontend :3000):
    pip install playwright            # dev-only, not in requirements.txt
    python scripts/ui_qa.py                         # all roles, both widths
    python scripts/ui_qa.py --roles admin --widths 1400 --out qa_shots
Exit code 1 if any issue is found.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
PASSWORD = "Demo@12345"

USERS = {
    "admin": "admin@company.com",
    "hr": "neha.hr@company.com",
    "manager": "priya.mgr@company.com",
    "employee": "aman@company.com",
}

ALL = ["admin", "hr", "manager", "employee"]
STAFF = ["admin", "hr", "manager"]
HR = ["admin", "hr"]

# (path, label in navbar or None, roles allowed)
PAGES = [
    ("/dashboard", "Dashboard", ALL),
    ("/my-profile", "My Profile", ALL),
    ("/employees", "Employees", STAFF),
    ("/employees/add", None, HR),
    ("/employees/{emp_id}", None, STAFF),
    ("/employees/{emp_id}/edit", None, HR),
    ("/departments", "Departments", STAFF),
    ("/attendance", "Attendance", ALL),
    ("/leave", "Leave", ALL),
    ("/payroll", "Payroll", ALL),
    ("/documents", "Documents", ALL),
    ("/reports", "Reports", HR),
    ("/assistant", "AI Assistant", ALL),
    ("/settings", "Settings", ["admin"]),
]

NAV_LABELS = {p[1]: p[2] for p in PAGES if p[1]}

# Detail/edit pages use Aman (EMP004): visible to every staff role (he reports to the manager Priya).
# For the employee role, /employees/<aman id> is still checked as a forbidden route.


def check_page(page, path: str, role: str, width: int, out: Path, issues: list, api_errors: list):
    api_errors.clear()
    page.goto(BASE + path, wait_until="networkidle")
    # let skeleton/spinners resolve
    try:
        page.wait_for_function(
            "() => !document.querySelector('[data-loading=\"true\"], .animate-spin, [role=status] .skeleton')", timeout=8000
        )
    except Exception:
        issues.append(f"{role}@{width} {path}: still loading after 8s")
    page.wait_for_timeout(300)

    final = page.url.replace(BASE, "")
    overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    if overflow > 1:
        issues.append(f"{role}@{width} {path}: horizontal overflow {overflow}px")
    for err in api_errors:
        issues.append(f"{role}@{width} {path}: API {err}")

    safe = re.sub(r"[^a-z0-9]+", "_", path.strip("/").lower()) or "root"
    page.screenshot(path=str(out / f"{role}_{width}_{safe}.png"), full_page=True)
    return final


def run(roles, widths, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    report = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for role in roles:
            for width in widths:
                height = 900 if width >= 1000 else 844
                ctx = browser.new_context(viewport={"width": width, "height": height})
                page = ctx.new_page()
                console_errors: list[str] = []
                api_errors: list[str] = []
                page.on("console", lambda m: m.type == "error" and console_errors.append(m.text))
                page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
                page.on(
                    "response",
                    lambda r: ("/api/" in r.url and r.status >= 400)
                    and api_errors.append(f"{r.status} {r.request.method} {r.url.replace(BASE, '')}"),
                )

                # --- login through the form
                page.goto(BASE + "/login", wait_until="networkidle")
                page.fill("#email", USERS[role])
                page.fill("#password", PASSWORD)
                page.click("button[type=submit]")
                page.wait_for_url("**/dashboard", timeout=15000)
                page.wait_for_load_state("networkidle")
                page.wait_for_selector("h1", timeout=15000)  # route pages are lazy-loaded (KI-006)

                # --- layout invariants
                layout = page.evaluate(
                    """() => {
                        const header = document.querySelector('header');
                        const aside = document.querySelector('aside');
                        const vis = (el) => !!(el && el.offsetWidth > 0 && el.offsetHeight > 0);
                        const links = [...document.querySelectorAll('aside nav[aria-label="Main"] a')].map(a => (a.getAttribute('aria-label') || a.textContent).trim());
                        const burger = document.querySelector('header button[aria-label="Open navigation menu"]');
                        return {
                          header: !!header,
                          headerHeight: header ? Math.round(header.getBoundingClientRect().height) : 0,
                          sticky: header ? getComputedStyle(header).position : null,
                          asideVisible: vis(aside),
                          asideWidth: aside ? Math.round(aside.getBoundingClientRect().width) : 0,
                          links,
                          menuButtonVisible: vis(burger),
                          searchButton: !!document.querySelector('header button[aria-label^="Search"]'),
                          themeButton: !!document.querySelector('header button[aria-label^="Theme"]'),
                          greeting: (document.querySelector('h1')||{}).textContent || '',
                        };
                    }"""
                )
                if not layout["header"]:
                    issues.append(f"{role}@{width}: no <header> top bar")
                if layout["sticky"] not in ("sticky", "fixed"):
                    issues.append(f"{role}@{width}: top bar not sticky ({layout['sticky']})")
                if not layout["searchButton"] or not layout["themeButton"]:
                    issues.append(f"{role}@{width}: top bar missing search or theme control")
                if width >= 768:
                    if not layout["asideVisible"]:
                        issues.append(f"{role}@{width}: sidebar not visible at >= 768px")
                    elif width >= 1280 and layout["asideWidth"] < 200:
                        issues.append(f"{role}@{width}: sidebar should be expanded at >= 1280px (width {layout['asideWidth']})")
                    elif width < 1280 and layout["asideWidth"] > 100:
                        issues.append(f"{role}@{width}: sidebar should be an icon rail at 768-1279px (width {layout['asideWidth']})")
                    expected = [lbl for lbl, rs in NAV_LABELS.items() if role in rs]
                    if layout["links"] != expected:
                        issues.append(f"{role}@{width}: menu {layout['links']} != expected {expected}")
                else:
                    if layout["asideVisible"]:
                        issues.append(f"{role}@{width}: sidebar visible on phone (should be a drawer)")
                    if not layout["menuButtonVisible"]:
                        issues.append(f"{role}@{width}: hamburger menu button not visible on phone")

                # employee id for detail pages (only roles that may call the directory API)
                emp_id = None if role not in STAFF else page.evaluate(
                    """async () => {
                        const t = localStorage.getItem('hr_token');
                        const r = await fetch('/api/employees?search=aman', {headers:{Authorization:'Bearer '+t}});
                        if (!r.ok) return null; const d = await r.json(); return d[0] ? d[0].id : null;
                    }"""
                )

                visited = {}
                for path, _label, allowed in PAGES:
                    if "{emp_id}" in path:
                        if emp_id is None:
                            path = path.replace("{emp_id}", "1")  # employee role: must still be guarded
                        else:
                            path = path.replace("{emp_id}", str(emp_id))
                    final = check_page(page, path, role, width, out, issues, api_errors)
                    allowed_here = role in allowed
                    if allowed_here and final.split("?")[0] != path:
                        issues.append(f"{role}@{width} {path}: redirected to {final} although allowed")
                    if not allowed_here and final.split("?")[0] == path:
                        issues.append(f"{role}@{width} {path}: forbidden page rendered (no guard redirect)")
                    visited[path] = final

                for e in console_errors:
                    issues.append(f"{role}@{width}: console {e[:200]}")
                report.append({"role": role, "width": width, "layout": layout, "visited": visited})
                ctx.close()
        browser.close()

    (out / "report.json").write_text(json.dumps({"issues": issues, "runs": report}, indent=2), encoding="utf-8")
    print(f"Screenshots + report.json in {out}")
    for r in report:
        print(f"  {r['role']:<9} {r['width']:>4}px  greeting={r['layout']['greeting']!r}  links={len(r['layout']['links'])}")
    print(f"\n{len(issues)} issue(s)")
    for i in issues:
        print("  - " + i)
    return 1 if issues else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", nargs="*", default=ALL)
    ap.add_argument("--widths", nargs="*", type=int, default=[1440, 1024, 390])
    ap.add_argument("--out", default="qa_shots")
    args = ap.parse_args()
    sys.exit(run(args.roles, args.widths, Path(args.out)))
