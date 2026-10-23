import { useMemo, useState } from "react";
import { Lock, LockOpen, Pencil, Plus, Shield, Sparkles, Trash2, Wind, Zap } from "lucide-react";
import type { JobAbility, JobSpell, PhaseStatus } from "../types";
import { FOCUS_MODES, phaseStateLabel, slotLabelOf, type PhaseConfig } from "../lib/phase";
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
  const overrides = Object.entries(config.spellOverrides);
  const jaOverrideCount = Object.keys(config.jaOverrides).length;
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
        hint="Build TP in the first set; the default WS set is worn before a weaponskill unless its own Weaponskills card picks another set."
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
        hint="Wear a weaponset and pin its slots so no precast, midcast, idle or GearSwap swap can replace them. A main or support job change releases the lock and the pins, wherever the change happens; /!gs lock main, sub also works in game."
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
        badge={<Badge tone="neutral">{wsNames.length} WS</Badge>}
        hint="Every WS gets a card. Empty picks the default WS set above (or the library's precast.WS); the TP set returns the moment the WS result lands or misses."
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
        {wsNames.length === 0 ? (
          <p className="muted padded">This library has no sets.WS.* cards.</p>
        ) : (
          <div className="phase-cards">
            {wsNames.map((name) => (
              <div key={name} className="phase-card-row">
                <span className="phase-card-name">{name}</span>
                <InlineSetSelect
                  value={config.wsOverrides[name] ?? ""}
                  sets={sets}
                  prefixes={["WS."]}
                  empty="— library WS set —"
                  onChange={(path) => {
                    const next = { ...config.wsOverrides };
                    if (path) next[name] = path;
                    else delete next[name];
                    onConfig({ wsOverrides: next });
                  }}
                />
              </div>
            ))}
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
        hint="This server has no rest packet, so resting is a manual state: start it, or use /!gs rest on, and turn it off when you stand."
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
        badge={<Badge tone="neutral">{overrides.length} overrides</Badge>}
        hint="Precast is worn before the cast is timed; the midcast default is worn for every spell; a per-spell override wins over the default. The spell is tracked by its action id, so macc, mab and magic-skill sets can be picked per spell."
      >
        <div className="phase-row">
          <SetSelect
            label="Precast set"
            value={config.precast}
            sets={sets}
            prefixes={["precast."]}
            empty="— library precast.FC —"
            onChange={(precast) => onConfig({ precast })}
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
          <Field label="Add a spell override" className="phase-return">
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
