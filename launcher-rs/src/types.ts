export interface CharacterDesign {
  race: number;
  race_key: string;
  race_name: string;
  gender: "male" | "female";
  race_label: string;
  face: number;
  hair: number;
  size: number;
  raw_face: number;
  variant: number;
  variants: number;
  face_label: string;
  hair_label: string;
  size_label: string;
  label: string;
}

export interface Character {
  id: number;
  name: string;
  race?: number;
  face?: number;
  hair?: number;
  size?: number;
  variant?: number;
  design?: CharacterDesign;
  nation?: number;
  main_job?: number;
  sub_job?: number;
  main_level?: number;
  zone?: number;
  hp?: number;
  mp?: number;
  hp_current?: number;
  mp_current?: number;
  exp?: number;
  exp_next?: number;
  gil?: number;
  [key: string]: unknown;
}

export interface AccountView {
  username: string;
  characterId: number | null;
  characters: Character[];
  tokenExpiresAt: string;
  signedIn: boolean;
}

export interface ConfigView {
  apiUrl: string;
  username: string;
  characterId: number | null;
  /** The character selected in the global tenant bar; may be a sub-account box. */
  tenantCharacterId: number | null;
  gameDir: string;
  host64: string;
  repoRoot: string;
  apiInsecure: boolean;
  autoLogin: boolean;
  lastPage: string;
  signedIn: boolean;
  accounts: AccountView[];
}

export interface SessionView {
  account: {
    id?: number;
    username: string;
    role?: string;
    status?: string;
    [key: string]: unknown;
  };
  characters: Character[];
  tokenExpiresAt: string;
}

export interface NewsItem {
  id?: number;
  slug?: string;
  title: string;
  body?: string;
  published_at?: string;
  [key: string]: unknown;
}

export interface WorldInfo {
  name?: string;
  host?: string;
  [key: string]: unknown;
}

export interface ServerStatus {
  name?: string;
  version?: string;
  time?: string;
  uptime_seconds?: number;
  online?: number;
  accounts?: number;
  sub_accounts?: number;
  characters?: number;
  registration_open?: boolean;
  world?: WorldInfo;
  features?: Record<string, boolean>;
  [key: string]: unknown;
}

export interface PublicView {
  status: ServerStatus | null;
  news: NewsItem[];
  error: string | null;
}

export interface Bootstrap {
  config: ConfigView;
  session: SessionView | null;
  sessionError: string | null;
  public: PublicView;
  repoRoot: string | null;
  gameDir: string | null;
  host64: string | null;
  gearswapDir: string | null;
  version: string;
}

export interface ControlPlayer {
  index?: number;
  id?: number;
  name?: string;
  hp?: number;
  mp?: number;
  tp?: number;
  hpp?: number;
  status?: number;
  hpmax?: number;
  mpmax?: number;
  exp?: number;
  exp_needed?: number;
  job?: number;
  level?: number;
  position?: { x?: number; y?: number; z?: number; heading?: number };
  [key: string]: unknown;
}

export interface ControlTarget {
  index?: number;
  id?: number;
  name?: string;
  hpp?: number;
  distance?: number;
}

export interface ControlState {
  login_status?: number;
  menu?: string | null;
  chat_input?: string | null;
  player?: ControlPlayer;
  zone?: { id?: number; name?: string | null };
  target?: ControlTarget;
  [key: string]: unknown;
}

export interface Kpi {
  exp?: number;
  exp_needed?: number;
  exp_percent?: number;
  exp_gained?: number;
  exp_per_hour?: number;
  dps?: number;
  damage?: number;
  damage_total?: number;
  session_seconds?: number;
  level?: number;
}

/** The four in-game HUD windows, each with its own layout and grouping. */
export type HudTypeKey = "abilities" | "spells" | "trusts" | "weapon_skills";
export type HudLayout = "grid" | "list" | "bar";
export type HudLabelMode = "always" | "hover" | "off";

export interface HudTypeState {
  layout: HudLayout;
  columns: number;
  size: number;
  labels: HudLabelMode;
  /** Label font size in px (7-12). The game scales it down further on very small tiles. */
  font: number;
  /** One group per page with a folder tab strip. */
  tabs: boolean;
  /** type, skill, element, job, none or custom. */
  group: string;
  /** Custom group names, in display order. */
  groups: string[];
  /** Item key (s123, a513, t896, w32) -> custom group name. */
  assign: Record<string, string>;
}

export interface HudItem {
  key: string;
  name: string;
  short: string;
}

/** The in-game combat HUD state reported by the control addon. */
export interface HudState {
  show_abilities: boolean;
  show_spells: boolean;
  show_trusts: boolean;
  show_weapon_skills: boolean;
  /** The Battle Info and Party Info hubs drawn beside the action HUD. */
  show_battle_info: boolean;
  show_party_info: boolean;
  edit: boolean;
  opacity: number;
  /** Hide left-side windows while the game's own menu is open. */
  menu_hide: boolean;
  types: Record<HudTypeKey, HudTypeState>;
  /** Counts for the four lists. */
  abilities: number;
  spells: number;
  trusts: number;
  weapon_skills: number;
  items: Record<HudTypeKey, HudItem[]>;
  character: string;
}

/** A partial HUD update. `type` names the tab the layout fields apply to. */
export interface HudPatch {
  show_abilities?: boolean;
  show_spells?: boolean;
  show_trusts?: boolean;
  show_weapon_skills?: boolean;
  show_battle_info?: boolean;
  show_party_info?: boolean;
  edit?: boolean;
  opacity?: number;
  menu_hide?: boolean;
  reset_positions?: boolean;
  type?: HudTypeKey;
  layout?: HudLayout;
  columns?: number;
  size?: number;
  labels?: HudLabelMode;
  font?: number;
  tabs?: boolean;
  group?: string;
  custom_groups?: string[];
  assign_key?: string;
  assign_group?: string | null;
}

export interface GearSlot {
  id?: number;
  bag?: number;
  index?: number;
  name?: string | null;
  count?: number;
}

export interface GearData {
  slots?: Record<string, GearSlot>;
  /** One bit per equipment slot, main first, from the client's 0x01B packet. */
  encumbrance?: number;
}

export interface Metrics {
  state?: ControlState;
  kpi?: Kpi;
  gear?: GearData;
  /** The in-game ability/spell overlay switches, from the control addon's hud command. */
  hud?: HudState | null;
  [key: string]: unknown;
}

export interface EquipIcons {
  /** item id -> PNG data URL */
  icons: Record<string, string>;
  /** ids the game had no icon for */
  missing: number[];
  error: string | null;
}

export interface ResolvedItem {
  name: string;
  id: number;
}

export interface InstanceView {
  account: string;
  character: Character;
  name: string;
  port: number;
  pid: number;
  startedAt: number;
  uptimeSeconds: number;
  alive: boolean;
  exitCode: number | null;
  state: ControlState | null;
  metrics: Metrics | null;
  error: string;
  logPath: string;
}

export interface JobInfo {
  jobId: number;
  name: string;
  abbr: string;
  level: number;
  character: string;
}

export interface GearItem {
  name: string;
  augments: string[];
}

export interface GearLibrary {
  path: string;
  sets: Record<string, Record<string, string>>;
  detailed: Record<string, Record<string, GearItem>>;
  job: JobInfo | null;
}

export interface GearDefaultFile {
  job: string;
  abbr: string;
  name: string;
  path: string;
}

export interface GearDefaults {
  folder: string;
  files: GearDefaultFile[];
}

export interface GearVersion {
  name: string;
  path: string;
  savedAt: string;
  character: string;
  job: string;
}

export interface GearSetResult {
  sets: Record<string, Record<string, string>>;
  path: string;
}

export interface GearSaveResult {
  path: string;
  profile: string;
}

export interface GearLibrarySaveResult {
  path: string;
  backup: string | null;
  persistent: boolean;
}

export interface LaunchAllResult {
  launched: InstanceView[];
  failed: { account: string; error: string }[];
}

/** A server-owned sub-account: no password, no token, launched by the main account. */
export interface SubAccount {
  id: number;
  username: string;
  status: string;
  parentId?: number;
  createdAt?: string;
  character: Character | null;
}

export interface TeamView {
  subs: SubAccount[];
  limit: number;
}

export interface TeamMutation {
  sub: SubAccount;
  limit: number;
}

/**
 * One character the launcher can scope its character pages to. The main account's characters
 * and every sub-account box use the same shape so the global tenant bar does not care which
 * account owns the character.
 */
export interface Tenant {
  character: Character;
  /** The account that owns the character (the main account or a box username). */
  account: string;
  kind: "main" | "sub";
  /** Short role label for the tenant bar: "Main" or "Box 2". */
  label: string;
  sub: SubAccount | null;
}

export interface FollowStatus {
  enabled: boolean;
  leader: string | null;
  state: string;
  distance: number;
  stuck: number;
  leaderFound: boolean;
  trail: number;
}

export interface FollowEvent {
  line: string;
  at: number;
}

export interface BuildEvent {
  line: string;
  phase: string | null;
  percent: number | null;
}

export interface BuildResult {
  host64: string;
  tail: string[];
}

/** One row of the Armory's purchase history.  `owned` is recomputed from every permanent
 * bag, storage and the locker each time the snapshot is read. */
export interface ArmoryPurchase {
  id: number;
  item_id: number;
  name: string;
  quantity: number;
  price: number;
  equip_slot: string;
  rare: number;
  ex: number;
  owned: boolean;
  created_at: string;
}

export interface ArmoryItem {
  item_id: number;
  name: string;
  equip_slot: string;
  level: number;
  item_level: number;
  jobs: number;
  rare: number;
  ex: number;
  stack: number;
  skill: number;
  price: number;
  base_sell: number;
  description: string;
  owned: boolean;
  /** Rare or Ex: the Armory will not sell a second copy to the same character. */
  exclusive: boolean;
}

export interface CharacterRanks {
  nation: number;
  sandoria: number;
  bastok: number;
  windurst: number;
  points: number;
  rank_max: number;
  mog_garden_rank: number;
  mog_garden_max: number;
}

export interface JobProgress {
  job: number;
  level: number;
  master_level: number;
}

export interface CraftSkill {
  skill_id: number;
  name: string;
  value: number;
}

export interface FameEntry {
  city: string;
  value: number;
}

export interface AugmentPath {
  key: string;
  label: string;
  bundle: number;
  rank: number;
  tier: number;
  rp: number;
  curve: number;
  augments: string[];
}

export interface AugmentItem {
  container: number;
  slot: number;
  item_id: number;
  name: string;
  slot_name: string;
  set: string;
  kind: string;
  quantity: number;
  current: {
    path: string;
    rank: number;
    tier: number;
    rp: number;
    curve: number;
    index: number;
  } | null;
  paths: AugmentPath[];
}

export interface TrustSummary {
  spells: number;
  key_items: string;
  summoning: boolean;
}

/** The Data page snapshot, as the server sends it (snake_case fields). */
export interface CharacterData {
  character: {
    id: number;
    name: string;
    main_job: number;
    main_level: number;
    gil: number;
    mastery_rank: number;
  };
  merits: { points: number; cap: number };
  job_points: {
    all_capped: boolean;
    jobs: number;
    current: number;
    capacity: number;
    spent: number;
  };
  mastery_rank: number;
  mastery_rank_max: number;
  gil: number;
  gil_max: number;
  home_points: { registered: number; total: number };
  survival_guides: { total: number; all_available: boolean };
  key_items: { tables: number; all_granted: boolean };
  currencies: { name: string; amount: number; updated_at: string }[];
  currency_catalog: string[];
  purchases: ArmoryPurchase[];
  ranks: CharacterRanks;
  fame: FameEntry[];
  fame_max: number;
  jobs: JobProgress[];
  exemplar: { points: number; next: number };
  crafts: CraftSkill[];
  craft_max: number;
  trusts: TrustSummary;
  augments: AugmentItem[];
}

export interface ArmoryAddResult {
  item: { item_id: number; name: string; quantity: number; price: number; purchased: boolean };
  data: CharacterData;
}

/** One saved place from `/!warp mark`, numbered 1-1000. */
export interface WarpPoint {
  slot: number;
  alias: string;
  zone: number;
  zone_name: string;
  x: number;
  y: number;
  z: number;
  rot: number;
  created_at: string;
  updated_at: string;
}

/** The Warps page snapshot. */
export interface WarpList {
  character: {
    id: number;
    name: string;
    zone: number;
    zone_name: string;
    position: { x: number; y: number; z: number; rot: number };
  };
  warps: WarpPoint[];
  limit: number;
  next_slot: number | null;
}

/** Mark, rename and delete all return the refreshed list plus the row they touched. */
export interface WarpMutation {
  data: WarpList;
  warp?: WarpPoint;
  deleted?: WarpPoint;
}

export type Page =
  | "home"
  | "characters"
  | "design"
  | "accounts"
  | "team"
  | "control"
  | "warps"
  | "data"
  | "gear"
  | "news"
  | "settings";


/** What the host's precast/midcast engine is doing for one client. */
export interface JobSpell {
  id: number;
  name: string;
  skill: string;
  level: number;
  /** Spell-override groups the host puts this spell in (enfeebles_macc, helix_magic, ...). */
  categories?: string[];
}

/** An ability the current main/sub job pair can use, from the client's ability menu. */
export interface JobAbility {
  id: number;
  name: string;
  type: string;
  recastId?: number;
}

/** A weapon or ammo item in the character's bags that the current main job can equip. */
export interface GearWeapon {
  id: number;
  name: string;
  /** Client slot mask: 1 main, 2 sub, 4 ranged, 8 ammo. */
  slots: number;
  /** Number of inventory copies (for Main/Sub duplicate checks). */
  count: number;
  /** Total stack size (ammo). */
  quantity: number;
  level: number;
  itemLevel: number;
  damage: number;
  delay: number;
  skill: number;
  category: string;
}

export type PhaseStatus = {
  enabled: boolean;
  player?: number;
  sets?: number;
  rules?: number;
  actions?: number;
  seen?: number;
  held?: number;
  restored?: number;
  restoredLate?: number;
  pending?: boolean;
  pendingAction?: number;
  settling?: boolean;
  ws?: number;
  ja?: number;
  magic?: number;
  swapped?: number;
  engaged?: boolean;
  moving?: boolean;
  kiting?: boolean;
  resting?: boolean;
  /** 0 auto, 1 dt, 2 pdt, 3 mdt, 4 eva, 5 meva */
  focus?: number;
  /** Equipment slot indices (main 0 ... back 15) pinned by /!gs lock. */
  lockedSlots?: number[];
  locked?: boolean;
  /** "engaged" | "movement" | "idle.town" | "idle.field" | "locked" */
  state?: string;
  /** The set path the host says is active, e.g. "idle.town". */
  set?: string | null;
  /** -1 before a zone is known, 1 in a town, 0 in the field. */
  town?: number;
  zone?: number;
  job?: number;
  path?: string;
  engaged_set?: string;
  kite_set?: string;
  rest_set?: string;
  focus_sets?: Record<string, string | null>;
  idle_town_set?: string;
  idle_field_set?: string;
  idle_set?: string;
  movement_set?: string;
};
