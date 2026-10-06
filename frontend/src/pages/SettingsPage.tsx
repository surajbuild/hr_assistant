/**
 * Settings (admin only — route guard in App.tsx, every endpoint enforces admin server-side).
 * Tabs: Users & Roles (GET/PATCH /users) · AI Chat Audit Log (GET /chat/logs, server-paginated) ·
 * Company Policy (documents, holiday calendar, leave entitlements — real data only).
 * The selected tab is kept in the URL (?tab=) so it survives reloads and can be linked to.
 */
import { Building2, ScrollText, UserCog } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Tabs } from "@/components/Tabs";
import { navigate, useRoute } from "@/lib/router";
import { AuditLogTab } from "./settings/AuditLogTab";
import { PolicyTab } from "./settings/PolicyTab";
import { UsersTab } from "./settings/UsersTab";

type TabKey = "users" | "logs" | "policy";
const TAB_KEYS: TabKey[] = ["users", "logs", "policy"];

export function SettingsPage() {
  const { query } = useRoute();
  const raw = query.get("tab") as TabKey | null;
  const tab: TabKey = raw && TAB_KEYS.includes(raw) ? raw : "users";

  function setTab(t: TabKey) {
    navigate(t === "users" ? "/settings" : `/settings?tab=${t}`, { replace: true });
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="Access control, AI assistant oversight and company policy sources" />
      <Tabs
        tabs={[
          { key: "users", label: "Users & Roles", icon: <UserCog /> },
          { key: "logs", label: "AI Chat Audit Log", icon: <ScrollText /> },
          { key: "policy", label: "Company Policy", icon: <Building2 /> },
        ]}
        value={tab}
        onChange={setTab}
        className="mb-5"
      />
      <div role="tabpanel" aria-label={tab === "users" ? "Users & Roles" : tab === "logs" ? "AI Chat Audit Log" : "Company Policy"}>
        {tab === "users" && <UsersTab />}
        {tab === "logs" && <AuditLogTab />}
        {tab === "policy" && <PolicyTab />}
      </div>
    </>
  );
}
