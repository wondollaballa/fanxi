import type { Character, ControlState, InstanceView } from "../types";

export const RACES = [
  { value: 1, label: "Hume male" },
  { value: 2, label: "Hume female" },
  { value: 3, label: "Elvaan male" },
  { value: 4, label: "Elvaan female" },
  { value: 5, label: "Tarutaru male" },
  { value: 6, label: "Tarutaru female" },
  { value: 7, label: "Mithra" },
  { value: 8, label: "Galka" },
];

export const NATIONS = [
  { value: 0, label: "San d'Oria" },
  { value: 1, label: "Bastok" },
  { value: 2, label: "Windurst" },
];

export const JOBS = [
  "Warrior",
  "Monk",
  "White Mage",
  "Black Mage",
  "Red Mage",
  "Thief",
  "Paladin",
  "Dark Knight",
  "Beastmaster",
  "Bard",
  "Ranger",
  "Samurai",
  "Ninja",
  "Dragoon",
  "Summoner",
  "Blue Mage",
  "Corsair",
  "Puppetmaster",
  "Dancer",
  "Scholar",
  "Geomancer",
  "Rune Fencer",
];

export const JOB_ABBRS = [
  "WAR",
  "MNK",
  "WHM",
  "BLM",
  "RDM",
  "THF",
  "PLD",
  "DRK",
  "BST",
  "BRD",
  "RNG",
  "SAM",
  "NIN",
  "DRG",
  "SMN",
  "BLU",
  "COR",
  "PUP",
  "DNC",
  "SCH",
  "GEO",
  "RUN",
];

export const ZONES: Record<number, string> = {
  48: "Al Zahbi",
  50: "Aht Urhgan Whitegate",
  100: "West Ronfaure",
  101: "East Ronfaure",
  102: "La Theine Plateau",
  103: "Valkurm Dunes",
  104: "Jugner Forest",
  105: "Batallia Downs",
  106: "North Gustaberg",
  107: "South Gustaberg",
  108: "Konschtat Highlands",
  109: "Pashhow Marshlands",
  110: "Rolanberry Fields",
  111: "Beaucedine Glacier",
  112: "Xarcabard",
  113: "Cape Teriggan",
  114: "Eastern Altepa Desert",
  115: "West Sarutabaruta",
  116: "East Sarutabaruta",
  117: "Tahrongi Canyon",
  118: "Buburimu Peninsula",
  119: "Meriphataud Mountains",
  120: "Sauromugue Champaign",
  121: "The Sanctuary of Zi'Tah",
  122: "Ro'Maeve",
  123: "Yuhtunga Jungle",
  124: "Yhoator Jungle",
  125: "Western Altepa Desert",
  126: "Qufim Island",
  127: "Behemoth's Dominion",
  128: "Valley of Sorrows",
  130: "Ru'Aun Gardens",
  230: "Southern San d'Oria",
  231: "Northern San d'Oria",
  232: "Port San d'Oria",
  233: "Chateau d'Oraguille",
  234: "Bastok Mines",
  235: "Bastok Markets",
  236: "Port Bastok",
  237: "Metalworks",
  238: "Windurst Waters",
  239: "Windurst Walls",
  240: "Port Windurst",
  241: "Windurst Woods",
  243: "Ru'Lude Gardens",
  244: "Upper Jeuno",
  245: "Lower Jeuno",
  246: "Port Jeuno",
  247: "Rabao",
  248: "Selbina",
  249: "Mhaura",
  250: "Kazham",
};

export const SLOT_KEYS = [
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
];

export const SLOT_LABELS: Record<string, string> = {
  main: "Main",
  sub: "Sub",
  range: "Range",
  ranged: "Range",
  ammo: "Ammo",
  head: "Head",
  body: "Body",
  hands: "Hands",
  legs: "Legs",
  feet: "Feet",
  neck: "Neck",
  waist: "Waist",
  ear1: "Left ear",
  ear2: "Right ear",
  ring1: "Left ring",
  ring2: "Right ring",
  back: "Back",
};

export function raceName(value?: number): string {
  return RACES.find((race) => race.value === value)?.label ?? "Adventurer";
}

export function nationName(value?: number): string {
  return NATIONS.find((nation) => nation.value === value)?.label ?? "Unaffiliated";
}

export function jobName(value?: number): string {
  if (!value || value < 1 || value > JOBS.length) return "Adventurer";
  return JOBS[value - 1];
}

export function jobAbbr(value?: number): string {
  if (!value || value < 1 || value > JOB_ABBRS.length) return "—";
  return JOB_ABBRS[value - 1];
}

/** A main job and its support job, with the levels when they are known. */
export interface JobPair {
  main?: number;
  mainLevel?: number;
  sub?: number;
  subLevel?: number;
}

function knownJob(value?: number): number {
  const job = Number(value ?? 0);
  return Number.isInteger(job) && job >= 1 && job <= JOB_ABBRS.length ? job : 0;
}

function knownLevel(value?: number): number {
  const level = Math.trunc(Number(value ?? 0));
  return Number.isFinite(level) && level > 0 ? level : 0;
}

/** "WAR 99", or just "WAR" when the level is not known yet. */
export function jobLevel(value?: number, level?: number): string {
  const job = knownJob(value);
  if (!job) return "—";
  const amount = knownLevel(level);
  return amount > 0 ? `${jobAbbr(job)} ${amount}` : jobAbbr(job);
}

/** "WAR 99 / NIN 49", or the main job alone when there is no support job. */
export function jobPairAbbr(pair: JobPair): string {
  const main = knownJob(pair.main);
  if (!main) return "Adventurer";
  const text = jobLevel(main, pair.mainLevel);
  const sub = knownJob(pair.sub);
  return sub ? `${text} / ${jobLevel(sub, pair.subLevel)}` : text;
}

/** "Warrior 99 / Ninja 49", or the main job alone when there is no support job. */
export function jobPairName(pair: JobPair): string {
  const main = knownJob(pair.main);
  if (!main) return "Adventurer";
  const mainLevel = knownLevel(pair.mainLevel);
  const text = mainLevel > 0 ? `${jobName(main)} ${mainLevel}` : jobName(main);
  const sub = knownJob(pair.sub);
  if (!sub) return text;
  const subLevel = knownLevel(pair.subLevel);
  return `${text} / ${subLevel > 0 ? `${jobName(sub)} ${subLevel}` : jobName(sub)}`;
}

export function characterJobPair(character?: Character | null): JobPair {
  return {
    main: character?.main_job,
    mainLevel: character?.main_level,
    sub: character?.sub_job,
    subLevel: character?.sub_level,
  };
}

export function characterJob(character?: Character | null): string {
  return jobPairAbbr(characterJobPair(character));
}

/** The full-name form, for cards with room for "Warrior 99 / Ninja 49". */
export function characterJobLabel(character?: Character | null): string {
  return jobPairName(characterJobPair(character));
}

/**
 * The job pair for a running client, preferring the addon's live main/support job over the
 * saved character row. An older addon reports no `sub_job`, so the saved support job fills in.
 */
export function instanceJobPair(instance?: InstanceView | null): JobPair {
  const player = instance?.state?.player;
  const character = instance?.character;
  return {
    main: player?.job ?? character?.main_job,
    mainLevel: player?.level ?? character?.main_level,
    sub: player?.sub_job ?? character?.sub_job,
    subLevel: player?.sub_level ?? character?.sub_level,
  };
}

export function zoneName(value?: number): string {
  if (!value) return "Unknown zone";
  return ZONES[value] ?? `Zone ${value}`;
}

export function characterName(character?: Character | null): string {
  return character?.name ?? "Adventurer";
}

export function prettyDate(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function timeAgo(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function formatDuration(seconds?: number): string {
  const value = Math.max(0, Math.floor(seconds ?? 0));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${value}s`;
}

export function formatNumber(value?: number, digits = 0): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function pct(current?: number, max?: number): number {
  if (!max || max <= 0 || current === undefined) return 0;
  return Math.max(0, Math.min(100, (current / max) * 100));
}

export function playerName(state?: ControlState | null): string {
  return state?.player?.name ?? "";
}

export function stateZone(state?: ControlState | null): string {
  return state?.zone?.name ?? (state?.zone?.id ? `Zone ${state.zone.id}` : "—");
}

/**
 * The server has answered authoritatively that this client has no zone session.
 *
 * A client keeps its last `login_status` and zone after a server restart, so its own state
 * cannot see the difference. `serverOnline` is only false when the server's live roster said
 * so; null/undefined (older server, gateway off, network failure) must never mark a box stale.
 */
export function serverSaysOffline(instance?: InstanceView | null): boolean {
  const status = instance?.state?.login_status;
  if (instance?.serverOnline !== false) return false;
  const uptime = instance?.uptimeSeconds ?? 0;
  if (status === 2) return uptime > 15;
  // At the title/login screens a box is legitimately absent from the roster; only call it
  // stale once a normal sign-in (or a client that noticed the restart) has had time to finish.
  return status === 0 && uptime > 60;
}

/** A client that says it is in world while the server has no session for it. */
export function orphanedSession(instance?: InstanceView | null): boolean {
  return instance?.state?.login_status === 2 && serverSaysOffline(instance);
}

/**
 * A running process is not a running character. Only `login_status === 2` backed by the
 * server (or unverifiable) counts as in world; an orphaned session does not.
 */
export function inWorld(instance?: InstanceView | null): boolean {
  if (!instance || orphanedSession(instance)) return false;
  const status = instance.state?.login_status;
  if (typeof status === "number") return status === 2;
  // Before the addon reported the status, the character block was the only signal.
  return Boolean(instance.state?.player && instance.state.zone?.id);
}

/**
 * The control addon reports the client's own axes: `x`/`y` are the ground plane and `z` is
 * height. The server's `//pos`/`//zone` commands and its warp rows take `x`, `y` (height),
 * `z` (ground). Convert at that boundary: forwarding the block unchanged puts a box hundreds
 * of yalms above the world, where no entity is in range and follow stays `waiting`.
 */
export function serverPosition(
  position?: { x?: number; y?: number; z?: number } | null,
): { x: number; y: number; z: number } | null {
  const x = Number(position?.x);
  const y = Number(position?.y);
  const z = Number(position?.z);
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return null;
  return { x, y: z, z: y };
}

export function slotLabel(slot: string): string {
  return SLOT_LABELS[slot] ?? slot;
}

export function clampText(value: string, max = 80): string {
  const text = value.trim();
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}
