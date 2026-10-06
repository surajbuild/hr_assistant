/** Profile dropdown: identity, My Profile, Logout. */
import { LogOut, UserCircle } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { RoleBadge } from "@/components/StatusBadge";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { displayName, useAuth } from "@/lib/auth";
import { navigate } from "@/lib/router";

export function ProfileMenu() {
  const { user, role, logout } = useAuth();
  const name = displayName(user);

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Account menu for ${name}`}
          className="flex items-center gap-2 rounded-lg p-1 pr-1.5 transition-colors hover:bg-accent sm:pr-2.5"
        >
          <Avatar name={name} seed={user?.user_id} size="sm" />
          <span className="hidden max-w-[140px] truncate text-sm font-medium text-foreground sm:block">{name}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64">
        <div className="flex items-center gap-3 px-2.5 py-2.5">
          <Avatar name={name} seed={user?.user_id} size="md" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{name}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
            <div className="mt-1 flex items-center gap-1.5">
              <RoleBadge role={role} />
              {user?.employee?.designation && <span className="truncate text-xs text-muted-foreground">{user.employee.designation}</span>}
            </div>
          </div>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/my-profile")}>
          <UserCircle /> My Profile
        </DropdownMenuItem>
        <DropdownMenuItem destructive onSelect={handleLogout}>
          <LogOut /> Logout
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
