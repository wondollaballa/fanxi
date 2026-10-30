import { useEffect, useMemo, useRef, useState } from "react";
import {
  Crosshair,
  Eye,
  EyeOff,
  MapPin,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Sparkles,
  Square,
  Swords,
  Target,
  Trash2,
  X,
} from "lucide-react";
import type { BattleProfile, BattleState, InstanceView, Tenant } from "../types";
import { backend } from "../lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  SectionHeader,
  Select,
  TextInput,
  cn,
} from "./ui";

type Notify = (message: string, kind?: "success" | "error" | "info") => void;

type TabKey = "roster" | "camp" | "rules" | "spells" | "profiles";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "roster", label: "Roster" },
  { key: "camp", label: "Camp & engage" },
  { key: "rules", label: "Rules" },
  { key: "spells", label: "Healing & spells" },
  { key: "profiles", label: "Profiles" },
];

const ENGAGE_MODES: Array<[BattleProfile["engage"]["mode"], string]> = [
  ["puller", "When the puller has claim"],
  ["tank", "When the tank has claim"],
  ["player", "When a named player has claim"],
  ["leader", "When the party leader has claim"],
  ["always", "On any party claim"],
  ["none", "Never"],
];

const JOB_ABBR = [
  "NON", "WAR", "MNK", "WHM", "BLM", "RDM", "THF", "PLD", "DRK", "BST", "BRD",
  "RNG", "SAM", "NIN", "DRG", "SMN", "BLU", "COR", "PUP", "DNC", "SCH", "GEO", "RUN",
];

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function numberOr(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function nextRowId(profile: BattleProfile): number {
  const ids = [
    ...profile.heal.cures.map((row) => row.id),
    ...profile.buffs.rows.map((row) => row.id),
    ...profile.enfeebles.rows.map((row) => row.id),
  ];
  return Math.max(0, ...ids) + 1;
}

function hasRole(profile: BattleProfile, role: "support" | "melee" | "ranged", name: string): boolean {
  return profile.roster[role].includes(name);
}

function setSingle(profile: BattleProfile, role: "tank" | "puller" | "kiter", name: string) {
  if (name) {
    for (const key of ["tank", "puller", "kiter"] as const) {
      if (key !== role && profile.roster[key] === name) profile.roster[key] = "";
    }
    profile.roster.support = profile.roster.support.filter((item) => item !== name);
    profile.roster.melee = profile.roster.melee.filter((item) => item !== name);
    profile.roster.ranged = profile.roster.ranged.filter((item) => item !== name);
  }
  profile.roster[role] = name;
}

function toggleMulti(profile: BattleProfile, role: "support" | "melee" | "ranged", name: string) {
  const list = profile.roster[role];
  if (list.includes(name)) {
    profile.roster[role] = list.filter((item) => item !== name);
    return;
  }
  for (const key of ["tank", "puller", "kiter"] as const) {
    if (profile.roster[key] === name) profile.roster[key] = "";
  }
  for (const key of ["support", "melee", "ranged"] as const) {
    if (key !== role) profile.roster[key] = profile.roster[key].filter((item) => item !== name);
  }
  profile.roster[role] = [...list, name];
}

function RoleButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn("battle-role-btn", active && "on")}
      onClick={onClick}
      title={active ? `Remove from ${label}` : `Assign to ${label}`}
    >
      {label}
    </button>
  );
}

function Check({
  checked,
  title,
  body,
  onChange,
}: {
  checked: boolean;
  title: string;
  body?: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="check-row">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>
        <strong>{title}</strong>
        {body && <small>{body}</small>}
      </span>
    </label>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label}>
      <TextInput
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(numberOr(event.target.value, value))}
      />
    </Field>
  );
}

export function BattlePage({
  instances,
  tenant,
  notify,
}: {
  instances: InstanceView[];
  tenant: Tenant | null;
  notify: Notify;
}) {
  const running = instances.filter((instance) => instance.alive);
  const instance = useMemo(() => {
    if (tenant) {
      const own = running.find(
        (item) => Number(item.character?.id) === Number(tenant.character.id),
      );
      if (own) return own;
    }
    return running[0] ?? null;
  }, [running, tenant]);

  const [state, setState] = useState<BattleState | null>(null);
  const [profile, setProfile] = useState<BattleProfile | null>(null);
  const [tab, setTab] = useState<TabKey>("roster");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [mobDraft, setMobDraft] = useState("");
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const port = instance?.port ?? null;
  const nearbyMobs = useMemo(() => {
    const map = new Map<string, { name: string; distance: number; count: number }>();
    for (const mob of state?.status.mobs ?? []) {
      const key = mob.name.toLowerCase();
      const current = map.get(key);
      if (current) {
        current.count += 1;
        current.distance = Math.min(current.distance, mob.distance);
      } else {
        map.set(key, { name: mob.name, distance: mob.distance, count: 1 });
      }
    }
    return [...map.values()].sort((a, b) => a.distance - b.distance || a.name.localeCompare(b.name));
  }, [state?.status.mobs]);

  function togglePullMob(name: string) {
    edit((draft) => {
      const at = draft.pull.mobs.findIndex((item) => item.toLowerCase() === name.toLowerCase());
      if (at >= 0) draft.pull.mobs.splice(at, 1);
      else if (draft.pull.mobs.length < 40) draft.pull.mobs.push(name);
    });
  }

  function addPullMob() {
    const name = mobDraft.trim();
    if (!name) return;
    if (!profile?.pull.mobs.some((item) => item.toLowerCase() === name.toLowerCase())) {
      edit((draft) => {
        if (draft.pull.mobs.length < 40) draft.pull.mobs.push(name);
      });
    }
    setMobDraft("");
  }

  function adopt(next: BattleState, keepDirty: boolean) {
    setState(next);
    if (!keepDirty && !dirtyRef.current) setProfile(next.profile);
  }

  async function load(silent = false) {
    if (!port) return;
    try {
      const next = await backend.battle(port, { action: "state" });
      adopt(next, false);
      setError("");
    } catch (caught) {
      if (!silent) setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  useEffect(() => {
    if (!port) {
      setState(null);
      setProfile(null);
      setDirty(false);
      return;
    }
    setState(null);
    setProfile(null);
    setDirty(false);
    setError("");
    void load();
    const timer = window.setInterval(() => void load(true), 3000);
    return () => window.clearInterval(timer);
    // `load` only depends on the port; the interval is replaced when the client changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port]);

  function edit(mutator: (draft: BattleProfile) => void) {
    setProfile((previous) => {
      if (!previous) return previous;
      const next = clone(previous);
      mutator(next);
      return next;
    });
    setDirty(true);
  }

  async function send(
    label: string,
    args: Record<string, unknown>,
    options: { keepDirty?: boolean; message?: string } = {},
  ) {
    if (!port) return null;
    setBusy(label);
    setError("");
    try {
      const next = await backend.battle(port, args);
      setState(next);
      if (!options.keepDirty) {
        setProfile(next.profile);
        setDirty(false);
      }
      if (options.message) notify(options.message, "success");
      return next;
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      setError(message);
      notify(message, "error");
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function saveProfile() {
    if (!profile) return;
    const next = await send(
      "save",
      { action: "save", profile, name: profile.name },
      { message: `Battle profile "${profile.name}" saved.` },
    );
    if (next) setDirty(false);
  }

  async function startBattle() {
    if (!profile) return;
    if (dirty) {
      const applied = await send("apply", { action: "update", profile }, { keepDirty: true });
      if (!applied) return;
    }
    await send("start", { action: "start" }, { keepDirty: true, message: "Battle started." });
  }

  async function applyProfile() {
    if (!profile) return;
    await send("apply", { action: "update", profile }, { keepDirty: true, message: "Applied to the running client (not saved)." });
  }

  async function refresh() {
    if (!profile) return;
    if (dirty && !window.confirm("Discard the unsaved changes and reload the client's profile?")) return;
    setDirty(false);
    await load();
  }

  function mergeCamp(next: BattleState) {
    setProfile((previous) => (previous ? { ...previous, camp: next.profile.camp } : next.profile));
    setDirty(true);
  }

  function mergeSupportCamp(next: BattleState) {
    setProfile((previous) => (previous ? { ...previous, support_camp: next.profile.support_camp } : next.profile));
    setDirty(true);
  }

  async function suggest(scope: "heal" | "buff" | "enfeeble") {
    if (!profile) return;
    const applied = await send("apply", { action: "update", profile }, { keepDirty: true });
    if (!applied) return;
    const next = await send("suggest", { action: "suggest", scope }, { keepDirty: true });
    if (next) {
      setProfile(next.profile);
      setDirty(true);
      notify("Suggested spells from the current job.", "success");
    }
  }

  if (!instance) {
    return (
      <div className="page">
        <SectionHeader
          eyebrow="Battle"
          title="Battle hub"
          subtitle="Automated camps, formations, pulling, healing and enfeebling rules, edited per character."
        />
        <Card>
          <EmptyState
            icon={<Swords size={28} />}
            title="No running client"
            body="Start a character from the Control room; the Battle page talks to that client's in-game hub."
          />
        </Card>
      </div>
    );
  }

  if (!state || !profile) {
    return (
      <div className="page">
        <SectionHeader
          eyebrow="Battle"
          title="Battle hub"
          subtitle={instance.character?.name ? `${instance.character.name} on control port ${instance.port}` : undefined}
        />
        <Card>
          <div className="battle-loading">
            <RefreshCw className="spin" size={16} />
            Reading the battle profile…
          </div>
        </Card>
      </div>
    );
  }

  const status = state.status;
  const members = status.members ?? [];
  const joined = members.length > 0;
  const roleCount =
    (profile.roster.tank ? 1 : 0) +
    (profile.roster.puller ? 1 : 0) +
    (profile.roster.kiter ? 1 : 0) +
    profile.roster.support.length +
    profile.roster.melee.length +
    profile.roster.ranged.length;

  function renderRoster() {
    const p = profile!;
    return (
      <>
        <div className="form-grid two">
          <Field label="Tank" hint="Holds the mob and is the formation anchor.">
            <Select value={p.roster.tank} onChange={(event) => edit((draft) => setSingle(draft, "tank", event.target.value))}>
              <option value="">(unassigned)</option>
              {members.map((member) => (
                <option key={member.slot} value={member.name}>{member.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Puller" hint="Claims the next mob and brings it to camp.">
            <Select value={p.roster.puller} onChange={(event) => edit((draft) => setSingle(draft, "puller", event.target.value))}>
              <option value="">(unassigned)</option>
              {members.map((member) => (
                <option key={member.slot} value={member.name}>{member.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Kiter" hint="Runs the kite when the fight turns.">
            <Select value={p.roster.kiter} onChange={(event) => edit((draft) => setSingle(draft, "kiter", event.target.value))}>
              <option value="">(unassigned)</option>
              {members.map((member) => (
                <option key={member.slot} value={member.name}>{member.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Engage when" hint="The claim that must exist before the party joins.">
            <Select
              value={p.engage.mode}
              onChange={(event) =>
                edit((draft) => {
                  draft.engage.mode = event.target.value as BattleProfile["engage"]["mode"];
                })
              }
            >
              {ENGAGE_MODES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </Select>
          </Field>
        </div>
        {p.engage.mode === "player" && (
          <Field label="Named player" hint="Engage once this player has claimed the mob.">
            <TextInput
              value={p.engage.player}
              onChange={(event) => edit((draft) => { draft.engage.player = event.target.value; })}
            />
          </Field>
        )}

        <div className="battle-member-table">
          <div className="battle-member-head">
            <span>Character</span>
            <span>Roles (T tank, P puller, K kiter, S support, M melee, R ranged)</span>
          </div>
          {joined ? (
            members.map((member) => (
              <div className="battle-member-row" key={member.slot}>
                <div>
                  <strong>{member.name}</strong>
                  <small>
                    {JOB_ABBR[member.job] ?? "???"} {member.level || ""}
                    {member.sub
                      ? ` / ${JOB_ABBR[member.sub] ?? "???"}${member.sub_level ? ` ${member.sub_level}` : ""}`
                      : ""}
                    {member.slot === 0 ? " · you" : ""} · {Math.round(member.hpp)}%
                  </small>
                </div>
                <div className="battle-role-buttons">
                  <RoleButton active={p.roster.tank === member.name} label="T" onClick={() => edit((draft) => setSingle(draft, "tank", draft.roster.tank === member.name ? "" : member.name))} />
                  <RoleButton active={p.roster.puller === member.name} label="P" onClick={() => edit((draft) => setSingle(draft, "puller", draft.roster.puller === member.name ? "" : member.name))} />
                  <RoleButton active={p.roster.kiter === member.name} label="K" onClick={() => edit((draft) => setSingle(draft, "kiter", draft.roster.kiter === member.name ? "" : member.name))} />
                  <RoleButton active={hasRole(p, "support", member.name)} label="S" onClick={() => edit((draft) => toggleMulti(draft, "support", member.name))} />
                  <RoleButton active={hasRole(p, "melee", member.name)} label="M" onClick={() => edit((draft) => toggleMulti(draft, "melee", member.name))} />
                  <RoleButton active={hasRole(p, "ranged", member.name)} label="R" onClick={() => edit((draft) => toggleMulti(draft, "ranged", member.name))} />
                </div>
              </div>
            ))
          ) : (
            <p className="battle-hint">The client has no party roster yet; you can still save the profile and assign names in game.</p>
          )}
        </div>

        <div className="form-grid two">
          <Field label="Support" hint="Heals, buffs, dispels and status removal.">
            <TextInput
              value={p.roster.support.join(", ")}
              onChange={(event) =>
                edit((draft) => {
                  draft.roster.support = event.target.value.split(",").map((name) => name.trim()).filter(Boolean);
                })
              }
            />
          </Field>
          <Field label="Melee" hint="Order here is the formation slot order.">
            <TextInput
              value={p.roster.melee.join(", ")}
              onChange={(event) =>
                edit((draft) => {
                  draft.roster.melee = event.target.value.split(",").map((name) => name.trim()).filter(Boolean);
                })
              }
            />
          </Field>
          <Field label="Ranged">
            <TextInput
              value={p.roster.ranged.join(", ")}
              onChange={(event) =>
                edit((draft) => {
                  draft.roster.ranged = event.target.value.split(",").map((name) => name.trim()).filter(Boolean);
                })
              }
            />
          </Field>
        </div>

        <div className="battle-pauses">
          <span>Pause a role:</span>
          {(["tank", "support", "melee", "ranged"] as const).map((role) => (
            <button
              type="button"
              key={role}
              className={cn("battle-role-btn", p.paused[role] && "on")}
              onClick={() =>
                void send("pause", { action: "pause", role }, { keepDirty: true }).then((next) => {
                  if (!next) return;
                  setProfile((previous) => (previous ? { ...previous, paused: next.profile.paused } : next.profile));
                  setDirty(true);
                })
              }
            >
              {role}
            </button>
          ))}
        </div>
      </>
    );
  }

  function renderCamp() {
    return (
      <>
        <div className="battle-camp-row">
          <div>
            <strong>{profile!.camp.set ? "Camp set" : "No camp"}</strong>
            <small>
              {profile!.camp.set
                ? `${profile!.camp.x.toFixed(1)}, ${profile!.camp.y.toFixed(1)} · radius ${profile!.camp.radius.toFixed(1)} yalms`
                : "Start auto-sets the current spot if you leave this empty."}
            </small>
          </div>
          <div className="battle-actions">
            <Button size="sm" variant="secondary" icon={<MapPin size={14} />} onClick={() => void send("camp", { action: "camp_here" }, { keepDirty: true }).then((next) => next && mergeCamp(next))}>
              Set at my position
            </Button>
            <Button size="sm" variant="secondary" icon={<Crosshair size={14} />} onClick={() => void send("place", { action: "place_there" }, { message: "Place the camp circle in game; Enter drops it." })}>
              Set on the ground
            </Button>
            <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => void send("camp", { action: "camp_clear" }, { keepDirty: true }).then((next) => next && mergeCamp(next))}>
              Clear
            </Button>
          </div>
        </div>
        <div className="form-grid three">
          <NumberField label="X" value={profile!.camp.x} step={0.1} onChange={(value) => edit((draft) => { draft.camp.x = value; })} />
          <NumberField label="Y" value={profile!.camp.y} step={0.1} onChange={(value) => edit((draft) => { draft.camp.y = value; })} />
          <NumberField label="Z (height)" value={profile!.camp.z} step={0.1} onChange={(value) => edit((draft) => { draft.camp.z = value; })} />
        </div>
        <div className="form-grid two">
          <NumberField label="Camp radius (yalms)" value={profile!.camp.radius} min={1} max={50} step={0.5} onChange={(value) => edit((draft) => { draft.camp.radius = value; })} />
          <Field label="Camp circle in game">
            <label className="battle-inline-check">
              <input type="checkbox" checked={profile!.camp.show} onChange={(event) => edit((draft) => { draft.camp.show = event.target.checked; })} />
              <span>Draw the camp ring on the ground while the hub or the script is active</span>
            </label>
          </Field>
        </div>
        <div className="battle-camp-row">
          <div>
            <strong>{profile!.support_camp.set ? "Support camp set" : "Support uses the tank camp"}</strong>
            <small>
              {profile!.support_camp.set
                ? `${profile!.support_camp.x.toFixed(1)}, ${profile!.support_camp.y.toFixed(1)} · radius ${profile!.support_camp.radius.toFixed(1)} yalms`
                : "Place a separate support camp for healers, GEO/BRD and ranged."}
            </small>
          </div>
          <div className="battle-actions">
            <Button size="sm" variant="secondary" icon={<MapPin size={14} />} onClick={() => void send("support-camp", { action: "support_camp_here" }, { keepDirty: true }).then((next) => next && mergeSupportCamp(next))}>
              Set at my position
            </Button>
            <Button size="sm" variant="secondary" icon={<Crosshair size={14} />} onClick={() => void send("support-place", { action: "support_place_there" }, { message: "Place the support camp in game; Enter drops it." })}>
              Set on the ground
            </Button>
            <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => void send("support-camp-clear", { action: "support_camp_clear" }, { keepDirty: true }).then((next) => next && mergeSupportCamp(next))}>
              Clear
            </Button>
          </div>
        </div>
        <div className="form-grid three">
          <NumberField label="Support X" value={profile!.support_camp.x} step={0.1} onChange={(value) => edit((draft) => { draft.support_camp.x = value; })} />
          <NumberField label="Support Y" value={profile!.support_camp.y} step={0.1} onChange={(value) => edit((draft) => { draft.support_camp.y = value; })} />
          <NumberField label="Support Z (height)" value={profile!.support_camp.z} step={0.1} onChange={(value) => edit((draft) => { draft.support_camp.z = value; })} />
        </div>
        <div className="form-grid two">
          <NumberField label="Support radius (yalms)" value={profile!.support_camp.radius} min={1} max={50} step={0.5} onChange={(value) => edit((draft) => { draft.support_camp.radius = value; })} />
          <Field label="Support radar">
            <label className="battle-inline-check">
              <input type="checkbox" checked={profile!.support_camp.show} onChange={(event) => edit((draft) => { draft.support_camp.show = event.target.checked; })} />
              <span>Show the support camp on the radar</span>
            </label>
          </Field>
        </div>
        <div className="battle-actions">
          <Button size="sm" variant="secondary" icon={<Swords size={14} />} onClick={() => void send("rally", { action: "rally" }, { keepDirty: true, message: "Calling the team to this character (//warp all me)." })}>
            Rally team here
          </Button>
          <Button size="sm" variant="secondary" icon={<Plus size={14} />} onClick={() => void send("invite", { action: "invite_team" }, { keepDirty: true, message: "Inviting online sub-accounts." })}>
            Invite subs
          </Button>
          <Button size="sm" variant="secondary" onClick={() => void send("import", { action: "import_party" }, { keepDirty: true, message: "Imported unassigned party members." })}>
            Import party names
          </Button>
        </div>
        <Check
          checked={profile!.engage.camp_only}
          title="Only engage targets inside the camp"
          body="Tank and puller are exempt; melee will not chase a mob beyond the leash."
          onChange={(value) => edit((draft) => { draft.engage.camp_only = value; })}
        />
        <Check
          checked={profile!.engage.wait_claim}
          title="Wait for a party claim"
          body="Never steal another party's mob. The tank or puller claims it first."
          onChange={(value) => edit((draft) => { draft.engage.wait_claim = value; })}
        />
        <div className="form-grid two">
          <NumberField label="Max engage distance" value={profile!.engage.max_distance} min={5} max={100} onChange={(value) => edit((draft) => { draft.engage.max_distance = value; })} />
          <NumberField label="Find next mob at target HP%" value={profile!.pull.at_hp} min={1} max={100} onChange={(value) => edit((draft) => { draft.pull.at_hp = value; })} />
        </div>

        <h3 className="battle-subhead">Melee formation</h3>
        <Check
          checked={profile!.formation.enabled}
          title="Tank-anchored formation"
          body="The arc is computed from the line mob→tank: the mob faces the tank, so melee can pick the back or flank."
          onChange={(value) => edit((draft) => { draft.formation.enabled = value; })}
        />
        <div className="form-grid three">
          <Field label="Style">
            <Select value={profile!.formation.style} onChange={(event) => edit((draft) => { draft.formation.style = event.target.value as BattleProfile["formation"]["style"]; })}>
              <option value="tank">Tank-anchored arc</option>
              <option value="behind">Behind the mob</option>
              <option value="side">Flanks</option>
            </Select>
          </Field>
          <Field label="Prefer side">
            <Select value={profile!.formation.side} onChange={(event) => edit((draft) => { draft.formation.side = event.target.value as BattleProfile["formation"]["side"]; })}>
              <option value="auto">Auto</option>
              <option value="left">Left</option>
              <option value="right">Right</option>
            </Select>
          </Field>
          <NumberField label="Arc (degrees)" value={profile!.formation.arc} min={40} max={300} onChange={(value) => edit((draft) => { draft.formation.arc = value; })} />
        </div>
        <div className="form-grid two">
          <NumberField label="Spacing (yalms)" value={profile!.formation.spacing} min={1.4} max={6} step={0.1} onChange={(value) => edit((draft) => { draft.formation.spacing = value; })} />
          <Field label="Weapon skill at 1000 TP" hint="Leave empty to keep TP and never use a skill automatically.">
            <TextInput value={profile!.engage.weapon_skill} onChange={(event) => edit((draft) => { draft.engage.weapon_skill = event.target.value; })} />
          </Field>
        </div>

        <h3 className="battle-subhead">Puller</h3>
        <Check checked={profile!.pull.enabled} title="Pull for the party" onChange={(value) => edit((draft) => { draft.pull.enabled = value; })} />
        <div className="form-grid three">
          <Field label="Method">
            <Select value={profile!.pull.method} onChange={(event) => edit((draft) => { draft.pull.method = event.target.value as BattleProfile["pull"]["method"]; })}>
              <option value="ranged">Ranged attack</option>
              <option value="spell">Spell</option>
              <option value="ability">Job ability</option>
              <option value="melee">Melee pull</option>
            </Select>
          </Field>
          <NumberField label="Max mobs at camp" value={profile!.pull.max_mobs} min={1} max={12} onChange={(value) => edit((draft) => { draft.pull.max_mobs = value; })} />
          <NumberField label="Leash (yalms)" value={profile!.pull.leash} min={5} max={100} onChange={(value) => edit((draft) => { draft.pull.leash = value; })} />
        </div>
        {profile!.pull.method === "spell" && (
          <Field label="Pull spell">
            <TextInput value={profile!.pull.spell} onChange={(event) => edit((draft) => { draft.pull.spell = event.target.value; })} />
          </Field>
        )}
        {profile!.pull.method === "ability" && (
          <Field label="Pull ability">
            <TextInput value={profile!.pull.ability} onChange={(event) => edit((draft) => { draft.pull.ability = event.target.value; })} />
          </Field>
        )}
        <div className="form-grid two">
          <Field label="Sleep spell" hint="Used on extra mobs that reach the camp.">
            <TextInput value={profile!.pull.sleep_spell} onChange={(event) => edit((draft) => { draft.pull.sleep_spell = event.target.value; })} />
          </Field>
          <Field label="Bind spell">
            <TextInput value={profile!.pull.bind_spell} onChange={(event) => edit((draft) => { draft.pull.bind_spell = event.target.value; })} />
          </Field>
        </div>
        <Check checked={profile!.pull.sleep_extras} title="Sleep/bind extras at camp" onChange={(value) => edit((draft) => { draft.pull.sleep_extras = value; })} />
        <NumberField label="Puller search distance (yalms)" value={profile!.pull.find_distance} min={5} max={100} onChange={(value) => edit((draft) => { draft.pull.find_distance = value; })} />
        <p className="battle-hint">Measured from the camp. The puller will not travel farther to find a mob.</p>

        <div className="battle-subhead-row">
          <h3 className="battle-subhead">Mobs to pull</h3>
          <span className="battle-hint">{profile!.pull.mobs.length ? `${profile!.pull.mobs.length} selected` : "Any mob"}</span>
        </div>
        <p className="battle-hint">Leave empty to pull any mob. Nearby mobs come from the live client; click a name to allow only those names.</p>
        <div className="battle-mob-grid">
          {nearbyMobs.length === 0 && <span className="battle-hint">No live mobs detected nearby right now.</span>}
          {nearbyMobs.map((mob) => {
            const selected = profile!.pull.mobs.some((item) => item.toLowerCase() === mob.name.toLowerCase());
            return (
              <button
                type="button"
                key={mob.name}
                className={cn("battle-mob", selected && "on")}
                onClick={() => togglePullMob(mob.name)}
                title={selected ? "Remove from the pull list" : "Only pull this mob"}
              >
                <span>{mob.name}</span>
                <small>{mob.distance}y{mob.count > 1 ? ` ×${mob.count}` : ""}</small>
              </button>
            );
          })}
        </div>
        {profile!.pull.mobs.length > 0 && (
          <div className="battle-mob-selected">
            {profile!.pull.mobs.map((name) => (
              <button type="button" className="battle-mob-chip" key={name} onClick={() => togglePullMob(name)} title="Remove">
                {name}
                <X size={12} />
              </button>
            ))}
          </div>
        )}
        <div className="battle-mob-add">
          <TextInput
            value={mobDraft}
            placeholder="Add a mob name"
            onChange={(event) => setMobDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addPullMob();
              }
            }}
          />
          <Button size="sm" variant="secondary" icon={<Plus size={14} />} onClick={addPullMob}>
            Add name
          </Button>
        </div>
      </>
    );
  }

  function renderRules() {
    return (
      <>
        <h3 className="battle-subhead">Priority</h3>
        <p className="battle-hint">Each tick asks these in order; the first ready step acts.</p>
        <div className="battle-priority">
          {profile!.priority.map((key, index) => (
            <div className="battle-priority-row" key={key}>
              <Badge tone="accent">{index + 1}</Badge>
              <strong>{key === "heal" ? "Healing" : key === "buff" ? "Buffs" : key === "enfeeble" ? "Enfeebling" : "Dispelling"}</strong>
              <Button
                size="sm"
                variant="ghost"
                disabled={index === 0}
                onClick={() =>
                  edit((draft) => {
                    const list = draft.priority;
                    [list[index - 1], list[index]] = [list[index], list[index - 1]];
                  })
                }
              >
                Up
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={index === profile!.priority.length - 1}
                onClick={() =>
                  edit((draft) => {
                    const list = draft.priority;
                    [list[index + 1], list[index]] = [list[index], list[index + 1]];
                  })
                }
              >
                Down
              </Button>
            </div>
          ))}
        </div>

        <h3 className="battle-subhead">Death</h3>
        <div className="form-grid three">
          <Field label="On K.O.">
            <Select value={profile!.death.mode} onChange={(event) => edit((draft) => { draft.death.mode = event.target.value as BattleProfile["death"]["mode"]; })}>
              <option value="raise">Wait for raise / recovery</option>
              <option value="homepoint">Return to home point</option>
            </Select>
          </Field>
          <NumberField label="Wait (seconds)" value={profile!.death.wait} min={0} max={600} onChange={(value) => edit((draft) => { draft.death.wait = value; })} />
          <NumberField label="Home point number" value={profile!.death.home_point} min={1} max={128} onChange={(value) => edit((draft) => { draft.death.home_point = value; })} />
        </div>
        <p className="battle-hint">This server recovers a K.O.'d character after six seconds; home point mode sends //hp as soon as death is seen.</p>

        <h3 className="battle-subhead">Kiting</h3>
        <Check checked={profile!.kiting.enabled} title="Kiter runs the kite" onChange={(value) => edit((draft) => { draft.kiting.enabled = value; })} />
        <div className="form-grid three">
          <Field label="Mode">
            <Select value={profile!.kiting.mode} onChange={(event) => edit((draft) => { draft.kiting.mode = event.target.value as BattleProfile["kiting"]["mode"]; })}>
              <option value="circle">Circle the camp</option>
              <option value="away">Run away from the mob</option>
              <option value="camp">Hold camp</option>
            </Select>
          </Field>
          <NumberField label="Radius" value={profile!.kiting.radius} min={5} max={60} onChange={(value) => edit((draft) => { draft.kiting.radius = value; })} />
          <NumberField label="Kite at player HP%" value={profile!.kiting.below} min={0} max={100} onChange={(value) => edit((draft) => { draft.kiting.below = value; })} />
        </div>

        <h3 className="battle-subhead">Loot</h3>
        <Field label="Distribution policy">
          <Select value={profile!.loot.mode} onChange={(event) => edit((draft) => { draft.loot.mode = event.target.value as BattleProfile["loot"]["mode"]; })}>
            <option value="free">Free lot</option>
            <option value="lot">Lot everything</option>
            <option value="pass">Pass everything</option>
            <option value="leader">Leader distributes</option>
          </Select>
        </Field>
        <p className="battle-hint">
          This build's server has no item drops or treasure pool yet. The policy is saved with the
          profile for when the pool exists; the engine never sends a blind /lot.
        </p>
      </>
    );
  }

  function renderSpells() {
    return (
      <>
        <div className="battle-subhead-row">
          <h3 className="battle-subhead">Healing</h3>
          <Button size="sm" variant="secondary" icon={<Sparkles size={14} />} onClick={() => void suggest("heal")}>
            Suggest from job
          </Button>
        </div>
        <Check checked={profile!.heal.enabled} title="Heal the party" onChange={(value) => edit((draft) => { draft.heal.enabled = value; })} />
        <div className="form-grid three">
          <Field label="Observe">
            <Select value={profile!.heal.observe} onChange={(event) => edit((draft) => { draft.heal.observe = event.target.value as BattleProfile["heal"]["observe"]; })}>
              <option value="party">Party only</option>
              <option value="alliance">Party + alliance</option>
            </Select>
          </Field>
          <NumberField label="Emergency %" value={profile!.heal.emergency} min={1} max={100} onChange={(value) => edit((draft) => { draft.heal.emergency = value; })} />
          <NumberField label="MP reserve %" value={profile!.heal.mp_reserve} min={0} max={100} onChange={(value) => edit((draft) => { draft.heal.mp_reserve = value; })} />
        </div>
        <Check
          checked={profile!.heal.waltz ?? true}
          title="Use Curing Waltz for HP"
          body="Dancer main or sub job; the waltz spends TP instead of MP."
          onChange={(value) => edit((draft) => { draft.heal.waltz = value; })}
        />
        <Check
          checked={profile!.heal.waltz_status ?? true}
          title="Use Healing Waltz for status effects"
          body="Removes one waltzable status per 200 TP."
          onChange={(value) => edit((draft) => { draft.heal.waltz_status = value; })}
        />
        <div className="form-grid three">
          <NumberField label="Waltz below %" value={profile!.heal.waltz_below ?? 75} min={1} max={100} onChange={(value) => edit((draft) => { draft.heal.waltz_below = value; })} />
          <NumberField label="Keep TP" value={profile!.heal.waltz_tp_reserve ?? 0} min={0} max={3000} step={100} onChange={(value) => edit((draft) => { draft.heal.waltz_tp_reserve = value; })} />
          <div />
        </div>
        <div className="battle-table">
          <div className="battle-table-head"><span>Cure spell</span><span>Use at or below HP%</span><span /></div>
          {profile!.heal.cures.map((row) => (
            <div className="battle-table-row" key={row.id}>
              <TextInput value={row.spell} onChange={(event) => edit((draft) => { const item = draft.heal.cures.find((entry) => entry.id === row.id); if (item) item.spell = event.target.value; })} />
              <TextInput type="number" value={row.below} onChange={(event) => edit((draft) => { const item = draft.heal.cures.find((entry) => entry.id === row.id); if (item) item.below = numberOr(event.target.value, item.below); })} />
              <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => edit((draft) => { draft.heal.cures = draft.heal.cures.filter((entry) => entry.id !== row.id); })} />
            </div>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus size={14} />} onClick={() => edit((draft) => { draft.heal.cures.push({ id: nextRowId(draft), spell: "", below: 50 }); })}>
            Add cure
          </Button>
        </div>
        <Check checked={profile!.heal.status} title="Remove status effects with -na spells" onChange={(value) => edit((draft) => { draft.heal.status = value; })} />
        <Check checked={profile!.heal.erase} title="Use Erase for anything the -na list cannot name" onChange={(value) => edit((draft) => { draft.heal.erase = value; })} />
        <div className="form-grid two">
          <Field label="Raise spell" hint="Saved for the engine's death policy; this server currently recovers on its own.">
            <TextInput value={profile!.heal.raise_spell} onChange={(event) => edit((draft) => { draft.heal.raise_spell = event.target.value; })} />
          </Field>
          <Field label="Never cast">
            <TextInput value={profile!.heal.avoid} placeholder="Cure VI, Curaga" onChange={(event) => edit((draft) => { draft.heal.avoid = event.target.value; })} />
          </Field>
        </div>

        <div className="battle-subhead-row">
          <h3 className="battle-subhead">Buffs</h3>
          <Button size="sm" variant="secondary" icon={<Sparkles size={14} />} onClick={() => void suggest("buff")}>
            Suggest from job
          </Button>
        </div>
        <div className="battle-table">
          <div className="battle-table-head"><span>Spell</span><span>Target</span><span>Refresh (s)</span><span /></div>
          {profile!.buffs.rows.map((row) => (
            <div className="battle-table-row" key={row.id}>
              <TextInput value={row.spell} onChange={(event) => edit((draft) => { const item = draft.buffs.rows.find((entry) => entry.id === row.id); if (item) item.spell = event.target.value; })} />
              <Select value={row.target ?? "self"} onChange={(event) => edit((draft) => { const item = draft.buffs.rows.find((entry) => entry.id === row.id); if (item) item.target = event.target.value as "self" | "party" | "alliance"; })}>
                <option value="self">Self</option>
                <option value="party">Party</option>
                <option value="alliance">Alliance</option>
              </Select>
              <TextInput type="number" value={row.interval ?? 300} onChange={(event) => edit((draft) => { const item = draft.buffs.rows.find((entry) => entry.id === row.id); if (item) item.interval = numberOr(event.target.value, item.interval ?? 300); })} />
              <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => edit((draft) => { draft.buffs.rows = draft.buffs.rows.filter((entry) => entry.id !== row.id); })} />
            </div>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus size={14} />} onClick={() => edit((draft) => { draft.buffs.rows.push({ id: nextRowId(draft), spell: "", target: "self", interval: 300 }); })}>
            Add buff
          </Button>
        </div>

        <div className="battle-subhead-row">
          <h3 className="battle-subhead">Enfeebles & dispel</h3>
          <Button size="sm" variant="secondary" icon={<Sparkles size={14} />} onClick={() => void suggest("enfeeble")}>
            Suggest from job
          </Button>
        </div>
        <div className="battle-table">
          <div className="battle-table-head"><span>Spell</span><span>Reapply (s)</span><span /></div>
          {profile!.enfeebles.rows.map((row) => (
            <div className="battle-table-row" key={row.id}>
              <TextInput value={row.spell} onChange={(event) => edit((draft) => { const item = draft.enfeebles.rows.find((entry) => entry.id === row.id); if (item) item.spell = event.target.value; })} />
              <TextInput type="number" value={row.interval ?? 120} onChange={(event) => edit((draft) => { const item = draft.enfeebles.rows.find((entry) => entry.id === row.id); if (item) item.interval = numberOr(event.target.value, item.interval ?? 120); })} />
              <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => edit((draft) => { draft.enfeebles.rows = draft.enfeebles.rows.filter((entry) => entry.id !== row.id); })} />
            </div>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus size={14} />} onClick={() => edit((draft) => { draft.enfeebles.rows.push({ id: nextRowId(draft), spell: "", interval: 120 }); })}>
            Add enfeeble
          </Button>
        </div>
        <div className="form-grid two">
          <Field label="Dispel spell">
            <TextInput value={profile!.dispel.spell} onChange={(event) => edit((draft) => { draft.dispel.spell = event.target.value; })} />
          </Field>
          <NumberField label="Dispel interval (s)" value={profile!.dispel.interval} min={1} max={3600} onChange={(value) => edit((draft) => { draft.dispel.interval = value; })} />
        </div>
        <Check checked={profile!.dispel.enabled} title="Dispel the current target" onChange={(value) => edit((draft) => { draft.dispel.enabled = value; })} />

        <h3 className="battle-subhead">Support jobs</h3>
        <p className="battle-hint">
          GEO keeps Indi at the support camp and parks the Luopan at the tank camp, running between them to refresh Geo.
          BRD sings the tank set at the tank camp and the support set at the support camp; Nitro means Nightingale + Troubadour.
        </p>
        <Check checked={profile!.support.geo.enabled} title="Run the GEO camp loop" onChange={(value) => edit((draft) => { draft.support.geo.enabled = value; })} />
        <div className="form-grid three">
          <Field label="Indi at support camp">
            <TextInput value={profile!.support.geo.indi} onChange={(event) => edit((draft) => { draft.support.geo.indi = event.target.value; })} />
          </Field>
          <Field label="Geo on Luopan at tank camp">
            <TextInput value={profile!.support.geo.geo} onChange={(event) => edit((draft) => { draft.support.geo.geo = event.target.value; })} />
          </Field>
          <NumberField label="Indi refresh (s)" value={profile!.support.geo.indi_interval} min={30} max={600} onChange={(value) => edit((draft) => { draft.support.geo.indi_interval = value; })} />
        </div>
        <NumberField label="Geo refresh (s)" value={profile!.support.geo.geo_interval} min={30} max={600} onChange={(value) => edit((draft) => { draft.support.geo.geo_interval = value; })} />

        <Check checked={profile!.support.brd.enabled} title="Run the BRD camp song cycle" onChange={(value) => edit((draft) => { draft.support.brd.enabled = value; })} />
        <div className="form-grid two">
          <Field label="Tank camp songs" hint="Victory March, Valor Minuet V, Blade Madrigal">
            <TextInput value={profile!.support.brd.tank_songs} onChange={(event) => edit((draft) => { draft.support.brd.tank_songs = event.target.value; })} />
          </Field>
          <Field label="Support camp songs" hint="Mages Ballad III, Advancing March">
            <TextInput value={profile!.support.brd.support_songs} onChange={(event) => edit((draft) => { draft.support.brd.support_songs = event.target.value; })} />
          </Field>
        </div>
        <div className="form-grid three">
          <Field label="Pianissimo on tank">
            <TextInput value={profile!.support.brd.piano_tank} onChange={(event) => edit((draft) => { draft.support.brd.piano_tank = event.target.value; })} />
          </Field>
          <Field label="Pianissimo on support">
            <TextInput value={profile!.support.brd.piano_support} onChange={(event) => edit((draft) => { draft.support.brd.piano_support = event.target.value; })} />
          </Field>
          <Field label="Nitro">
            <Select value={profile!.support.brd.nitro} onChange={(event) => edit((draft) => { draft.support.brd.nitro = event.target.value as BattleProfile["support"]["brd"]["nitro"]; })}>
              <option value="both">Both camps (on tank set)</option>
              <option value="tank">Tank set only</option>
              <option value="support">Support set only</option>
              <option value="off">Never</option>
            </Select>
          </Field>
        </div>
        <NumberField label="Song refresh (s)" value={profile!.support.brd.interval} min={30} max={600} onChange={(value) => edit((draft) => { draft.support.brd.interval = value; })} />
      </>
    );
  }

  function renderProfiles() {
    const s = state!;
    return (
      <>
        <p className="battle-hint">
          `//battle save` writes the profile under the client's data folder as
          <code> battle/&lt;character&gt;/&lt;name&gt;.json</code>; this page edits the same object.
        </p>
        <div className="battle-profile-actions">
          <Button size="sm" variant="secondary" icon={<Plus size={14} />} onClick={() => void send("new", { action: "new", name: "" }, { message: "Started a new profile." })}>
            New profile
          </Button>
          <Button size="sm" variant="secondary" icon={<RefreshCw size={14} />} onClick={() => void refresh()}>
            Reload from client
          </Button>
        </div>
        <div className="battle-profile-list">
          {s.profiles.length === 0 && <p className="battle-hint">No saved profiles for this character yet.</p>}
          {s.profiles.map((item) => (
            <div className="battle-profile-row" key={item.file}>
              <div>
                <strong>{item.name}</strong>
                <small>{item.zone_name || `zone ${item.zone}`} · {new Date(item.updated * 1000).toLocaleString()}</small>
              </div>
              <div className="battle-actions">
                <Button size="sm" variant="secondary" onClick={() => void send("load", { action: "load", name: item.name }, { message: `Loaded "${item.name}".` })}>
                  Load
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Trash2 size={14} />}
                  onClick={() => {
                    if (!window.confirm(`Delete the battle profile "${item.name}"?`)) return;
                    void send("delete", { action: "delete", name: item.name }, { message: `Deleted "${item.name}".` });
                  }}
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      </>
    );
  }

  return (
    <div className="page">
      <SectionHeader
        eyebrow="Battle"
        title="Battle hub"
        subtitle={`${instance.character?.name ?? "client"} on control port ${instance.port}. The same profile drives the in-game //battle hub.`}
        actions={
          <>
            <Button
              variant={status.running ? "danger" : "primary"}
              size="sm"
              icon={status.running ? <Square size={14} /> : <Swords size={14} />}
              loading={busy === "start" || busy === "stop"}
              onClick={() => (status.running ? void send("stop", { action: "stop" }, { keepDirty: true }) : void startBattle())}
            >
              {status.running ? "Stop" : "Start"}
            </Button>
            <Button size="sm" variant="secondary" icon={status.visible ? <EyeOff size={14} /> : <Eye size={14} />} onClick={() => void send("hub", { action: status.visible ? "hide" : "show" }, { keepDirty: true })}>
              {status.visible ? "Hide in-game hub" : "Show in-game hub"}
            </Button>
            <Button size="sm" variant="secondary" icon={<RefreshCw size={14} />} onClick={() => void refresh()}>
              Reload
            </Button>
          </>
        }
      />

      {error && <div className="banner banner-error">{error}</div>}

      <Card className="battle-status-card">
        <div className="battle-status-top">
          <div>
            <Badge tone={status.running ? "success" : "neutral"} dot>
              {status.running ? "Running" : "Stopped"}
            </Badge>
            {status.dead && <Badge tone="danger">K.O.</Badge>}
            {status.role_label && <Badge tone="accent">{status.role_label}</Badge>}
            {status.paused.length > 0 && <Badge tone="warning">paused: {status.paused.join(", ")}</Badge>}
            <Badge tone="neutral">{roleCount} assigned</Badge>
            {dirty && <Badge tone="warning">unsaved edits</Badge>}
          </div>
          <div className="battle-status-target">
            <Target size={14} />
            {status.target ? (
              <span>{status.target.name} · {Math.round(status.target.hpp)}%{status.target.claimed_by ? ` · ${status.target.claimed_by}` : ""}</span>
            ) : (
              <span>no target</span>
            )}
          </div>
        </div>
        <div className="battle-status-grid">
          <div><span>Profile</span><strong>{profile.name || "unsaved"}</strong></div>
          <div><span>Camp</span><strong>{status.camp ? `${status.camp.x.toFixed(1)}, ${status.camp.y.toFixed(1)} · ${status.camp.radius.toFixed(0)}y` : "not set"}</strong></div>
          <div><span>Last action</span><strong>{status.last_action || "—"}</strong></div>
          <div><span>Ground projection</span><strong>{status.projection ? "available" : "unavailable (no camera)"}</strong></div>
        </div>
        {status.notes.length > 0 && (
          <div className="battle-notes">
            {status.notes.slice(-5).map((note, index) => (
              <div key={`${note.at}-${index}`} className={cn("battle-note", note.kind)}>{note.text}</div>
            ))}
          </div>
        )}
      </Card>

      <Card className="battle-editor">
        <div className="battle-editor-bar">
          <div className="battle-name">
            <Field label="Profile name" hint="Default is the zone and a timestamp; rename it here or with //battle save <name>.">
              <TextInput value={profile.name} onChange={(event) => edit((draft) => { draft.name = event.target.value; })} />
            </Field>
          </div>
          <div className="battle-actions">
            <Button size="sm" variant="ghost" icon={<RotateCcw size={14} />} onClick={() => void applyProfile()} loading={busy === "apply"}>
              Apply live
            </Button>
            <Button size="sm" variant="primary" icon={<Save size={14} />} onClick={() => void saveProfile()} loading={busy === "save"}>
              Save
            </Button>
          </div>
        </div>

        <div className="battle-tabs">
          {TABS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={cn("battle-tab", tab === item.key && "on")}
              onClick={() => setTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="battle-editor-body">
          {tab === "roster" && renderRoster()}
          {tab === "camp" && renderCamp()}
          {tab === "rules" && renderRules()}
          {tab === "spells" && renderSpells()}
          {tab === "profiles" && renderProfiles()}
        </div>
      </Card>
    </div>
  );
}
