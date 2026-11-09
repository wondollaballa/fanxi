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
import type {
  BattleMobCatalog,
  BattleProfile,
  BattleSongGroup,
  BattleSpellOption,
  BattleState,
  BattleSupportAbility,
  BattleWeaponSkill,
  InstanceView,
  JobAbility,
  JobSpell,
  Tenant,
} from "../types";
import { backend } from "../lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Modal,
  SectionHeader,
  Select,
  TextInput,
  cn,
} from "./ui";
import {
  BattleActionDialog,
  BattleActionPick,
  abilityActionEntries,
  spellActionEntries,
  type BattleActionEntry,
  type BattleActionKind,
} from "./BattleActionPicker";

type Notify = (message: string, kind?: "success" | "error" | "info") => void;

type TabKey = "roster" | "camp" | "rules" | "spells" | "support" | "skillchain" | "profiles";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "roster", label: "Roster" },
  { key: "camp", label: "Camp & engage" },
  { key: "rules", label: "Rules" },
  { key: "spells", label: "Healing & spells" },
  { key: "support", label: "Support" },
  { key: "skillchain", label: "Skillchain" },
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
  "CHM",
];

type PickerSource =
  | "spell"
  | "ability"
  | "any"
  | "song"
  | "roll"
  | "indi"
  | "geo"
  | "weapon_skill"
  | "all_spells"
  | "mob_move";

/** One open picker.  A multi picker returns a whole set of names (songs, watched moves). */
type PickerRequest = {
  source: PickerSource;
  title: string;
  subtitle: string;
  mode: "single" | "multi";
  value?: string;
  values?: string[];
  emptyHint?: string;
  onSelect?: (name: string, kind: BattleActionKind) => void;
  onConfirm?: (names: string[]) => void;
};

/** The two client lists the picker reads: the same main/sub job lists the Gear page uses. */
type ActionCatalog = {
  spells: JobSpell[];
  abilities: JobAbility[];
  main: number;
  mainLevel: number;
  sub: number;
  subLevel: number;
};

const SKILLCHAINS = [
  "Any", "Transfixion", "Compression", "Liquefaction", "Scission", "Reverberation",
  "Detonation", "Induration", "Impaction", "Gravitation", "Distortion", "Fusion",
  "Fragmentation", "Light", "Darkness", "Light II", "Darkness II",
];

const SPELL_SKILL_LABELS: Record<number, string> = {
  32: "Divine Magic", 33: "Healing Magic", 34: "Enhancing Magic", 35: "Enfeebling Magic",
  36: "Elemental Magic", 37: "Dark Magic", 38: "Summoning Magic", 39: "Ninjutsu",
  40: "Singing", 41: "String Instrument", 42: "Wind Instrument", 43: "Blue Magic",
  44: "Geomancy", 45: "Handbell",
};

const WEAPON_SKILL_LABELS: Record<number, string> = {
  1: "Hand-to-hand", 2: "Dagger", 3: "Sword", 4: "Great sword", 5: "Axe",
  6: "Great axe", 7: "Scythe", 8: "Polearm", 9: "Katana", 10: "Great katana",
  11: "Club", 12: "Staff", 25: "Archery", 26: "Marksmanship", 27: "Throwing",
};

function splitNames(value: string): string[] {
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

function joinNames(names: string[]): string {
  return names.join(", ");
}

function catalogJobLabel(catalog: ActionCatalog | null): string {
  if (!catalog || catalog.main <= 0) return "";
  const name = (job: number) => JOB_ABBR[job] ?? `Job ${job}`;
  const sub = catalog.sub > 0 ? ` / ${name(catalog.sub)} ${catalog.subLevel}` : "";
  return `${name(catalog.main)} ${catalog.mainLevel}${sub}`;
}

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
  const [picker, setPicker] = useState<PickerRequest | null>(null);
  const [catalog, setCatalog] = useState<ActionCatalog | null>(null);
  const [catalogErrors, setCatalogErrors] = useState({ spells: "", abilities: "" });
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [weaponSkills, setWeaponSkills] = useState<BattleWeaponSkill[]>([]);
  const [weaponSkillsLoading, setWeaponSkillsLoading] = useState(false);
  const [weaponSkillsError, setWeaponSkillsError] = useState("");
  const [allSpells, setAllSpells] = useState<BattleSpellOption[]>([]);
  const [allSpellsLoading, setAllSpellsLoading] = useState(false);
  const [allSpellsError, setAllSpellsError] = useState("");
  const [mobCatalog, setMobCatalog] = useState<BattleMobCatalog | null>(null);
  const [mobLoading, setMobLoading] = useState(false);
  const [mobError, setMobError] = useState("");
  const [saveAsOpen, setSaveAsOpen] = useState(false);
  const [saveAsName, setSaveAsName] = useState("");
  const catalogSeq = useRef(0);
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
  const pickerEntries = useMemo<BattleActionEntry[]>(() => {
    if (!picker) return [];
    if (picker.source === "weapon_skill") {
      return weaponSkills
        .map((skill) => ({
          name: skill.name,
          kind: "weapon_skill" as const,
          detail: `${WEAPON_SKILL_LABELS[skill.skill] ?? "Weapon"}${skill.skill_level > 0 ? ` · Lv ${skill.skill_level}` : ""}`,
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
    }
    if (picker.source === "all_spells") {
      return allSpells
        .map((spell) => ({
          name: spell.name,
          kind: "spell" as const,
          detail: SPELL_SKILL_LABELS[spell.skill] ?? (spell.skill > 0 ? `Skill ${spell.skill}` : "Spell"),
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
    }
    if (picker.source === "mob_move") {
      return (mobCatalog?.moves ?? [])
        .filter((move) => move.dispellable)
        .map((move) => ({
          name: move.name,
          kind: "move" as const,
          detail: `${move.description}${move.mobs.length ? ` · ${move.mobs.join(", ")}` : ""}`,
        }));
    }
    if (!catalog) return [];
    const spells = spellActionEntries(catalog.spells);
    if (picker.source === "ability") return abilityActionEntries(catalog.abilities);
    if (picker.source === "any") {
      return [...spells, ...abilityActionEntries(catalog.abilities)];
    }
    if (picker.source === "song") return spells.filter((entry) => entry.kind === "song");
    if (picker.source === "roll") {
      return abilityActionEntries(catalog.abilities).filter((entry) =>
        entry.name.toLowerCase().endsWith(" roll"),
      );
    }
    if (picker.source === "indi") {
      return spells.filter((entry) => entry.name.toLowerCase().startsWith("indi-"));
    }
    if (picker.source === "geo") {
      return spells.filter((entry) => entry.name.toLowerCase().startsWith("geo-"));
    }
    return spells;
  }, [allSpells, catalog, mobCatalog, picker, weaponSkills]);

  const pickerLoading =
    picker?.source === "weapon_skill"
      ? weaponSkillsLoading
      : picker?.source === "all_spells"
        ? allSpellsLoading
        : picker?.source === "mob_move"
          ? mobLoading
          : catalogLoading;
  const pickerError =
    picker?.source === "weapon_skill"
      ? weaponSkillsError
      : picker?.source === "all_spells"
        ? allSpellsError
        : picker?.source === "mob_move"
          ? mobError
          : picker?.source === "ability"
            ? catalogErrors.abilities
            : catalogErrors.spells;
  const pickerValue = picker?.value ?? "";

  function togglePullMob(name: string) {
    edit((draft) => {
      const at = draft.pull.mobs.findIndex((item) => item.toLowerCase() === name.toLowerCase());
      if (at >= 0) draft.pull.mobs.splice(at, 1);
      else if (draft.pull.mobs.length < 40) draft.pull.mobs.push(name);
    });
  }

  function setPullField(field: "spell" | "ability" | "sleep_spell" | "bind_spell", name: string) {
    edit((draft) => {
      draft.pull[field] = name;
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

  /** Read the running client's main/sub job lists.  The Gear page uses the same two calls;
   * the Battle page reuses them so a picked spell or ability is always one this job pair has. */
  async function loadActionCatalog() {
    if (!port) return;
    const seq = ++catalogSeq.current;
    setCatalogLoading(true);
    setCatalogErrors({ spells: "", abilities: "" });
    const [spellResult, abilityResult] = await Promise.allSettled([
      backend.gearJobSpells(port),
      backend.gearJobAbilities(port),
    ]);
    if (seq !== catalogSeq.current) return;
    const spells = spellResult.status === "fulfilled" ? spellResult.value.spells ?? [] : [];
    const abilityReply = abilityResult.status === "fulfilled" ? abilityResult.value : null;
    const reason = (result: PromiseRejectedResult) =>
      result.reason instanceof Error ? result.reason.message : String(result.reason);
    setCatalog({
      spells,
      abilities: abilityReply?.abilities ?? [],
      main: Number(abilityReply?.main ?? 0),
      mainLevel: Number(abilityReply?.main_level ?? 0),
      sub: Number(abilityReply?.sub ?? 0),
      subLevel: Number(abilityReply?.sub_level ?? 0),
    });
    setCatalogErrors({
      spells: spellResult.status === "rejected" ? `Spell list: ${reason(spellResult)}` : "",
      abilities: abilityResult.status === "rejected" ? `Ability list: ${reason(abilityResult)}` : "",
    });
    setCatalogLoading(false);
  }

  async function loadWeaponSkills(force = false) {
    if (!force && weaponSkills.length > 0) return;
    setWeaponSkillsLoading(true);
    setWeaponSkillsError("");
    try {
      const reply = await backend.battleWeaponSkills();
      setWeaponSkills(reply.weapon_skills ?? []);
    } catch (caught) {
      setWeaponSkillsError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setWeaponSkillsLoading(false);
    }
  }

  async function loadAllSpells(force = false) {
    if (!force && allSpells.length > 0) return;
    setAllSpellsLoading(true);
    setAllSpellsError("");
    try {
      const reply = await backend.battleSpells();
      setAllSpells(reply.spells ?? []);
    } catch (caught) {
      setAllSpellsError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setAllSpellsLoading(false);
    }
  }

  async function loadMobMoves() {
    if (!profile) return;
    const names = profile.pull.mobs;
    setMobError("");
    if (names.length === 0) {
      setMobCatalog({ moves: [], unmatched: [] });
      return;
    }
    setMobLoading(true);
    try {
      const reply = await backend.battleMobMoves(names, profile.zone);
      setMobCatalog(reply);
      if (reply.unmatched.length > 0) {
        setMobError(`No move list for ${reply.unmatched.join(", ")} in this zone.`);
      }
    } catch (caught) {
      setMobCatalog({ moves: [], unmatched: [] });
      setMobError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setMobLoading(false);
    }
  }

  function openPicker(request: PickerRequest) {
    setPicker(request);
    if (request.source === "weapon_skill") {
      void loadWeaponSkills();
    } else if (request.source === "all_spells") {
      void loadAllSpells();
    } else if (request.source === "mob_move") {
      void loadMobMoves();
    } else {
      void loadActionCatalog();
    }
  }

  function openSinglePicker(
    source: PickerSource,
    title: string,
    subtitle: string,
    value: string,
    onSelect: (name: string, kind: BattleActionKind) => void,
  ) {
    openPicker({ source, title, subtitle, mode: "single", value, onSelect });
  }

  function openMultiPicker(
    source: PickerSource,
    title: string,
    subtitle: string,
    values: string[],
    onConfirm: (names: string[]) => void,
    emptyHint?: string,
  ) {
    openPicker({ source, title, subtitle, mode: "multi", values, onConfirm, emptyHint });
  }

  useEffect(() => {
    catalogSeq.current += 1;
    setPicker(null);
    setCatalog(null);
    setCatalogErrors({ spells: "", abilities: "" });
    setCatalogLoading(false);
    setMobCatalog(null);
    setMobLoading(false);
    setMobError("");
    setSaveAsOpen(false);
    setSaveAsName("");
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

  function teamTargets(): InstanceView[] {
    const roster = new Set<string>();
    if (profile) {
      for (const name of [
        profile.roster.tank,
        profile.roster.puller,
        profile.roster.kiter,
        ...profile.roster.support,
        ...profile.roster.melee,
        ...profile.roster.ranged,
      ]) {
        if (name) roster.add(name.toLowerCase());
      }
    }
    const alive = instances.filter((item) => item.alive);
    const assigned = alive.filter((item) => {
      const name = item.character?.name ?? "";
      return name !== "" && roster.has(name.toLowerCase());
    });
    if (assigned.length > 0) return assigned;
    return instance ? [instance] : alive;
  }

  async function startTeam() {
    if (!profile) return;
    if (dirty) {
      const applied = await send("apply", { action: "update", profile }, { keepDirty: true });
      if (!applied) return;
    }
    const targets = teamTargets();
    const runId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    setBusy("start");
    setError("");
    // The shared sections belong to the team, not to whichever tenant happens to be
    // selected.  Prefer the current profile when it already has a tank and puller;
    // otherwise take the richest team profile from the server (the main's saved roster).
    const assignedCount = (value: BattleProfile) => {
      const roster = value.roster;
      let count = (roster.tank ? 1 : 0) + (roster.puller ? 1 : 0) + (roster.kiter ? 1 : 0);
      for (const key of ["support", "melee", "ranged"] as const) count += roster[key]?.length ?? 0;
      return count;
    };
    const hasCommand = (value: BattleProfile) => value.roster.tank !== "" && value.roster.puller !== "";
    let source = profile;
    if (!hasCommand(source)) {
      try {
        const team = await backend.battleTeamProfiles();
        const candidates = team.characters
          .map((row) => row.profile)
          .filter((row): row is BattleProfile => row !== null && hasCommand(row))
          .sort((a, b) => assignedCount(b) - assignedCount(a));
        if (candidates[0]) source = candidates[0];
      } catch {
        // Keep the selected profile when the team API is unavailable.
      }
    }
    if (!hasCommand(source)) {
      const message = "No tank and puller are assigned. Set them in Roster, save, then press Start team.";
      setError(message);
      notify(message, "error");
      setBusy(null);
      return;
    }
    // Push the shared sections into every assigned client before starting it, otherwise a
    // freshly restarted box still has an empty roster and cannot resolve its own role.
    const results = await Promise.allSettled(
      targets.map(async (item) => {
        const current = await backend.battle(item.port, { action: "state" });
        if (!current.profile) throw new Error(`${item.character?.name ?? item.account} has no Battle profile`);
        const merged: BattleProfile = {
          ...current.profile,
          roster: source.roster,
          camp: source.camp,
          support_camp: source.support_camp,
          camp_assign: source.camp_assign,
          combat_style: source.combat_style,
        };
        await backend.battle(item.port, { action: "update", profile: merged });
        return backend.battle(item.port, { action: "start", run_id: runId });
      }),
    );
    const failures = results.filter((result) => result.status === "rejected");
    const failed = failures.length;
    if (failed > 0) {
      const reasons = failures.slice(0, 2).map((result) =>
        result.status === "rejected"
          ? result.reason instanceof Error ? result.reason.message : String(result.reason)
          : "",
      ).filter(Boolean).join("; ");
      const message = `${targets.length - failed}/${targets.length} clients started; ${failed} failed${reasons ? `: ${reasons}` : "."}`;
      setError(message);
      notify(message, "error");
    } else {
      notify(`Battle started on ${targets.length} client${targets.length === 1 ? "" : "s"}; preparing camps and buffs.`, "success");
    }
    setBusy(null);
    await load();
  }

  async function stopTeam() {
    const targets = instances.filter((item) => item.alive);
    if (targets.length === 0 && instance) targets.push(instance);
    setBusy("stop");
    setError("");
    const results = await Promise.allSettled(
      targets.map((item) => backend.battle(item.port, { action: "stop" })),
    );
    const failed = results.filter((result) => result.status === "rejected").length;
    if (failed > 0) {
      notify(`${failed} client${failed === 1 ? "" : "s"} did not stop.`, "error");
    } else {
      notify(`Battle stopped on ${targets.length} client${targets.length === 1 ? "" : "s"}.`, "success");
    }
    setBusy(null);
    await load();
  }

  async function applyProfile() {
    if (!profile) return;
    await send("apply", { action: "update", profile }, { keepDirty: true, message: "Applied to the running client (not saved)." });
  }

  async function switchProfile(name: string) {
    if (!profile || !name || name === profile.name) return;
    if (dirty && !window.confirm(`Discard the unsaved changes and switch to "${name}"?`)) return;
    await send("load", { action: "load", name }, { message: `Switched to battle profile "${name}".` });
  }

  async function saveProfileAs() {
    if (!profile) return;
    const name = saveAsName.trim();
    if (!name) {
      notify("Give the profile a name first.", "error");
      return;
    }
    const exists = state?.profiles.some((item) => item.name === name);
    if (exists && !window.confirm(`Overwrite the saved profile "${name}"?`)) return;
    const next = await send("save", { action: "save_as", profile, name }, { message: `Saved battle profile "${name}" as a copy.` });
    if (next) {
      setSaveAsOpen(false);
      setSaveAsName("");
    }
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
        <div className="form-grid three">
          <NumberField label="Camp radius (yalms)" value={profile!.camp.radius} min={1} max={50} step={0.5} onChange={(value) => edit((draft) => { draft.camp.radius = value; })} />
          <NumberField label="Follow distance (yalms)" value={profile!.camp.follow_distance} min={5} max={30} onChange={(value) => edit((draft) => { draft.camp.follow_distance = value; })} />
          <Field label="Camp circle in game">
            <label className="battle-inline-check">
              <input type="checkbox" checked={profile!.camp.show} onChange={(event) => edit((draft) => { draft.camp.show = event.target.checked; })} />
              <span>Draw the camp ring on the ground</span>
            </label>
          </Field>
        </div>
        <div className="form-grid two">
          <Check
            checked={profile!.camp.mobile}
            title="Mobile camp"
            body="Everyone follows the tank; the BRD keeps one song group and support and melee hear the same songs."
            onChange={(value) => edit((draft) => { draft.camp.mobile = value; })}
          />
          <Check
            checked={profile!.camp.tank_enabled}
            title="The tank sets the camp"
            body="When off, the party holds the saved camp without a tank anchor."
            onChange={(value) => edit((draft) => { draft.camp.tank_enabled = value; })}
          />
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
        <Check
          checked={profile!.formation.follow_tank}
          title="Melee follows the tank"
          body="Formation slots re-anchor as the tank moves instead of staying on the last camp position."
          onChange={(value) => edit((draft) => { draft.formation.follow_tank = value; })}
        />
        <div className="form-grid two">
          <NumberField label="Spacing (yalms)" value={profile!.formation.spacing} min={1.4} max={6} step={0.1} onChange={(value) => edit((draft) => { draft.formation.spacing = value; })} />
          <Field label="Weapon skill at 1000 TP" hint="Leave empty to keep TP and never use a skill automatically.">
            <BattleActionPick
              value={profile!.engage.weapon_skill}
              placeholder="Choose a weapon skill…"
              onClick={() => openSinglePicker("weapon_skill", "Weapon skill", "Search the full weapon-skill catalogue, then click the skill to use at 1000 TP.", profile!.engage.weapon_skill, (name) =>
                edit((draft) => { draft.engage.weapon_skill = name; }),
              )}
            />
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
          <NumberField label="Party leash (yalms)" value={profile!.pull.leash} min={5} max={100} onChange={(value) => edit((draft) => { draft.pull.leash = value; })} />
        </div>
        <p className="battle-hint">
          The leash limits how far the rest of the party chases. The puller may leave camp up to
          the puller search distance, then retraces the waypoints it recorded on the way out.
        </p>
        {profile!.pull.method === "spell" && (
          <Field label="Pull spell" hint="Chosen from this character's spells and songs; no typing.">
            <BattleActionPick
              value={profile!.pull.spell ?? ""}
              placeholder="Choose a spell or song…"
              onClick={() => openSinglePicker("spell", "Pull spell", "Spells and songs this character can cast. Search, then click one to pull with it.", profile!.pull.spell ?? "", (name) => setPullField("spell", name))}
            />
          </Field>
        )}
        {profile!.pull.method === "ability" && (
          <Field label="Pull ability" hint="Chosen from this character's job abilities; no typing.">
            <BattleActionPick
              value={profile!.pull.ability ?? ""}
              placeholder="Choose a job ability…"
              onClick={() => openSinglePicker("ability", "Pull ability", "Job abilities this character can use. Search, then click one to pull with it.", profile!.pull.ability ?? "", (name) => setPullField("ability", name))}
            />
          </Field>
        )}
        <div className="form-grid two">
          <Field label="Sleep spell" hint="Used on extra mobs that reach the camp. Leave empty to skip.">
            <BattleActionPick
              value={profile!.pull.sleep_spell ?? ""}
              placeholder="Choose a sleep spell or song…"
              onClick={() => openSinglePicker("spell", "Sleep spell", "Spells and songs for the extra mobs that reach camp.", profile!.pull.sleep_spell ?? "", (name) => setPullField("sleep_spell", name))}
            />
          </Field>
          <Field label="Bind spell" hint="Used on extra mobs that reach the camp. Leave empty to skip.">
            <BattleActionPick
              value={profile!.pull.bind_spell ?? ""}
              placeholder="Choose a bind spell or song…"
              onClick={() => openSinglePicker("spell", "Bind spell", "Spells and songs for holding an extra mob at camp.", profile!.pull.bind_spell ?? "", (name) => setPullField("bind_spell", name))}
            />
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
              <option value="raise">Wait for raise</option>
              <option value="homepoint">Return to home point</option>
            </Select>
          </Field>
          <NumberField label="Wait (seconds)" value={profile!.death.wait} min={0} max={600} onChange={(value) => edit((draft) => { draft.death.wait = value; })} />
          <NumberField label="Home point number" value={profile!.death.home_point} min={1} max={128} onChange={(value) => edit((draft) => { draft.death.home_point = value; })} />
        </div>
        <p className="battle-hint">The server keeps a K.O.'d character down until a raise lands. A healer with a raise spell raises the party; home point mode sends //hp after the wait.</p>

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
              <BattleActionPick
                value={row.spell}
                placeholder="Choose a cure spell…"
                onClick={() => openSinglePicker("spell", "Cure spell", "Spells and songs this character can cast on the party.", row.spell, (name) =>
                  edit((draft) => {
                    const item = draft.heal.cures.find((entry) => entry.id === row.id);
                    if (item) item.spell = name;
                  }),
                )}
              />
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
          <Field label="Raise spell" hint="A living healer casts this on a fallen party member; the server implements Raise and Arise.">
            <BattleActionPick
              value={profile!.heal.raise_spell}
              placeholder="Choose a raise spell…"
              onClick={() => openSinglePicker("spell", "Raise spell", "Raise, Raise II, Raise III or Arise this healer can cast.", profile!.heal.raise_spell, (name) =>
                edit((draft) => { draft.heal.raise_spell = name; }),
              )}
            />
          </Field>
          <Field label="Never cast" hint="These spells are skipped by healing suggestions and casts.">
            <BattleActionPick
              value={profile!.heal.avoid}
              placeholder="Choose spells to never cast…"
              onClick={() => openMultiPicker("spell", "Never cast", "Pick the spells this healer must skip. Apply to save the set.", splitNames(profile!.heal.avoid), (names) =>
                edit((draft) => { draft.heal.avoid = joinNames(names); }),
              )}
            />
          </Field>
        </div>

        <div className="battle-subhead-row">
          <h3 className="battle-subhead">Buffs</h3>
          <Button size="sm" variant="secondary" icon={<Sparkles size={14} />} onClick={() => void suggest("buff")}>
            Suggest from job
          </Button>
        </div>
        <div className="battle-table battle-table-four">
          <div className="battle-table-head"><span>Spell</span><span>Target</span><span>Refresh (s)</span><span /></div>
          {profile!.buffs.rows.map((row) => (
            <div className="battle-table-row" key={row.id}>
              <BattleActionPick
                value={row.spell}
                label={row.ability ? `[JA] ${row.spell || "Choose a buff…"}` : undefined}
                placeholder="Choose a spell or ability…"
                onClick={() => openSinglePicker("any", "Buff", "Known buff spells and job abilities. Search, then click one.", row.spell, (name, kind) =>
                  edit((draft) => {
                    const item = draft.buffs.rows.find((entry) => entry.id === row.id);
                    if (item) {
                      item.spell = name;
                      item.ability = kind === "ability";
                    }
                  }),
                )}
              />
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
        <div className="form-grid three">
          <Field label="Resist policy" hint="What a row does after each resisted cast.">
            <Select
              value={profile!.enfeebles.max_tries === 0 ? "keep" : "limit"}
              onChange={(event) =>
                edit((draft) => {
                  if (event.target.value === "keep") draft.enfeebles.max_tries = 0;
                  else if (draft.enfeebles.max_tries === 0) draft.enfeebles.max_tries = 3;
                })
              }
            >
              <option value="keep">Keep applying enfeeble</option>
              <option value="limit">Stop after attempts</option>
            </Select>
          </Field>
          {profile!.enfeebles.max_tries > 0 ? (
            <NumberField
              label="Attempts"
              value={profile!.enfeebles.max_tries}
              min={1}
              max={10}
              onChange={(value) => edit((draft) => { draft.enfeebles.max_tries = value; })}
            />
          ) : (
            <div className="battle-hint battle-actions-bottom">No resist limit — the row keeps retrying.</div>
          )}
          <div className="battle-actions battle-actions-bottom">
            <Button size="sm" variant="ghost" icon={<RefreshCw size={14} />} onClick={() => void send("reset-tries", { action: "reset_enfeebles" }, { keepDirty: true, message: "Enfeeble resist counters reset." })}>
              Reset tries
            </Button>
          </div>
        </div>
        <p className="battle-hint">
          Each resist adds one try. "Stop after attempts" stops the row until the wear-off/landing
          log clears it or Reset tries is pressed. "Keep applying" never stops it.
        </p>
        <div className="battle-table">
          <div className="battle-table-head"><span>Spell</span><span>Reapply (s)</span><span /></div>
          {profile!.enfeebles.rows.map((row) => (
            <div className="battle-table-row" key={row.id}>
              <BattleActionPick
                value={row.spell}
                placeholder="Choose an enfeeble…"
                onClick={() => openSinglePicker("spell", "Enfeeble", "Spells and songs this character can cast on the claimed mob.", row.spell, (name) =>
                  edit((draft) => {
                    const item = draft.enfeebles.rows.find((entry) => entry.id === row.id);
                    if (item) item.spell = name;
                  }),
                )}
              />
              <TextInput type="number" value={row.interval ?? 120} onChange={(event) => edit((draft) => { const item = draft.enfeebles.rows.find((entry) => entry.id === row.id); if (item) item.interval = numberOr(event.target.value, item.interval ?? 120); })} />
              <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => edit((draft) => { draft.enfeebles.rows = draft.enfeebles.rows.filter((entry) => entry.id !== row.id); })} />
            </div>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus size={14} />} onClick={() => edit((draft) => { draft.enfeebles.rows.push({ id: nextRowId(draft), spell: "", interval: 120 }); })}>
            Add enfeeble
          </Button>
        </div>
        <div className="form-grid two">
          <Field label="Dispel spell" hint="Dispel, Dispelga or a Bard finale this character knows.">
            <BattleActionPick
              value={profile!.dispel.spell}
              placeholder="Choose a dispel spell…"
              onClick={() => openSinglePicker("spell", "Dispel spell", "Spells and songs this character can cast to strip a mob buff.", profile!.dispel.spell, (name) =>
                edit((draft) => { draft.dispel.spell = name; }),
              )}
            />
          </Field>
          <NumberField label="Dispel interval (s)" value={profile!.dispel.interval} min={1} max={3600} onChange={(value) => edit((draft) => { draft.dispel.interval = value; })} />
        </div>
        <Check checked={profile!.dispel.enabled} title="Dispel the current target" onChange={(value) => edit((draft) => { draft.dispel.enabled = value; })} />
        <Check
          checked={profile!.dispel.reactive}
          title="Dispel reactively when a watched mob buff lands"
          body="The chat log line for the selected move triggers the dispel immediately instead of waiting for the interval."
          onChange={(value) => edit((draft) => { draft.dispel.reactive = value; })}
        />
        <Field
          label="Watched mob self-buffs"
          hint="Only self-buff moves the server stores as dispellable are listed. Select the pull targets above first."
        >
          <BattleActionPick
            value={profile!.dispel.watch.join(", ")}
            placeholder="Choose mob self-buffs to watch…"
            onClick={() =>
              openMultiPicker(
                "mob_move",
                "Reactive dispel watch",
                "Self-buffs used by the selected pull targets. The engine dispels as soon as one lands.",
                profile!.dispel.watch,
                (names) => edit((draft) => { draft.dispel.watch = names; }),
                profile!.pull.mobs.length === 0
                  ? "Select one or more mobs in Mobs to pull first; their move lists come from the server."
                  : "No dispellable self-buff was found for the selected mobs.",
              )
            }
          />
        </Field>
        {profile!.dispel.watch.length > 0 ? (
          <div className="battle-mob-selected">
            {profile!.dispel.watch.map((name) => (
              <span className="battle-mob-chip" key={name}>
                {name}
              </span>
            ))}
          </div>
        ) : null}
        <Check
          checked={profile!.dispel.stymie}
          title="Use Stymie first on RDM"
          body="When Stymie is ready, cast it before the dispel so the strip cannot be resisted."
          onChange={(value) => edit((draft) => { draft.dispel.stymie = value; })}
        />

      </>
    );
  }

  function renderSkillchain() {
    const p = profile!;
    const skillchain = p.skillchain;
    const names = Array.from(
      new Set(
        [
          ...members.map((member) => member.name),
          p.roster.tank,
          p.roster.puller,
          p.roster.kiter,
          ...p.roster.support,
          ...p.roster.melee,
          ...p.roster.ranged,
        ].filter((name) => Boolean(name)),
      ),
    ).sort((a, b) => a.localeCompare(b));
    const filled = skillchain.steps.filter((step) => step.ws !== "").length;
    const bursters = skillchain.bursters;

    return (
      <>
        <h3 className="battle-subhead">Skillchain style</h3>
        <Check
          checked={skillchain.enabled}
          title="Plan and follow a skillchain"
          body="The Battle hub validates the chain and its Magic Burst windows; spam mode just fires the steps in order."
          onChange={(value) => edit((draft) => { draft.skillchain.enabled = value; })}
        />
        <div className="form-grid three">
          <Field label="Mode">
            <Select value={skillchain.mode} onChange={(event) => edit((draft) => { draft.skillchain.mode = event.target.value as "chain" | "spam"; })}>
              <option value="chain">Make a skillchain</option>
              <option value="spam">No chain — spam weapon skills</option>
            </Select>
          </Field>
          <Field label="Target chain" hint="The chain the plan should finish on.">
            <Select value={skillchain.target} disabled={skillchain.mode === "spam"} onChange={(event) => edit((draft) => { draft.skillchain.target = Number(event.target.value); })}>
              {SKILLCHAINS.map((name, index) => <option value={index} key={name}>{index === 0 ? "Any chain" : name}</option>)}
            </Select>
          </Field>
          <Field label="Repeat" hint="Infinite repeats the configured cycle; a goal stops after that many links.">
            <div className="battle-inline-fields">
              <label className="battle-inline-check">
                <input type="checkbox" checked={skillchain.infinite} disabled={skillchain.mode === "spam"} onChange={(event) => edit((draft) => { draft.skillchain.infinite = event.target.checked; })} />
                <span>Loop</span>
              </label>
              <TextInput
                type="number"
                min={0}
                max={11}
                value={skillchain.goal}
                disabled={!skillchain.infinite || skillchain.mode === "spam"}
                onChange={(event) => edit((draft) => { draft.skillchain.goal = numberOr(event.target.value, draft.skillchain.goal); })}
              />
            </div>
          </Field>
        </div>

        <div className="battle-subhead-row">
          <h3 className="battle-subhead">Weapon skill order</h3>
          <span className="battle-hint">{filled} of {skillchain.steps.length} steps set</span>
        </div>
        <p className="battle-hint">
          The actor list uses the live party. The weapon skill is selected from the server catalogue,
          not typed.
        </p>
        <div className="battle-sc-steps">
          {skillchain.steps.map((step, index) => (
            <div className="battle-sc-step" key={`sc-${index}`}>
              <strong>{index === 0 ? "OPEN" : `SC${index}`}</strong>
              <Select value={step.actor} onChange={(event) => edit((draft) => { draft.skillchain.steps[index].actor = event.target.value; })}>
                <option value="">Choose actor…</option>
                {names.map((name) => <option value={name} key={name}>{name}</option>)}
              </Select>
              <BattleActionPick
                value={step.ws}
                placeholder="Choose a weapon skill…"
                onClick={() => openSinglePicker("weapon_skill", `Weapon skill for ${index === 0 ? "the opener" : `SC${index}`}`, "Search the full weapon-skill catalogue, then click one.", step.ws, (name) =>
                  edit((draft) => { draft.skillchain.steps[index].ws = name; }),
                )}
              />
              <label className="battle-inline-check">
                <input
                  type="checkbox"
                  checked={step.diamond}
                  disabled={skillchain.mode === "spam"}
                  onChange={(event) => edit((draft) => { draft.skillchain.steps[index].diamond = event.target.checked; })}
                />
                <span>Diamond</span>
              </label>
              <Button
                size="sm"
                variant="ghost"
                icon={<X size={14} />}
                disabled={skillchain.steps.length <= 2}
                onClick={() => edit((draft) => { draft.skillchain.steps.splice(index, 1); })}
              />
            </div>
          ))}
        </div>
        <Button
          size="sm"
          variant="secondary"
          icon={<Plus size={14} />}
          disabled={skillchain.steps.length >= 12}
          onClick={() => edit((draft) => { draft.skillchain.steps.push({ actor: "", ws: "", diamond: false }); })}
        >
          Add step
        </Button>

        <div className="battle-subhead-row">
          <h3 className="battle-subhead">Magic Burst</h3>
          <span className="battle-hint">{bursters.filter((row) => row.spell).length} burster{bursters.filter((row) => row.spell).length === 1 ? "" : "s"}</span>
        </div>
        <p className="battle-hint">
          A burster links an actor to the spell they cast inside the window. Add one to allow Magic
          Burst; remove them all to keep the plan to weapon skills only.
        </p>
        <div className="battle-sc-steps">
          {bursters.map((row, index) => (
            <div className="battle-sc-burster" key={`mb-${index}`}>
              <Select value={row.name} onChange={(event) => edit((draft) => { draft.skillchain.bursters[index].name = event.target.value; })}>
                <option value="">Choose actor…</option>
                {names.map((name) => <option value={name} key={name}>{name}</option>)}
              </Select>
              <BattleActionPick
                value={row.spell}
                placeholder="Choose a Magic Burst spell…"
                onClick={() => openSinglePicker("all_spells", "Magic Burst spell", "Every spell in the server catalogue, so the plan can name another party member's spell.", row.spell, (name) =>
                  edit((draft) => { draft.skillchain.bursters[index].spell = name; }),
                )}
              />
              <Button
                size="sm"
                variant="ghost"
                icon={<X size={14} />}
                onClick={() => edit((draft) => { draft.skillchain.bursters.splice(index, 1); })}
              />
            </div>
          ))}
          <Button
            size="sm"
            variant="secondary"
            icon={<Plus size={14} />}
            disabled={bursters.length >= 4}
            onClick={() => edit((draft) => { draft.skillchain.bursters.push({ name: "", spell: "" }); })}
          >
            Add burster
          </Button>
        </div>
        <p className="battle-hint">
          The launcher shows the configured steps. The in-game Battle hub draws the chain diagram and
          validates the links.
        </p>
      </>
    );
  }

  function renderSupport() {
    const p = profile!;
    const geo = p.support.geo;
    const cor = p.support.cor;
    const brd = p.support.brd;
    const groups: BattleSongGroup[] = brd.song_groups;
    const abilityRows: BattleSupportAbility[] = p.support.abilities;
    const names = Array.from(
      new Set(
        [
          ...members.map((member) => member.name),
          p.roster.tank,
          p.roster.puller,
          p.roster.kiter,
          ...p.roster.support,
          ...p.roster.melee,
          ...p.roster.ranged,
        ].filter((name) => Boolean(name)),
      ),
    ).sort((a, b) => a.localeCompare(b));

    function addGroup() {
      edit((draft) => {
        const groupNames = draft.support.brd.song_groups.map((group) => group.name.toLowerCase());
        let index = draft.support.brd.song_groups.length + 1;
        while (groupNames.includes(`group ${index}`)) index += 1;
        draft.support.brd.song_groups.push({ name: `Group ${index}`, songs: [] });
      });
    }

    function renameGroup(index: number, next: string) {
      edit((draft) => {
        const group = draft.support.brd.song_groups[index];
        if (!group) return;
        const old = group.name;
        group.name = next;
        if (draft.support.brd.tank_group === old) draft.support.brd.tank_group = next;
        if (draft.support.brd.support_group === old) draft.support.brd.support_group = next;
        if (draft.support.brd.mobile_group === old) draft.support.brd.mobile_group = next;
      });
    }

    function removeGroup(index: number) {
      edit((draft) => {
        if (draft.support.brd.song_groups.length <= 1) return;
        const [removed] = draft.support.brd.song_groups.splice(index, 1);
        const fallback = draft.support.brd.song_groups[0]?.name ?? "";
        if (removed && draft.support.brd.tank_group === removed.name) draft.support.brd.tank_group = fallback;
        if (removed && draft.support.brd.support_group === removed.name) draft.support.brd.support_group = fallback;
        if (removed && draft.support.brd.mobile_group === removed.name) draft.support.brd.mobile_group = fallback;
      });
    }

    return (
      <>
        <p className="battle-hint">
          The engine uses the COR section for a Corsair support, the GEO section for a
          Geomancer and the BRD section for a Bard; the other jobs' settings stay saved in the
          profile. Every spell, song, roll and ability here is chosen from the live client's lists.
        </p>

        <h3 className="battle-subhead">Support abilities</h3>
        <p className="battle-hint">
          Job abilities the support loop may use on its interval. Bolster, Blaze of Glory and
          Entrust are sequenced by the GEO controls below, not by this interval list.
        </p>
        <div className="battle-table">
          <div className="battle-table-head"><span>Ability</span><span>Interval (s)</span><span /></div>
          {abilityRows.map((row, index) => (
            <div className="battle-table-row" key={`${row.name}-${index}`}>
              <label className="battle-inline-check">
                <input
                  type="checkbox"
                  checked={row.enabled}
                  onChange={(event) =>
                    edit((draft) => {
                      const item = draft.support.abilities[index];
                      if (item) item.enabled = event.target.checked;
                    })
                  }
                />
                <span>{row.name}</span>
              </label>
              <TextInput
                type="number"
                value={row.interval}
                onChange={(event) =>
                  edit((draft) => {
                    const item = draft.support.abilities[index];
                    if (item) item.interval = numberOr(event.target.value, item.interval);
                  })
                }
              />
              <Button
                size="sm"
                variant="ghost"
                icon={<X size={14} />}
                onClick={() => edit((draft) => { draft.support.abilities.splice(index, 1); })}
              />
            </div>
          ))}
          <Button
            size="sm"
            variant="secondary"
            icon={<Plus size={14} />}
            onClick={() =>
              openSinglePicker("ability", "Support ability", "Job abilities this character can use while supporting.", "", (name) => {
                if (["bolster", "blaze of glory", "entrust", "clarion call", "soul voice"].includes(name.toLowerCase())
                  || name.toLowerCase().endsWith(" roll")) {
                  notify(`${name} is sequenced by the dedicated support controls below.`, "info");
                  return;
                }
                edit((draft) => {
                  if (!draft.support.abilities.some((row) => row.name.toLowerCase() === name.toLowerCase())) {
                    draft.support.abilities.push({ name, enabled: true, interval: 300 });
                  }
                });
              })
            }
          >
            Add ability
          </Button>
        </div>

        <h3 className="battle-subhead">Corsair</h3>
        <Check checked={cor.enabled} title="Run the COR roll cycle" onChange={(value) => edit((draft) => { draft.support.cor.enabled = value; })} />
        <p className="battle-hint">
          Pick up to two rolls from this COR's job abilities. The roll loop uses them at the
          support camp and refreshes them on the interval; recast still has to allow it.
        </p>
        <Field label="Rolls" hint="Trust-style selection, like Luzaf's Set rolls.">
          <BattleActionPick
            value={cor.rolls.join(", ")}
            placeholder="Choose up to two rolls…"
            onClick={() =>
              openMultiPicker(
                "roll",
                "Corsair rolls",
                "Rolls this Corsair can use. Pick up to two; the loop uses them at the support camp.",
                cor.rolls,
                (names) => edit((draft) => { draft.support.cor.rolls = names.slice(0, 2); }),
              )
            }
          />
        </Field>
        {cor.rolls.length > 0 ? (
          <div className="battle-mob-selected">
            {cor.rolls.map((name) => <span className="battle-mob-chip" key={name}>{name}</span>)}
          </div>
        ) : null}
        <NumberField label="Roll refresh (s)" value={cor.interval} min={60} max={600} onChange={(value) => edit((draft) => { draft.support.cor.interval = value; })} />

        <h3 className="battle-subhead">Geomancer</h3>
        <Check checked={geo.enabled} title="Run the GEO camp loop" onChange={(value) => edit((draft) => { draft.support.geo.enabled = value; })} />
        <div className="form-grid three">
          <Field label="Indi at support camp" hint="Maintained around the GEO.">
            <BattleActionPick
              value={geo.indi}
              placeholder="Choose an Indi- spell…"
              onClick={() => openSinglePicker("indi", "Indi spell", "Indi- spells this GEO can cast. Search, then click one.", geo.indi, (name) =>
                edit((draft) => { draft.support.geo.indi = name; }),
              )}
            />
          </Field>
          <Field label="Geo on the Luopan" hint="Placed at the tank camp.">
            <BattleActionPick
              value={geo.geo}
              placeholder="Choose a Geo- spell…"
              onClick={() => openSinglePicker("geo", "Geo spell", "Geo- spells this GEO can cast. Search, then click one.", geo.geo, (name) =>
                edit((draft) => { draft.support.geo.geo = name; }),
              )}
            />
          </Field>
          <NumberField label="Indi refresh (s)" value={geo.indi_interval} min={30} max={600} onChange={(value) => edit((draft) => { draft.support.geo.indi_interval = value; })} />
        </div>
        <div className="form-grid three">
          <NumberField label="Geo refresh (s)" value={geo.geo_interval} min={30} max={600} onChange={(value) => edit((draft) => { draft.support.geo.geo_interval = value; })} />
          <Field label="Geo anchor" hint="Member the bubble is centred on; the tank is the fallback.">
            <Select value={geo.anchor} onChange={(event) => edit((draft) => { draft.support.geo.anchor = event.target.value; })}>
              <option value="">Tank / fallback</option>
              {names.map((name) => <option value={name} key={name}>{name}</option>)}
            </Select>
          </Field>
          <NumberField label="Cast range (yalms)" value={geo.range} min={5} max={40} onChange={(value) => edit((draft) => { draft.support.geo.range = value; })} />
        </div>
        <Check
          checked={geo.entrust_enabled}
          title="Entrust an Indi on another player"
          body="Uses Entrust, then casts the chosen Indi- on the target on the Indi refresh clock."
          onChange={(value) => edit((draft) => { draft.support.geo.entrust_enabled = value; })}
        />
        {geo.entrust_enabled ? (
          <div className="form-grid two">
            <Field label="Entrust target">
              <Select value={geo.entrust_target} onChange={(event) => edit((draft) => { draft.support.geo.entrust_target = event.target.value; })}>
                <option value="">Choose a party member…</option>
                {names.map((name) => <option value={name} key={name}>{name}</option>)}
              </Select>
            </Field>
            <Field label="Entrusted Indi">
              <BattleActionPick
                value={geo.entrust_indi}
                placeholder="Choose an Indi- spell…"
                onClick={() => openSinglePicker("indi", "Entrusted Indi", "The Indi- spell Entrust places on the target.", geo.entrust_indi, (name) =>
                  edit((draft) => { draft.support.geo.entrust_indi = name; }),
                )}
              />
            </Field>
          </div>
        ) : null}
        <div className="form-grid two">
          <Check
            checked={geo.blaze_of_glory}
            title="Use Blaze of Glory when it is ready"
            body="The engine uses the 1-hour before an Indi/Geo cast to keep the BOG buff alive."
            onChange={(value) => edit((draft) => { draft.support.geo.blaze_of_glory = value; })}
          />
          <Check
            checked={geo.bolster}
            title="Use Bolster when it is ready"
            body="The 2-hour is used just before the next bubble cast."
            onChange={(value) => edit((draft) => { draft.support.geo.bolster = value; })}
          />
        </div>

        <h3 className="battle-subhead">Bard</h3>
        <Check checked={brd.enabled} title="Run the BRD camp song cycle" onChange={(value) => edit((draft) => { draft.support.brd.enabled = value; })} />
        <div className="form-grid three">
          <Field label="Song slots" hint="Four from gear; five only while Clarion Call is up.">
            <Select value={brd.max_songs} onChange={(event) => edit((draft) => { draft.support.brd.max_songs = Number(event.target.value) === 5 ? 5 : 4; })}>
              <option value={4}>Up to 4 songs</option>
              <option value={5}>Try for 5 songs</option>
            </Select>
          </Field>
          <Field label="Nitro set">
            <Select value={brd.nitro} onChange={(event) => edit((draft) => { draft.support.brd.nitro = event.target.value as BattleProfile["support"]["brd"]["nitro"]; })}>
              <option value="both">Both camps</option>
              <option value="tank">Tank camp only</option>
              <option value="support">Support camp only</option>
              <option value="off">Never</option>
            </Select>
          </Field>
          <Field label="Song groups" hint="Pick a group for each camp; song names are never typed.">
            <div className="battle-hint">
              {groups.length} group{groups.length === 1 ? "" : "s"} · max {brd.max_songs} songs
            </div>
          </Field>
        </div>
        <div className="form-grid three">
          <Field label="Tank camp group">
            <Select value={brd.tank_group} onChange={(event) => edit((draft) => { draft.support.brd.tank_group = event.target.value; })}>
              {groups.map((group) => <option value={group.name} key={group.name}>{group.name}</option>)}
            </Select>
          </Field>
          <Field label="Support camp group">
            <Select value={brd.support_group} onChange={(event) => edit((draft) => { draft.support.brd.support_group = event.target.value; })}>
              {groups.map((group) => <option value={group.name} key={group.name}>{group.name}</option>)}
            </Select>
          </Field>
          <Field label="Mobile group">
            <Select value={brd.mobile_group} onChange={(event) => edit((draft) => { draft.support.brd.mobile_group = event.target.value; })}>
              {groups.map((group) => <option value={group.name} key={group.name}>{group.name}</option>)}
            </Select>
          </Field>
        </div>
        <div className="form-grid two">
          <Check
            checked={brd.clarion_call}
            title="Use Clarion Call for the fifth song"
            body="The engine reaches for the fifth slot only while Clarion Call's buff is up."
            onChange={(value) => edit((draft) => { draft.support.brd.clarion_call = value; })}
          />
          <Check
            checked={brd.soul_voice}
            title="Use Soul Voice before a full set"
            body="The Bard 2-hour is used at the start of a set when it is ready."
            onChange={(value) => edit((draft) => { draft.support.brd.soul_voice = value; })}
          />
          <Check
            checked={brd.nitro_all_songs}
            title="Start a full set only when every song is due"
            body="Waits for the whole group to expire, then starts the set with Nitro so every song gets the window."
            onChange={(value) => edit((draft) => { draft.support.brd.nitro_all_songs = value; })}
          />
        </div>

        <div className="battle-song-groups">
          {groups.map((group, index) => (
            <div className="battle-song-group" key={`${group.name}-${index}`}>
              <div className="battle-song-group-head">
                <TextInput value={group.name} onChange={(event) => renameGroup(index, event.target.value)} />
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Trash2 size={14} />}
                  disabled={groups.length <= 1}
                  onClick={() => removeGroup(index)}
                />
              </div>
              {group.songs.length > brd.max_songs ? (
                <span className="battle-hint">
                  {group.songs.length} songs saved; the engine keeps {brd.max_songs} unless
                  {brd.max_songs < 5 ? " the profile is set to try for 5 and" : ""} Clarion Call is up.
                </span>
              ) : null}
              <div className="battle-song-list">
                {group.songs.length === 0 ? (
                  <span className="battle-hint">No songs selected yet.</span>
                ) : (
                  group.songs.map((song) => <span className="battle-song-chip" key={song}>{song}</span>)
                )}
              </div>
              <Button
                size="sm"
                variant="secondary"
                icon={<Plus size={14} />}
                onClick={() =>
                  openMultiPicker(
                    "song",
                    `Songs for ${group.name || "this group"}`,
                    "Pick the Bard songs this camp keeps. Apply to save the set.",
                    group.songs,
                    (songs) =>
                      edit((draft) => {
                        const target = draft.support.brd.song_groups[index];
                        if (target) target.songs = songs.slice(0, 5);
                      }),
                  )
                }
              >
                Choose songs
              </Button>
            </div>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus size={14} />} onClick={addGroup}>
            Add song group
          </Button>
        </div>

        <div className="form-grid two">
          <Field label="Pianissimo target" hint="Single extra song outside the camp groups.">
            <Select value={brd.pianissimo_target} onChange={(event) => edit((draft) => { draft.support.brd.pianissimo_target = event.target.value; })}>
              <option value="">No Pianissimo target</option>
              {names.map((name) => <option value={name} key={name}>{name}</option>)}
            </Select>
          </Field>
          <Field label="Pianissimo song">
            <BattleActionPick
              value={brd.pianissimo_song}
              placeholder="Choose a Bard song…"
              onClick={() => openSinglePicker("song", "Pianissimo song", "Bard songs this character can sing on the target.", brd.pianissimo_song, (name) =>
                edit((draft) => { draft.support.brd.pianissimo_song = name; }),
              )}
            />
          </Field>
        </div>
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
              onClick={() => (status.running ? void stopTeam() : void startTeam())}
            >
              {status.running ? "Stop team" : "Start team"}
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
              {!status.running ? "Stopped" : status.phase === "preparing" ? "Preparing" : "Running"}
            </Badge>
            {status.running && status.ready ? <Badge tone="success">Ready</Badge> : null}
            {status.running && !status.team_ready && (status.waiting_on?.length ?? 0) > 0 ? (
              <Badge tone="warning">
                waiting on {(status.waiting_on ?? []).slice(0, 3).join(", ")}
                {(status.waiting_on?.length ?? 0) > 3 ? ` +${(status.waiting_on?.length ?? 0) - 3}` : ""}
              </Badge>
            ) : null}
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
          <div>
            <span>Preparation</span>
            <strong>
              {!status.running
                ? "stopped"
                : status.team_ready
                  ? "team ready"
                  : status.ready
                    ? `waiting on ${(status.waiting_on ?? []).slice(0, 3).join(", ")}`
                    : "camps, buffs and HP"}
            </strong>
          </div>
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
        <div className="battle-profile-bar">
          <div className="battle-profile-switch">
            <span className="field-label">Saved profile</span>
            <Select
              value={profile.name}
              disabled={busy === "load"}
              onChange={(event) => void switchProfile(event.target.value)}
              title="Switch the whole Battle configuration live. This is the hot-swap list."
            >
              <option value={profile.name}>{profile.name || "Unsaved profile"}{profile.name ? " (current)" : ""}</option>
              {state!.profiles
                .filter((item) => item.name !== profile.name)
                .map((item) => (
                  <option value={item.name} key={item.file}>
                    {item.name} · {item.zone_name || `zone ${item.zone}`}
                  </option>
                ))}
            </Select>
          </div>
          <Button
            size="sm"
            variant="secondary"
            icon={<Plus size={14} />}
            onClick={() => {
              setSaveAsName(profile.name || "New battle profile");
              setSaveAsOpen(true);
            }}
          >
            Save as
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              if (dirty && !window.confirm("Discard the unsaved changes and start a new profile?")) return;
              void send("new", { action: "new", name: "" }, { message: "Started a new battle profile." });
            }}
          >
            New
          </Button>
          <span className="battle-hint battle-profile-hint">
            Switching loads the named profile and applies it to the running client.
          </span>
        </div>

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
          {tab === "support" && renderSupport()}
          {tab === "skillchain" && renderSkillchain()}
          {tab === "profiles" && renderProfiles()}
        </div>
      </Card>

      {saveAsOpen && (
        <Modal
          title="Save battle profile as"
          subtitle="Save this whole configuration under a name. It appears in the saved-profile picker and can be hot-swapped at any time."
          onClose={() => setSaveAsOpen(false)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setSaveAsOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" icon={<Save size={14} />} onClick={() => void saveProfileAs()} loading={busy === "save"}>
                Save profile
              </Button>
            </>
          }
        >
          <Field label="Profile name">
            <TextInput
              value={saveAsName}
              autoFocus
              onChange={(event) => setSaveAsName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void saveProfileAs();
              }}
              placeholder="e.g. Bibiki EP · tank mode"
            />
          </Field>
          {state && state.profiles.length > 0 ? (
            <p className="battle-hint">
              Existing names: {state.profiles.map((item) => item.name).join(", ")}
            </p>
          ) : null}
        </Modal>
      )}

      {picker && (
        <BattleActionDialog
          title={picker.title}
          subtitle={`${picker.subtitle}${
            catalogJobLabel(catalog) && picker.source !== "weapon_skill" && picker.source !== "all_spells" && picker.source !== "mob_move"
              ? ` The client is on ${catalogJobLabel(catalog)}.`
              : ""
          }`}
          mode={picker.mode}
          value={pickerValue}
          values={picker.values ?? []}
          entries={pickerEntries}
          loading={pickerLoading}
          error={pickerError}
          emptyHint={picker.emptyHint}
          onRefresh={() => {
            if (picker.source === "weapon_skill") void loadWeaponSkills(true);
            else if (picker.source === "all_spells") void loadAllSpells(true);
            else if (picker.source === "mob_move") void loadMobMoves();
            else void loadActionCatalog();
          }}
          onSelect={(name, kind) => {
            picker.onSelect?.(name, kind);
            setPicker(null);
          }}
          onConfirm={(names) => {
            picker.onConfirm?.(names);
            setPicker(null);
          }}
          onClose={() => setPicker(null)}
        />
      )}
    </div>
  );
}
