import { UsersRound } from "lucide-react";
import type { InstanceView, Tenant } from "../types";
import { Badge, Button, Select } from "./ui";

/**
 * The global tenant bar. It sits above the page area (not inside a page) so the selected
 * tenant is visible everywhere and survives navigation. Changing it here changes the context
 * for Home, Data, Warps and Gear at once.
 */
export function TenantBar({
  tenants,
  tenant,
  instances,
  loading,
  onSelect,
  onTeam,
}: {
  tenants: Tenant[];
  tenant: Tenant | null;
  instances: InstanceView[];
  loading: boolean;
  onSelect: (characterId: number) => void;
  onTeam: () => void;
}) {
  const live = tenant
    ? instances.find(
        (instance) =>
          instance.alive && Number(instance.character?.id) === Number(tenant.character.id),
      ) ?? null
    : null;

  return (
    <section className="tenant-bar" aria-label="Selected tenant">
      <div className="tenant-label">
        <UsersRound size={15} strokeWidth={1.9} />
        <span className="eyebrow">Tenant</span>
      </div>

      {tenant ? (
        <>
          <div className="tenant-current">
            <div className="avatar small">{tenant.character.name.slice(0, 1).toUpperCase()}</div>
            <div className="tenant-current-copy">
              <div className="tenant-current-name">
                <strong>{tenant.character.name}</strong>
                <Badge tone={tenant.kind === "sub" ? "accent" : "neutral"}>{tenant.label}</Badge>
                {live ? (
                  <Badge tone="success" dot>
                    In game
                  </Badge>
                ) : (
                  <span className="tenant-offline">Not running</span>
                )}
              </div>
              <span className="tenant-account">@{tenant.account}</span>
            </div>
          </div>

          <label className="tenant-switch">
            <span>Viewing</span>
            <Select
              value={tenant.character.id}
              onChange={(event) => onSelect(Number(event.target.value))}
              aria-label="Tenant to view"
            >
              {tenants.map((entry) => (
                <option key={entry.character.id} value={entry.character.id}>
                  {entry.character.name} · @{entry.account}
                  {entry.kind === "sub" ? ` · ${entry.label}` : ""}
                </option>
              ))}
            </Select>
          </label>

          <Button variant="ghost" size="sm" onClick={onTeam}>
            Team
          </Button>
        </>
      ) : (
        <div className="tenant-empty">
          <span>
            {loading
              ? "Loading your team…"
              : "No characters yet — create one, or add a box on the Team page."}
          </span>
          <Button variant="secondary" size="sm" onClick={onTeam}>
            Open Team
          </Button>
        </div>
      )}
    </section>
  );
}
