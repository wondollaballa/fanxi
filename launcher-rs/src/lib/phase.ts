/** The Gear page's auto-swap configuration, kept in one place so the page and the autostart
 * effect push exactly the same plan. All set paths are dotted library paths without "sets.".
 */

export const PHASE_CONFIG_KEY = "fanxi.phase.config";
/** Master switch for the host's auto-swap. "1" means on; anything else (including a fresh
 * profile) means off. The launcher owns the setting, not an individual client. */
export const PHASE_ON_KEY = "fanxi.phase.on";

export function loadPhaseEnabled(): boolean {
  return localStorage.getItem(PHASE_ON_KEY) === "1";
}

export function savePhaseEnabled(enabled: boolean): void {
  localStorage.setItem(PHASE_ON_KEY, enabled ? "1" : "0");
}

/** Equipment slot order of the client's 0x01B flags and the host's pinned-slot mask. */
export const SLOT_MASK_KEYS = [
  "main",
  "sub",
  "range",
  "ammo",
  "head",
  "body",
  "hands",
  "legs",
  "feet",
  "neck",
  "waist",
  "ear1",
  "ear2",
  "ring1",
  "ring2",
  "back",
] as const;

export type PhaseFocusSets = {
  dt: string;
  pdt: string;
  mdt: string;
  eva: string;
  meva: string;
};

export type FocusMode = "auto" | "dt" | "pdt" | "mdt" | "eva" | "meva";

export type SpellCategoryKey =
  | "enfeebles_macc"
  | "enfeebles_duration"
  | "buff_potency"
  | "buff_duration"
  | "cure_potency"
  | "cure_cast"
  | "nuke_mab"
  | "nuke_mdmg"
  | "nuke_mb"
  | "helix_magic"
  | "helix_duration"
  | "enspells"
  | "song_duration"
  | "song_potency"
  | "song_aeonic"
  | "song_prime";

export type SpellGroupKey =
  | "enfeebles"
  | "enhancing"
  | "enspells"
  | "curing"
  | "nuking"
  | "helix"
  | "songs";

export type SpellMode = {
  key: string;
  label: string;
  /** Short label for the in-game mode strip. */
  short: string;
  category: SpellCategoryKey;
  detail: string;
};

export type SpellGroup = {
  key: SpellGroupKey;
  label: string;
  /** Short label for the in-game mode strip. */
  short: string;
  defaultMode: string;
  modes: SpellMode[];
  /** A set worn by itself while its condition is live, not an armable mode. */
  autoMode?: SpellMode;
};

/** The spell groups the host classifies (`job_spells.categories`) and the Spells panel edits. */
export const SPELL_GROUPS: SpellGroup[] = [
  {
    key: "enfeebles",
    label: "Enfeebles",
    short: "Enf",
    defaultMode: "macc",
    modes: [
      {
        key: "macc",
        label: "Macc / landing",
        short: "Macc",
        category: "enfeebles_macc",
        detail: "Magic Accuracy set for landing every Enfeebling Magic spell.",
      },
      {
        key: "duration",
        label: "Duration",
        short: "Dur",
        category: "enfeebles_duration",
        detail: "Duration set for every Enfeebling Magic spell.",
      },
    ],
  },
  {
    key: "enhancing",
    label: "Enhancing / buffs",
    short: "Enh",
    defaultMode: "potency",
    modes: [
      {
        key: "potency",
        label: "Potency",
        short: "Pot",
        category: "buff_potency",
        detail: "Potency set for every Enhancing Magic spell.",
      },
      {
        key: "duration",
        label: "Duration",
        short: "Dur",
        category: "buff_duration",
        detail: "Duration set for every Enhancing Magic spell.",
      },
    ],
  },
  {
    key: "enspells",
    label: "Enspells",
    short: "Ensp",
    defaultMode: "damage",
    modes: [
      {
        key: "damage",
        label: "Enspell damage",
        short: "Dmg",
        category: "enspells",
        detail:
          "Enhancing Magic Skill / MND set for casting Enfire, Enblizzard, Enaero, Enstone, Enthunder and Enwater.",
      },
    ],
  },
  {
    key: "curing",
    label: "Curing / healing",
    short: "Cure",
    defaultMode: "potency",
    modes: [
      {
        key: "potency",
        label: "Potency",
        short: "Pot",
        category: "cure_potency",
        detail: "Potency set for every Healing Magic spell.",
      },
      {
        key: "cast",
        label: "Cast time",
        short: "Cast",
        category: "cure_cast",
        detail: "Fast-cast / cast-time set for every Healing Magic spell.",
      },
    ],
  },
  {
    key: "nuking",
    label: "Nuking",
    short: "Nuke",
    defaultMode: "mab",
    modes: [
      {
        key: "mab",
        label: "Magic Attack",
        short: "MAB",
        category: "nuke_mab",
        detail: "Magic Attack Bonus set for Elemental Magic nukes.",
      },
      {
        key: "mdmg",
        label: "Magic damage",
        short: "M.Dmg",
        category: "nuke_mdmg",
        detail: "Magic Damage set for Elemental Magic nukes.",
      },
    ],
    autoMode: {
      key: "magic_burst",
      label: "Magic Burst",
      short: "Magic Burst",
      category: "nuke_mb",
      detail:
        "Worn for Elemental Magic while a Magic Burst window is open; the armed mode is the fallback.",
    },
  },
  {
    key: "helix",
    label: "Helixes",
    short: "Helix",
    defaultMode: "mab",
    modes: [
      {
        key: "mab",
        label: "Magic Attack",
        short: "MAB",
        category: "helix_magic",
        detail: "Magic Attack / Magic Damage set for helix spells.",
      },
      {
        key: "duration",
        label: "Duration",
        short: "Dur",
        category: "helix_duration",
        detail: "Duration set for helix spells.",
      },
    ],
  },
  {
    key: "songs",
    label: "Bard songs",
    short: "Song",
    defaultMode: "duration",
    modes: [
      {
        key: "duration",
        label: "Song duration",
        short: "Dur",
        category: "song_duration",
        detail: "Duration set for every Bard song.",
      },
      {
        key: "potency",
        label: "Song potency",
        short: "Pot",
        category: "song_potency",
        detail: "All Songs / song-family potency set for every Bard song.",
      },
    ],
  },
];

export const DEFAULT_SPELL_MODES: Record<SpellGroupKey, string> = Object.fromEntries(
  SPELL_GROUPS.map((group) => [group.key, group.defaultMode]),
) as Record<SpellGroupKey, string>;

export type PhaseConfig = {
  engaged: string;
  idleTown: string;
  idleField: string;
  movement: string;
  kite: string;
  rest: string;
  precast: string;
  precastSong: string;
  midcast: string;
  defaultWs: string;
  defaultJa: string;
  weaponset: string;
  focus: PhaseFocusSets;
  focusMode: FocusMode;
  /** weaponskill name -> set path */
  wsOverrides: Record<string, string>;
  /** job ability name -> set path */
  jaOverrides: Record<string, string>;
  /** spell id (string) -> set path */
  spellOverrides: Record<string, string>;
  /** song spell id (string) -> { pre, mid } set paths */
  songOverrides: Record<string, { pre: string; mid: string }>;
  /** spell category key -> one set for every spell the host puts in that category */
  spellCategoryOverrides: Record<string, string>;
  /** spell group key -> the mode whose set is worn */
  spellModes: Record<string, string>;
};

export const FOCUS_MODES: { value: FocusMode; label: string }[] = [
  { value: "auto", label: "Auto (town / field)" },
  { value: "dt", label: "DT focus" },
  { value: "pdt", label: "PDT focus" },
  { value: "mdt", label: "MDT focus" },
  { value: "eva", label: "Eva focus" },
  { value: "meva", label: "Meva focus" },
];

export const DEFAULT_PHASE_CONFIG: PhaseConfig = {
  engaged: "engaged.tp",
  idleTown: "idle.town",
  idleField: "idle.field",
  movement: "idle.movement",
  kite: "",
  rest: "",
  precast: "",
  precastSong: "",
  midcast: "",
  defaultWs: "",
  defaultJa: "",
  weaponset: "",
  focus: { dt: "", pdt: "", mdt: "", eva: "", meva: "" },
  focusMode: "auto",
  wsOverrides: {},
  jaOverrides: {},
  spellOverrides: {},
  songOverrides: {},
  spellCategoryOverrides: {},
  spellModes: { ...DEFAULT_SPELL_MODES },
};

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function songOverrideMap(value: unknown): Record<string, { pre: string; mid: string }> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out: Record<string, { pre: string; mid: string }> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    const entry = item as Record<string, unknown>;
    const pre = text(entry.pre);
    const mid = text(entry.mid);
    if (pre || mid) out[key] = { pre, mid };
  }
  return out;
}

function objectMap(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out: Record<string, string> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (typeof item === "string" && item) out[key] = item;
  }
  return out;
}

/** Conventional library paths for each spell category, in preference order. */
const SPELL_CATEGORY_FALLBACKS: Record<SpellCategoryKey, string[]> = {
  enfeebles_macc: ["midcast.Enfeebling Magic"],
  enfeebles_duration: ["midcast.Enfeebling Magic"],
  buff_potency: ["midcast.Enhancing Magic"],
  buff_duration: ["midcast.EnhancingDuration", "midcast.Enhancing Magic"],
  cure_potency: ["midcast.Cure", "midcast.Healing Magic"],
  cure_cast: ["midcast.Healing Magic"],
  nuke_mab: ["midcast.Elemental Magic"],
  nuke_mdmg: ["midcast.Elemental Magic"],
  nuke_mb: ["midcast.Elemental Magic MB"],
  helix_magic: ["midcast.Elemental Magic"],
  helix_duration: [],
  enspells: ["midcast.Enspell", "midcast.EnhancingSkill"],
  song_duration: ["midcast.SongDuration", "midcast.Song", "midcast.Singing"],
  song_potency: ["midcast.SongPotency", "midcast.Song", "midcast.Singing"],
  song_aeonic: ["midcast.SongHonor", "midcast.SongDuration", "midcast.Song"],
  song_prime: ["midcast.SongAria", "midcast.SongDuration", "midcast.Song"],
};

/**
 * Point each category at the conventional set when the saved path is missing. A path that exists
 * is left alone, so a player's deliberate pick is never replaced. Missing paths with no
 * conventional fallback are dropped, which lets the host fall back to the spell's skill set.
 */
export function reconcileSpellCategoryOverrides(
  overrides: Record<string, string>,
  setPaths: Iterable<string>,
): { overrides: Record<string, string>; changed: boolean } {
  const paths = new Set(setPaths);
  const next = { ...overrides };
  let changed = false;
  for (const [category, fallbacks] of Object.entries(SPELL_CATEGORY_FALLBACKS) as [
    SpellCategoryKey,
    string[],
  ][]) {
    const current = next[category];
    if (current && paths.has(current)) continue;
    const fallback = fallbacks.find((path) => paths.has(path));
    if (fallback) {
      if (current !== fallback) {
        next[category] = fallback;
        changed = true;
      }
    } else if (current) {
      delete next[category];
      changed = true;
    }
  }
  return { overrides: next, changed };
}

export function normalizeSpellModes(
  savedModes: Record<string, string>,
  overrides: Record<string, string>,
): Record<string, string> {
  const out: Record<string, string> = { ...DEFAULT_SPELL_MODES };
  for (const group of SPELL_GROUPS) {
    const saved = savedModes[group.key];
    if (saved && group.modes.some((mode) => mode.key === saved)) {
      out[group.key] = saved;
      continue;
    }
    // Old configs only had the category picks. Preserve the old effective choice when
    // exactly one face of the pair was configured.
    const configured = group.modes.filter((mode) => overrides[mode.category]);
    if (configured.length === 1) out[group.key] = configured[0].key;
  }
  return out;
}

/** Reads the saved config, migrating the first single-idle layout. */
export function loadPhaseConfig(): PhaseConfig {
  let saved: Record<string, unknown> = {};
  try {
    const raw = localStorage.getItem(PHASE_CONFIG_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        saved = parsed as Record<string, unknown>;
      }
    }
  } catch {
    // A corrupt entry is replaced by the defaults below.
  }
  const legacyIdle = localStorage.getItem("fanxi.phase.idleTown") ?? localStorage.getItem("fanxi.phase.idle");
  const focus = (saved.focus ?? {}) as Record<string, unknown>;
  const mode = text(saved.focusMode, "auto");
  const spellCategoryOverrides = objectMap(saved.spellCategoryOverrides);
  return {
    engaged: text(saved.engaged, localStorage.getItem("fanxi.phase.engaged") ?? "engaged.tp"),
    idleTown: text(saved.idleTown, legacyIdle ?? "idle.town"),
    idleField: text(saved.idleField, localStorage.getItem("fanxi.phase.idleField") ?? "idle.field"),
    movement: text(saved.movement, localStorage.getItem("fanxi.phase.movement") ?? "idle.movement"),
    kite: text(saved.kite),
    rest: text(saved.rest),
    precast: text(saved.precast),
    precastSong: text(saved.precastSong),
    midcast: text(saved.midcast),
    defaultWs: text(saved.defaultWs),
    defaultJa: text(saved.defaultJa),
    weaponset: text(saved.weaponset),
    focus: {
      dt: text(focus.dt),
      pdt: text(focus.pdt),
      mdt: text(focus.mdt),
      eva: text(focus.eva),
      meva: text(focus.meva),
    },
    focusMode: (["auto", "dt", "pdt", "mdt", "eva", "meva"] as string[]).includes(mode)
      ? (mode as FocusMode)
      : "auto",
    wsOverrides: objectMap(saved.wsOverrides),
    jaOverrides: objectMap(saved.jaOverrides),
    spellOverrides: objectMap(saved.spellOverrides),
    songOverrides: songOverrideMap(saved.songOverrides),
    spellCategoryOverrides,
    spellModes: normalizeSpellModes(objectMap(saved.spellModes), spellCategoryOverrides),
  };
}

export function savePhaseConfig(config: PhaseConfig): void {
  localStorage.setItem(PHASE_CONFIG_KEY, JSON.stringify(config));
  // Keep the old keys in step for the running autostart effect and for older builds.
  localStorage.setItem("fanxi.phase.engaged", config.engaged);
  localStorage.setItem("fanxi.phase.idleTown", config.idleTown);
  localStorage.setItem("fanxi.phase.idleField", config.idleField);
  localStorage.setItem("fanxi.phase.movement", config.movement);
}

/** The extra JSON the host's phase command reads: forced states, spell/WS overrides. */
export function phaseOptions(config: PhaseConfig): Record<string, unknown> {
  const focus: Record<string, string> = {};
  for (const [key, value] of Object.entries(config.focus)) {
    if (value) focus[key] = value;
  }
  return {
    kite: config.kite || null,
    rest: config.rest || null,
    precast: config.precast || null,
    precast_song: config.precastSong || null,
    midcast: config.midcast || null,
    default_ws: config.defaultWs || null,
    default_ja: config.defaultJa || null,
    focus: Object.keys(focus).length ? focus : null,
    ws_overrides: config.wsOverrides,
    ja_overrides: config.jaOverrides,
    spell_overrides: config.spellOverrides,
    song_overrides: config.songOverrides,
    spell_category_overrides: config.spellCategoryOverrides,
    spell_modes: config.spellModes,
  };
}

export function slotMask(names: Iterable<string>): number {
  let mask = 0;
  for (const raw of names) {
    const name = raw === "ranged" ? "range" : raw;
    const index = SLOT_MASK_KEYS.indexOf(name as (typeof SLOT_MASK_KEYS)[number]);
    if (index >= 0) mask |= 1 << index;
  }
  return mask >>> 0;
}

export function slotsFromMask(indices?: number[]): Set<string> {
  const out = new Set<string>();
  for (const index of indices ?? []) {
    const name = SLOT_MASK_KEYS[index];
    if (name) out.add(name);
  }
  return out;
}

export function slotLabelOf(name: string): string {
  const labels: Record<string, string> = {
    main: "Main",
    sub: "Sub",
    range: "Ranged",
    ammo: "Ammo",
    head: "Head",
    body: "Body",
    hands: "Hands",
    legs: "Legs",
    feet: "Feet",
    neck: "Neck",
    waist: "Waist",
    ear1: "Ear 1",
    ear2: "Ear 2",
    ring1: "Ring 1",
    ring2: "Ring 2",
    back: "Back",
  };
  return labels[name] ?? name;
}

/** Human title for the host's state name. */
export function phaseStateLabel(state?: string): string {
  switch (state) {
    case "engaged":
      return "Engaged";
    case "kiting":
      return "Kiting";
    case "resting":
      return "Resting";
    case "movement":
      return "Moving";
    case "idle.town":
      return "Idle · Town";
    case "idle.field":
      return "Idle · Field";
    case "idle.dt":
      return "Idle · DT";
    case "idle.pdt":
      return "Idle · PDT";
    case "idle.mdt":
      return "Idle · MDT";
    case "idle.eva":
      return "Idle · Eva";
    case "idle.meva":
      return "Idle · Meva";
    case "locked":
      return "Locked";
    default:
      return "Idle";
  }
}

/** One `sets.WS.*` name, split at a trailing `(Buff, Buff)` condition. */
export interface WsSetName {
  /** The library's full name, e.g. "Victory Smite (Impetus)". */
  raw: string;
  /** The action's name, e.g. "Victory Smite". */
  base: string;
  /** Active statuses required for this set, in the order the library wrote them. */
  conditions: string[];
}

/** A weaponskill and every conditional variant the library has for it. */
export interface WsSetGroup {
  base: string;
  variants: WsSetName[];
  /** The library has a plain set for the action, not only conditional variants. */
  hasBase: boolean;
}

const WS_CONDITION_RE = /^(.*?)\s*\(([^()]*)\)\s*$/;

/**
 * Split a GearSwap WS set name at its trailing condition: `Victory Smite (Impetus)` is the
 * Victory Smite action under Impetus; `(Impetus, Focus)` requires both. A name without the
 * suffix is the action's unconditional set.
 */
export function parseWsSetName(raw: string): WsSetName {
  const match = WS_CONDITION_RE.exec(raw);
  if (!match) return { raw, base: raw, conditions: [] };
  const base = match[1].trim();
  const conditions = match[2]
    .split(",")
    .map((part) => part.trim().replace(/^"(.*)"$/, "$1").trim())
    .filter(Boolean);
  if (!base || conditions.length === 0) return { raw, base: raw, conditions: [] };
  return { raw, base, conditions };
}

/** Group a library's WS set names by the action they belong to, variants after the base. */
export function groupWsNames(names: string[]): WsSetGroup[] {
  const groups = new Map<string, WsSetGroup>();
  for (const raw of names) {
    const parsed = parseWsSetName(raw);
    let group = groups.get(parsed.base);
    if (!group) {
      group = { base: parsed.base, variants: [], hasBase: false };
      groups.set(parsed.base, group);
    }
    group.variants.push(parsed);
    if (parsed.conditions.length === 0) group.hasBase = true;
  }
  return Array.from(groups.values())
    .sort((a, b) => a.base.localeCompare(b.base))
    .map((group) => ({
      ...group,
      variants: [...group.variants].sort((a, b) => a.raw.localeCompare(b.raw)),
    }));
}
