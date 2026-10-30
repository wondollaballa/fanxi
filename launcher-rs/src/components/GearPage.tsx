import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  FileCode2,
  FolderOpen,
  Import,
  Lock,
  LockOpen,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Shirt,
  Sparkles,
  Trash2,
  UserRound,
  Wand2,
} from "lucide-react";
import type {
  CharacterBagItem,
  GearDefaultFile,
  GearItem,
  GearLibrary,
  GearSlot,
  GearVersion,
  GearWeapon,
  InstanceView,
  JobAbility,
  JobInfo,
  JobSpell,
  PhaseStatus,
  Tenant,
} from "../types";
import { backend } from "../lib/api";
import { SLOT_KEYS, jobAbbr, jobName, slotLabel } from "../lib/format";
import {
  loadPhaseConfig,
  normalizeSpellModes,
  phaseOptions,
  phaseStateLabel,
  reconcileSpellCategoryOverrides,
  savePhaseConfig,
  slotMask,
  slotsFromMask,
  type PhaseConfig,
} from "../lib/phase";
import { PhasePanel } from "./PhasePanel";
import { EquipViewer } from "./EquipViewer";
import { SetEquipmentPreview } from "./SetEquipmentPreview";
import { SetStatTotals } from "./SetStatTotals";
import { LiveSetStats } from "./LiveSetStats";
import { useCharacterStatReport } from "../lib/characterstats";
import { useGearStats } from "../lib/gearstats";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Field,
  Modal,
  Select,
  Spinner,
  TextInput,
  cn,
} from "./ui";

type PickedItem = {
  name: string;
  augments: string;
  container?: number;
  slot?: number;
  item_id?: number;
  extra?: string;
};

type EditorState = {
  path: string;
  items: Record<string, string>;
  details?: Record<string, PickedItem>;
  originalPath: string | null;
  keepOriginal: boolean;
  title: string;
  /** Only main/sub/range/ammo, for a weaponset. */
  weaponOnly?: boolean;
};

type DetailedSets = Record<string, Record<string, GearItem>>;

type GearTab = "sets" | "manage";

const WEAPON_SLOT_BITS: Record<string, number> = { main: 1, sub: 2, range: 4, ammo: 8 };

/** The client's equipment-slot bits, used to filter bag copies for the picker. */
const SLOT_BITS: Record<string, number> = {
  main: 1,
  sub: 2,
  range: 4,
  ammo: 8,
  head: 16,
  body: 32,
  hands: 64,
  legs: 128,
  feet: 256,
  neck: 512,
  waist: 1024,
  ear1: 2048,
  ear2: 4096,
  ring1: 8192,
  ring2: 16384,
  back: 32768,
};

function bagLabel(container: number): string {
  if (container === 0) return "Inventory";
  if (container === 8) return "Wardrobe 1";
  if (container >= 10 && container <= 16) return `Wardrobe ${container - 8}`;
  return `Bag ${container}`;
}

function jobBit(jobId: number): number {
  return jobId > 0 ? 1 << (jobId - 1) : 0;
}

/** "set" edits the set form that is already open, "library" writes the selected set's slot
 * straight back to the library file, and "equip" wears the row on the live character. */
type ItemPickerMode = "set" | "library" | "equip";

type ItemPickerState = {
  slot: string;
  mode: ItemPickerMode;
  query: string;
};

type JobPair = {
  mainBit: number;
  subBit: number;
  mainLevel: number;
  subLevel: number;
  /** "COR 99 / DNC 49", or empty while no live job is known. */
  label: string;
};

/** The bag copies that can fill `slot` on this job pair, with the name/augment search applied.
 * Shared by the set editor's picker and the EquipViewer's quick equip so both offer the same
 * wearable copies in the same order. */
function wearableCopies(
  items: CharacterBagItem[],
  slot: string | null,
  query: string,
  pair: JobPair,
): CharacterBagItem[] {
  if (!slot) return [];
  const bit = SLOT_BITS[slot] ?? 0;
  if (!bit) return [];
  const needle = query.trim().toLowerCase();
  return items
    .filter((item) => {
      if (!(item.slot_mask & bit)) return false;
      // An item with no job bits is "All Jobs" in LSB, not "no job".
      const mainOk = pair.mainBit !== 0 && (item.jobs === 0 || (item.jobs & pair.mainBit) !== 0)
        && (!item.level || item.level <= pair.mainLevel);
      const subOk = pair.subBit !== 0 && (item.jobs === 0 || (item.jobs & pair.subBit) !== 0)
        && (!item.level || item.level <= pair.subLevel);
      if (!mainOk && !subOk) return false;
      if (!needle) return true;
      return item.name.toLowerCase().includes(needle)
        || item.augments.toLowerCase().includes(needle);
    })
    .sort((a, b) => a.name.localeCompare(b.name)
      || a.container - b.container
      || a.slot - b.slot);
}

// Weapon-skill ids for the two-handed families. A grip only fits a two-handed main, while
// shields and off-hand weapons only fit a one-handed (or empty) main.
const TWO_HANDED_SKILLS = new Set([4, 6, 7, 8, 10, 12]);

function isGrip(weapon: GearWeapon): boolean {
  return /grip$/i.test(weapon.name.trim());
}

function isTwoHanded(weapon?: GearWeapon): boolean {
  return !!weapon && TWO_HANDED_SKILLS.has(weapon.skill);
}

/** A main/sub/ranged/ammo picker fed by the character's own bags. Main and Sub share one pool:
 * a single copy can go in one of them; a second copy unlocks the other (dual wield). */
function WeaponSelect({
  slot,
  value,
  weapons,
  items,
  onChange,
}: {
  slot: string;
  value: string;
  weapons: GearWeapon[];
  items: Record<string, string>;
  onChange: (value: string) => void;
}) {
  const bit = WEAPON_SLOT_BITS[slot] ?? 0;
  const mainWeapon = weapons.find((weapon) => weapon.name === items.main);
  const mainTwoHanded = isTwoHanded(mainWeapon);
  let list = weapons.filter((weapon) => (weapon.slots & bit) !== 0);
  if (slot === "sub") {
    // A two-handed main leaves only grips in Sub; a one-handed/empty main leaves one-handed
    // weapons and shields, never grips.
    list = list.filter((weapon) => (mainTwoHanded ? isGrip(weapon) : !isGrip(weapon)));
  }
  const other = slot === "main" ? "sub" : slot === "sub" ? "main" : null;
  const otherValue = other ? items[other] ?? "" : "";
  const currentWeapon = weapons.find((weapon) => weapon.name === value);
  const currentInList = list.some((weapon) => weapon.name === value);

  // A saved set (or a Main change) can leave a grip or off-hand weapon that no longer fits;
  // clear it instead of showing a value that is not a legal option.
  useEffect(() => {
    if (value && currentWeapon && !currentInList) onChange("");
  }, [value, currentWeapon, currentInList, onChange]);

  return (
    <Select value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">— none —</option>
      {value && !currentWeapon ? (
        <option value={value}>{value} · unavailable</option>
      ) : null}
      {list.map((weapon) => {
        const used = otherValue === weapon.name ? 1 : 0;
        const blocked = used > 0 && weapon.count <= used;
        const count =
          other && weapon.count > 1
            ? ` · ×${weapon.count}`
            : !other && weapon.quantity > 1
              ? ` · ×${weapon.quantity}`
              : "";
        const usedLabel = other && used ? ` · used by ${slotLabel(other)}` : "";
        return (
          <option
            key={weapon.id}
            value={weapon.name}
            disabled={blocked && value !== weapon.name}
          >
            {weapon.name}
            {count}
            {usedLabel}
          </option>
        );
      })}
    </Select>
  );
}

export function GearPage({
  instances,
  tenant,
  onControl,
  onTeam,
  notify,
  phaseOn,
  onTogglePhase,
}: {
  instances: InstanceView[];
  tenant: Tenant | null;
  onControl: () => void;
  onTeam: () => void;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
  /** The launcher-wide GearSwap master switch, shared with Settings. */
  phaseOn: boolean;
  onTogglePhase: () => void;
}) {
  const running = instances.filter((instance) => instance.alive);
  const [tab, setTab] = useState<GearTab>("sets");
  const pageRef = useRef<HTMLDivElement | null>(null);

  const [slots, setSlots] = useState<Record<string, GearSlot>>({});
  const [encumbrance, setEncumbrance] = useState(0);
  const [job, setJob] = useState<JobInfo | null>(null);
  const [library, setLibrary] = useState<GearLibrary | null>(null);
  const [defaults, setDefaults] = useState<GearDefaultFile[]>([]);
  const [versions, setVersions] = useState<GearVersion[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [picker, setPicker] = useState<ItemPickerState | null>(null);
  const [pickerError, setPickerError] = useState("");
  const [config, setConfig] = useState<PhaseConfig>(loadPhaseConfig);
  const [phase, setPhase] = useState<PhaseStatus | null>(null);
  const [phaseLive, setPhaseLive] = useState<PhaseStatus | null>(null);
  const [phaseError, setPhaseError] = useState("");
  const [spells, setSpells] = useState<JobSpell[]>([]);
  const [abilities, setAbilities] = useState<JobAbility[]>([]);
  const [weapons, setWeapons] = useState<GearWeapon[]>([]);
  const [bagItems, setBagItems] = useState<CharacterBagItem[]>([]);
  const [lockBusy, setLockBusy] = useState(false);
  /** The job whose default library this window loaded last, so a manual pick of another job's
   * library is not immediately replaced. Cleared when the client goes away (logout). */
  const loadedJob = useRef<string | null>(null);
  /** The client the loaded library belongs to; a relaunch usually gets a new control port. */
  const instancePort = useRef<number | null>(null);
  /** Latest master-switch value for an enable request that was already in flight. */
  const phaseOnRef = useRef(phaseOn);
  phaseOnRef.current = phaseOn;
  /** The armed modes the host reported last, so a stale poll cannot undo a local switch. */
  const hostModesRef = useRef<Record<string, string> | null>(null);
  const lockedSlots = useMemo(
    () => slotsFromMask(phaseLive?.lockedSlots),
    [phaseLive?.lockedSlots],
  );

  const instance = tenant
    ? running.find(
        (item) => Number(item.character?.id) === Number(tenant.character.id),
      ) ?? null
    : null;

  // The picker uses the live job pair the client is on, not only the saved character row: a
  // job change in the Mog House must not leave the list filtered by the old jobs.
  const jobPair = useMemo<JobPair>(() => {
    const live = instance?.state?.player;
    const mainJob = Number(job?.jobId || live?.job || instance?.character?.main_job || 0);
    const subJob = Number(
      job?.subJobId || live?.sub_job || instance?.character?.sub_job || 0,
    );
    const mainLevel = Number(
      job?.level || live?.level || instance?.character?.main_level || 0,
    );
    const subLevel = Number(
      job?.subLevel || live?.sub_level || instance?.character?.sub_level || 0,
    );
    return {
      mainBit: jobBit(mainJob),
      subBit: jobBit(subJob),
      mainLevel,
      subLevel,
      label: mainJob
        ? `${jobAbbr(mainJob)}${mainLevel ? ` ${mainLevel}` : ""}${
            subJob ? ` / ${jobAbbr(subJob)}${subLevel ? ` ${subLevel}` : ""}` : ""
          }`
        : "",
    };
  }, [instance, job]);

  /** The bag copies that can fill the open slot for this character's job pair. */
  const pickerItems = useMemo(
    () => wearableCopies(bagItems, picker?.slot ?? null, picker?.query ?? "", jobPair),
    [bagItems, jobPair, picker?.slot, picker?.query],
  );

  useEffect(() => {
    if (!instance) {
      setSlots({});
      setEncumbrance(0);
      setJob(null);
      setLibrary(null);
      // A logout clears the library; signing back in on the same job must load it again.
      loadedJob.current = null;
      instancePort.current = null;
      return;
    }
    if (instancePort.current !== instance.port) {
      // A relaunched client gets a new port; its library has to be read again.
      instancePort.current = instance.port;
      loadedJob.current = null;
      setLibrary(null);
    }
    setLoading(true);
    setError("");
    Promise.all([
      backend.gearSlots(instance.port),
      backend.gearJob(instance.port, instance.character),
    ])
      .then(([gear, jobInfo]) => {
        const record = gear as { slots?: Record<string, GearSlot>; encumbrance?: number };
        setSlots(record.slots ?? {});
        setEncumbrance(record.encumbrance ?? 0);
        setJob(jobInfo);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : String(caught)))
      .finally(() => setLoading(false));
  }, [instance?.port, instance?.character.id]);

  // The set picker reads every bag copy once per character. The server decodes the
  // augment block, so two capes with the same name are distinguishable by their rows.
  useEffect(() => {
    if (!instance) {
      setBagItems([]);
      return;
    }
    let live = true;
    backend
      .characterBags(Number(instance.character.id))
      .then((result) => {
        if (live) setBagItems(result.items ?? []);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [instance?.character.id]);

  // EquipViewer updates when the client equips something. The control port is request/response,
  // so a short poll is the closest equivalent to Windower's 0x050 packet hook.
  const refreshGear = useCallback(async () => {
    if (!instance) return;
    try {
      const gear = (await backend.gearSlots(instance.port)) as {
        slots?: Record<string, GearSlot>;
        encumbrance?: number;
      };
      setSlots(gear.slots ?? {});
      setEncumbrance(gear.encumbrance ?? 0);
    } catch {
      // Keep the last good snapshot; the next tick retries.
    }
  }, [instance?.port]);

  // The job can change in the Mog House at any time; the Gear page follows it instead of
  // waiting for a manual Refresh, so its library and the phase plan move to the new job.
  const refreshJob = useCallback(async () => {
    if (!instance) return;
    try {
      const next = await backend.gearJob(instance.port, instance.character);
      setJob((current) => {
        if (!next) return current;
        if (current && current.jobId === next.jobId && current.level === next.level) {
          return current;
        }
        return next;
      });
    } catch {
      // Keep the last job; the next tick retries.
    }
  }, [instance?.port, instance?.character.id]);

  // The weapon set form lists the weapons the character actually carries and can use. The bags
  // change while playing, so this is re-read when the page opens, when the job changes, and when
  // the weapon editor is opened.
  const refreshWeapons = useCallback(async () => {
    if (!instance) {
      setWeapons([]);
      return;
    }
    try {
      const reply = await backend.gearWeapons(instance.port);
      setWeapons(reply.weapons ?? []);
    } catch {
      setWeapons([]);
    }
  }, [instance?.port]);

  useEffect(() => {
    let cancelled = false;
    let tries = 0;
    let timer: number | undefined;
    const load = async () => {
      if (!instance) {
        setWeapons([]);
        return;
      }
      try {
        const reply = await backend.gearWeapons(instance.port);
        if (cancelled) return;
        const list = reply.weapons ?? [];
        setWeapons(list);
        // At zone-in the bags can still be filling; try again shortly rather than leaving the
        // weapon form empty until the user reopens it.
        if (list.length === 0 && tries < 4) {
          tries += 1;
          timer = window.setTimeout(() => void load(), 1500);
        }
      } catch {
        if (!cancelled) setWeapons([]);
      }
    };
    void load();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [instance?.port, job?.jobId]);

  useEffect(() => {
    if (!instance) return;
    let busy = false;
    const tick = async () => {
      // Do not gate this on document.visibilityState: macOS WebKit marks the window
      // hidden whenever another app is active, and this page is normally watched from a
      // second display while the player is in the game.  The gear, job and server stat
      // rows all have to follow the character while it is being played.
      if (busy) return;
      busy = true;
      await Promise.all([refreshGear(), refreshJob()]);
      busy = false;
    };
    const timer = window.setInterval(() => void tick(), 2000);
    // Catch up at once after a minimised window or an app-napped timer.
    const refresh = () => void tick();
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [instance?.port, refreshGear, refreshJob]);

  // The whole auto-swap configuration (states, forced modes, spell/WS overrides) is persisted
  // together, so the Gear page and the autostart effect push the same plan. localStorage stays
  // the synchronous cache the autostart effect reads; the account's DB row is the durable copy
  // and is written after a short debounce so a burst of selector changes is one request.
  useEffect(() => {
    savePhaseConfig(config);
    const timer = window.setTimeout(() => {
      void backend
        .saveGearswapSettings(config as unknown as Record<string, unknown>)
        .catch(() => undefined);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [config]);

  useEffect(() => {
    if (!instance) {
      setPhase(null);
      return;
    }
    if (!phaseOn) {
      setPhase(null);
      setPhaseError("");
      backend.gearPhaseOff(instance.port).catch(() => undefined);
      return;
    }
    if (!library?.path) {
      setPhaseError("Load a GearSwap library first.");
      return;
    }
    localStorage.setItem("fanxi.phase.library", library.path);
    // The first push can land before the library effect has replaced a set name the new
    // library does not carry (a NIN library has idle.dt, not idle.field). Resolve against the
    // library here so the plan never falls back to the wrong state on the first push.
    const paths = Object.keys(library.sets).map((path) => path.replace(/^sets\./, ""));
    const resolve = (value: string, fallbacks: string[]) =>
      paths.includes(value) ? value : (fallbacks.find((path) => paths.includes(path)) ?? value);
    const planEngaged = resolve(config.engaged, ["engaged.tp", "engaged"]);
    const planTown = resolve(config.idleTown, ["idle.town", "idle"]);
    const planField = resolve(config.idleField, [
      "idle.field",
      "idle.dt",
      "idle.pdt",
      "idle.town",
      "idle",
    ]);
    const planMovement = resolve(config.movement, ["idle.movement", "idle"]);
    let cancelled = false;
    backend
      .gearPhase(
        instance.port,
        true,
        library.path,
        planEngaged,
        planTown,
        planField,
        planMovement,
        phaseOptions({ ...config, engaged: planEngaged, idleTown: planTown, idleField: planField, movement: planMovement }),
      )
      .then((status) => {
        if (!phaseOnRef.current) {
          // The user stopped GearSwap while this enable was in flight. Stop after it so the
          // host cannot be left armed by a slow reply.
          void backend.gearPhaseOff(instance.port).catch(() => undefined);
          return;
        }
        if (cancelled) return;
        setPhase(status);
        setPhaseError("");
      })
      .catch((caught) => {
        if (!phaseOnRef.current) {
          void backend.gearPhaseOff(instance.port).catch(() => undefined);
          return;
        }
        if (cancelled) return;
        setPhase(null);
        setPhaseError(caught instanceof Error ? caught.message : String(caught));
      });
    return () => {
      cancelled = true;
    };
  }, [instance?.port, instance?.startedAt, phaseOn, library, config, job?.jobId]);

  // What the engine is wearing right now: engaged, moving or idle, from its own counters.
  // This runs faster than the gear poll because an action set (a weaponskill's) is only on for
  // the ~second between the held action and its result.  The engine's history makes a swap
  // impossible to miss; a fresh action set also refreshes the gear grid at once, so the
  // EquipViewer draws that set instead of waiting for the two-second tick.
  const lastActionSetRef = useRef<string | null>(null);
  useEffect(() => {
    if (!instance || !phase?.enabled) {
      setPhaseLive(null);
      lastActionSetRef.current = null;
      return;
    }
    let cancelled = false;
    const tick = () => {
      backend
        .gearPhaseStatus(instance.port)
        .then((status) => {
          if (cancelled) return;
          setPhaseLive(status);
          const next = status.actionSet ?? null;
          if (next && next !== lastActionSetRef.current) void refreshGear();
          lastActionSetRef.current = next;
        })
        .catch(() => undefined);
    };
    tick();
    const timer = window.setInterval(tick, 400);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [instance?.port, phase?.enabled, refreshGear]);

  // A job change clears the host's session focus; reflect that in the picker instead of
  // showing a mode the engine is no longer in.
  useEffect(() => {
    if (!phaseLive?.enabled) return;
    if (phaseLive.focus === 0 && config.focusMode !== "auto") {
      setConfig((current) =>
        current.focusMode === "auto" ? current : { ...current, focusMode: "auto" },
      );
    }
  }, [phaseLive?.enabled, phaseLive?.focus, config.focusMode]);

  // The //modes command can change a mode in-game. The host mirrors the armed modes in phase_status;
  // fold a *changed* host mode back into the saved config. Ignoring an unchanged status
  // means a stale poll cannot undo a switch the user just made in the dropdown.
  useEffect(() => {
    const modes = phaseLive?.modes;
    if (!modes) return;
    const previous = hostModesRef.current;
    const hostChanged =
      !previous || Object.entries(modes).some(([group, mode]) => previous[group] !== mode);
    if (!hostChanged) return;
    hostModesRef.current = { ...modes };
    setConfig((current) => {
      let changed = false;
      const next = { ...current.spellModes };
      for (const [group, mode] of Object.entries(modes)) {
        if (mode && next[group] !== mode) {
          next[group] = mode;
          changed = true;
        }
      }
      return changed ? { ...current, spellModes: next } : current;
    });
  }, [phaseLive?.modes]);

  useEffect(() => {
    backend
      .gearDefaults()
      .then((value) => setDefaults(value.files))
      .catch(() => setDefaults([]));
    backend
      .gearVersions()
      .then(setVersions)
      .catch(() => setVersions([]));
  }, []);

  const visibleSets = useMemo(() => {
    if (!library) return [];
    const needle = filter.trim().toLowerCase();
    return Object.keys(library.sets)
      .filter((path) => !needle || path.toLowerCase().includes(needle))
      .sort((a, b) => a.localeCompare(b));
  }, [library, filter]);

  const selectedItems = library && selected ? library.sets[selected] ?? {} : {};
  // The library keys carry the "sets." prefix the launcher uses; the phase plan wants the
  // dotted path alone ("engaged.tp", "idle.town", "midcast.Healing Magic").
  // Opening the page with a live client loads that job's default library, the way the docs
  // describe. A job change swaps a job-named default (gearswap/NIN.lua) for the new job's,
  // while an imported custom library is left where the user put it.
  useEffect(() => {
    if (!instance || !job) return;
    if (loadedJob.current === job.abbr) return;
    loadedJob.current = job.abbr;
    const base = library?.path.split(/[/\\]/).pop() ?? "";
    const jobFile = /^[A-Za-z]{3}\.lua$/.test(base);
    if (library && !jobFile) return;
    if (base.toLowerCase() === `${job.abbr.toLowerCase()}.lua`) return;
    void loadDefault(job.abbr);
  }, [instance?.port, job?.abbr, library?.path]);

  // A new library may not carry the previous job's set names; point the state choices at sets
  // it does have, without discarding a custom path the plan builder can fall back from.
  useEffect(() => {
    if (!library) return;
    const paths = Object.keys(library.sets).map((path) => path.replace(/^sets\./, ""));
    const has = (path: string) => paths.includes(path);
    const firstEngaged = paths.find((path) => path.startsWith("engaged."));
    const firstIdle = paths.find((path) => path.startsWith("idle."));
    setConfig((current) => {
      const next = { ...current };
      const category = reconcileSpellCategoryOverrides(current.spellCategoryOverrides, paths);
      const modes = normalizeSpellModes(current.spellModes, category.overrides);
      if (category.changed) next.spellCategoryOverrides = category.overrides;
      if (JSON.stringify(modes) !== JSON.stringify(current.spellModes)) next.spellModes = modes;
      if (!has(next.engaged)) next.engaged = firstEngaged ?? (has("engaged") ? "engaged" : "engaged.tp");
      if (!has(next.idleTown)) next.idleTown = has("idle.town") ? "idle.town" : firstIdle ?? "idle.town";
      if (!has(next.idleField)) {
        next.idleField = has("idle.field")
          ? "idle.field"
          : has("idle.dt")
            ? "idle.dt"
            : has("idle.pdt")
              ? "idle.pdt"
              : firstIdle ?? "idle.field";
      }
      if (!has(next.movement)) {
        next.movement = has("idle.movement") ? "idle.movement" : firstIdle ?? "idle.movement";
      }
      if (next.weaponset && !has(next.weaponset)) next.weaponset = "";
      if (
        next.engaged === current.engaged &&
        next.idleTown === current.idleTown &&
        next.idleField === current.idleField &&
        next.movement === current.movement &&
        next.weaponset === current.weaponset &&
        !category.changed &&
        next.spellModes === current.spellModes
      ) {
        return current;
      }
      return next;
    });
  }, [library?.path]);

  // The per-spell override and per-ability cards need the job pair's own lists.
  useEffect(() => {
    if (!instance) {
      setSpells([]);
      setAbilities([]);
      return;
    }
    let cancelled = false;
    let tries = 0;
    let timer: number | undefined;
    const load = () => {
      Promise.all([
        backend.gearJobSpells(instance.port).catch(() => ({ spells: [] as JobSpell[] })),
        backend.gearJobAbilities(instance.port).catch(() => ({ abilities: [] as JobAbility[] })),
      ]).then(([spellReply, abilityReply]) => {
        if (cancelled) return;
        setSpells(spellReply.spells ?? []);
        const list = abilityReply.abilities ?? [];
        setAbilities(list);
        // 0x0AC can arrive a moment after the launcher sees the new job; retry an empty list.
        if (list.length === 0 && tries < 4) {
          tries += 1;
          timer = window.setTimeout(load, 1200);
        }
      });
    };
    load();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [instance?.port, instance?.startedAt, job?.jobId]);

  const returnPaths = useMemo(() => {
    const paths = library
      ? Object.keys(library.sets).map((path) => path.replace(/^sets\./, ""))
      : [];
    if (paths.length && !paths.includes("engaged.tp")) paths.unshift("engaged.tp");
    if (paths.length && !paths.includes("idle.town")) paths.unshift("idle.town");
    if (paths.length && !paths.includes("idle.field")) paths.unshift("idle.field");
    if (paths.length && !paths.includes("idle.movement")) paths.unshift("idle.movement");
    return paths;
  }, [library]);
  const wsNames = useMemo(() => {
    if (!library) return [];
    return Object.keys(library.sets)
      .filter((path) => path.startsWith("sets.WS."))
      .map((path) => path.slice("sets.WS.".length))
      .sort((a, b) => a.localeCompare(b));
  }, [library]);
  const selectedDetails: Record<string, GearItem> =
    library && selected ? library.detailed[selected] ?? {} : {};
  const statQueries = useMemo(
    () =>
      SLOT_KEYS.filter((slot) => selectedItems[slot]).map((slot) => ({
        slot,
        name: selectedItems[slot],
        augments: selectedDetails[slot]?.augments ?? [],
      })),
    [selectedItems, selectedDetails],
  );
  const gearStats = useGearStats(
    tab === "manage" ? instance?.port ?? null : null,
    statQueries,
  );
  // The server owns the final numbers (food, buffs and the job-ability layer live only
  // there), so the live sheet is polled from the HTTP API rather than rebuilt from the
  // client's item tooltips. It is read only while the Sets tab is on screen.
  const liveReport = useCharacterStatReport(
    instance ? Number(instance.character.id) : null,
    tab === "sets" && !!instance,
  );
  const statsBySlot = useMemo(
    () => Object.fromEntries(gearStats.items.map((item) => [item.slot, item])),
    [gearStats.items],
  );
  const libraryName = library?.path.split(/[/\\]/).pop() ?? "";
  const librarySetCount = library ? Object.keys(library.sets).length : 0;

  async function loadDefault(jobAbbr: string) {
    if (!instance || !jobAbbr) return;
    setBusy("default");
    setError("");
    try {
      const value = await backend.gearLoadDefault(instance.port, jobAbbr);
      setLibrary(value);
      setSelected(Object.keys(value.sets)[0] ?? null);
      notify(`Loaded the ${jobAbbr} default library`, "success");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function importFile() {
    if (!instance) return;
    const path = await open({
      multiple: false,
      directory: false,
      filters: [{ name: "GearSwap library", extensions: ["lua"] }],
    });
    if (!path || typeof path !== "string") return;
    setBusy("import");
    setError("");
    try {
      const value = await backend.gearLoadFile(instance.port, path);
      setLibrary(value);
      setSelected(Object.keys(value.sets)[0] ?? null);
      notify("Imported GearSwap sets", "success");
      openTab("manage");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function wearSet() {
    if (!instance || !selected) return;
    setBusy("wear");
    setError("");
    try {
      const result = (await backend.gearWearSet(instance.port, selectedItems)) as {
        equipped?: number;
        skipped?: number;
        errors?: string[];
        elapsedMs?: number;
      };
      const count = result?.equipped ?? 0;
      const skipped = result?.skipped ?? 0;
      const errors = result?.errors ?? [];
      const elapsed = result?.elapsedMs;
      const took = typeof elapsed === "number" ? ` in ${elapsed} ms` : "";
      const parts =
        count === 0 && skipped > 0
          ? ["Set already worn"]
          : [`Wore ${count} piece${count === 1 ? "" : "s"}${took}`];
      if (skipped > 0 && count > 0) parts.push(`${skipped} already on`);
      if (errors.length) parts.push(`${errors.length} could not be found`);
      notify(parts.join("; "), errors.length ? "info" : "success");
      // The host has already injected every 0x050; the client shows them once the server echoes
      // them back, so read the slots again now and once more after that round trip.
      void refreshGear();
      window.setTimeout(() => void refreshGear(), 180);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  const locked = phaseLive?.locked ?? false;
  const stateTitle = !phase?.enabled
    ? "Auto-swap off"
    : phaseLive?.state
      ? phaseStateLabel(phaseLive.state)
      : "Waiting for the client";

  function updateConfig(patch: Partial<PhaseConfig>) {
    setConfig((current) => ({ ...current, ...patch }));
  }

  async function refreshPhaseLive() {
    if (!instance) return;
    try {
      setPhaseLive(await backend.gearPhaseStatus(instance.port));
    } catch {
      // Keep the last status; the 2 s poll retries.
    }
  }

  async function toggleKiting(on: boolean) {
    if (!instance) return;
    setBusy("kiting");
    try {
      const result = await backend.gearPhaseKiting(instance.port, on);
      await refreshPhaseLive();
      notify(`${on ? "Kiting" : "Kiting off"}${result.set ? ` · ${result.set}` : ""}`, "success");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function toggleResting(on: boolean) {
    if (!instance) return;
    setBusy("resting");
    try {
      const result = await backend.gearPhaseResting(instance.port, on);
      await refreshPhaseLive();
      notify(`${on ? "Resting" : "Resting off"}${result.set ? ` · ${result.set}` : ""}`, "success");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function setFocus(mode: string) {
    if (!instance) return;
    setBusy("focus");
    try {
      const result = await backend.gearPhaseFocus(instance.port, mode);
      await refreshPhaseLive();
      notify(`Idle focus: ${mode}${result.set ? ` · ${result.set}` : ""}`, "success");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function toggleLockSlot(slot: string) {
    if (!instance) return;
    const next = new Set(lockedSlots);
    if (next.has(slot)) next.delete(slot);
    else next.add(slot);
    setBusy("slot-lock");
    try {
      await backend.gearPhaseLockSlots(instance.port, slotMask(next));
      await refreshPhaseLive();
      notify(`${next.has(slot) ? "Locked" : "Unlocked"} ${slotLabel(slot)}`, "success");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  function weaponItems(path: string): Record<string, string> {
    const items = library?.sets[`sets.${path}`] ?? {};
    const out: Record<string, string> = {};
    for (const slot of ["main", "sub", "range", "ammo"]) {
      if (items[slot]) out[slot] = items[slot];
    }
    return out;
  }

  async function wearWeaponSet(path: string) {
    if (!instance || !path) return;
    const items = weaponItems(path);
    if (Object.keys(items).length === 0) {
      notify("That weaponset has no main, sub, ranged or ammo pieces.", "info");
      return;
    }
    setBusy("weapon-wear");
    try {
      const result = (await backend.gearWearSet(instance.port, items)) as {
        equipped?: number;
        skipped?: number;
        errors?: string[];
      };
      await refreshGear();
      notify(
        `Wore ${result.equipped ?? 0} weapon${result.equipped === 1 ? "" : "s"}${
          result.skipped ? `, ${result.skipped} already on` : ""
        }`,
        "success",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function lockWeaponSet(path: string) {
    if (!instance || !path) return;
    const items = weaponItems(path);
    const slots = Object.keys(items);
    if (slots.length === 0) {
      notify("That weaponset has no main, sub, ranged or ammo pieces.", "info");
      return;
    }
    setBusy("weapon-lock");
    try {
      // "Wear & lock" is an explicit override: release the set's own slots first so the manual
      // wear is not skipped by a pin left from another weaponset, then lock the result.
      const setMask = slotMask(slots);
      const currentMask = slotMask(lockedSlots);
      if ((currentMask & setMask) !== 0) {
        await backend.gearPhaseLockSlots(instance.port, (currentMask & ~setMask) >>> 0);
      }
      const result = (await backend.gearWearSet(instance.port, items)) as {
        equipped?: number;
        skipped?: number;
      };
      const next = new Set(lockedSlots);
      for (const slot of slots) next.add(slot);
      await backend.gearPhaseLockSlots(instance.port, slotMask(next));
      await refreshGear();
      await refreshPhaseLive();
      notify(
        `Wearing and locking ${slots.map((slot) => slotLabel(slot)).join(", ")}${
          result.equipped ? ` (${result.equipped} piece${result.equipped === 1 ? "" : "s"})` : ""
        }`,
        "success",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  function newWeaponSet() {
    void refreshWeapons();
    setEditor({
      path: "sets.weaponset.new",
      items: {},
      originalPath: null,
      keepOriginal: false,
      title: "New weapon set",
      weaponOnly: true,
    });
  }

  /** Edit a weaponset from the Weaponset card (path without the "sets." prefix). */
  function editWeaponSet(path: string) {
    if (!library || !path) return;
    const full = `sets.${path}`;
    const items = library.sets[full];
    if (!items) return;
    void refreshWeapons();
    setEditor({
      path: full,
      items: { ...items },
      originalPath: full,
      keepOriginal: false,
      title: `Edit ${full}`,
      weaponOnly: true,
    });
  }

  /** Change one weapon slot, clearing a Sub that the new Main makes illegal. */
  function setWeaponItem(slot: string, value: string) {
    if (!editor) return;
    const items = { ...editor.items, [slot]: value };
    if (slot === "main") {
      const main = weapons.find((weapon) => weapon.name === value);
      const twoHanded = isTwoHanded(main);
      const subName = items.sub ?? "";
      const sub = weapons.find((weapon) => weapon.name === subName);
      if (subName && sub && (twoHanded ? !isGrip(sub) : isGrip(sub))) {
        items.sub = "";
      }
    }
    setEditor({ ...editor, items });
  }

  async function toggleLock() {
    if (!instance) return;
    const next = !locked;
    setLockBusy(true);
    try {
      const result = await backend.gearPhaseLock(instance.port, next);
      const status = await backend.gearPhaseStatus(instance.port);
      setPhaseLive(status);
      notify(
        next
          ? `Locked ${result.set ?? "the current set"} — auto-swap is paused`
          : `Unlocked — now following ${status.state ?? "idle"}`,
        "success",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLockBusy(false);
    }
  }

  async function saveVersion() {
    if (!library || !instance) return;
    const folder = await open({ directory: true, multiple: false });
    setBusy("save");
    setError("");
    try {
      const result = await backend.gearSave({
        sets: library.sets,
        base: `${instance.name}-${job?.abbr ?? "GEAR"}`,
        character: instance.name,
        job: job?.abbr ?? "",
        source: library.path,
        folder: typeof folder === "string" ? folder : null,
      });
      backend.gearVersions().then(setVersions).catch(() => undefined);
      notify(`Saved ${result.path}`, "success");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  function openItemPicker(slot: string, mode: ItemPickerMode) {
    setPicker({ slot, mode, query: "" });
    setPickerError("");
    if (instance) {
      // Re-read the bags on every open: an item can have been moved, equipped or
      // granted since the page loaded, and the cached copy would keep filtering it
      // with stale slot/job data (Farsha's off-hand bit was fixed in migration 149
      // while this page was open).
      backend
        .characterBags(Number(instance.character.id))
        .then((result) => setBagItems(result.items ?? []))
        .catch(() => undefined);
    }
  }

  function closePicker() {
    setPicker(null);
    setPickerError("");
  }

  /** Inline edit from the Manage tab's set preview: replace (or clear) one slot and write the
   * library, so the preview and the .lua agree the moment a row is clicked. */
  async function saveLibrarySlot(slot: string, item: CharacterBagItem | null) {
    if (!library || !selected || busy === "apply") return;
    const setPath = selected;
    setBusy("apply");
    setPickerError("");
    setError("");
    try {
      const items = { ...(library.sets[setPath] ?? {}) };
      const details = { ...(library.detailed[setPath] ?? {}) };
      if (item) {
        items[slot] = item.name;
        details[slot] = {
          name: item.name,
          augments: item.augments ? item.augments.split(" | ") : [],
          container: item.container,
          slot: item.slot,
          item_id: item.item_id,
          extra: item.extra,
        };
      } else {
        delete items[slot];
        delete details[slot];
      }
      const sets = { ...library.sets, [setPath]: items };
      const detailed = { ...library.detailed, [setPath]: details };
      const written = await persistLibrary(sets);
      setLibrary({ ...library, path: written.path, sets, detailed });
      closePicker();
      const name = setPath.replace(/^sets\./, "");
      const what = item ? `${slotLabel(slot)} → ${item.name}` : `${slotLabel(slot)} cleared`;
      if (written.saved) {
        notify(`Saved ${what} in ${name}`, "success");
      } else if (written.imported) {
        notify(
          `Changed ${what} in ${name} in this window only — imported libraries are never modified. Use Save version to keep it.`,
          "info",
        );
      } else {
        notify(`Changed ${what} in this window; the library file could not be written.`, "error");
      }
    } catch (caught) {
      setPickerError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  function pickItem(item: CharacterBagItem) {
    if (!picker) return;
    if (picker.mode === "equip") {
      void equipBagItem(item);
      return;
    }
    if (picker.mode === "library") {
      void saveLibrarySlot(picker.slot, item);
      return;
    }
    if (!editor) return;
    setEditor({
      ...editor,
      items: { ...editor.items, [picker.slot]: item.name },
      details: {
        ...(editor.details ?? {}),
        [picker.slot]: {
          name: item.name,
          augments: item.augments,
          container: item.container,
          slot: item.slot,
          item_id: item.item_id,
          extra: item.extra,
        },
      },
    });
    setPicker(null);
  }

  function clearPickerSlot() {
    if (!picker) return;
    if (picker.mode === "library") {
      void saveLibrarySlot(picker.slot, null);
      return;
    }
    if (!editor) return;
    const items = { ...editor.items };
    const details = { ...(editor.details ?? {}) };
    delete items[picker.slot];
    delete details[picker.slot];
    setEditor({ ...editor, items, details });
    setPicker(null);
  }

  function startEdit(path: string, asCopy: boolean) {
    if (!library) return;
    const items = { ...(library.sets[path] ?? {}) };
    const details: Record<string, PickedItem> = Object.fromEntries(
      Object.entries(library.detailed[path] ?? {}).map(([slot, item]) => [
        slot,
        { name: item.name, augments: (item.augments ?? []).join(" | ") },
      ]),
    );
    const weaponOnly = path.startsWith("sets.weaponset.");
    if (weaponOnly) void refreshWeapons();
    if (!asCopy) {
      setEditor({
        path,
        items,
        details,
        originalPath: path,
        keepOriginal: false,
        title: `Edit ${path}`,
        weaponOnly,
      });
      return;
    }
    const suggestion = `${path}.copy`;
    setEditor({
      path: suggestion,
      items,
      details,
      originalPath: path,
      keepOriginal: true,
      title: "Duplicate set",
      weaponOnly,
    });
  }

  function startNew() {
    setEditor({
      path: "sets.idle.new",
      items: {},
      details: {},
      originalPath: null,
      keepOriginal: false,
      title: "New set",
    });
  }

  /** Write the edited sets back to the .lua the page loaded. The bundled job libraries are
   * rewritten in place (the first copy is kept as a .bak); an imported GearSwap file is never
   * modified, so the edit only lives in this window and Save version is the way to keep it. */
  async function persistLibrary(nextSets: Record<string, Record<string, string>>) {
    if (!library) return { path: "", saved: false, imported: false };
    try {
      const result = await backend.gearSaveLibrary({
        path: library.path,
        sets: nextSets,
        character: instance?.name ?? "",
        job: job?.abbr ?? "",
        source: library.path,
      });
      return {
        path: result.persistent ? result.path : library.path,
        saved: result.persistent,
        imported: !result.persistent,
      };
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      return { path: library.path, saved: false, imported: false };
    }
  }

  async function applyEditor() {
    if (!library || !editor) return;
    setBusy("apply");
    setError("");
    try {
      const cleanItems: Record<string, string> = {};
      for (const [slot, item] of Object.entries(editor.items)) {
        if (item.trim()) cleanItems[slot] = item.trim();
      }
      const result = await backend.gearApplySet({
        sets: library.sets,
        path: editor.path,
        items: cleanItems,
        originalPath: editor.originalPath,
        keepOriginal: editor.keepOriginal,
      });
      const written = await persistLibrary(result.sets);
      const detailed: DetailedSets = { ...library.detailed };
      if (editor.originalPath && !editor.keepOriginal) delete detailed[editor.originalPath];
      detailed[result.path] = Object.fromEntries(
        Object.entries(cleanItems).map(([slot, name]) => {
          const picked = editor.details?.[slot];
          return [
            slot,
            {
              name,
              augments: picked?.augments ? picked.augments.split(" | ") : [],
              ...(picked && picked.container !== undefined
                ? {
                    container: picked.container,
                    slot: picked.slot,
                    item_id: picked.item_id,
                    extra: picked.extra,
                  }
                : {}),
            },
          ];
        }),
      );
      setLibrary({ ...library, path: written.path, sets: result.sets, detailed });
      setSelected(result.path);
      if (editor.weaponOnly) {
        setConfig((current) => ({
          ...current,
          weaponset: result.path.replace(/^sets\./, ""),
        }));
      }
      setEditor(null);
      const name = result.path.replace(/^sets\./, "");
      if (written.saved) {
        notify(`Saved ${name} to ${written.path.split(/[/\\]/).pop() ?? "the library"}`, "success");
      } else if (written.imported) {
        notify(
          `Added ${name} in this window only — imported libraries are never modified. Use Save version to keep it.`,
          "info",
        );
      } else {
        notify(`Applied ${name} in this window; the library file could not be written.`, "error");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function removeSelected() {
    if (!library || !selected) return;
    const sets = { ...library.sets };
    delete sets[selected];
    const detailed = { ...library.detailed };
    delete detailed[selected];
    const written = await persistLibrary(sets);
    setLibrary({ ...library, path: written.path, sets, detailed });
    setSelected(Object.keys(sets)[0] ?? null);
    const name = selected.replace(/^sets\./, "");
    if (written.saved) {
      notify(`Removed ${name} from the library`, "info");
    } else if (written.imported) {
      notify(
        `Removed ${name} in this window only — imported libraries are never modified. Use Save version to keep it.`,
        "info",
      );
    } else {
      notify(`Removed ${name} in this window; the library file could not be written.`, "error");
    }
  }

  async function equipBagItem(item: CharacterBagItem) {
    if (!instance || !picker || picker.mode !== "equip" || busy === "equip") return;
    const target = picker;
    setBusy("equip");
    setPickerError("");
    setError("");
    try {
      await backend.gearEquip(instance.port, target.slot, item.name);
      closePicker();
      notify(`Equipped ${item.name}`, "success");
      // The EquipViewer polls every two seconds; update it now so the grid and legend show
      // the new piece without waiting for the next tick.
      backend
        .gearSlots(instance.port)
        .then((gear) => {
          setSlots((gear as { slots?: Record<string, GearSlot> }).slots ?? {});
        })
        .catch(() => undefined);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      setPickerError(message);
      setError(message);
    } finally {
      setBusy(null);
    }
  }

  function openTab(next: GearTab) {
    if (next === tab) return;
    setTab(next);
    pageRef.current?.closest(".page-scroll")?.scrollTo({ top: 0 });
  }

  if (!tenant || !instance) {
    return (
      <div className="page">
        <div className="section-header">
          <div>
            <div className="eyebrow">Gear & GearSwap</div>
            <h1 className="page-title">Gear</h1>
          </div>
        </div>
        <Card>
          <EmptyState
            icon={<Shirt size={26} />}
            title={
              tenant
                ? `${tenant.character.name} is not running`
                : "No tenant selected"
            }
            body={
              tenant
                ? `Gear and GearSwap read the live client. Start ${tenant.character.name} (@${tenant.account}) from the Team or Control room, then come back.`
                : "Pick a tenant in the bar at the top, or add a box on the Team page."
            }
            action={
              <>
                <Button onClick={onTeam}>Open Team</Button>
                <Button variant="ghost" onClick={onControl}>
                  Control room
                </Button>
              </>
            }
          />
        </Card>
      </div>
    );
  }

  // The live job card follows the client's main job. The same control state carries the support
  // job; an older client state without those fields falls back to the saved character row.
  const livePlayer = instance.state?.player;
  const supportJobId = Number(
    livePlayer?.sub_job !== undefined ? livePlayer.sub_job : (instance.character?.sub_job ?? 0),
  );
  const supportLevel = Number(
    livePlayer?.sub_level !== undefined
      ? livePlayer.sub_level
      : (instance.character?.sub_level ?? 0),
  );
  const supportJob = supportJobId >= 1 && supportJobId <= 22 ? supportJobId : 0;
  const supportLabel = supportJob
    ? `${jobAbbr(supportJob)}${supportLevel ? ` ${supportLevel}` : ""} · ${jobName(supportJob)}`
    : "none";

  return (
    <div className="page" ref={pageRef}>
      <div className="section-header">
        <div>
          <div className="eyebrow">Tenant · @{tenant.account}</div>
          <h1 className="page-title">Gear &amp; GearSwap</h1>
          <p className="page-subtitle">
            The live gear and the state sets the host wears, plus the GearSwap library that feeds
            them. Sets are saved back to the loaded job library (the first copy stays as a .bak);
            imported files are left untouched and Save version writes a timestamped export.
          </p>
        </div>
        <div className="section-actions">
          <Button
            variant="ghost"
            icon={<RefreshCw size={15} />}
            loading={loading}
            onClick={() => {
              if (!instance) return;
              setLoading(true);
              Promise.all([
                backend.gearSlots(instance.port),
                backend.gearJob(instance.port, instance.character),
                backend.gearJobSpells(instance.port).catch(() => ({ spells: [] as JobSpell[] })),
                backend
                  .gearJobAbilities(instance.port)
                  .catch(() => ({ abilities: [] as JobAbility[] })),
                backend
                  .gearWeapons(instance.port)
                  .catch(() => ({ weapons: [] as GearWeapon[] })),
              ])
                .then(([gear, jobInfo, spellReply, abilityReply, weaponReply]) => {
                  setSlots((gear as { slots?: Record<string, GearSlot> }).slots ?? {});
                  setJob(jobInfo);
                  setSpells(spellReply.spells ?? []);
                  setAbilities(abilityReply.abilities ?? []);
                  setWeapons(weaponReply.weapons ?? []);
                })
                .catch((caught) => setError(caught instanceof Error ? caught.message : String(caught)))
                .finally(() => setLoading(false));
            }}
          >
            Refresh
          </Button>
          <Button variant="secondary" icon={<Import size={15} />} loading={busy === "import"} onClick={() => void importFile()}>
            Import .lua
          </Button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError("")} />}

      <div className="gear-tabs-row">
        <div className="gear-tabs" role="tablist" aria-label="Gear sections">
          <button
            type="button"
            id="gear-tab-sets"
            role="tab"
            aria-selected={tab === "sets"}
            aria-controls="gear-panel-sets"
            className={cn("gear-tab", tab === "sets" && "active")}
            onClick={() => openTab("sets")}
          >
            <Shirt size={15} />
            Sets
            {phase?.enabled ? (
              <span className="gear-tab-dot" title="Auto-swap is on" aria-hidden="true" />
            ) : null}
          </button>
          <button
            type="button"
            id="gear-tab-manage"
            role="tab"
            aria-selected={tab === "manage"}
            aria-controls="gear-panel-manage"
            className={cn("gear-tab", tab === "manage" && "active")}
            onClick={() => openTab("manage")}
          >
            <FolderOpen size={15} />
            Manage
            {library ? <span className="gear-tab-count">{librarySetCount}</span> : null}
          </button>
        </div>
        <button
          type="button"
          className="gear-tabs-library"
          onClick={() => openTab("manage")}
          title={library?.path ?? "No GearSwap library loaded"}
        >
          <FileCode2 size={13} />
          {library ? (
            <>
              <span className="gear-tabs-file">{libraryName}</span>
              <span className="gear-tabs-count">
                {librarySetCount} set{librarySetCount === 1 ? "" : "s"}
              </span>
            </>
          ) : (
            <span>No library loaded</span>
          )}
        </button>
      </div>

      {tab === "sets" ? (
        <div
          className="gear-panel"
          id="gear-panel-sets"
          role="tabpanel"
          aria-labelledby="gear-tab-sets"
        >
          <div className="gear-layout">
            <Card className="active-gear-card">
              <div className="card-topline">
                <span className="eyebrow">Active gear · EquipViewer</span>
                <div className="inline-actions">
                  {phase?.enabled ? (
                    <Button
                      size="sm"
                      variant={locked ? "primary" : "ghost"}
                      icon={locked ? <Lock size={14} /> : <LockOpen size={14} />}
                      loading={lockBusy}
                      onClick={() => void toggleLock()}
                    >
                      {locked ? "Unlock" : "Lock"}
                    </Button>
                  ) : null}
                  {loading ? <Spinner /> : <Badge tone="success" dot>live</Badge>}
                </div>
              </div>
              {phase?.enabled ? (
                <div className="active-gear-state">
                  <span className="eyebrow">State</span>
                  <strong>{stateTitle}</strong>
                  <span className="dot-sep" />
                  <span className="muted">wearing</span>
                  <code className={phaseLive?.actionSet ? "phase-action-live" : undefined}>
                    {phaseLive?.actionSet ?? phaseLive?.set ?? "—"}
                  </code>
                  {phaseLive?.actionSet ? (
                    <Badge tone="success" dot>
                      {((phaseLive.actionMs ?? 0) / 1000).toFixed(1)}s
                    </Badge>
                  ) : null}
                  {locked ? <Badge tone="accent">override</Badge> : null}
                </div>
              ) : null}
              {phase?.enabled && phaseLive?.history?.length ? (
                <div className="phase-history" title="The last action sets the engine wore">
                  <span className="eyebrow">Recent</span>
                  {phaseLive.history.slice(0, 6).map((swap, index) => (
                    <span
                      key={`${swap.set ?? "?"}-${swap.action}-${index}`}
                      className={swap.active ? "phase-swap active" : "phase-swap"}
                      title={`action ${swap.action} · ${(swap.ms / 1000).toFixed(2)}s`}
                    >
                      {swap.set ?? "?"}
                      <em>{(swap.ms / 1000).toFixed(1)}s</em>
                    </span>
                  ))}
                </div>
              ) : null}
              <div className="active-gear-viewer">
                <EquipViewer
                  port={instance.port}
                  slots={slots}
                  encumbrance={encumbrance}
                  locked={Array.from(lockedSlots)}
                  onSlotClick={(slot) => openItemPicker(slot, "equip")}
                />
                <div className="active-gear-legend">
                  {SLOT_KEYS.filter((slot) => slots[slot]?.name).map((slot) => (
                    <button
                      key={slot}
                      className="gear-legend-row"
                      onClick={() => openItemPicker(slot, "equip")}
                    >
                      <span>{slotLabel(slot)}</span>
                      <strong>{slots[slot]?.name}</strong>
                      {(slots[slot]?.count ?? 0) > 1 ? (
                        <em>×{slots[slot]?.count}</em>
                      ) : null}
                    </button>
                  ))}
                  {!SLOT_KEYS.some((slot) => slots[slot]?.name) && (
                    <span className="muted">No gear read from the client yet.</span>
                  )}
                </div>
              </div>
              <LiveSetStats
                characterName={instance.name}
                report={liveReport.report}
                loading={liveReport.loading}
                error={liveReport.error}
                onReload={liveReport.reload}
              />
              <p className="gear-hint">
                The same 4×4 layout, size, alpha, ammo count and encumbrance X as Windower's
                EquipViewer. Click a slot to change it; the totals above are the server's live
                sheet, and clicking one opens every source behind it.
              </p>
            </Card>

            <Card className="job-card">
              <div className="card-topline">
                <span className="eyebrow">Live job</span>
                <UserRound size={14} />
              </div>
              {job ? (
                <>
                  <div className="job-abbr">{job.abbr}</div>
                  <div className="job-name">{job.name}</div>
                  <div className="job-meta">
                    {job.character || instance.name}
                    {job.level ? ` · Main Lv ${job.level}` : ""}
                  </div>
                  <div className="job-meta job-meta-sub">Support · {supportLabel}</div>
                  <Button
                    className="job-load"
                    variant="secondary"
                    icon={<Wand2 size={15} />}
                    loading={busy === "default"}
                    onClick={() => void loadDefault(job.abbr)}
                  >
                    Load {job.abbr} defaults
                  </Button>
                </>
              ) : (
                <div className="job-empty">
                  <span>Waiting for the character to enter the world.</span>
                  <span className="muted">Press Refresh after signing in.</span>
                </div>
              )}
              <div className="job-defaults">
                <span className="field-label">Other job libraries</span>
                <button type="button" className="link-btn" onClick={() => openTab("manage")}>
                  Open Manage
                </button>
              </div>
            </Card>
          </div>

          <PhasePanel
            config={config}
            sets={returnPaths}
            phase={phase}
            status={phaseLive}
            phaseOn={phaseOn}
            busy={busy}
            wsNames={wsNames}
            spells={spells}
            abilities={abilities}
            lockedSlots={lockedSlots}
            onConfig={updateConfig}
            onTogglePhase={onTogglePhase}
            onKiting={(on) => void toggleKiting(on)}
            onResting={(on) => void toggleResting(on)}
            onFocus={(mode) => void setFocus(mode)}
            onLockSlot={(slot) => void toggleLockSlot(slot)}
            onNewWeaponSet={newWeaponSet}
            onEditWeaponSet={editWeaponSet}
            onWearWeaponSet={(path) => void wearWeaponSet(path)}
            onLockWeaponSet={(path) => void lockWeaponSet(path)}
          />
          {phaseError && <p className="gear-hint phase-error">{phaseError}</p>}
        </div>
      ) : (
        <div
          className="gear-panel"
          id="gear-panel-manage"
          role="tabpanel"
          aria-labelledby="gear-tab-manage"
        >
          <Card className="gear-library">
            <div className="card-topline">
              <span className="eyebrow">GearSwap library</span>
              <div className="inline-actions">
                {library && (
                  <Badge tone="neutral">{libraryName}</Badge>
                )}
                <Button size="sm" variant="ghost" icon={<Plus size={14} />} disabled={!library} onClick={startNew}>
                  New set
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Save size={14} />}
                  loading={busy === "save"}
                  disabled={!library}
                  onClick={() => void saveVersion()}
                >
                  Save version
                </Button>
              </div>
            </div>
            <div className="library-load">
              <div className="library-load-label">
                <span className="eyebrow">Job defaults</span>
                <span className="muted">Load a job's bundled GearSwap file.</span>
              </div>
              <Select
                value=""
                disabled={busy === "default"}
                onChange={(event) => {
                  if (event.target.value) void loadDefault(event.target.value);
                }}
              >
                <option value="">Choose a job library…</option>
                {defaults.map((file) => (
                  <option key={file.abbr} value={file.abbr}>
                    {file.abbr} · {file.name}
                  </option>
                ))}
              </Select>
            </div>
            {!library ? (
              <EmptyState
                icon={<Sparkles size={22} />}
                title="No library loaded"
                body="Choose a job library above, or import one of your GearSwap files to browse and edit its sets."
                action={
                  <Button icon={<Import size={15} />} onClick={() => void importFile()}>
                    Import .lua
                  </Button>
                }
              />
            ) : (
              <div className="library-layout">
                <div className="set-sidebar">
                  <div className="set-filter">
                    <TextInput
                      value={filter}
                      onChange={(event) => setFilter(event.target.value)}
                      placeholder="Filter sets…"
                    />
                  </div>
                  <div className="set-list">
                    {visibleSets.map((path) => (
                      <button
                        key={path}
                        className={cn("set-row", selected === path && "active")}
                        onClick={() => setSelected(path)}
                      >
                        <span>{path.replace(/^sets\./, "")}</span>
                        <span className="set-count">
                          {Object.keys(library.sets[path] ?? {}).length}
                        </span>
                      </button>
                    ))}
                    {visibleSets.length === 0 && <div className="muted padded">No sets match.</div>}
                  </div>
                </div>
                <div className="set-detail">
                  {selected ? (
                    <>
                      <div className="set-detail-head">
                        <div>
                          <div className="set-path">{selected}</div>
                          <div className="muted">
                            {Object.keys(selectedItems).length} piece
                            {Object.keys(selectedItems).length === 1 ? "" : "s"}
                          </div>
                        </div>
                        <div className="inline-actions">
                          <Button size="sm" variant="ghost" icon={<Pencil size={14} />} onClick={() => startEdit(selected, false)}>
                            Edit
                          </Button>
                          <Button size="sm" variant="ghost" icon={<FolderOpen size={14} />} onClick={() => startEdit(selected, true)}>
                            Duplicate
                          </Button>
                          <Button size="sm" variant="ghost" icon={<Trash2 size={14} />} onClick={() => void removeSelected()}>
                            Delete
                          </Button>
                          <Button size="sm" icon={<Shirt size={14} />} loading={busy === "wear"} onClick={() => void wearSet()}>
                            Wear set
                          </Button>
                        </div>
                      </div>
                      <div className="set-body">
                        <div className="set-preview">
                          <span className="eyebrow">Set preview</span>
                          <SetEquipmentPreview
                            port={instance.port}
                            items={selectedItems}
                            onSlotClick={(slot) => openItemPicker(slot, "library")}
                            emptyLabel="This set has no items."
                          />
                          <span className="muted">
                            Click a slot to change that piece; the library saves it.
                          </span>
                          {statQueries.length > 0 ? (
                            <SetStatTotals
                              items={gearStats.items}
                              loading={gearStats.loading}
                              error={gearStats.error}
                              onRetry={gearStats.reload}
                            />
                          ) : null}
                        </div>
                        <div className="set-items">
                          {SLOT_KEYS.filter((slot) => selectedItems[slot]).map((slot) => {
                            const detail = selectedDetails[slot];
                            const stats = statsBySlot[slot];
                            return (
                              <div key={slot} className="set-item">
                                <span className="set-slot">{slotLabel(slot)}</span>
                                <div>
                                  <strong>{selectedItems[slot]}</strong>
                                  {stats?.baseLines?.length ? (
                                    <div
                                      className="item-base-stats"
                                      title="Base item stats from the game client"
                                    >
                                      {stats.baseLines.map((line, index) => (
                                        <span key={`${line}-${index}`}>{line}</span>
                                      ))}
                                    </div>
                                  ) : null}
                                  {detail?.augments?.length ? (
                                    <div
                                      className="augments"
                                      title="Augments recorded in this GearSwap set"
                                    >
                                      {detail.augments.map((augment, index) => (
                                        <span key={`${augment}-${index}`}>{augment}</span>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </>
                  ) : (
                    <EmptyState title="Select a set" body="Pick a set on the left to inspect it." />
                  )}
                </div>
              </div>
            )}
          </Card>

          <Card className="gear-versions">
            <div className="card-topline">
              <span className="eyebrow">Saved versions</span>
              <Badge tone="neutral">{versions.length}</Badge>
            </div>
            {versions.length === 0 ? (
              <p className="muted padded">No versions saved yet. Use Save version in a library.</p>
            ) : (
              <div className="version-list">
                {versions.slice(0, 12).map((version) => (
                  <div key={version.path} className="version-row" title={version.path}>
                    <div>
                      <strong>{version.name}</strong>
                      <span>
                        {version.character || "Character"} · {version.job || "Gear"}
                      </span>
                    </div>
                    <span>{version.savedAt.replace("T", " ")}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {editor && (
        <Modal
          title={editor.title}
          subtitle={
            editor.weaponOnly
              ? "Choose from this character's bags. Empty slots are omitted from the saved file."
              : "Paths start with sets. Empty slots are omitted from the saved file."
          }
          wide
          onClose={() => setEditor(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setEditor(null)}>
                Cancel
              </Button>
              <Button loading={busy === "apply"} onClick={() => void applyEditor()}>
                Apply set
              </Button>
            </>
          }
        >
          <div className="editor">
            <div className="editor-layout">
              <div className="editor-fields">
                <Field label="Set path">
                  <TextInput
                    value={editor.path}
                    onChange={(event) => setEditor({ ...editor, path: event.target.value })}
                    placeholder="sets.idle.pdt"
                  />
                </Field>
                {editor.weaponOnly ? (
                  <div className="weapon-editor">
                    <div className="weapon-editor-head">
                      <span className="eyebrow">Weapons from bags</span>
                      <span className="muted">
                        {weapons.length} usable
                        {job
                          ? ` · ${job.abbr}${job.level ? ` ${job.level}` : ""}${
                              supportJob
                                ? ` / ${jobAbbr(supportJob)}${supportLevel ? ` ${supportLevel}` : ""}`
                                : ""
                            }`
                          : ""}
                      </span>
                    </div>
                    <p className="gear-hint">
                      Main and Sub share the bag: one copy can fill either slot, and a second
                      copy unlocks the other. Grips are offered only with a two-handed Main;
                      off-hand weapons and shields only with a one-handed or empty Main.
                      Ranged and ammo come from the same bags.
                    </p>
                    <p className="gear-hint">
                      Reads the client's 18 bags (inventory, Mog Safe, Storage, wardrobes,
                      satchel/sack/case). The hidden //locker needs //locker grab first.
                    </p>
                    {weapons.length === 0 ? (
                      <p className="gear-hint">
                        No usable weapons were read yet; type the item names below.
                      </p>
                    ) : null}
                    <div className="weapon-fields">
                      {["main", "sub", "range", "ammo"].map((slot) => (
                        <Field key={slot} label={slotLabel(slot)}>
                          {weapons.length > 0 ? (
                            <WeaponSelect
                              slot={slot}
                              value={editor.items[slot] ?? ""}
                              weapons={weapons}
                              items={editor.items}
                              onChange={(value) => setWeaponItem(slot, value)}
                            />
                          ) : (
                            <TextInput
                              value={editor.items[slot] ?? ""}
                              onChange={(event) =>
                                setEditor({
                                  ...editor,
                                  items: { ...editor.items, [slot]: event.target.value },
                                })
                              }
                              placeholder="—"
                            />
                          )}
                        </Field>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="editor-grid">
                    {SLOT_KEYS.map((slot) => {
                      const picked = editor.details?.[slot];
                      return (
                        <Field key={slot} label={slotLabel(slot)}>
                          <button
                            type="button"
                            className={cn("item-pick", editor.items[slot] && "filled")}
                            onClick={() => openItemPicker(slot, "set")}
                            title={picked?.augments || undefined}
                          >
                            <span className="item-pick-name">
                              {editor.items[slot] || "Choose item…"}
                            </span>
                            {picked?.augments ? (
                              <span className="item-pick-aug">{picked.augments}</span>
                            ) : null}
                          </button>
                        </Field>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="editor-preview">
                <span className="eyebrow">Equip set preview</span>
                <SetEquipmentPreview
                  port={instance.port}
                  items={editor.items}
                  emptyLabel={
                    editor.weaponOnly
                      ? "Pick weapons and their icons appear here."
                      : "Pick items and their icons appear here."
                  }
                />
                <span className="muted">
                  The same 4×4 grid the client shows, updated as you edit.
                </span>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {picker && (
        <Modal
          title={`${picker.mode === "equip" ? "Equip" : "Choose"} ${slotLabel(picker.slot)}`}
          subtitle={
            picker.mode === "equip"
              ? `Wearable copies${
                  jobPair.label ? ` for ${jobPair.label}` : ""
                } in this character's bags. Click one to equip it.`
              : picker.mode === "library"
                ? `Every copy in this character's bags. Click one to change ${slotLabel(
                    picker.slot,
                  ).toLowerCase()} in ${selected?.replace(/^sets\./, "") ?? "this set"}; the library is saved immediately.`
                : "Every copy in this character's bags, with its augment rows."
          }
          wide
          onClose={closePicker}
          footer={
            <>
              <Button variant="ghost" onClick={closePicker}>
                Cancel
              </Button>
              {picker.mode !== "equip" ? (
                <Button variant="ghost" onClick={clearPickerSlot}>
                  Clear slot
                </Button>
              ) : null}
            </>
          }
        >
          {pickerError ? (
            <div className="picker-error">
              <ErrorBanner message={pickerError} onClose={() => setPickerError("")} />
            </div>
          ) : null}
          <Field label="Search">
            <TextInput
              value={picker.query}
              onChange={(event) => setPicker({ ...picker, query: event.target.value })}
              placeholder="Item name or augment…"
              autoFocus
            />
          </Field>
          <div className="item-picker-list">
            {pickerItems.map((item) => {
              const current = picker.mode === "equip" ? slots[picker.slot] : undefined;
              const worn = current?.bag === item.container && current?.index === item.slot;
              const inSet =
                picker.mode === "library" &&
                library?.sets[selected ?? ""]?.[picker.slot] === item.name;
              return (
                <button
                  key={`${item.container}:${item.slot}`}
                  type="button"
                  className="item-picker-row"
                  disabled={
                    (picker.mode === "equip" && busy === "equip") ||
                    (picker.mode === "library" && busy === "apply")
                  }
                  onClick={() => pickItem(item)}
                >
                  <span className="item-picker-head">
                    <strong>{item.name}</strong>
                    <span className="muted">
                      {bagLabel(item.container)} · slot {item.slot}
                      {item.item_level
                        ? ` · iLv ${item.item_level}`
                        : item.level
                          ? ` · Lv ${item.level}`
                          : ""}
                      {item.quantity > 1 ? ` · ×${item.quantity}` : ""}
                      {worn ? " · worn" : ""}
                      {inSet ? " · in set" : ""}
                    </span>
                  </span>
                  {item.augments ? <span className="augments">{item.augments}</span> : null}
                </button>
              );
            })}
            {pickerItems.length === 0 ? (
              <div className="muted padded">
                {bagItems.length === 0
                  ? "Reading the character's bags…"
                  : `No wearable ${slotLabel(picker.slot).toLowerCase()} copies match. The item must be in this character's bags${
                      jobPair.label ? ` and usable by ${jobPair.label}` : ""
                    }.`}
              </div>
            ) : null}
          </div>
        </Modal>
      )}
    </div>
  );
}
