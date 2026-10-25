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
  | "helix_magic"
  | "helix_duration";

export type SpellGroupKey = "enfeebles" | "enhancing" | "curing" | "nuking" | "helix";

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
  midcast: "",
  defaultWs: "",
  defaultJa: "",
  weaponset: "",
  focus: { dt: "", pdt: "", mdt: "", eva: "", meva: "" },
  focusMode: "auto",
  wsOverrides: {},
  jaOverrides: {},
  spellOverrides: {},
  spellCategoryOverrides: {},
  spellModes: { ...DEFAULT_SPELL_MODES },
};

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function objectMap(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out: Record<string, string> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (typeof item === "string" && item) out[key] = item;
  }
  return out;
}

function normalizeSpellModes(
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
    midcast: config.midcast || null,
    default_ws: config.defaultWs || null,
    default_ja: config.defaultJa || null,
    focus: Object.keys(focus).length ? focus : null,
    ws_overrides: config.wsOverrides,
    ja_overrides: config.jaOverrides,
    spell_overrides: config.spellOverrides,
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
