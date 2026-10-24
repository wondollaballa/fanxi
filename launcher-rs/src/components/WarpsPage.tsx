import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  Crosshair,
  Gamepad2,
  Keyboard,
  MapPin,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  UserRound,
  UsersRound,
} from "lucide-react";
import type {
  InstanceView,
  SessionView,
  TeamView,
  Tenant,
  WarpList,
  WarpPoint,
} from "../types";
import { backend, LauncherError } from "../lib/api";
import { jobAbbr, jobName, ZONES } from "../lib/format";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  Modal,
  SectionHeader,
  TextInput,
  cn,
} from "./ui";

type Notify = (message: string, kind?: "success" | "error" | "info") => void;
type WarpTarget = "me" | "all";

function messageOf(error: unknown): string {
  if (error instanceof LauncherError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}

function slotLabel(slot: number): string {
  return `#${String(slot).padStart(3, "0")}`;
}

function warpLabel(warp: WarpPoint): string {
  return warp.alias || "Unnamed warp";
}

function coord(value: number | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";
}

export function WarpsPage({
  session,
  tenant,
  team,
  instances,
  notify,
  onControl,
  onCharacters,
  onTeam,
}: {
  session: SessionView;
  tenant: Tenant | null;
  team: TeamView | null;
  instances: InstanceView[];
  notify: Notify;
  onControl: () => void;
  onCharacters: () => void;
  onTeam: () => void;
}) {
  const [data, setData] = useState<WarpList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [aliasInput, setAliasInput] = useState("");
  const [target, setTarget] = useState<WarpTarget>("me");
  const [busy, setBusy] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<WarpPoint | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<WarpPoint | null>(null);

  // The tenant bar is the one character context shared by Home, Data, Gear and Warps.
  const selectedCharacter = tenant?.character ?? null;
  const selectedId = selectedCharacter ? Number(selectedCharacter.id) : null;

  const load = useCallback(async () => {
    if (selectedId === null) {
      setData(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setData(await backend.characterWarps(selectedId));
    } catch (problem) {
      setError(messageOf(problem));
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    setData(null);
    setSearch("");
    setAliasInput("");
    void load();
  }, [load]);

  const liveInstance = useMemo(
    () =>
      instances.find(
        (instance) =>
          instance.alive && Number(instance.character?.id) === selectedId,
      ) ?? null,
    [instances, selectedId],
  );

  const familyAccounts = useMemo(() => {
    const names = new Set<string>([session.account.username.toLowerCase()]);
    for (const sub of team?.subs ?? []) names.add(sub.username.toLowerCase());
    if (tenant) names.add(tenant.account.toLowerCase());
    return names;
  }, [session.account.username, team, tenant]);

  const familyOnline = useMemo(
    () =>
      instances.filter(
        (instance) => instance.alive && familyAccounts.has(instance.account.toLowerCase()),
      ),
    [instances, familyAccounts],
  );

  const liveState = liveInstance?.state ?? null;
  const livePosition = liveState?.player?.position;
  const currentZone = liveState?.zone?.id ?? data?.character.zone ?? 0;
  const currentZoneName =
    liveState?.zone?.name ??
    data?.character.zone_name ??
    ZONES[currentZone] ??
    (currentZone ? `Zone ${currentZone}` : "Unknown zone");
  const position = livePosition ?? data?.character.position ?? null;
  const rotation = livePosition?.heading ?? data?.character.position.rot ?? null;
  const isLive = liveInstance !== null;
  /** A live process can still be at the character-select screen; commands and marks need a
   * character actually in the world. */
  const inGame = Boolean(isLive && liveState?.player && liveState.zone?.id);
  const isActing = busy !== null;

  const visibleWarps = useMemo(() => {
    const query = search.trim().toLowerCase();
    const warps = data?.warps ?? [];
    if (!query) return warps;
    return warps.filter((warp) =>
      [warp.alias, warp.zone_name, String(warp.slot), slotLabel(warp.slot)]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [data, search]);

  async function markCurrent() {
    if (!selectedId || !liveInstance || !inGame || isActing) return;
    setBusy("mark");
    try {
      const payload: Record<string, unknown> = {};
      const alias = aliasInput.trim();
      if (alias) payload.alias = alias;
      try {
        const state = await backend.controlState(liveInstance.port);
        const where = state.player?.position;
        const zone = state.zone?.id;
        if (
          zone &&
          where &&
          typeof where.x === "number" &&
          typeof where.y === "number" &&
          typeof where.z === "number"
        ) {
          payload.zone = zone;
          payload.x = where.x;
          payload.y = where.y;
          payload.z = where.z;
          payload.rot = where.heading ?? 0;
        }
      } catch {
        // The server's last saved position is still a useful mark; keep going.
      }
      const result = await backend.markCharacterWarp(selectedId, payload);
      setData(result.data);
      setAliasInput("");
      const created = result.warp;
      notify(
        created
          ? `Marked warp ${created.slot}${created.alias ? ` — ${created.alias}` : ""}`
          : "Marked the current spot",
        "success",
      );
    } catch (problem) {
      notify(messageOf(problem), "error");
    } finally {
      setBusy(null);
    }
  }

  async function warpTo(warp: WarpPoint) {
    if (!liveInstance || !inGame || isActing) return;
    setBusy(`warp-${warp.slot}`);
    try {
      await backend.sendCommand(
        liveInstance.port,
        `!warp ${target === "all" ? "all" : "me"} ${warp.slot}`,
      );
      const label = warpLabel(warp);
      notify(
        target === "all"
          ? `Warping ${Math.max(1, familyOnline.length)} character${
              familyOnline.length === 1 ? "" : "s"
            } to ${label}`
          : `Warping to ${label}`,
        "success",
      );
    } catch (problem) {
      notify(messageOf(problem), "error");
    } finally {
      setBusy(null);
    }
  }

  function openRename(warp: WarpPoint) {
    setRenameTarget(warp);
    setRenameValue(warp.alias);
  }

  async function saveRename() {
    if (!selectedId || !renameTarget || isActing) return;
    setBusy("rename");
    try {
      const result = await backend.renameCharacterWarp(
        selectedId,
        renameTarget.slot,
        renameValue.trim(),
      );
      setData(result.data);
      notify(
        renameValue.trim()
          ? `Warp ${renameTarget.slot} renamed to ${renameValue.trim()}`
          : `Warp ${renameTarget.slot} now has no alias`,
        "success",
      );
      setRenameTarget(null);
    } catch (problem) {
      notify(messageOf(problem), "error");
    } finally {
      setBusy(null);
    }
  }

  async function confirmDelete() {
    if (!selectedId || !deleteTarget || isActing) return;
    setBusy("delete");
    try {
      const result = await backend.deleteCharacterWarp(selectedId, deleteTarget.slot);
      setData(result.data);
      notify(`Warp ${deleteTarget.slot} deleted`, "info");
      setDeleteTarget(null);
    } catch (problem) {
      notify(messageOf(problem), "error");
    } finally {
      setBusy(null);
    }
  }

  if (!tenant || !selectedCharacter) {
    return (
      <div className="page warps-page">
        <SectionHeader
          eyebrow="Travel"
          title="Warps"
          subtitle="Save the camps and corners you keep coming back to, then return with a name instead of a zone id."
        />
        <EmptyState
          icon={<MapPin size={22} />}
          title="No tenant selected"
          body="Pick a character in the tenant bar, create one, or add a box on the Team page."
          action={
            <>
              <Button onClick={onTeam}>Open Team</Button>
              <Button variant="ghost" onClick={onCharacters}>
                Characters
              </Button>
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="page warps-page">
      <SectionHeader
        eyebrow="Travel"
        title="Warps"
        subtitle="Mark a camp once, name it, and warp yourself or your whole team back without remembering a zone id or a coordinate."
        actions={
          <>
            <Button variant="ghost" icon={<Gamepad2 size={15} />} onClick={onControl}>
              Control room
            </Button>
            <Button
              variant="ghost"
              icon={<RefreshCw size={15} />}
              loading={loading}
              onClick={() => void load()}
            >
              Refresh
            </Button>
          </>
        }
      />

      <Card className="warp-identity">
        <div className="warp-identity-character">
          <div className="avatar">
            {(selectedCharacter?.name ?? "?").slice(0, 1).toUpperCase()}
          </div>
          <div className="warp-identity-copy">
            <strong>{selectedCharacter?.name ?? "No character"}</strong>
            <span>
              {selectedCharacter
                ? `${jobAbbr(Number(selectedCharacter.main_job))} · ${jobName(
                    Number(selectedCharacter.main_job),
                  )} Lv ${selectedCharacter.main_level ?? "?"}`
                : "Pick a character to manage"}
            </span>
          </div>
        </div>
        <div className="warp-identity-side">
          <div className="warp-live-state">
            {inGame ? (
              <Badge tone="success" dot>
                Client live
              </Badge>
            ) : isLive ? (
              <Badge tone="warning" dot>
                Signing in
              </Badge>
            ) : (
              <Badge tone="neutral">Offline</Badge>
            )}
            <span className="muted">
              {inGame
                ? "Position is read from the running client"
                : isLive
                  ? "The client is still signing in; wait for the character to enter the world"
                  : "Edit aliases offline; launch the client to mark or warp"}
            </span>
          </div>
          <div className="warp-tenant">
            <span className="eyebrow">Tenant</span>
            <strong>{tenant.label}</strong>
            <span className="muted">@{tenant.account}</span>
            <Button variant="ghost" size="sm" onClick={onTeam}>
              Team
            </Button>
          </div>
        </div>
      </Card>

      <Card accent className="warp-hero">
        <div className="warp-current">
          <div className="warp-current-head">
            <span className="eyebrow">Current position</span>
            <Badge tone={inGame ? "success" : isLive ? "warning" : "neutral"} dot={inGame || isLive}>
              {inGame ? "Live" : isLive ? "Signing in" : "Last saved"}
            </Badge>
          </div>
          <h2>{currentZoneName}</h2>
          <p>
            {inGame
              ? "Mark where you are standing right now; the launcher reads the client's live position."
              : isLive
                ? "The client is still signing in. Wait for the character to enter the world, then mark or warp."
                : "Start the client from the Control room to mark the spot you are standing on."}
          </p>
          <div className="warp-coordinate-row">
            <span>
              <b>X</b> {coord(position?.x)}
            </span>
            <span>
              <b>Y</b> {coord(position?.y)}
            </span>
            <span>
              <b>Z</b> {coord(position?.z)}
            </span>
            <span>
              <b>Rot</b> {rotation ?? "—"}
            </span>
          </div>
        </div>
        <div className="warp-mark-panel">
          <div className="warp-mark-title">
            <Crosshair size={15} />
            <span>Mark this spot</span>
            <Badge tone="accent">
              {data?.next_slot ? `Next ${slotLabel(data.next_slot)}` : "Slots full"}
            </Badge>
          </div>
          <div className="warp-mark-row">
            <TextInput
              value={aliasInput}
              onChange={(event) => setAliasInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && inGame) void markCurrent();
              }}
              maxLength={40}
              placeholder="Name it — e.g. Cape Teriggan camp"
              aria-label="Alias for the new warp"
              disabled={!inGame}
            />
            <Button
              icon={<Crosshair size={15} />}
              loading={busy === "mark"}
              disabled={!inGame || isActing || data?.next_slot === null}
              onClick={() => void markCurrent()}
            >
              Mark
            </Button>
          </div>
          <p className="warp-mark-hint">
            The alias is optional. Leave it blank and name the number here later.
          </p>
        </div>
      </Card>

      {error && <ErrorBanner message={error} onClose={() => setError("")} />}

      <Card className="warp-list-card">
        <div className="warp-toolbar">
          <div className="warp-toolbar-title">
            <div>
              <span className="eyebrow">Saved places</span>
              <strong>
                {data
                  ? `${data.warps.length} of ${data.limit} slots${
                      search ? ` · ${visibleWarps.length} shown` : ""
                    }`
                  : "Loading…"}
              </strong>
            </div>
            <div className="warp-search">
              <Search size={14} />
              <TextInput
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search aliases and zones"
                aria-label="Search warps"
              />
            </div>
          </div>
          <div className="warp-target">
            <span className="warp-target-label">Warp</span>
            <div className="segmented small">
              <button
                type="button"
                className={cn(target === "me" && "active")}
                onClick={() => setTarget("me")}
              >
                <UserRound size={13} /> Just me
              </button>
              <button
                type="button"
                className={cn(target === "all" && "active")}
                onClick={() => setTarget("all")}
              >
                <UsersRound size={13} /> Everyone ({Math.max(1, familyOnline.length)})
              </button>
            </div>
          </div>
        </div>

        {target === "all" && (
          <p className="warp-target-hint">
            Everyone means this character's main account and its online sub-account characters —
            the same group <code>!warp all</code> moves in game.
          </p>
        )}

        {loading && !data ? (
          <div className="warp-loading">Reading saved places…</div>
        ) : visibleWarps.length === 0 ? (
          <EmptyState
            icon={<MapPin size={22} />}
            title={search ? "No warp matches that search" : "No places saved yet"}
            body={
              search
                ? "Try the number, the alias or the zone name."
                : inGame
                  ? "Stand at a camp, give it a name above and press Mark. It gets the next free number."
                  : isLive
                    ? "Wait for the character to finish signing in, then mark the spot."
                    : "Launch this character from the Control room, stand where you want to return, then mark it."
            }
            action={
              search ? (
                <Button variant="ghost" onClick={() => setSearch("")}>
                  Clear search
                </Button>
              ) : !inGame ? (
                <Button onClick={onControl}>Open Control room</Button>
              ) : undefined
            }
          />
        ) : (
          <div className="warp-list">
            {visibleWarps.map((warp) => (
              <div className="warp-row" key={warp.slot}>
                <div className="warp-slot">{slotLabel(warp.slot)}</div>
                <div className="warp-row-main">
                  <strong className={cn(!warp.alias && "muted")}>{warpLabel(warp)}</strong>
                  <span>
                    <MapPin size={12} /> {warp.zone_name}
                  </span>
                </div>
                <div className="warp-row-coords">
                  <span>X {coord(warp.x)}</span>
                  <span>Y {coord(warp.y)}</span>
                  <span>Z {coord(warp.z)}</span>
                </div>
                <div className="warp-row-actions">
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={
                      target === "all" ? (
                        <UsersRound size={13} />
                      ) : (
                        <Crosshair size={13} />
                      )
                    }
                    loading={busy === `warp-${warp.slot}`}
                    disabled={!inGame || isActing}
                    onClick={() => void warpTo(warp)}
                    title={
                      inGame
                        ? `Warp ${target === "all" ? "everyone" : "there"}`
                        : isLive
                          ? "Wait for the character to enter the world"
                          : "Start this client to warp"
                    }
                  >
                    {target === "all" ? "Warp all" : "Warp"}
                  </Button>
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => openRename(warp)}
                    aria-label={`Rename warp ${warp.slot}`}
                    title="Edit alias"
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    type="button"
                    className="icon-btn warp-delete"
                    onClick={() => setDeleteTarget(warp)}
                    aria-label={`Delete warp ${warp.slot}`}
                    title="Delete warp"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="warp-help-card">
        <div className="warp-help-head">
          <Keyboard size={16} />
          <div>
            <strong>In-game commands</strong>
            <span>Everything the page does has a chat equivalent.</span>
          </div>
        </div>
        <div className="warp-command-grid">
          <code>/!warp mark [alias]</code>
          <span>Save your current zone and position; the next number is assigned.</span>
          <code>/!warp me 3</code>
          <span>Warp yourself to number 3 (or type its alias instead of the number).</span>
          <code>/!warp all 3</code>
          <span>Warp your main and sub-account characters that are online.</span>
          <code>/!warp list</code>
          <span>Print the numbered list; add a page number for more.</span>
          <code>/!warp delete 3</code>
          <span>Remove a saved place.</span>
          <code>/!warp rename 3 Camp</code>
          <span>Set or clear the alias from chat.</span>
        </div>
        <p className="warp-tab-hint">
          Type <code>/!wa</code> in chat and press <kbd>Tab</kbd> — the client completes the
          command when the prefix is unique. If more than one command matches, Tab leaves the line
          alone; add a letter and press Tab again (<code>/!w</code> does nothing, <code>/!wh</code>{' '}
          becomes <code>/!where</code>). That also works for <code> /!warp ma</code>,{' '}
          <code>/!warp li</code> and the rest of the command set.
        </p>
      </Card>

      {renameTarget && (
        <Modal
          title={`Rename warp ${slotLabel(renameTarget.slot)}`}
          subtitle={`${renameTarget.zone_name} · ${coord(renameTarget.x)}, ${coord(
            renameTarget.y,
          )}, ${coord(renameTarget.z)}`}
          onClose={() => setRenameTarget(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setRenameTarget(null)}>
                Cancel
              </Button>
              <Button
                icon={<Check size={15} />}
                loading={busy === "rename"}
                disabled={isActing}
                onClick={() => void saveRename()}
              >
                Save alias
              </Button>
            </>
          }
        >
          <label className="warp-rename-field">
            <span>Alias</span>
            <TextInput
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void saveRename();
              }}
              maxLength={40}
              autoFocus
              placeholder="e.g. Airship dock"
            />
            <small>Up to 40 characters. Leave it empty to remove the name.</small>
          </label>
        </Modal>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title={`Delete warp ${slotLabel(deleteTarget.slot)}?`}
          body={`${warpLabel(deleteTarget)} in ${deleteTarget.zone_name} will be removed. This cannot be undone.`}
          confirmLabel="Delete warp"
          danger
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => void confirmDelete()}
        />
      )}
    </div>
  );
}
