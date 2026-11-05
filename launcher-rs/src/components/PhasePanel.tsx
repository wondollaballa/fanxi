import { useMemo, useState } from "react";
import { Lock, LockOpen, Pencil, Plus, Shield, Sparkles, Trash2, Wind, Zap } from "lucide-react";
import type { GearItem, JobAbility, JobSpell, PhaseStatus } from "../types";
import {
  FOCUS_MODES,
  SPELL_GROUPS,
  SPELL_GROUP_JOBS,
  groupWsNames,
  phaseStateLabel,
  slotLabelOf,
  type PhaseConfig,
  type SpellGroupKey,
} from "../lib/phase";
import { SLOT_KEYS } from "../lib/format";
import { SetEquipmentPreview } from "./SetEquipmentPreview";
import { Badge, Button, Card, Field, Select, cn } from "./ui";

type PhasePanelProps = {
  config: PhaseConfig;
  sets: string[];
  phase: PhaseStatus | null;
  status: PhaseStatus | null;
  phaseOn: boolean;
  busy: string | null;
  /** weaponskills the loaded library has a set for */
  wsNames: string[];
  spells: JobSpell[];
  abilities: JobAbility[];
  /** The live main/sub job ids; drives which spell groups the page shows. */
  job?: { main: number; sub: number };
  /** The live client, for the gear preview's item icons. */
  port?: number | null;
  /** The loaded library's slot -> item names, keyed by set path ("sets.midcast..."). */
  setItems?: Record<string, Record<string, string>>;
  /** The loaded library's parsed items (augments included), keyed by set path. */
  setDetails?: Record<string, Record<string, GearItem>>;
  lockedSlots: Set<string>;
  onConfig: (patch: Partial<PhaseConfig>) => void;
  onTogglePhase: () => void;
  onKiting: (on: boolean) => void;
  onResting: (on: boolean) => void;
  onFocus: (mode: string) => void;
  onLockSlot: (slot: string) => void;
  onNewWeaponSet: () => void;
  onEditWeaponSet: (path: string) => void;
  onWearWeaponSet: (path: string) => void;
  onLockWeaponSet: (path: string) => void;
};

const WEAPON_SLOTS = ["main", "sub", "range", "ammo"] as const;

/** Set paths whose prefix matches first, then the rest; the current value is always present. */
function optionsFor(sets: string[], prefixes: string[], current: string): string[] {
  const rank = (path: string) => {
    const index = prefixes.findIndex((prefix) => path.startsWith(prefix));
    return index < 0 ? prefixes.length : index;
  };
  const out = [...new Set([...(current ? [current] : []), ...sets])];
  out.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  return out;
}

function SetSelect({
  label,
  value,
  sets,
  prefixes = [],
  empty = "— none —",
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  sets: string[];
  prefixes?: string[];
  empty?: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const options = useMemo(() => optionsFor(sets, prefixes, value), [sets, prefixes, value]);
  return (
    <Field label={label} className="phase-return">
      <Select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
        <option value="">{empty}</option>
        {options.map((path) => (
          <option key={path} value={path}>
            {path}
          </option>
        ))}
      </Select>
    </Field>
  );
}

function InlineSetSelect({
  value,
  sets,
  prefixes = [],
  empty,
  onChange,
}: {
  value: string;
  sets: string[];
  prefixes?: string[];
  empty: string;
  onChange: (value: string) => void;
}) {
  const options = useMemo(() => optionsFor(sets, prefixes, value), [sets, prefixes, value]);
  return (
    <Select
      className="phase-inline-select"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">{empty}</option>
      {options.map((path) => (
        <option key={path} value={path}>
          {path}
        </option>
      ))}
    </Select>
  );
}

function Group({
  title,
  badge,
  hint,
  wide = false,
  children,
}: {
  title: string;
  badge?: React.ReactNode;
  hint?: string;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card className={cn("phase-group", wide && "phase-group-wide")}>
      <div className="card-topline">
        <span className="eyebrow">{title}</span>
        {badge}
      </div>
      {children}
      {hint && <p className="gear-hint">{hint}</p>}
    </Card>
  );
}

export function PhasePanel({
  config,
  sets,
  phase,
  status,
  phaseOn,
  busy,
  wsNames,
  spells,
  abilities,
  job,
  port,
  setItems,
  setDetails,
  lockedSlots,
  onConfig,
  onTogglePhase,
  onKiting,
  onResting,
  onFocus,
  onLockSlot,
  onNewWeaponSet,
  onEditWeaponSet,
  onWearWeaponSet,
  onLockWeaponSet,
}: PhasePanelProps) {
  const [addSpell, setAddSpell] = useState("");
  const [addSong, setAddSong] = useState("");
  /** The enfeebling kind whose gear preview is open, by group and kind key. */
  const [kindView, setKindView] = useState<string>("enfeebles:skill");
  const itemsFor = (path?: string) =>
    (path && (setItems?.[`sets.${path}`] ?? setItems?.[path])) || {};
  const augmentsFor = (path?: string) => {
    const entry = path && (setDetails?.[`sets.${path}`] ?? setDetails?.[path]);
    if (!entry) return undefined;
    const out: Record<string, string[]> = {};
    for (const [slot, item] of Object.entries(entry)) {
      if (item?.augments?.length) out[slot] = item.augments;
    }
    return Object.keys(out).length ? out : undefined;
  };
  const weaponSets = useMemo(
    () => sets.filter((path) => path.startsWith("weaponset.")),
    [sets],
  );
  const spellById = useMemo(() => {
    const map = new Map<number, JobSpell>();
    for (const spell of spells) map.set(Number(spell.id), spell);
    return map;
  }, [spells]);
  const spellChoices = useMemo(
    () => spells.filter((spell) => !(String(spell.id) in config.spellOverrides)),
    [spells, config.spellOverrides],
  );
  const jobGroups = useMemo(() => {
    const ids = [job?.main ?? 0, job?.sub ?? 0];
    const out = new Set<SpellGroupKey>();
    for (const [key, jobs] of Object.entries(SPELL_GROUP_JOBS) as [
      SpellGroupKey,
      number[],
    ][]) {
      if (jobs.some((id) => ids.includes(id))) out.add(key);
    }
    return out;
  }, [job?.main, job?.sub]);
  const spellGroups = useMemo(
    () =>
      SPELL_GROUPS.filter((group) => !job || jobGroups.has(group.key))
        .map((group) => ({
          ...group,
          spells: spells.filter((spell) => spell.categories?.includes(group.key)),
        }))
        // With no spell list we still show the job's groups so their sets can be picked;
        // once the list loads, an empty group (a sub job that cannot cast it, Helix on a
        // Red Mage, songs off a Bard) is not a field this job uses.
        .filter((group) => spells.length === 0 || group.spells.length > 0),
    [spells, job, jobGroups],
  );
  const overrides = Object.entries(config.spellOverrides).filter(([id]) =>
    spellById.has(Number(id)),
  );
  const songSpells = useMemo(
    () => spells.filter((spell) => spell.categories?.includes("songs")),
    [spells],
  );
  // A non-Bard has no song card at all; a Bard (or a Bard sub job) keeps it.
  const songOverrideEntries = job && !jobGroups.has("songs")
    ? []
    : Object.entries(config.songOverrides);
  const songChoices = songSpells.filter(
    (spell) => !(String(spell.id) in config.songOverrides),
  );
  const categoryOverrideCount = spellGroups.reduce((count, group) => {
    // Enfeebles arms the same category from a mode and its kind row; count each category once.
    const categories = new Set<string>();
    for (const mode of group.modes) if (mode.category) categories.add(mode.category);
    for (const kind of group.kinds ?? []) categories.add(kind.category);
    if (group.autoMode?.category) categories.add(group.autoMode.category);
    for (const mode of group.autoModes ?? []) {
      if (mode.category) categories.add(mode.category);
    }
    let configured = 0;
    for (const category of categories) {
      if (config.spellCategoryOverrides[category]) configured += 1;
    }
    return count + configured;
  }, 0);
  const jaOverrideCount = Object.keys(config.jaOverrides).length;
  const wsGroups = useMemo(() => groupWsNames(wsNames), [wsNames]);
  const wsConditionCount = wsGroups.reduce(
    (count, group) =>
      count + group.variants.filter((variant) => variant.conditions.length > 0).length,
    0,
  );
  const now = status?.state ? `${phaseStateLabel(status.state)}` : "—";
  const activeSet = status?.set ?? null;

  return (
    <div className="phase-groups">
      <Card className="phase-group phase-stage">
        <div className="card-topline">
          <span className="eyebrow">Precast · Midcast · Idle</span>
          <Badge tone={phaseOn ? "accent" : "neutral"} dot={phaseOn}>
            {phaseOn ? "auto-swap on · all clients" : "off · all clients"}
          </Badge>
        </div>
        <div className="phase-row">
          <Button
            size="sm"
            variant={phaseOn ? "secondary" : "primary"}
            icon={<Zap size={14} />}
            loading={busy === "phase"}
            onClick={onTogglePhase}
          >
            {phaseOn ? "Turn GearSwap off" : "Turn GearSwap on"}
          </Button>
          {phase?.enabled ? (
            <>
              <Badge tone="accent">
                now: {now}
                {activeSet ? ` · ${activeSet}` : ""}
              </Badge>
              <Badge tone="neutral">
                {phase.ws ?? 0} WS · {phase.ja ?? 0} JA · {phase.magic ?? 0} spells ·{" "}
                {phase.sets ?? 0} sets
              </Badge>
            </>
          ) : (
            <span className="muted">The host is not holding action packets.</span>
          )}
        </div>
        <p className="gear-hint">
          This is the launcher-wide GearSwap switch: turning it off clears the plan in every
          running client immediately, so no action packet is held and no automatic set is worn.
          Manual gear changes on this page still work. When it is on, the host holds the action
          packet, wears the precast set, sends the action, then wears the midcast set behind it,
          and returns to the state set when the result arrives. The groups below replace the old
          single plan: each one is a state or an override, and the Active gear card above names
          the state and the set currently worn.
        </p>
      </Card>

      <Group
        title="Engaged"
        badge={<Badge tone={status?.engaged ? "accent" : "neutral"}>TP · WS</Badge>}
        hint="Build TP in the first set; the WS gear comes from the Weaponskills card below (the card's set, else the library's sets.WS.<name>, else this default)."
      >
        <div className="phase-row">
          <SetSelect
            label="TP set"
            value={config.engaged}
            sets={sets}
            prefixes={["engaged."]}
            empty="— use engaged.tp —"
            onChange={(engaged) => onConfig({ engaged })}
          />
          <SetSelect
            label="Default WS set"
            value={config.defaultWs}
            sets={sets}
            prefixes={["WS.", "precast.WS"]}
            empty="— library precast.WS —"
            onChange={(defaultWs) => onConfig({ defaultWs })}
          />
        </div>
      </Group>

      <Group
        title="Kiting"
        badge={
          <Badge tone={status?.kiting ? "danger" : "neutral"} dot={status?.kiting}>
            {status?.kiting ? "forced on" : "off"}
          </Badge>
        }
        hint="A forced state: the kiting set stays on until you turn it off, even while engaged or moving."
      >
        <div className="phase-row">
          <SetSelect
            label="Kiting set"
            value={config.kite}
            sets={sets}
            prefixes={["idle.", "engaged."]}
            empty="— no set —"
            onChange={(kite) => onConfig({ kite })}
          />
          <Button
            size="sm"
            variant={status?.kiting ? "danger" : "secondary"}
            icon={<Wind size={14} />}
            disabled={busy === "kiting" || (!status?.kiting && !config.kite)}
            onClick={() => onKiting(!status?.kiting)}
          >
            {status?.kiting ? "Stop kiting" : "Start kiting"}
          </Button>
        </div>
      </Group>

      <Group
        title="Weaponset"
        wide
        badge={<Badge tone="neutral">session locks</Badge>}
        hint="Wear a weaponset and pin its slots so no precast, midcast, idle, GearSwap or weapon-skill set can replace them. The pinned hand is put back when the weapon is drawn; a cast while disengaged and a Bard's Nitro song may take it for that action only, then restore it. A main or support job change releases the lock and the pins; //gs lock main, sub also works in game."
      >
        <div className="phase-row">
          <SetSelect
            label="Weaponset"
            value={config.weaponset}
            sets={weaponSets}
            prefixes={["weaponset."]}
            empty={weaponSets.length ? "— choose a set —" : "— no weaponsets yet —"}
            onChange={(weaponset) => onConfig({ weaponset })}
          />
          <Button
            size="sm"
            variant="ghost"
            icon={<Plus size={14} />}
            onClick={onNewWeaponSet}
          >
            New set
          </Button>
          <Button
            size="sm"
            variant="ghost"
            icon={<Pencil size={14} />}
            disabled={!config.weaponset || !weaponSets.includes(config.weaponset)}
            onClick={() => onEditWeaponSet(config.weaponset)}
          >
            Edit
          </Button>
          <Button
            size="sm"
            variant="secondary"
            icon={<Shield size={14} />}
            disabled={
              !config.weaponset ||
              !weaponSets.includes(config.weaponset) ||
              busy === "weapon-wear"
            }
            onClick={() => onWearWeaponSet(config.weaponset)}
          >
            Wear
          </Button>
          <Button
            size="sm"
            icon={<Lock size={14} />}
            disabled={
              !config.weaponset ||
              !weaponSets.includes(config.weaponset) ||
              busy === "weapon-lock"
            }
            onClick={() => onLockWeaponSet(config.weaponset)}
          >
            Wear &amp; lock
          </Button>
        </div>
        <div className="phase-locks">
          {WEAPON_SLOTS.map((slot) => {
            const locked = lockedSlots.has(slot);
            return (
              <button
                key={slot}
                type="button"
                className={cn("phase-lock-chip", locked && "locked")}
                onClick={() => onLockSlot(slot)}
                title={locked ? `Unlock ${slotLabelOf(slot)}` : `Lock ${slotLabelOf(slot)}`}
              >
                {locked ? <Lock size={12} /> : <LockOpen size={12} />}
                {slotLabelOf(slot)}
              </button>
            );
          })}
        </div>
      </Group>

      <Group
        title="Weaponskills"
        wide
        badge={
          <Badge tone="neutral">
            {wsGroups.length} WS
            {wsConditionCount
              ? ` · ${wsConditionCount} conditional`
              : ""}
          </Badge>
        }
        hint="Every WS gets a base row. A trailing (Buff, Buff) in the set name adds a conditional row: it is worn only while all listed buffs are up, and the row with the most matching buffs wins. A row's set wins; an empty row uses the library's set, then the default set (or the library's precast.WS) for a WS the library has no set for. The TP set returns the moment the WS result lands or misses."
      >
        <div className="phase-row">
          <SetSelect
            label="Default (all WS)"
            value={config.defaultWs}
            sets={sets}
            prefixes={["WS.", "precast.WS"]}
            empty="— library precast.WS —"
            onChange={(defaultWs) => onConfig({ defaultWs })}
          />
        </div>
        {wsGroups.length === 0 ? (
          <p className="muted padded">This library has no sets.WS.* cards.</p>
        ) : (
          <div className="phase-cards phase-ws-groups">
            {wsGroups.map((group) => {
              const conditional = group.variants.filter(
                (variant) => variant.conditions.length > 0,
              );
              return (
                <div className="phase-ws-group" key={group.base}>
                  <div className="phase-ws-group-head">
                    <span className="phase-ws-group-title">{group.base}</span>
                    {conditional.length > 0 ? (
                      <span className="phase-ws-group-note">
                        {conditional.length} condition{conditional.length === 1 ? "" : "s"}
                      </span>
                    ) : null}
                  </div>
                  <div className="phase-card-row">
                    <span className="phase-card-name">
                      Always
                      <em>base set</em>
                    </span>
                    <InlineSetSelect
                      value={config.wsOverrides[group.base] ?? ""}
                      sets={sets}
                      prefixes={["WS."]}
                      empty={group.hasBase ? "— library WS set —" : "— none —"}
                      onChange={(path) => {
                        const next = { ...config.wsOverrides };
                        if (path) next[group.base] = path;
                        else delete next[group.base];
                        onConfig({ wsOverrides: next });
                      }}
                    />
                  </div>
                  {conditional.map((variant) => (
                    <div className="phase-card-row phase-card-subrow" key={variant.raw}>
                      <span className="phase-card-name" title={`sets.WS.${variant.raw}`}>
                        <span className="phase-condition-list">
                          {variant.conditions.map((condition, index) => (
                            <span className="phase-condition" key={`${condition}-${index}`}>
                              {condition}
                            </span>
                          ))}
                        </span>
                        <em>while active</em>
                      </span>
                      <InlineSetSelect
                        value={config.wsOverrides[variant.raw] ?? ""}
                        sets={sets}
                        prefixes={["WS."]}
                        empty="— library WS set —"
                        onChange={(path) => {
                          const next = { ...config.wsOverrides };
                          if (path) next[variant.raw] = path;
                          else delete next[variant.raw];
                          onConfig({ wsOverrides: next });
                        }}
                      />
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </Group>

      <Group
        title="Job abilities"
        wide
        badge={
          <Badge tone="neutral">
            {abilities.length} abilities
            {jaOverrideCount ? ` · ${jaOverrideCount} override${jaOverrideCount === 1 ? "" : "s"}` : ""}
          </Badge>
        }
        hint="The host matches the ability's action id, so a card wins over the default; an empty card uses the default JA set above (or the library's precast.JA). The list covers the live main and sub job."
      >
        <div className="phase-row">
          <SetSelect
            label="Default JA set"
            value={config.defaultJa}
            sets={sets}
            prefixes={["JA.", "precast.JA"]}
            empty="— library precast.JA —"
            onChange={(defaultJa) => onConfig({ defaultJa })}
          />
        </div>
        {abilities.length === 0 ? (
          <p className="muted padded">
            Waiting for the client's ability list; it arrives with zone-in and the job change.
          </p>
        ) : (
          <div className="phase-cards">
            {abilities.map((ability) => (
              <div key={ability.id} className="phase-card-row">
                <span className="phase-card-name">
                  {ability.name}
                  {ability.type && ability.type !== "JobAbility" ? (
                    <em>{ability.type}</em>
                  ) : null}
                </span>
                <InlineSetSelect
                  value={config.jaOverrides[ability.name] ?? ""}
                  sets={sets}
                  prefixes={["JA.", "precast.JA"]}
                  empty="— use the default —"
                  onChange={(path) => {
                    const next = { ...config.jaOverrides };
                    if (path) next[ability.name] = path;
                    else delete next[ability.name];
                    onConfig({ jaOverrides: next });
                  }}
                />
              </div>
            ))}
          </div>
        )}
      </Group>

      <Group
        title="Resting"
        badge={
          <Badge tone={status?.resting ? "accent" : "neutral"} dot={status?.resting}>
            {status?.resting ? "resting" : "off"}
          </Badge>
        }
        hint="This server has no rest packet, so resting is a manual state: start it, or use //gs rest on, and turn it off when you stand."
      >
        <div className="phase-row">
          <SetSelect
            label="Resting set"
            value={config.rest}
            sets={sets}
            prefixes={["idle.", "rest"]}
            empty="— no resting set —"
            onChange={(rest) => onConfig({ rest })}
          />
          <Button
            size="sm"
            variant={status?.resting ? "danger" : "secondary"}
            icon={<Sparkles size={14} />}
            disabled={busy === "resting" || (!status?.resting && !config.rest)}
            onClick={() => onResting(!status?.resting)}
          >
            {status?.resting ? "Stop resting" : "Start resting"}
          </Button>
        </div>
      </Group>

      <Group
        title="Spells"
        wide
        badge={
          <Badge tone="neutral">
            {overrides.length} per-spell
            {categoryOverrideCount ? ` · ${categoryOverrideCount} modes` : ""}
          </Badge>
        }
        hint="Spell precast is worn before any spell; song precast is worn only for Bard songs. The midcast default is worn for every spell. A group card can hold a set for every mode; the Mode dropdown chooses which one is worn for that group's spells. Enfeebles is the exception: Auto wears the set for each spell's own kind — Skill (Frazzle III), Macc (Sleep), Duration, MND (Slow II), INT (Blind II), Macc + potency (Gravity) or General (Dispel) — and picking a Mode forces every enfeebling spell through that one set. Click a kind's name to see its gear. The Nuking card's Magic Burst row is automatic: it is worn while a Magic Burst window is open, and the armed mode otherwise. A per-spell card wins over its group. Switching modes is also available in the in-game spell HUD and with //modes."
      >
        <div className="phase-row">
          <SetSelect
            label="Spell precast"
            value={config.precast}
            sets={sets}
            prefixes={["precast."]}
            empty="— library precast.Spell / FC —"
            onChange={(precast) => onConfig({ precast })}
          />
          <SetSelect
            label="Song precast"
            value={config.precastSong}
            sets={sets}
            prefixes={["precast."]}
            empty="— library precast.Song / FCBardSong —"
            onChange={(precastSong) => onConfig({ precastSong })}
          />
          <SetSelect
            label="Midcast default"
            value={config.midcast}
            sets={sets}
            prefixes={["midcast."]}
            empty="— library midcast.<skill> —"
            onChange={(midcast) => onConfig({ midcast })}
          />
        </div>
        <div className="phase-category-heading">
          <span className="eyebrow">Spell mode groups</span>
          <span className="muted">Configure every mode; the armed mode is worn.</span>
        </div>
        <div className="phase-category-cards">
          {spellGroups.map((group) => {
            const activeMode = config.spellModes[group.key] ?? group.defaultMode;
            const autoModes = [
              ...(group.autoMode ? [group.autoMode] : []),
              ...(group.autoModes ?? []),
            ];
            const kinds = group.kinds ?? [];
            const autoConfigured = autoModes.some(
              (mode) => mode.category && Boolean(config.spellCategoryOverrides[mode.category]),
            );
            const configured =
              group.modes.some(
                (mode) => mode.category && Boolean(config.spellCategoryOverrides[mode.category]),
              ) ||
              kinds.some((kind) => Boolean(config.spellCategoryOverrides[kind.category])) ||
              autoConfigured;
            const forcedMode = group.modes.find((mode) => mode.key === activeMode);
            // A buff-conditional overlay (Enfeebles' Saboteur hands): shown under the kind
            // preview so the swap is visible next to the set it modifies.
            const overlayMode = autoModes.find((mode) => mode.merge && mode.category);
            const overlayPath = overlayMode?.category
              ? config.spellCategoryOverrides[overlayMode.category] ?? ""
              : "";
            const overlayItems = itemsFor(overlayPath);
            // The kind whose gear preview is open. The first kind is the default.
            const shownKind =
              kinds.find((kind) => `${group.key}:${kind.key}` === kindView) ?? kinds[0];
            const shownPath = shownKind
              ? config.spellCategoryOverrides[shownKind.category] ?? ""
              : "";
            const shownItems = itemsFor(shownPath);
            const shownSpells = shownKind
              ? group.spells.filter((spell) => spell.categories?.includes(shownKind.category))
              : [];
            return (
              <div key={group.key} className={cn("phase-category", configured && "configured")}>
                <div className="phase-category-head">
                  <span className="phase-category-title">{group.label}</span>
                  <Badge tone={configured ? "accent" : "neutral"}>
                    {group.spells.length} spells
                  </Badge>
                </div>
                <div className="phase-mode-row">
                  <span className="phase-mode-label">Mode</span>
                  <Select
                    className="phase-inline-select"
                    value={activeMode}
                    onChange={(event) =>
                      onConfig({
                        spellModes: { ...config.spellModes, [group.key]: event.target.value },
                      })
                    }
                  >
                    {group.modes.map((mode) => (
                      <option key={mode.key} value={mode.key}>
                        {mode.label}
                      </option>
                    ))}
                  </Select>
                  {kinds.length > 0 && activeMode !== "auto" ? (
                    <span className="phase-mode-forced">
                      forced: every spell wears the {forcedMode?.label ?? activeMode} set
                    </span>
                  ) : null}
                </div>
                {kinds.map((kind) => {
                  const kindSpells = group.spells.filter((spell) =>
                    spell.categories?.includes(kind.category),
                  );
                  const selected = shownKind?.key === kind.key;
                  return (
                    <div
                      key={kind.key}
                      className={cn("phase-kind-row", selected && "selected")}
                      title={kind.detail}
                    >
                      <button
                        type="button"
                        className="phase-kind-label"
                        onClick={() => setKindView(`${group.key}:${kind.key}`)}
                      >
                        {kind.label}
                        <em>{kindSpells.length}</em>
                      </button>
                      <InlineSetSelect
                        value={config.spellCategoryOverrides[kind.category] ?? ""}
                        sets={sets}
                        prefixes={["midcast.", "precast."]}
                        empty="— use the default —"
                        onChange={(nextPath) => {
                          const next = { ...config.spellCategoryOverrides };
                          if (nextPath) next[kind.category] = nextPath;
                          else delete next[kind.category];
                          onConfig({ spellCategoryOverrides: next });
                        }}
                      />
                    </div>
                  );
                })}
                {autoModes.map((autoMode) => {
                  const category = autoMode.category;
                  if (!category) return null;
                  return (
                    <div
                      key={autoMode.key}
                      className={cn(
                        "phase-mode-set",
                        "phase-mode-auto",
                        autoMode.key === "magic_burst" && status?.burst && "live",
                      )}
                      title={autoMode.detail}
                    >
                      <span className="phase-mode-name">
                        {autoMode.short}
                        <em>{autoMode.merge ? "on buff" : "auto"}</em>
                      </span>
                      <InlineSetSelect
                        value={config.spellCategoryOverrides[category] ?? ""}
                        sets={sets}
                        prefixes={["midcast.", "precast."]}
                        empty={autoMode.merge ? "— no overlay —" : "— use the armed mode —"}
                        onChange={(nextPath) => {
                          const next = { ...config.spellCategoryOverrides };
                          if (nextPath) next[category] = nextPath;
                          else delete next[category];
                          onConfig({ spellCategoryOverrides: next });
                        }}
                      />
                      {autoMode.key === "magic_burst" && status?.burst &&
                      config.spellCategoryOverrides[category] ? (
                        <span className="phase-mode-live">open</span>
                      ) : null}
                    </div>
                  );
                })}
                {kinds.length > 0 && shownKind ? (
                  <div className="phase-kind-gear">
                    <div className="phase-kind-gear-head">
                      <span className="eyebrow">{shownKind.label} gear</span>
                      <code>
                        {shownPath || "— no set; the library's midcast.Enfeebling Magic applies —"}
                      </code>
                    </div>
                    <div className="phase-kind-gear-body">
                      <SetEquipmentPreview
                        port={port ?? null}
                        items={shownItems}
                        augments={augmentsFor(shownPath)}
                        compact
                        emptyLabel="Pick a set for this kind to see its pieces."
                      />
                      <div className="phase-kind-pieces">
                        {SLOT_KEYS.filter((slot) => shownItems[slot]).map((slot) => (
                          <span key={slot}>
                            <b>{slotLabelOf(slot)}</b>
                            {shownItems[slot]}
                          </span>
                        ))}
                        {!SLOT_KEYS.some((slot) => shownItems[slot]) && (
                          <span className="muted">No pieces loaded for this set.</span>
                        )}
                      </div>
                    </div>
                    {overlayMode && SLOT_KEYS.some((slot) => overlayItems[slot]) ? (
                      <div className="phase-kind-overlay" title={overlayMode.detail}>
                        <span className="eyebrow">{overlayMode.label}</span>
                        {SLOT_KEYS.filter((slot) => overlayItems[slot]).map((slot) => (
                          <span key={slot}>
                            {slotLabelOf(slot)} → {overlayItems[slot]}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <p className="phase-kind-spells">
                      {shownSpells.length
                        ? shownSpells.map((spell) => (
                            <span key={spell.id} title={`${spell.skill} · Lv ${spell.level}`}>
                              {spell.name}
                            </span>
                          ))
                        : <em>No spell of this type is on the current job pair.</em>}
                    </p>
                    <p className="gear-hint">{shownKind.detail}</p>
                  </div>
                ) : null}
                {kinds.length === 0 &&
                  group.modes.filter((mode) => mode.category).map((mode) => {
                    const category = mode.category;
                    if (!category) return null;
                    return (
                      <div key={mode.key} className="phase-mode-set">
                        <span className="phase-mode-name">{mode.short}</span>
                        <InlineSetSelect
                          value={config.spellCategoryOverrides[category] ?? ""}
                          sets={sets}
                          prefixes={["midcast.", "precast."]}
                          empty="— use the default —"
                          onChange={(nextPath) => {
                            const next = { ...config.spellCategoryOverrides };
                            if (nextPath) next[category] = nextPath;
                            else delete next[category];
                            onConfig({ spellCategoryOverrides: next });
                          }}
                        />
                      </div>
                    );
                  })}
                <details className="phase-category-spells">
                  <summary>
                    {[...group.modes, ...autoModes]
                      .map((mode) => `${mode.label}: ${mode.detail}`)
                      .join(" ")}
                    {kinds.map((kind) => ` ${kind.label}: ${kind.detail}`).join("")}
                  </summary>
                  <div className="phase-category-names">
                    {group.spells.map((spell) => (
                      <span key={spell.id} title={`${spell.skill || "spell"} · Lv ${spell.level}`}>
                        {spell.name}
                      </span>
                    ))}
                  </div>
                </details>
              </div>
            );
          })}
        </div>
        <div className="phase-category-heading">
          <span className="eyebrow">Per-spell overrides</span>
          <span className="muted">A spell card wins over its category.</span>
        </div>
        {overrides.map(([id, path]) => {
          const spell = spellById.get(Number(id));
          return (
            <div key={id} className="phase-card-row">
              <span className="phase-card-name">
                {spell?.name ?? `Spell ${id}`}
                {spell?.skill ? <em>{spell.skill}</em> : null}
              </span>
              <InlineSetSelect
                value={path}
                sets={sets}
                prefixes={["midcast.", "precast."]}
                empty="— use the default —"
                onChange={(nextPath) => {
                  const next = { ...config.spellOverrides };
                  if (nextPath) next[id] = nextPath;
                  else delete next[id];
                  onConfig({ spellOverrides: next });
                }}
              />
              <Button
                size="sm"
                variant="ghost"
                icon={<Trash2 size={13} />}
                title="Remove override"
                onClick={() => {
                  const next = { ...config.spellOverrides };
                  delete next[id];
                  onConfig({ spellOverrides: next });
                }}
              />
            </div>
          );
        })}
        <div className="phase-row">
          <Field label="Add a per-spell override" className="phase-return">
            <Select value={addSpell} onChange={(event) => setAddSpell(event.target.value)}>
              <option value="">{spells.length ? "Choose a spell…" : "No spell list yet"}</option>
              {spellChoices.map((spell) => (
                <option key={spell.id} value={spell.id}>
                  {spell.name} · {spell.skill || "spell"} · Lv {spell.level}
                </option>
              ))}
            </Select>
          </Field>
          <Button
            size="sm"
            icon={<Plus size={14} />}
            disabled={!addSpell}
            onClick={() => {
              if (!addSpell) return;
              onConfig({
                spellOverrides: {
                  ...config.spellOverrides,
                  [addSpell]: config.midcast || "",
                },
              });
              setAddSpell("");
            }}
          >
            Add override
          </Button>
        </div>
      </Group>

      {(!job || jobGroups.has("songs")) ? (
      <Group
        title="Song overrides"
        wide
        badge={<Badge tone="neutral">{songOverrideEntries.length} songs</Badge>}
        hint="Only Bard songs are listed here. Each card can pick its own precast and midcast set; an empty pick falls back to the Song precast / armed song mode."
      >
        {songOverrideEntries.map(([id, entry]) => {
          const spell = spellById.get(Number(id));
          return (
            <div key={id} className="phase-card-row">
              <span className="phase-card-name">
                {spell?.name ?? `Song ${id}`}
                <em>Bard song</em>
              </span>
              <InlineSetSelect
                value={entry.pre}
                sets={sets}
                prefixes={["precast."]}
                empty="— Song precast —"
                onChange={(pre) => {
                  const next = { ...config.songOverrides, [id]: { ...entry, pre: pre ?? "" } };
                  onConfig({ songOverrides: next });
                }}
              />
              <InlineSetSelect
                value={entry.mid}
                sets={sets}
                prefixes={["midcast."]}
                empty="— Song mode set —"
                onChange={(mid) => {
                  const next = { ...config.songOverrides, [id]: { ...entry, mid: mid ?? "" } };
                  onConfig({ songOverrides: next });
                }}
              />
              <Button
                size="sm"
                variant="ghost"
                icon={<Trash2 size={13} />}
                title="Remove song override"
                onClick={() => {
                  const next = { ...config.songOverrides };
                  delete next[id];
                  onConfig({ songOverrides: next });
                }}
              />
            </div>
          );
        })}
        <div className="phase-row">
          <Field label="Add a song override" className="phase-return">
            <Select value={addSong} onChange={(event) => setAddSong(event.target.value)}>
              <option value="">{songChoices.length ? "Choose a song…" : "No songs on this job"}
              </option>
              {songChoices.map((spell) => (
                <option key={spell.id} value={spell.id}>
                  {spell.name} · Lv {spell.level}
                </option>
              ))}
            </Select>
          </Field>
          <Button
            size="sm"
            icon={<Plus size={14} />}
            disabled={!addSong}
            onClick={() => {
              if (!addSong) return;
              onConfig({
                songOverrides: {
                  ...config.songOverrides,
                  [addSong]: { pre: config.precastSong || "", mid: config.midcast || "" },
                },
              });
              setAddSong("");
            }}
          >
            Add song
          </Button>
        </div>
      </Group>
      ) : null}

      <Group
        title="Idle"
        wide
        badge={
          <Badge tone="neutral">
            {status?.town === 1 ? "Town" : status?.town === 0 ? "Field" : "—"}
          </Badge>
        }
        hint="Town and field are selected by the zone-in packet; movement wins while a step is in progress. The focus sets are manual: pick a focus to wear DT/PDT/MDT/Eva/Meva while idle."
      >
        <div className="phase-row">
          <SetSelect
            label="Field idle"
            value={config.idleField}
            sets={sets}
            prefixes={["idle.field", "idle.dt", "idle.pdt", "idle."]}
            empty="— use the town set —"
            onChange={(idleField) => onConfig({ idleField })}
          />
          <SetSelect
            label="Town idle"
            value={config.idleTown}
            sets={sets}
            prefixes={["idle.town", "idle."]}
            empty="— library idle.town —"
            onChange={(idleTown) => onConfig({ idleTown })}
          />
          <SetSelect
            label="Moving"
            value={config.movement}
            sets={sets}
            prefixes={["idle.movement", "idle."]}
            empty="— library idle.movement —"
            onChange={(movement) => onConfig({ movement })}
          />
        </div>
        <div className="phase-row">
          <Field label="Idle focus" className="phase-return">
            <Select
              value={config.focusMode}
              onChange={(event) => {
                const mode = event.target.value as PhaseConfig["focusMode"];
                onConfig({ focusMode: mode });
                onFocus(mode);
              }}
            >
              {FOCUS_MODES.map((mode) => (
                <option key={mode.value} value={mode.value}>
                  {mode.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="phase-row">
          <SetSelect
            label="DT set"
            value={config.focus.dt}
            sets={sets}
            prefixes={["idle.dt", "idle."]}
            empty="— no DT set —"
            onChange={(dt) => onConfig({ focus: { ...config.focus, dt } })}
          />
          <SetSelect
            label="PDT set"
            value={config.focus.pdt}
            sets={sets}
            prefixes={["idle.pdt", "idle."]}
            empty="— no PDT set —"
            onChange={(pdt) => onConfig({ focus: { ...config.focus, pdt } })}
          />
          <SetSelect
            label="MDT set"
            value={config.focus.mdt}
            sets={sets}
            prefixes={["idle.mdt", "idle."]}
            empty="— no MDT set —"
            onChange={(mdt) => onConfig({ focus: { ...config.focus, mdt } })}
          />
          <SetSelect
            label="Eva set"
            value={config.focus.eva}
            sets={sets}
            prefixes={["idle.eva", "idle."]}
            empty="— no Eva set —"
            onChange={(eva) => onConfig({ focus: { ...config.focus, eva } })}
          />
          <SetSelect
            label="Meva set"
            value={config.focus.meva}
            sets={sets}
            prefixes={["idle.meva", "idle."]}
            empty="— no Meva set —"
            onChange={(meva) => onConfig({ focus: { ...config.focus, meva } })}
          />
        </div>
      </Group>
    </div>
  );
}
