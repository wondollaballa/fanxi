import type { Character, ControlState } from "../types";

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

export function zoneName(value?: number): string {
  if (!value) return "Unknown zone";
  return ZONES[value] ?? `Zone ${value}`;
}

export function characterName(character?: Character | null): string {
  return character?.name ?? "Adventurer";
}

export function characterJob(character?: Character | null): string {
  return `${jobAbbr(character?.main_job)} · ${jobName(character?.main_job)}`;
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

export function slotLabel(slot: string): string {
  return SLOT_LABELS[slot] ?? slot;
}

export function clampText(value: string, max = 80): string {
  const text = value.trim();
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}
