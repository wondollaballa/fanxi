/** The Gear page's auto-swap configuration, kept in one place so the page and the autostart
 * effect push exactly the same plan. All set paths are dotted library paths without "sets.".
 */

export const PHASE_CONFIG_KEY = "fanxi.phase.config";
/** Master switch for the host's auto-swap. "1" means on; anything else (including a fresh
 * profile) means off. The launcher owns the setting, not an individual client. */
export const PHASE_ON_KEY = "fanxi.phase.on";
/** Bumped when a default mode changes in a way a saved config should follow. 2 split
 * Enfeebles into per-spell kinds and made Auto the default; 3 did the same for Enhancing;
 * 4 did it for Divine Magic (Flash now has its own kind, so Auto is the default). */
export const PHASE_CONFIG_VERSION = 4;

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
  | "enfeebles_skill"
  | "enfeebles_macc"
  | "enfeebles_duration"
  | "enfeebles_hybrid"
  | "enfeebles_mnd"
  | "enfeebles_int"
  | "enfeebles_general"
  | "enfeebles_saboteur"
  | "enhancing_skill"
  | "enhancing_stoneskin"
  | "enhancing_phalanx"
  | "enhancing_reprisal"
  | "enhancing_duration"
  | "enhancing_duration_self"
  | "enhancing_general"
  | "buff_potency"
  | "buff_duration"
  | "cure_potency"
  | "cure_cast"
  | "nuke_mab"
  | "nuke_mdmg"
  | "nuke_mb"
  | "nuke_immanence"
  | "helix_magic"
  | "helix_immanence"
  | "blue_mab"
  | "blue_macc"
  | "ninjutsu_macc"
  | "ninjutsu_damage"
  | "helix_duration"
  | "dark_potency"
  | "dark_macc"
  | "dark_duration"
  | "divine_mab"
  | "divine_flash"
  | "divine_macc"
  | "enspells"
  | "enspells_no_damage"
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
  | "dark"
  | "divine"
  | "songs"
  | "blue"
  | "ninjutsu";

export type SpellMode = {
  key: string;
  label: string;
  /** Short label for the in-game mode strip. */
  short: string;
  /** The category this mode forces.  Auto has none: it follows each spell's kind. */
  category?: SpellCategoryKey;
  detail: string;
  /** A live status id that activates this automatic set (Immanence = 470). */
  buff?: number;
  /**
   * Lay this set over the spell's own set instead of replacing it, slot by slot.  The
   * Enfeebles Saboteur row is only the hands, so one set covers every kind.
   */
  merge?: boolean;
  /**
   * Scope an automatic row to one kind of its group.  The Enhancing Composure row only
   * applies to the duration spells, not to Aquaveil or Stoneskin.
   */
  onlyKind?: string;
  /** Empty-option wording for the row (the automatic rows are not armed modes). */
  emptyLabel?: string;
};

/** One enfeebling kind: a spell group inside Enfeebles with its own set row. */
export type SpellKind = {
  key: string;
  label: string;
  /** Short label for the gear rows. */
  short: string;
  category: SpellCategoryKey;
  detail: string;
  /**
   * Jobs whose page shows this row.  Omit for a kind every job of the group uses; the
   * Phalanx and Reprisal rows are only meaningful where the spell is learned.
   */
  jobs?: number[];
};

export type SpellGroup = {
  key: SpellGroupKey;
  label: string;
  /** Short label for the in-game mode strip. */
  short: string;
  defaultMode: string;
  modes: SpellMode[];
  /** Per-spell-type sets inside the group (Enfeebles: skill, macc, mnd, ...). */
  kinds?: SpellKind[];
  /** A set worn by itself while its condition is live, not an armable mode. */
  autoMode?: SpellMode;
  /** Additional automatic sets with their own condition (Immanence, ...). */
  autoModes?: SpellMode[];
};

/** The spell groups the host classifies (`job_spells.categories`) and the Spells panel edits. */
export const SPELL_GROUPS: SpellGroup[] = [
  {
    key: "enfeebles",
    label: "Enfeebles",
    short: "Enf",
    defaultMode: "auto",
    // BG Wiki's Community Red Mage Guide splits the enfeebles by what their value reads:
    // Enfeebling Magic Skill, landing (Macc), duration, dMND, dINT, Macc + potency and the
    // non-scaling spells.  Auto follows the spell's own kind; arming another mode forces
    // every enfeebling spell through that one set.
    modes: [
      {
        key: "auto",
        label: "Auto — by spell type",
        short: "Auto",
        detail: "Wear the kind row for each spell (Skill, Macc, MND, INT, Hybrid, General).",
      },
      {
        key: "skill",
        label: "Skill",
        short: "Skill",
        category: "enfeebles_skill",
        detail: "Force every enfeebling spell through the Skill build.",
      },
      {
        key: "macc",
        label: "Macc / landing",
        short: "Macc",
        category: "enfeebles_macc",
        detail: "Force every enfeebling spell through the Macc build.",
      },
      {
        key: "duration",
        label: "Duration",
        short: "Dur",
        category: "enfeebles_duration",
        detail: "Force every enfeebling spell through the Duration build.",
      },
      {
        key: "hybrid",
        label: "Macc + potency",
        short: "Hybrid",
        category: "enfeebles_hybrid",
        detail: "Force every enfeebling spell through the Macc + potency build.",
      },
      {
        key: "mnd",
        label: "MND",
        short: "MND",
        category: "enfeebles_mnd",
        detail: "Force every enfeebling spell through the MND build.",
      },
      {
        key: "int",
        label: "INT",
        short: "INT",
        category: "enfeebles_int",
        detail: "Force every enfeebling spell through the INT build.",
      },
      {
        key: "general",
        label: "General",
        short: "Gen",
        category: "enfeebles_general",
        detail: "Force every enfeebling spell through the non-scaling build.",
      },
    ],
    kinds: [
      {
        key: "skill",
        label: "Skill",
        short: "Skill",
        category: "enfeebles_skill",
        detail: "Enfeebling Magic Skill carries the potency: Frazzle III, Distract III, Poison, Poison II.",
      },
      {
        key: "macc",
        label: "Macc / landing",
        short: "Macc",
        category: "enfeebles_macc",
        detail: "All-or-nothing landing: Frazzle II, Distract II, Dia, Sleep, Bind, Break, Silence.",
      },
      {
        key: "duration",
        label: "Duration",
        short: "Dur",
        category: "enfeebles_duration",
        detail: "Crowd control where the timer matters: Sleep, Sleep II, Bind, Break, Silence.",
      },
      {
        key: "hybrid",
        label: "Macc + potency",
        short: "Hybrid",
        category: "enfeebles_hybrid",
        detail: "Magic Accuracy and Enfeebling potency together: Gravity and Gravity II.",
      },
      {
        key: "mnd",
        label: "MND",
        short: "MND",
        category: "enfeebles_mnd",
        detail: "dMND sets the potency: Slow II, Paralyze II, Addle II.",
      },
      {
        key: "int",
        label: "INT",
        short: "INT",
        category: "enfeebles_int",
        detail: "dINT sets the potency: Blind II.",
      },
      {
        key: "general",
        label: "General",
        short: "Gen",
        category: "enfeebles_general",
        detail: "Nothing to scale and nothing to resist: Dispel, Dispelga, Inundation.",
      },
    ],
    // A live status, not an armed mode.  While Saboteur is up the host adds a
    // higher-priority rule for every enfeebling spell; merge keeps the kind set and lays the
    // hands-only overlay on top.
    autoModes: [
      {
        key: "saboteur",
        label: "Saboteur",
        short: "Sab",
        category: "enfeebles_saboteur",
        buff: 454,
        merge: true,
        detail:
          "While Saboteur is up, every enfeebling cast swaps the hands to Lethargy Gantherots.",
      },
    ],
  },
  {
    key: "enhancing",
    label: "Enhancing / buffs",
    short: "Enh",
    defaultMode: "auto",
    // The guide splits the enhancing spells the same way it splits the enfeebles: Aquaveil
    // wants SIRD, Stoneskin wants potency, the Bar-/Haste/Flurry/Blink line wants duration,
    // and the rest use the generic enhancing set.  Auto follows the spell; arming a kind
    // forces every enhancing spell through that set.
    modes: [
      {
        key: "auto",
        label: "Auto — by spell type",
        short: "Auto",
        detail: "Wear the kind row for each spell (Skill, Stoneskin, Duration, General).",
      },
      {
        key: "skill",
        label: "Skill (Aquaveil)",
        short: "SIRD",
        category: "enhancing_skill",
        detail: "Force every enhancing spell through the Aquaveil SIRD build.",
      },
      {
        key: "stoneskin",
        label: "Stoneskin",
        short: "Stone",
        category: "enhancing_stoneskin",
        detail: "Force every enhancing spell through the Stoneskin build.",
      },
      {
        key: "duration",
        label: "Duration",
        short: "Dur",
        category: "enhancing_duration",
        detail: "Force every enhancing spell through the duration build.",
      },
      {
        key: "general",
        label: "General",
        short: "Gen",
        category: "enhancing_general",
        detail: "Force every enhancing spell through the generic enhancing set.",
      },
    ],
    kinds: [
      {
        key: "skill",
        label: "Skill (Aquaveil)",
        short: "SIRD",
        category: "enhancing_skill",
        detail: "Aquaveil: spell interruption rate down, so the cast survives under fire.",
      },
      {
        key: "stoneskin",
        label: "Stoneskin",
        short: "Stone",
        category: "enhancing_stoneskin",
        detail: "Stoneskin: Enhancing skill and MND push the absorb past its base cap.",
      },
      {
        key: "phalanx",
        label: "Phalanx",
        short: "Phalanx",
        category: "enhancing_phalanx",
        jobs: [5, 7, 22],
        detail:
          "Phalanx: Enhancing Magic skill and the Phalanx+ pieces, the guide's Max Self Phalanx build.",
      },
      {
        key: "reprisal",
        label: "Reprisal",
        short: "Reprisal",
        category: "enhancing_reprisal",
        jobs: [7],
        detail:
          "Reprisal: enmity and duration first, with the block-rate boost riding on the shield.",
      },
      {
        key: "duration",
        label: "Duration",
        short: "Dur",
        category: "enhancing_duration",
        detail: "Barspell, Blink, Haste, Haste II, Flurry and Flurry II: duration first.",
      },
      {
        key: "general",
        label: "General",
        short: "Gen",
        category: "enhancing_general",
        detail: "Protect, Shell, Regen, Refresh, Temper and the rest: the generic enhancing set.",
      },
    ],
    // A live status, not an armed mode: Composure triples enhancing duration on self, so
    // the duration spells wear the self build while it is up and the party build otherwise.
    // onlyKind keeps the row off Aquaveil, Stoneskin and the general spells.
    autoModes: [
      {
        key: "composure",
        label: "Composure",
        short: "Comp",
        category: "enhancing_duration_self",
        buff: 419,
        onlyKind: "duration",
        emptyLabel: "— no self set —",
        detail: "While Composure is up, the duration spells wear the self duration set.",
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
      {
        key: "nodamage",
        label: "Enspell no dmg",
        short: "NoDmg",
        category: "enspells_no_damage",
        detail:
          "The enspell set to wear when the damage build is not wanted (defense, SIRD, a skill-up set, ...).",
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
    autoModes: [
      {
        key: "immanence",
        label: "Immanence",
        short: "Immanence",
        category: "nuke_immanence",
        buff: 470,
        detail:
          "Worn for Elemental Magic while Immanence is active; the armed mode is the fallback.",
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
    autoModes: [
      {
        key: "immanence",
        label: "Immanence",
        short: "Immanence",
        category: "helix_immanence",
        buff: 470,
        detail:
          "Worn for helix spells while Immanence is active; the armed mode is the fallback.",
      },
    ],
  },
  {
    key: "dark",
    label: "Dark Magic",
    short: "Dark",
    defaultMode: "potency",
    modes: [
      {
        key: "potency",
        label: "Potency",
        short: "Pot",
        category: "dark_potency",
        detail:
          "Drain and Aspir potency set, plus Magic Attack for Kaustra and Death.",
      },
      {
        key: "macc",
        label: "Macc / landing",
        short: "Macc",
        category: "dark_macc",
        detail:
          "Dark Magic Skill / Magic Accuracy set for landing Stun, Bio, Curse and the Absorb spells.",
      },
      {
        key: "duration",
        label: "Duration",
        short: "Dur",
        category: "dark_duration",
        detail: "Dark Magic duration set for Bio, Absorb and the other Dark Magic debuffs.",
      },
    ],
  },
  {
    key: "divine",
    label: "Divine Magic",
    short: "Divine",
    defaultMode: "auto",
    // The Community Paladin Guide builds Flash as a magic-enmity set (Enmity and Fast Cast),
    // not as a nuke or a landing set, so the group splits like Enfeebles: Auto follows each
    // spell's own kind and arming a mode forces every Divine Magic spell through one set.
    modes: [
      {
        key: "auto",
        label: "Auto — by spell type",
        short: "Auto",
        detail: "Wear the kind row for each spell (Banish/Holy, Flash, Macc).",
      },
      {
        key: "mab",
        label: "Magic Attack",
        short: "MAB",
        category: "divine_mab",
        detail: "Force every Divine Magic spell through the Banish / Holy build.",
      },
      {
        key: "flash",
        label: "Flash (enmity)",
        short: "Flash",
        category: "divine_flash",
        detail: "Force every Divine Magic spell through the Flash enmity build.",
      },
      {
        key: "macc",
        label: "Macc / landing",
        short: "Macc",
        category: "divine_macc",
        detail: "Force every Divine Magic spell through the landing build.",
      },
    ],
    kinds: [
      {
        key: "mab",
        label: "Banish / Holy",
        short: "MAB",
        category: "divine_mab",
        detail: "The Banish and Holy lines: Magic Attack and MND carry the damage.",
      },
      {
        key: "flash",
        label: "Flash",
        short: "Flash",
        category: "divine_flash",
        detail:
          "Flash reads enmity, not damage: the guide's Enmity / Fast Cast build. Repoint the row at the library's Flash SIRD set when the cast has to survive.",
      },
      {
        key: "macc",
        label: "Macc / landing",
        short: "Macc",
        category: "divine_macc",
        detail: "Repose and any Divine Magic spell whose landing has to win.",
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
  {
    key: "blue",
    label: "Blue Magic",
    short: "Blue",
    defaultMode: "mab",
    modes: [
      {
        key: "mab",
        label: "Magic Attack",
        short: "MAB",
        category: "blue_mab",
        detail: "Magic Attack set for Blue Magic.",
      },
      {
        key: "macc",
        label: "Magic Accuracy",
        short: "Macc",
        category: "blue_macc",
        detail: "Magic Accuracy set for landing Blue Magic.",
      },
    ],
  },
  {
    key: "ninjutsu",
    label: "Ninjutsu",
    short: "Nin",
    defaultMode: "macc",
    modes: [
      {
        key: "macc",
        label: "Magic Accuracy",
        short: "Macc",
        category: "ninjutsu_macc",
        detail: "Magic Accuracy / Ninjutsu skill set for landing Ninjutsu.",
      },
      {
        key: "damage",
        label: "Ninjutsu damage",
        short: "Dmg",
        category: "ninjutsu_damage",
        detail: "Ninjutsu skill / Magic Attack set for elemental Ninjutsu.",
      },
    ],
  },
];

/** Jobs that can cast one spell group.  The sub job opens its groups at 49, so the same
 *  table drives main and sub cards; the spell list then trims to what that job can learn. */
export const SPELL_GROUP_JOBS: Record<SpellGroupKey, number[]> = {
  enfeebles: [3, 4, 5, 8, 16, 20, 21],
  enhancing: [3, 5, 7, 16, 20, 21],
  enspells: [5, 7, 8, 20, 21],
  curing: [3, 5, 7, 16, 20, 21],
  nuking: [4, 5, 15, 16, 20, 21],
  helix: [20],
  dark: [4, 5, 8, 16, 20, 21],
  divine: [3, 5, 7, 15, 20],
  songs: [10],
  blue: [16],
  ninjutsu: [13],
};

export const DEFAULT_SPELL_MODES: Record<SpellGroupKey, string> = Object.fromEntries(
  SPELL_GROUPS.map((group) => [group.key, group.defaultMode]),
) as Record<SpellGroupKey, string>;

export type PhaseConfig = {
  /** The config layout version, so a changed default can migrate a saved config once. */
  configVersion: number;
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
  configVersion: PHASE_CONFIG_VERSION,
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
  // Enfeebles: one path per kind.  A library that has only the plain enfeebling set
  // still binds every kind to it, so the behaviour is unchanged there; RDM.lua carries
  // the BG Wiki builds and each kind lands on its own set.
  enfeebles_skill: ["midcast.Enfeebling Magic Skill", "midcast.Enfeebling Magic"],
  enfeebles_macc: ["midcast.Enfeebling Magic Macc", "midcast.Enfeebling Magic"],
  enfeebles_duration: [
    "midcast.Enfeebling Magic Duration",
    "midcast.Enfeebling Magic Macc",
    "midcast.Enfeebling Magic",
  ],
  enfeebles_hybrid: ["midcast.Enfeebling Magic Hybrid", "midcast.Enfeebling Magic"],
  enfeebles_mnd: ["midcast.Enfeebling Magic MND", "midcast.Enfeebling Magic"],
  enfeebles_int: ["midcast.Enfeebling Magic INT", "midcast.Enfeebling Magic"],
  enfeebles_general: ["midcast.Enfeebling Magic General", "midcast.Enfeebling Magic"],
  // The Saboteur row is an overlay, not a replacement, so it only binds to the one-piece
  // overlay set; a library without one simply has no hands swap.
  enfeebles_saboteur: ["midcast.Enfeebling Magic Saboteur"],
  // Enhancing kinds.  The SIRD/Stoneskin sets are RDM's; other jobs fall through to the
  // generic enhancing set, so their behaviour is unchanged.  The duration kind prefers the
  // party build and Composure swaps in the self build while it is up.
  enhancing_skill: [
    "midcast.Enhancing Magic SIRD",
    "midcast.EnhancingSkill",
    "midcast.Enhancing Magic",
  ],
  enhancing_stoneskin: ["midcast.Enhancing Magic Stoneskin", "midcast.Enhancing Magic"],
  // Phalanx and Reprisal are the Community Paladin Guide builds; RDM and RUN carry Phalanx
  // too, and a library without the specific set keeps the generic enhancing set.
  enhancing_phalanx: ["midcast.Phalanx", "midcast.Enhancing Magic"],
  enhancing_reprisal: ["midcast.Reprisal", "midcast.Enhancing Magic"],
  enhancing_duration: [
    "midcast.EnhancingDurationOthers",
    "midcast.EnhancingDuration",
    "midcast.Enhancing Magic",
  ],
  enhancing_duration_self: ["midcast.EnhancingDuration"],
  enhancing_general: ["midcast.Enhancing Magic"],
  // The pre-kind categories stay mapped so an old saved config still resolves; the modes
  // no longer use them.
  buff_potency: ["midcast.Enhancing Magic"],
  buff_duration: ["midcast.EnhancingDuration", "midcast.Enhancing Magic"],
  cure_potency: ["midcast.Cure", "midcast.Healing Magic"],
  cure_cast: ["midcast.Healing Magic"],
  nuke_mab: ["midcast.Elemental Magic"],
  nuke_mdmg: ["midcast.Elemental Magic"],
  nuke_mb: ["midcast.Elemental Magic MB"],
  nuke_immanence: [],
  helix_magic: ["midcast.Elemental Magic"],
  helix_immanence: [],
  blue_mab: ["midcast.BlueMagic"],
  blue_macc: ["midcast.BlueMagic"],
  ninjutsu_macc: ["midcast.Ninjutsu"],
  ninjutsu_damage: ["midcast.Ninjutsu"],
  helix_duration: [],
  dark_potency: ["midcast.Dark Magic"],
  dark_macc: ["midcast.Dark Magic"],
  dark_duration: ["midcast.Dark Magic"],
  divine_mab: ["midcast.Divine Magic"],
  divine_flash: ["midcast.Flash", "midcast.Divine Magic"],
  divine_macc: ["midcast.Divine Magic"],
  enspells: ["midcast.Enspell", "midcast.EnhancingSkill"],
  // A library without a dedicated no-damage enspell set keeps the damage build until the
  // player picks their own set in the row.
  enspells_no_damage: ["midcast.EnspellNoDmg", "midcast.Enspell", "midcast.EnhancingSkill"],
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
    // exactly one face of the pair was configured.  A mode without a category (Enfeebles'
    // Auto, which follows each spell's own kind) never counts as a configured pick.
    const configured = group.modes.filter(
      (mode) => mode.category && overrides[mode.category],
    );
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
  const savedModes = objectMap(saved.spellModes);
  // Version 2 split Enfeebles into per-spell kinds.  A saved "macc" was the old default, not a
  // deliberate force, so move it to Auto once; a deliberate "duration" choice is kept.
  const configVersion = typeof saved.configVersion === "number" ? saved.configVersion : 1;
  if (configVersion < 2 && savedModes.enfeebles === "macc") savedModes.enfeebles = "auto";
  // Version 3 split Enhancing into per-spell kinds: the old potency/duration modes are gone,
  // so a saved one would otherwise be dropped by normalizeSpellModes anyway.  Move it to
  // Auto explicitly (including the old default "potency") so the kind rows take over.
  if (configVersion < 3) savedModes.enhancing = "auto";
  // Version 4 split Divine Magic into per-spell kinds: the old default "mab" would leave
  // Flash wearing the Banish / Holy set.  A deliberate "macc" pick is left alone.
  if (configVersion < 4 && (!savedModes.divine || savedModes.divine === "mab")) {
    savedModes.divine = "auto";
  }
  return {
    configVersion: PHASE_CONFIG_VERSION,
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
    spellModes: normalizeSpellModes(savedModes, spellCategoryOverrides),
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
    case "casting":
      return "Casting";
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
