import { useMemo, useState, type DragEvent, type ReactNode } from "react";
import {
  Crosshair,
  FileText,
  Gamepad2,
  LayoutGrid,
  List,
  MapPin,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Rows3,
  Send,
  Shirt,
  SlidersHorizontal,
  Sparkles,
  Square,
  Swords,
  Terminal,
  Trash2,
  Users,
  Wand2,
} from "lucide-react";
import type {
  ConfigView,
  HudItem,
  HudPatch,
  HudState,
  HudTypeKey,
  HudTypeState,
  InstanceView,
  SessionView,
} from "../types";
import {
  formatDuration,
  formatNumber,
  pct,
  stateZone,
} from "../lib/format";
import { backend } from "../lib/api";
import { EquipViewer } from "./EquipViewer";
import { FollowCard } from "./FollowCard";
import { Badge, Button, Card, EmptyState, Modal, Select, TextInput, cn } from "./ui";

const QUICK_COMMANDS = [
  ["Zone 100", "!zone 100"],
  ["Port Jeuno", "!zone 246"],
  ["Heal", "!heal"],
  ["Merits 5", "!merits 5"],
  ["Where", "!where"],
  ["Help", "!help"],
];

const HUD_TYPE_META: Array<{
  key: HudTypeKey;
  label: string;
  icon: ReactNode;
  showKey: "show_abilities" | "show_spells" | "show_trusts" | "show_weapon_skills";
}> = [
  { key: "abilities", label: "Abilities", icon: <Swords size={13} />, showKey: "show_abilities" },
  { key: "spells", label: "Spells", icon: <Wand2 size={13} />, showKey: "show_spells" },
  { key: "trusts", label: "Trusts", icon: <Users size={13} />, showKey: "show_trusts" },
  { key: "weapon_skills", label: "Weapon skills", icon: <Crosshair size={13} />, showKey: "show_weapon_skills" },
];

const HUD_GROUP_OPTIONS: Record<HudTypeKey, Array<[string, string]>> = {
  abilities: [
    ["job", "Main / sub job"],
    ["type", "Ability type"],
    ["none", "No grouping"],
    ["custom", "Custom groups"],
  ],
  spells: [
    ["type", "Type: heal, buff, debuff, nuke"],
    ["skill", "Magic skill"],
    ["element", "Element"],
    ["none", "No grouping"],
    ["custom", "Custom groups"],
  ],
  trusts: [
    ["job", "Trust job"],
    ["none", "No grouping"],
    ["custom", "Custom groups"],
  ],
  weapon_skills: [
    ["skill", "Weapon type"],
    ["none", "No grouping"],
    ["custom", "Custom groups"],
  ],
};

const HUD_KEYS: HudTypeKey[] = ["abilities", "spells", "trusts", "weapon_skills"];

function defaultHudType(key: HudTypeKey): HudTypeState {
  return {
    layout: "grid",
    columns: key === "spells" ? 7 : 6,
    size: 48,
    labels: "always",
    font: 10,
    tabs: true,
    group: key === "spells" ? "type" : key === "abilities" || key === "trusts" ? "job" : "skill",
    groups: [],
    assign: {},
  };
}

function defaultHudTypes(): Record<HudTypeKey, HudTypeState> {
  return {
    abilities: defaultHudType("abilities"),
    spells: defaultHudType("spells"),
    trusts: defaultHudType("trusts"),
    weapon_skills: defaultHudType("weapon_skills"),
  };
}

function recordOf(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
}

function arrayOf(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function numberOr(value: unknown, fallback: number): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeItem(value: unknown): HudItem | null {
  const source = recordOf(value);
  const key = typeof source.key === "string" ? source.key : "";
  const name = typeof source.name === "string" ? source.name : "";
  if (!key || !name) return null;
  return { key, name, short: typeof source.short === "string" && source.short ? source.short : name.slice(0, 5) };
}

function normalizeHudType(key: HudTypeKey, raw: unknown): HudTypeState {
  const source = recordOf(raw);
  const spec = defaultHudType(key);
  if (source.layout === "grid" || source.layout === "list" || source.layout === "bar") {
    spec.layout = source.layout;
  }
  spec.columns = Math.min(12, Math.max(3, Math.round(numberOr(source.columns, spec.columns))));
  spec.size = Math.min(72, Math.max(32, Math.round(numberOr(source.size, spec.size))));
  spec.font = Math.min(12, Math.max(7, Math.round(numberOr(source.font, spec.font))));
  spec.tabs = source.tabs !== false;
  if (source.labels === "always" || source.labels === "hover" || source.labels === "off") {
    spec.labels = source.labels;
  }
  const options = HUD_GROUP_OPTIONS[key].map(([value]) => value);
  if (typeof source.group === "string" && options.includes(source.group)) spec.group = source.group;
  spec.groups = arrayOf(source.groups)
    .map((group) => (typeof group === "string" ? group.trim() : ""))
    .filter((group, index, all) => Boolean(group) && group.length <= 24 && all.indexOf(group) === index)
    .slice(0, 12);
  const allowed = new Set(spec.groups);
  const assignments = recordOf(source.assign);
  spec.assign = {};
  for (const [itemKey, group] of Object.entries(assignments)) {
    if (typeof group === "string" && allowed.has(group)) spec.assign[itemKey] = group;
  }
  return spec;
}

function normalizeHud(raw: unknown): HudState {
  const source = recordOf(raw);
  const typesSource = recordOf(source.types);
  const legacy = {
    layout: source.layout,
    columns: source.columns,
    size: source.size,
    labels: source.labels,
  };
  const types = defaultHudTypes();
  for (const key of HUD_KEYS) {
    const specific = typesSource[key];
    const fallback = key === "abilities" || key === "spells" ? legacy : undefined;
    types[key] = normalizeHudType(key, specific ?? fallback);
  }
  const rawItems = recordOf(source.items);
  const items = {
    abilities: arrayOf(rawItems.abilities).map(normalizeItem).filter((item): item is HudItem => item !== null),
    spells: arrayOf(rawItems.spells).map(normalizeItem).filter((item): item is HudItem => item !== null),
    trusts: arrayOf(rawItems.trusts).map(normalizeItem).filter((item): item is HudItem => item !== null),
    weapon_skills: arrayOf(rawItems.weapon_skills)
      .map(normalizeItem)
      .filter((item): item is HudItem => item !== null),
  };
  return {
    show_abilities: source.show_abilities === true,
    show_spells: source.show_spells === true,
    show_trusts: source.show_trusts === true,
    show_weapon_skills: source.show_weapon_skills === true,
    show_battle_info: source.show_battle_info === true,
    show_party_info: source.show_party_info === true,
    edit: source.edit === true,
    opacity: Math.min(1, Math.max(0.45, numberOr(source.opacity, 0.9))),
    menu_hide: source.menu_hide !== false,
    types,
    abilities: Math.max(0, Math.round(numberOr(source.abilities, items.abilities.length))),
    spells: Math.max(0, Math.round(numberOr(source.spells, items.spells.length))),
    trusts: Math.max(0, Math.round(numberOr(source.trusts, items.trusts.length))),
    weapon_skills: Math.max(0, Math.round(numberOr(source.weapon_skills, items.weapon_skills.length))),
    items,
    character: typeof source.character === "string" ? source.character : "default",
  };
}

function hudFor(instance: InstanceView | undefined, own: HudState | undefined): HudState {
  return normalizeHud(own ?? instance?.metrics?.hud);
}

function HudToggle({
  label,
  icon,
  on,
  busy,
  disabled,
  title,
  onClick,
}: {
  label: string;
  icon: ReactNode;
  on: boolean;
  busy?: boolean;
  disabled?: boolean;
  title?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn("hud-toggle", on && "on")}
      disabled={disabled || busy}
      title={title}
      onClick={onClick}
    >
      {icon}
      <span>{label}</span>
      <i className="hud-toggle-dot" />
    </button>
  );
}

function HudControls({
  hud,
  busy,
  onChange,
  onLayout,
}: {
  hud: HudState;
  busy: boolean;
  onChange: (patch: HudPatch) => void;
  onLayout: () => void;
}) {
  return (
    <div className="hud-inline">
      <HudToggle
        label="Show abilities"
        icon={<Swords size={12} />}
        on={hud.show_abilities}
        busy={busy}
        title={
          hud.abilities
            ? `${hud.abilities} abilities for this job pair`
            : "Show the current job abilities in game"
        }
        onClick={() => onChange({ show_abilities: !hud.show_abilities })}
      />
      <HudToggle
        label="Show spells"
        icon={<Wand2 size={12} />}
        on={hud.show_spells}
        busy={busy}
        title={
          hud.spells ? `${hud.spells} spells for this job pair` : "Show the current spell list in game"
        }
        onClick={() => onChange({ show_spells: !hud.show_spells })}
      />
      <HudToggle
        label="Show trusts"
        icon={<Users size={12} />}
        on={hud.show_trusts}
        busy={busy}
        title={
          hud.trusts ? `${hud.trusts} trusts available` : "Show the trust magic window in game"
        }
        onClick={() => onChange({ show_trusts: !hud.show_trusts })}
      />
      <HudToggle
        label="Show weapon skills"
        icon={<Crosshair size={12} />}
        on={hud.show_weapon_skills}
        busy={busy}
        title={
          hud.weapon_skills
            ? `${hud.weapon_skills} weapon skills available`
            : "Show the weapon skill window in game"
        }
        onClick={() => onChange({ show_weapon_skills: !hud.show_weapon_skills })}
      />
      <HudToggle
        label="Battle info"
        icon={<Crosshair size={12} />}
        on={hud.show_battle_info}
        busy={busy}
        title="Show the battle statistics hub (DPS, accuracy, TP to 1000, FPS)"
        onClick={() => onChange({ show_battle_info: !hud.show_battle_info })}
      />
      <HudToggle
        label="Party info"
        icon={<Users size={12} />}
        on={hud.show_party_info}
        busy={busy}
        title="Show the party and alliance hub"
        onClick={() => onChange({ show_party_info: !hud.show_party_info })}
      />
      <button
        type="button"
        className="hud-config-btn"
        title="HUD layout, grouping and screen position"
        onClick={onLayout}
      >
        <SlidersHorizontal size={13} />
        <span>Layout</span>
      </button>
    </div>
  );
}

/** A tiny, game-free preview of the selected in-game window. */
function HudPreview({
  typeKey,
  spec,
  items,
}: {
  typeKey: HudTypeKey;
  spec: HudTypeState;
  items: HudItem[];
}) {
  const meta = HUD_TYPE_META.find((entry) => entry.key === typeKey);
  const groupLabel =
    HUD_GROUP_OPTIONS[typeKey].find(([value]) => value === spec.group)?.[1] ?? spec.group;
  const tile = Math.max(18, Math.round(spec.size * 0.42));
  const labelHeight = spec.labels === "always" ? Math.max(7, Math.min(12, spec.font)) : 0;
  const sample =
    items.length > 0
      ? items.slice(0, 18)
      : Array.from({ length: 12 }, (_, index) => ({
          key: `empty-${index}`,
          name: "Empty",
          short: "EMPTY",
        }));
  return (
    <div className="hud-preview" aria-hidden="true">
      <div className="hud-preview-caption">
        <span>{meta?.label ?? "HUD"}</span>
        <em>
          {spec.layout === "grid" ? `${spec.columns} columns` : spec.layout} · {groupLabel}
          {spec.tabs && spec.group !== "none" ? " · folder tabs" : ""}
        </em>
      </div>
      {spec.layout === "bar" ? (
        <div className="hud-preview-bar">
          {sample.slice(0, 8).map((item) => (
            <i key={item.key} style={{ width: tile, height: tile + labelHeight }}>
              {spec.labels === "always" && <small>{item.short}</small>}
            </i>
          ))}
        </div>
      ) : spec.layout === "list" ? (
        <div className="hud-preview-list">
          {sample.slice(0, 6).map((item) => (
            <div key={item.key}>
              <i style={{ width: tile, height: Math.max(16, tile - 6) }} />
              <span>{item.name}</span>
            </div>
          ))}
        </div>
      ) : (
        <div
          className="hud-preview-grid"
          style={{ gridTemplateColumns: `repeat(${spec.columns}, ${tile}px)` }}
        >
          {sample.map((item) => (
            <i key={item.key} style={{ width: tile, height: tile + labelHeight }}>
              {spec.labels === "always" && <small>{item.short}</small>}
            </i>
          ))}
        </div>
      )}
    </div>
  );
}

function HudGroupEditor({
  typeKey,
  spec,
  items,
  busy,
  onChange,
}: {
  typeKey: HudTypeKey;
  spec: HudTypeState;
  items: HudItem[];
  busy: boolean;
  onChange: (patch: HudPatch) => void;
}) {
  const [newGroup, setNewGroup] = useState("");
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const groups = spec.groups;
  const grouped = new Map<string, HudItem[]>();
  for (const group of groups) grouped.set(group, []);
  const unsorted: HudItem[] = [];
  for (const item of items) {
    const group = spec.assign[item.key];
    if (group && grouped.has(group)) grouped.get(group)?.push(item);
    else unsorted.push(item);
  }

  function addGroup() {
    const name = newGroup.trim().slice(0, 24);
    if (!name || name === "Unsorted" || groups.includes(name)) return;
    onChange({ type: typeKey, custom_groups: [...groups, name] });
    setNewGroup("");
  }

  function removeGroup(name: string) {
    onChange({ type: typeKey, custom_groups: groups.filter((group) => group !== name) });
  }

  function assign(itemKey: string, group: string) {
    onChange({ type: typeKey, assign_key: itemKey, assign_group: group || null });
  }

  function dragStart(event: DragEvent, item: HudItem) {
    event.dataTransfer.setData("text/hud-item", item.key);
    event.dataTransfer.setData("text/plain", item.key);
    event.dataTransfer.effectAllowed = "move";
  }

  function drop(event: DragEvent, group: string) {
    event.preventDefault();
    setDropTarget(null);
    const key = event.dataTransfer.getData("text/hud-item") || event.dataTransfer.getData("text/plain");
    if (key) assign(key, group);
  }

  function chips(list: HudItem[]) {
    return (
      <div className="hud-group-chips">
        {list.map((item) => (
          <span
            key={item.key}
            className="hud-item-chip"
            draggable
            title={item.name}
            onDragStart={(event) => dragStart(event, item)}
          >
            {item.name}
          </span>
        ))}
        {list.length === 0 && <em>Drop {typeKey === "spells" ? "spells" : "items"} here</em>}
      </div>
    );
  }

  return (
    <div className="hud-group-editor">
      <div className="hud-group-head">
        <div>
          <strong>Custom groups</strong>
          <span>Drag any item into a group. Items left in Unsorted use the normal list.</span>
        </div>
        <div className="hud-group-add">
          <TextInput
            value={newGroup}
            placeholder="Group name"
            maxLength={24}
            disabled={busy}
            onChange={(event) => setNewGroup(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") addGroup();
            }}
          />
          <Button
            variant="secondary"
            size="sm"
            icon={<Plus size={13} />}
            disabled={
              busy ||
              !newGroup.trim() ||
              newGroup.trim() === "Unsorted" ||
              groups.includes(newGroup.trim()) ||
              groups.length >= 12
            }
            onClick={addGroup}
          >
            Add
          </Button>
        </div>
      </div>
      <div className="hud-group-grid">
        {groups.map((group) => (
          <div
            key={group}
            className={cn("hud-group-column", dropTarget === group && "drop")}
            onDragOver={(event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
              setDropTarget(group);
            }}
            onDragLeave={() => setDropTarget((current) => (current === group ? null : current))}
            onDrop={(event) => drop(event, group)}
          >
            <header>
              <span>{group}</span>
              <div>
                <em>{grouped.get(group)?.length ?? 0}</em>
                <button
                  type="button"
                  className="hud-group-remove"
                  title={`Remove ${group}`}
                  disabled={busy}
                  onClick={() => removeGroup(group)}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </header>
            {chips(grouped.get(group) ?? [])}
          </div>
        ))}
        <div
          className={cn("hud-group-column", "unsorted", dropTarget === "" && "drop")}
          onDragOver={(event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            setDropTarget("");
          }}
          onDragLeave={() => setDropTarget((current) => (current === "" ? null : current))}
          onDrop={(event) => drop(event, "")}
        >
          <header>
            <span>Unsorted</span>
            <div>
              <em>{unsorted.length}</em>
            </div>
          </header>
          {chips(unsorted)}
        </div>
      </div>
    </div>
  );
}

export function ControlPage({
  config,
  session,
  instances,
  onLaunch,
  onStop,
  onLaunchAll,
  onStopAll,
  onCommand,
  onChat,
  onHud,
  onGear,
  onRefresh,
  onAccounts,
  onWarps,
  busy,
}: {
  config: ConfigView;
  session: SessionView;
  instances: InstanceView[];
  onLaunch: (account: string, characterId: number | null) => Promise<void>;
  onStop: (port: number) => Promise<void>;
  onLaunchAll: () => Promise<void>;
  onStopAll: () => void | Promise<void>;
  onCommand: (port: number, line: string) => Promise<void>;
  onChat: (port: number, line: string) => Promise<void>;
  onHud: (port: number, patch: HudPatch) => Promise<HudState>;
  onGear: (port: number) => void;
  onRefresh: () => Promise<void>;
  onAccounts: () => void;
  onWarps: () => void;
  busy: string | null;
}) {
  const running = instances.filter((instance) => instance.alive);
  const [choices, setChoices] = useState<Record<string, number>>({});
  const [selectedPort, setSelectedPort] = useState<number | null>(null);
  const [mode, setMode] = useState<"command" | "chat">("command");
  const [line, setLine] = useState("!zone 100");
  const [sending, setSending] = useState(false);
  const [logPort, setLogPort] = useState<number | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logLoading, setLogLoading] = useState(false);
  const [hudOverrides, setHudOverrides] = useState<Record<number, HudState>>({});
  const [hudBusy, setHudBusy] = useState<number | null>(null);
  const [hudAccount, setHudAccount] = useState<string | null>(null);
  const [hudType, setHudType] = useState<HudTypeKey>("spells");

  const selected = useMemo(
    () => running.find((instance) => instance.port === selectedPort) ?? running[0] ?? null,
    [running, selectedPort],
  );

  const chosenCharacter = (username: string, accountId: number | null | undefined) => {
    const entry = config.accounts.find(
      (account) => account.username.toLowerCase() === username.toLowerCase(),
    );
    if (choices[username] !== undefined) return choices[username];
    if (accountId && entry?.characters.some((character) => character.id === accountId)) {
      return accountId;
    }
    return entry?.characterId ?? entry?.characters[0]?.id ?? null;
  };

  async function launch(username: string, accountId: number | null | undefined) {
    const characterId = chosenCharacter(username, accountId);
    if (!characterId) return;
    await onLaunch(username, characterId);
  }

  async function openLog(port: number) {
    setLogPort(port);
    setLogLoading(true);
    try {
      setLogLines(await backend.gameLog(port, 180));
    } catch (error) {
      setLogLines([error instanceof Error ? error.message : String(error)]);
    } finally {
      setLogLoading(false);
    }
  }

  async function send() {
    if (!selected || !line.trim() || sending) return;
    setSending(true);
    try {
      if (mode === "command") {
        await onCommand(selected.port, line.trim());
      } else {
        await onChat(selected.port, line.trim());
      }
      setLine("");
    } finally {
      setSending(false);
    }
  }

  function openHud(account: string) {
    setHudType("spells");
    setHudAccount(account);
  }

  /** Apply a patch to the local copy so a switch answers before the addon replies. */
  function mergeHud(current: HudState, patch: HudPatch): HudState {
    const next: HudState = { ...current, types: { ...current.types } };
    if (patch.show_abilities !== undefined) next.show_abilities = patch.show_abilities;
    if (patch.show_spells !== undefined) next.show_spells = patch.show_spells;
    if (patch.show_trusts !== undefined) next.show_trusts = patch.show_trusts;
    if (patch.show_weapon_skills !== undefined) next.show_weapon_skills = patch.show_weapon_skills;
    if (patch.edit !== undefined) next.edit = patch.edit;
    if (patch.opacity !== undefined) next.opacity = patch.opacity;
    if (patch.menu_hide !== undefined) next.menu_hide = patch.menu_hide;
    if (patch.type && next.types[patch.type]) {
      const spec: HudTypeState = { ...next.types[patch.type], assign: { ...next.types[patch.type].assign } };
      if (patch.layout !== undefined) spec.layout = patch.layout;
      if (patch.columns !== undefined) spec.columns = patch.columns;
      if (patch.size !== undefined) spec.size = patch.size;
      if (patch.labels !== undefined) spec.labels = patch.labels;
      if (patch.font !== undefined) spec.font = patch.font;
      if (patch.tabs !== undefined) spec.tabs = patch.tabs;
      if (patch.group !== undefined) spec.group = patch.group;
      if (patch.custom_groups !== undefined) spec.groups = patch.custom_groups;
      if (patch.assign_key !== undefined) {
        if (patch.assign_group) spec.assign[patch.assign_key] = patch.assign_group;
        else delete spec.assign[patch.assign_key];
      }
      next.types[patch.type] = spec;
    }
    return next;
  }

  /** Optimistically paint a HUD patch, then replace it with the addon's saved state. */
  async function applyHud(instance: InstanceView, patch: HudPatch) {
    const current = hudFor(instance, hudOverrides[instance.port]);
    const optimistic = mergeHud(current, patch);
    setHudOverrides((previous) => ({ ...previous, [instance.port]: optimistic }));
    setHudBusy(instance.port);
    try {
      const next = normalizeHud(await onHud(instance.port, patch));
      setHudOverrides((previous) => ({ ...previous, [instance.port]: next }));
      // Let the next metrics poll take over once the addon's own state has had time to settle.
      window.setTimeout(() => {
        setHudOverrides((previous) => {
          if (previous[instance.port] !== next) return previous;
          const copy = { ...previous };
          delete copy[instance.port];
          return copy;
        });
      }, 4000);
    } catch {
      setHudOverrides((previous) => {
        const copy = { ...previous };
        delete copy[instance.port];
        return copy;
      });
    } finally {
      setHudBusy((busyPort) => (busyPort === instance.port ? null : busyPort));
    }
  }

  const hudInstance = hudAccount
    ? running.find((instance) => instance.account.toLowerCase() === hudAccount.toLowerCase()) ?? null
    : null;
  const hudOpen = hudInstance ? hudFor(hudInstance, hudOverrides[hudInstance.port]) : null;
  const hudMeta = HUD_TYPE_META.find((entry) => entry.key === hudType) ?? HUD_TYPE_META[0];
  const hudSpec = hudOpen?.types[hudType] ?? defaultHudType(hudType);
  const hudItems = hudOpen?.items[hudType] ?? [];
  const hudShown = hudOpen ? hudOpen[hudMeta.showKey] : false;

  return (
    <div className="page">
      <div className="section-header">
        <div>
          <div className="eyebrow">Party management</div>
          <h1 className="page-title">Control room</h1>
          <p className="page-subtitle">
            One client per account. Launch them here, then send commands or watch EXP/hr and DPS
            without leaving the launcher.
          </p>
        </div>
        <div className="section-actions">
          <Button variant="secondary" icon={<MapPin size={15} />} onClick={onWarps}>
            Warps
          </Button>
          <Button variant="ghost" icon={<RefreshCw size={15} />} onClick={() => void onRefresh()}>
            Refresh
          </Button>
          <Button
            variant="secondary"
            icon={<Square size={14} fill="currentColor" />}
            onClick={() => void onStopAll()}
            disabled={running.length === 0}
          >
            Stop all
          </Button>
          <Button
            icon={<Play size={15} fill="currentColor" />}
            loading={busy === "launch-all"}
            onClick={() => void onLaunchAll()}
            disabled={config.accounts.length === 0}
          >
            Launch all
          </Button>
        </div>
      </div>

      <Card className="party-manager">
        <div className="card-topline">
          <span className="eyebrow">Party</span>
          <button className="link-btn" onClick={onAccounts}>
            <Users size={13} /> {config.accounts.length} account
            {config.accounts.length === 1 ? "" : "s"}
          </button>
        </div>
        {config.accounts.length === 0 ? (
          <EmptyState
            icon={<Users size={22} />}
            title="No accounts yet"
            body="Add an account from the Accounts page to start a party."
          />
        ) : (
          <div className="party-manager-list">
            {config.accounts.map((account) => {
              const instance = running.find(
                (item) => item.account.toLowerCase() === account.username.toLowerCase(),
              );
              const characters = account.characters;
              const choice = chosenCharacter(account.username, account.characterId);
              const hud = hudFor(instance, instance ? hudOverrides[instance.port] : undefined);
              return (
                <div className="party-manager-row" key={account.username}>
                  <div className="party-manager-name">
                    <span className="avatar small">{account.username.slice(0, 1).toUpperCase()}</span>
                    <div>
                      <strong>@{account.username}</strong>
                      <span>
                        {instance
                          ? `online · control :${instance.port}`
                          : account.signedIn
                            ? "offline"
                            : "sign in again"}
                      </span>
                    </div>
                  </div>
                  {characters.length > 0 ? (
                    <Select
                      className="character-select"
                      value={choice ?? ""}
                      onChange={(event) =>
                        setChoices((current) => ({
                          ...current,
                          [account.username]: Number(event.target.value),
                        }))
                      }
                    >
                      {characters.map((character) => (
                        <option key={character.id} value={character.id}>
                          {character.name}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <span className="muted">No characters</span>
                  )}
                  {instance && (
                    <HudControls
                      hud={hud}
                      busy={hudBusy === instance.port}
                      onChange={(patch) => void applyHud(instance, patch)}
                      onLayout={() => openHud(account.username)}
                    />
                  )}
                  {instance ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Square size={13} fill="currentColor" />}
                      loading={busy === `stop-${instance.port}`}
                      onClick={() => void onStop(instance.port)}
                    >
                      Stop
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Play size={14} fill="currentColor" />}
                      loading={busy === `launch-${account.username}`}
                      disabled={!choice || !account.signedIn}
                      onClick={() => void launch(account.username, account.characterId)}
                    >
                      Launch
                    </Button>
                  )}
                </div>
              );
            })}
            {running
              .filter(
                (instance) =>
                  !config.accounts.some(
                    (account) =>
                      account.username.toLowerCase() === instance.account.toLowerCase(),
                  ),
              )
              .map((instance) => {
                const hud = hudFor(instance, hudOverrides[instance.port]);
                return (
                  <div className="party-manager-row" key={`hud-extra-${instance.account}`}>
                    <div className="party-manager-name">
                      <span className="avatar small">
                        {instance.account.slice(0, 1).toUpperCase()}
                      </span>
                      <div>
                        <strong>@{instance.account}</strong>
                        <span>
                          box · {instance.name} · control :{instance.port}
                        </span>
                      </div>
                    </div>
                    <span className="muted hud-extra-character">{instance.name}</span>
                    <HudControls
                      hud={hud}
                      busy={hudBusy === instance.port}
                      onChange={(patch) => void applyHud(instance, patch)}
                      onLayout={() => openHud(instance.account)}
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Square size={13} fill="currentColor" />}
                      loading={busy === `stop-${instance.port}`}
                      onClick={() => void onStop(instance.port)}
                    >
                      Stop
                    </Button>
                  </div>
                );
              })}
          </div>
        )}
      </Card>

      <FollowCard session={session} instances={instances} />

      <Card className="live-party">
        <div className="card-topline">
          <span className="eyebrow">Live party</span>
          <div className="inline-actions">
            <button className="link-btn" onClick={onWarps}>
              <MapPin size={13} /> Warps
            </button>
            <button className="link-btn" onClick={() => selected && onGear(selected.port)}>
              <Shirt size={13} /> Gear & GearSwap
            </button>
            <button
              className="link-btn"
              onClick={() => selected && void openLog(selected.port)}
              disabled={!selected}
            >
              <FileText size={13} /> Log
            </button>
            <button className="link-btn" onClick={() => void onRefresh()}>
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
        </div>
        {running.length === 0 ? (
          <EmptyState
            icon={<Gamepad2 size={22} />}
            title="No clients running"
            body="Launch a character above and its live state will appear here."
          />
        ) : (
          <div className="live-party-body">
            <div className="live-table-wrap">
              <table className="live-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Character</th>
                  <th>Zone</th>
                  <th>HP</th>
                  <th>MP</th>
                  <th>EXP/hr</th>
                  <th>DPS</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {running.map((instance) => {
                  const state = instance.state;
                  const player = state?.player;
                  const kpi = instance.metrics?.kpi;
                  const hp = pct(player?.hp, player?.hpmax);
                  const mp = pct(player?.mp, player?.mpmax);
                  return (
                    <tr
                      key={instance.port}
                      className={cn(selected?.port === instance.port && "selected")}
                      onClick={() => setSelectedPort(instance.port)}
                    >
                      <td>
                        <span className="account-cell">@{instance.account}</span>
                      </td>
                      <td>
                        <strong>{instance.name}</strong>
                      </td>
                      <td>{stateZone(state)}</td>
                      <td>
                        <div className="bar-cell">
                          <span>
                            {player?.hp ?? "—"}/{player?.hpmax ?? "—"}
                          </span>
                          <div className="mini-bar">
                            <div className="mini-bar-fill hp" style={{ width: `${hp}%` }} />
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="bar-cell">
                          <span>
                            {player?.mp ?? "—"}/{player?.mpmax ?? "—"}
                          </span>
                          <div className="mini-bar">
                            <div className="mini-bar-fill mp" style={{ width: `${mp}%` }} />
                          </div>
                        </div>
                      </td>
                      <td>{formatNumber(kpi?.exp_per_hour)}</td>
                      <td>{formatNumber(kpi?.dps, 1)}</td>
                      <td>
                        {player ? (
                          <Badge tone="success" dot>
                            {formatDuration(instance.uptimeSeconds)}
                          </Badge>
                        ) : instance.error ? (
                          <Badge tone="warning" dot>
                            waiting
                          </Badge>
                        ) : (
                          <Badge tone="neutral" dot>
                            starting
                          </Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
            {selected && (
              <aside className="live-equipment">
                <div className="card-topline">
                  <span className="eyebrow">Equipment</span>
                  <button className="link-btn" onClick={() => onGear(selected.port)}>
                    <Shirt size={12} /> Open
                  </button>
                </div>
                <EquipViewer
                  port={selected.port}
                  slots={selected.metrics?.gear?.slots}
                  encumbrance={selected.metrics?.gear?.encumbrance ?? 0}
                  compact
                  showSettings={false}
                />
                <div className="live-equipment-meta">
                  <strong>{selected.name}</strong>
                  <span>{stateZone(selected.state)}</span>
                  <span className="muted">
                    {selected.metrics?.gear?.slots
                      ? "Live from the client"
                      : "Waiting for the first gear read"}
                  </span>
                </div>
              </aside>
            )}
          </div>
        )}
        {running.length > 0 && (
          <div className="live-summary">
            {running.map((instance) => {
              const kpi = instance.metrics?.kpi;
              return (
                <div key={instance.port} className="summary-item">
                  <span>{instance.name}</span>
                  <strong>
                    {formatNumber(kpi?.exp_per_hour)} EXP/hr · {formatNumber(kpi?.dps, 1)} DPS
                  </strong>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card className="console-card">
        <div className="card-topline">
          <span className="eyebrow">Command console</span>
          <div className="segmented small">
            <button className={cn(mode === "command" && "active")} onClick={() => setMode("command")}>
              <Terminal size={13} /> Command
            </button>
            <button className={cn(mode === "chat" && "active")} onClick={() => setMode("chat")}>
              <Send size={13} /> Chat
            </button>
          </div>
        </div>
        <div className="console-row">
          <Select
            className="target-select"
            value={selected?.port ?? ""}
            onChange={(event) => setSelectedPort(Number(event.target.value))}
            disabled={running.length === 0}
          >
            {running.length === 0 && <option value="">(no client)</option>}
            {running.map((instance) => (
              <option key={instance.port} value={instance.port}>
                {instance.account} — {instance.name} (:{instance.port})
              </option>
            ))}
          </Select>
          <TextInput
            className="console-input"
            value={line}
            onChange={(event) => setLine(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void send();
            }}
            placeholder={mode === "command" ? "!zone 100" : "Say something…"}
            disabled={!selected}
          />
          <Button
            icon={<Send size={15} />}
            loading={sending}
            disabled={!selected || !line.trim()}
            onClick={() => void send()}
          >
            Send
          </Button>
          <Button
            variant="ghost"
            icon={<Shirt size={15} />}
            disabled={!selected}
            onClick={() => selected && onGear(selected.port)}
          >
            Gear
          </Button>
        </div>
        <div className="quick-row">
          {QUICK_COMMANDS.map(([label, command]) => (
            <button
              key={command}
              className="quick-chip"
              onClick={() => {
                setMode("command");
                setLine(command);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="console-hint">
          Commands start with <code>!</code> or <code>/</code>. Chat sends a line through the game;
          the client's control addon executes commands as if typed.
        </p>
      </Card>

      {hudInstance && hudOpen && (
        <Modal
          title={`Combat HUD — @${hudInstance.account}`}
          subtitle={`${hudInstance.name} · ${hudOpen.abilities} abilities · ${hudOpen.spells} spells · ${hudOpen.trusts} trusts · ${hudOpen.weapon_skills} weapon skills · saved per character`}
          wide
          onClose={() => setHudAccount(null)}
          footer={
            <>
              <Button
                variant="ghost"
                icon={<RotateCcw size={14} />}
                onClick={() => void applyHud(hudInstance, { reset_positions: true })}
              >
                Reset positions
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  if (hudOpen.edit) void applyHud(hudInstance, { edit: false });
                  setHudAccount(null);
                }}
              >
                Done
              </Button>
            </>
          }
        >
          <div className="hud-type-tabs">
            {HUD_TYPE_META.map((entry) => (
              <button
                type="button"
                key={entry.key}
                className={cn("hud-type-tab", hudType === entry.key && "on")}
                onClick={() => setHudType(entry.key)}
              >
                {entry.icon}
                <span>{entry.label}</span>
                <em>{hudOpen[entry.key]}</em>
                <i className={cn("hud-type-dot", hudOpen[entry.showKey] && "on")} />
              </button>
            ))}
          </div>

          <div className="hud-editor">
            <div className="hud-editor-visual">
              <HudPreview typeKey={hudType} spec={hudSpec} items={hudItems} />
              <p>
                Each type has its own layout, grouping, tile size and label size.{" "}
                <strong>Abilities</strong> clicks run <code>/ja</code>; spells and trusts run{" "}
                <code>/ma</code>; weapon skills run <code>/ws</code>. A fresh click darkens the
                tile and the clock hand unveils it as the recast finishes.
              </p>
              <HudToggle
                label={`Show ${hudMeta.label.toLowerCase()}`}
                icon={hudMeta.icon}
                on={hudShown}
                busy={hudBusy === hudInstance.port}
                onClick={() =>
                  void applyHud(hudInstance, {
                    [hudMeta.showKey]: !hudShown,
                  } as HudPatch)
                }
              />
            </div>
            <div className="hud-editor-controls">
              <div className="hud-field">
                <span className="eyebrow">{hudMeta.label} layout</span>
                <div className="hud-layout-choice">
                  {(
                    [
                      ["grid", "Grid", <LayoutGrid size={14} />],
                      ["list", "List", <List size={14} />],
                      ["bar", "Bar", <Rows3 size={14} />],
                    ] as const
                  ).map(([value, label, icon]) => (
                    <button
                      type="button"
                      key={value}
                      className={cn("hud-layout-btn", hudSpec.layout === value && "on")}
                      onClick={() => void applyHud(hudInstance, { type: hudType, layout: value })}
                    >
                      {icon}
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="hud-field-row">
                <label className="hud-field">
                  <span>Group by</span>
                  <Select
                    value={hudSpec.group}
                    onChange={(event) =>
                      void applyHud(hudInstance, { type: hudType, group: event.target.value })
                    }
                  >
                    {HUD_GROUP_OPTIONS[hudType].map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </label>
                {hudSpec.layout === "grid" && (
                  <label className="hud-field">
                    <span>
                      Columns <b>{hudSpec.columns}</b>
                    </span>
                    <input
                      className="hud-range"
                      type="range"
                      min={3}
                      max={12}
                      value={hudSpec.columns}
                      onChange={(event) =>
                        void applyHud(hudInstance, {
                          type: hudType,
                          columns: Number(event.target.value),
                        })
                      }
                    />
                  </label>
                )}
              </div>

              {hudSpec.group !== "none" && (
                <label className="hud-check hud-check-inline">
                  <input
                    type="checkbox"
                    checked={hudSpec.tabs}
                    onChange={(event) =>
                      void applyHud(hudInstance, { type: hudType, tabs: event.target.checked })
                    }
                  />
                  <span>
                    Folder tabs
                    <em>One group per page; click a tab to flip instead of scrolling.</em>
                  </span>
                </label>
              )}

              <div className="hud-field-row">
                <label className="hud-field">
                  <span>
                    Tile size <b>{hudSpec.size}px</b>
                  </span>
                  <input
                    className="hud-range"
                    type="range"
                    min={32}
                    max={72}
                    step={2}
                    value={hudSpec.size}
                    onChange={(event) =>
                      void applyHud(hudInstance, {
                        type: hudType,
                        size: Number(event.target.value),
                      })
                    }
                  />
                </label>
                <label className="hud-field">
                  <span>
                    Label size <b>{hudSpec.font}px</b>
                  </span>
                  <input
                    className="hud-range"
                    type="range"
                    min={7}
                    max={12}
                    step={1}
                    value={hudSpec.font}
                    onChange={(event) =>
                      void applyHud(hudInstance, {
                        type: hudType,
                        font: Number(event.target.value),
                      })
                    }
                  />
                </label>
              </div>

              <div className="hud-field-row">
                <label className="hud-field">
                  <span>Labels</span>
                  <Select
                    value={hudSpec.labels}
                    onChange={(event) =>
                      void applyHud(hudInstance, {
                        type: hudType,
                        labels: event.target.value as HudTypeState["labels"],
                      })
                    }
                  >
                    <option value="always">Always, under the icon</option>
                    <option value="hover">On hover</option>
                    <option value="off">Icons only</option>
                  </Select>
                </label>
                <label className="hud-field">
                  <span>
                    Background <b>{Math.round(hudOpen.opacity * 100)}%</b>
                  </span>
                  <input
                    className="hud-range"
                    type="range"
                    min={45}
                    max={100}
                    value={Math.round(hudOpen.opacity * 100)}
                    onChange={(event) =>
                      void applyHud(hudInstance, { opacity: Number(event.target.value) / 100 })
                    }
                  />
                </label>
              </div>

              <label className="hud-check">
                <input
                  type="checkbox"
                  checked={hudOpen.menu_hide}
                  onChange={(event) =>
                    void applyHud(hudInstance, { menu_hide: event.target.checked })
                  }
                />
                <span>
                  Hide the HUD on the game-menu side
                  <em>The client's Commands/Status menu is on the right and is drawn above the overlay.</em>
                </span>
              </label>

              <div className="hud-edit-box">
                <div>
                  <strong>Place on screen</strong>
                  <span>
                    Turn this on, then drag each window by its title bar in game. Each type keeps
                    its own position, and it saves as soon as you let go.
                  </span>
                </div>
                <button
                  type="button"
                  className={cn("hud-toggle", hudOpen.edit && "on")}
                  onClick={() => void applyHud(hudInstance, { edit: !hudOpen.edit })}
                >
                  <Sparkles size={12} />
                  <span>{hudOpen.edit ? "Editing" : "Edit"}</span>
                  <i className="hud-toggle-dot" />
                </button>
              </div>
              {hudOpen.edit && (
                <p className="hud-edit-hint">
                  Drag the <strong>{hudMeta.label} - drag to move</strong> title bar. Turn Edit off
                  to lock every window.
                </p>
              )}
            </div>
          </div>

          {hudSpec.group === "custom" && (
            <HudGroupEditor
              typeKey={hudType}
              spec={hudSpec}
              items={hudItems}
              busy={hudBusy === hudInstance.port}
              onChange={(patch) => void applyHud(hudInstance, patch)}
            />
          )}
        </Modal>
      )}

      {logPort !== null && (
        <Modal
          title={`Game log — ${running.find((item) => item.port === logPort)?.name ?? "client"}`}
          subtitle="The last lines host64 wrote to its account log."
          wide
          onClose={() => setLogPort(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setLogPort(null)}>
                Close
              </Button>
              <Button
                variant="secondary"
                icon={<RefreshCw size={14} />}
                loading={logLoading}
                onClick={() => void openLog(logPort)}
              >
                Refresh
              </Button>
            </>
          }
        >
          <pre className="game-log">{logLines.length ? logLines.join("\n") : "No log lines yet."}</pre>
        </Modal>
      )}
    </div>
  );
}
