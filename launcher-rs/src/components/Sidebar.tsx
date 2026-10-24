import {
  Database,
  Gamepad2,
  Home,
  LogOut,
  MapPin,
  Newspaper,
  Palette,
  Settings,
  Shirt,
  UserRound,
  Users,
  UsersRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Page, ServerStatus, SessionView } from "../types";
import { Badge, cn } from "./ui";

const NAV: { page: Page; label: string; icon: LucideIcon }[] = [
  { page: "home", label: "Home", icon: Home },
  { page: "characters", label: "Characters", icon: UserRound },
  { page: "design", label: "Design", icon: Palette },
  { page: "accounts", label: "Accounts", icon: Users },
  { page: "team", label: "Team", icon: UsersRound },
  { page: "control", label: "Control room", icon: Gamepad2 },
  { page: "warps", label: "Warps", icon: MapPin },
  { page: "data", label: "Data", icon: Database },
  { page: "gear", label: "Gear / GearSwap", icon: Shirt },
  { page: "news", label: "News", icon: Newspaper },
  { page: "settings", label: "Settings", icon: Settings },
];

export function Sidebar({
  page,
  onNavigate,
  session,
  online,
  status,
  version,
  onSignOut,
}: {
  page: Page;
  onNavigate: (page: Page) => void;
  session: SessionView;
  online: number;
  status: ServerStatus | null;
  version: string;
  onSignOut: () => void;
}) {
  const onlineLabel =
    status?.online === undefined ? "Server unknown" : `${status.online} online`;
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <img src="/fanxi-icon.png" alt="" />
        </div>
        <div>
          <div className="brand-name">FANXI</div>
          <div className="brand-sub">LAUNCHER</div>
        </div>
      </div>

      <div className="server-pill">
        <span className={cn("status-dot", status ? "status-online" : "status-offline")} />
        <span>{onlineLabel}</span>
        <span className="server-version">{status?.version ? `v${status.version}` : ""}</span>
      </div>

      <nav className="nav">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = page === item.page;
          return (
            <button
              key={item.page}
              className={cn("nav-item", active && "nav-active")}
              onClick={() => onNavigate(item.page)}
            >
              <span className="nav-bar" />
              <Icon size={17} strokeWidth={1.8} />
              <span>{item.label}</span>
              {item.page === "control" && online > 0 && (
                <Badge tone="success" dot>
                  {online}
                </Badge>
              )}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-foot">
        <div className="account-chip">
          <div className="avatar">{session.account.username.slice(0, 1).toUpperCase()}</div>
          <div className="account-meta">
            <strong>@{session.account.username}</strong>
            <span>{session.account.role === "admin" ? "Administrator" : "Adventurer"}</span>
          </div>
        </div>
        <button className="signout" onClick={onSignOut}>
          <LogOut size={14} />
          Sign out
        </button>
        <div className="build-tag">Fanxi Launcher {version}</div>
      </div>
    </aside>
  );
}
