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
  sub_level?: number;
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

export type GameWindowMode = "windowed" | "borderless" | "fullscreen" | "borderless-fullscreen";

/** One attached display, in the units the game's window API uses. */
export interface DisplayMonitor {
  /** What `launcher.json` remembers for this display; stable across launches. */
  id: string;
  name: string | null;
  width: number;
  height: number;
  workWidth: number;
  workHeight: number;
  physicalWidth: number;
  physicalHeight: number;
  scaleFactor: number;
  primary: boolean;
}

export interface DisplayInfo {
  monitors: DisplayMonitor[];
}

export interface ConfigView {
  apiUrl: string;
  username: string;
  characterId: number | null;
  /** The character selected in the global tenant bar; may be a sub-account box. */
  tenantCharacterId: number | null;
  gameDir: string;
  /** Optional separate install for windowless boxes; must match the Fanxi-headless build. */
  headlessGameDir: string;
  /** SSH target of the Linux host that runs headless boxes; empty means local. */
  remoteSsh: string;
  host64: string;
  repoRoot: string;
  apiInsecure: boolean;
  autoLogin: boolean;
  /** Cap the visible main client at 30 fps. */
  limitMainFps: boolean;
  /** The window every visible client opens at. */
  gameWindowMode: GameWindowMode;
  gameWidth: number;
  gameHeight: number;
  /** Window size divided by this is the menu resolution: 2 draws menus larger. */
  gameUiScale: number;
  /** The display the launcher window and the game open on; empty is the main display. */
  monitor: string;
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
  /** The account's saved phase/GearSwap config, loaded from the game database. */
  gearswapConfig: Record<string, unknown> | null;
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
  /** The support job, reported by the control addon; 0 when the character has none. */
  sub_job?: number;
  sub_level?: number;
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
  sleeping?: boolean;
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
  /** Roman rank for a ranked spell (the game draws it as an icon badge, not in `short`). */
  tier?: number | null;
}

/** One row of the server-side Magic Bag (visible bag, slip or locker). */
export interface MagicBagItem {
  source: "bag" | "slip" | "locker" | "claim";
  container: number;
  slot: number;
  item_id: number;
  quantity: number;
  name: string;
  equip_slot: string;
  slot_mask: number;
  jobs: number;
  level: number;
  skill: number;
  item_level: number;
  rare: number;
  ex: number;
  extra: string;
  augments: unknown[];
  slip?: number;
  purchase_id?: number;
  price?: number;
  purchased_at?: string;
}

/** The in-game combat HUD state reported by the control addon. */
export interface HudState {
  /** The master switch (`//hud` / Ctrl+H); every window below is hidden while it is off. */
  show_hud: boolean;
  show_abilities: boolean;
  show_spells: boolean;
  show_trusts: boolean;
  show_weapon_skills: boolean;
  /** The Battle Info and Party Info hubs drawn beside the action HUD. */
  show_battle_info: boolean;
  show_party_info: boolean;
  /** The Magic Bag inventory / Recycle Bin window. */
  show_inventory: boolean;
  /** The server-backed Target Debuffs window. */
  show_target: boolean;
  /** The in-game Equip View: collapsed it names the set being worn, expanded it is the
   * EquipViewer grid. */
  show_equipview?: boolean;
  /** The Battle automation HUD (the stop/start/follow window). */
  show_battle_hud: boolean;
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

/** One saved `//warp` place as the in-game Zoning page draws it. */
export interface HudWarpMark {
  slot: number;
  alias: string;
  zone_name: string;
}

/** A partial HUD update. `type` names the tab the layout fields apply to. */
export interface HudPatch {
  show_hud?: boolean;
  show_abilities?: boolean;
  show_spells?: boolean;
  show_trusts?: boolean;
  show_weapon_skills?: boolean;
  show_battle_info?: boolean;
  show_party_info?: boolean;
  show_inventory?: boolean;
  show_target?: boolean;
  show_equipview?: boolean;
  show_battle_hud?: boolean;
  /** The server-side Magic Bag rows pushed by the launcher. */
  inventory?: MagicBagItem[];
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
  /** Saved places for the Zoning spell page; sent by the launcher because the addon cannot
   * query the server's warp table. */
  warp_marks?: HudWarpMark[];
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
  remote: boolean;
  host: string | null;
  headless: boolean;
  sleeping: boolean;
  /** Server truth from `/world/online`; null/undefined means the roster could not be read. */
  serverOnline?: boolean | null;
}

export interface JobInfo {
  jobId: number;
  name: string;
  abbr: string;
  level: number;
  /** The support job paired with the main job; absent from older launcher cores. */
  subJobId?: number;
  subName?: string;
  subAbbr?: string;
  subLevel?: number;
  character: string;
}

export interface GearItem {
  name: string;
  augments: string[];
  /** The exact bag copy this piece was picked from, when the launcher knows it. */
  container?: number;
  slot?: number;
  item_id?: number;
  extra?: string;
}

/** One inventory copy as the set editor's picker sees it. */
export interface CharacterBagItem {
  container: number;
  slot: number;
  item_id: number;
  quantity: number;
  name: string;
  equip_slot: string;
  slot_mask: number;
  jobs: number;
  level: number;
  skill: number;
  item_level: number;
  /** Raw 24-byte augment block, hex. */
  extra: string;
  /** Decoded augment rows; empty when the copy is not augmented. */
  augments: string;
}

export interface CharacterBags {
  items: CharacterBagItem[];
}

/** One line inside a stat source: the item, trait, ability or buff that supplied it. */
export interface CharacterStatDetail {
  label: string;
  value: number;
  /** Augment/tooltip text for a gear row, e.g. "DEF+30 | Damage taken-3%". */
  note?: string;
}

/** One contributing layer (gear, food, JT, JA, buffs, ...) for a final stat. */
export interface CharacterStatSource {
  key: string;
  label: string;
  value: number;
  details: CharacterStatDetail[];
}

/** One row of the server's live checkparam-style sheet. */
export interface CharacterStat {
  key: string;
  label: string;
  value: number;
  percent: boolean;
  /** Shown on the compact card; false entries live only in the full-sheet modal. */
  primary: boolean;
  group: string;
  formula: string;
  sources: CharacterStatSource[];
  order: number;
}

/** The live stat sheet, built on the game server with every source kept apart. */
export interface CharacterStatReport {
  character_id: number;
  name: string;
  job: {
    main_job: number;
    main_level: number;
    sub_job: number;
    sub_level: number;
  };
  food: { item_id: number; name: string; until: number };
  updated: number;
  stats: CharacterStat[];
}

/** One normalized stat on an item, read from the client's tooltip or a GearSwap augment. */
export interface GearStat {
  key: string;
  label: string;
  value: number;
  /** Percent stats stay separate from flat stats with the same label (`HP+80` vs `HP+10%`). */
  percent: boolean;
  /** Preferred position in the Set totals list. */
  order: number;
}

/** One slot's client tooltip and normalized stats. */
export interface GearItemStats {
  slot: string;
  name: string;
  /** False when the client has no item with this name; augment stats still come back. */
  found: boolean;
  id: number;
  level: number;
  itemLevel: number;
  /** Readable base-stat lines, without conditional Set/Pet/Unity blocks. */
  baseLines: string[];
  /** The tooltip's numeric stats on their own. */
  baseStats: GearStat[];
  /** The numeric stats this slot's augment strings add. */
  augmentStats: GearStat[];
  /** Base and augment stats together, ready to total. */
  stats: GearStat[];
}

/** The request for one equipped slot: the item name plus the set's own augment strings. */
export interface GearStatQuery {
  slot: string;
  name: string;
  augments: string[];
  /** The live client's item id, when there is one; the backend prefers it over the name. */
  id?: number;
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
  /** The client's entity table has the leader in it. */
  leader_found: boolean;
  trail: number;
  points: number;
  cursor: number;
  goal: number;
}

export interface FollowEvent {
  line: string;
  at: number;
}

/** The Follow card's Fix button: the box was killed, relaunched and zoned to its leader. */
export interface FixFollowerResult {
  account: string;
  name: string;
  port: number;
  leader: string;
  zone: string;
  message: string;
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
  /** Prime weapon rows: the Armory now records only the final iLvl 119 III form. */
  prime_final?: boolean;
  prime_stage?: number;
  prime_stages?: number;
  /** REMA rows: the Armory records only the family's final afterglow form. */
  rema_final?: boolean;
  rema_family?: string;
}

export interface ArmoryItem {
  item_id: number;
  name: string;
  category?: string;
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
  /** Units held across bags, storage and the locker (migration 0156 Items tab). */
  held?: number;
  /** Rare: the Armory will not sell a second copy to the same character. Ex alone
   * does not limit purchases — it only stops the item being traded or sold. */
  unique: boolean;
  /** Prime weapons: the search returns only the family's final iLvl 119 III form. */
  prime_final?: boolean;
  prime_stage?: number;
  prime_stages?: number;
  prime_family?: string;
  /** REMA weapons: the search returns only the family's final afterglow form. */
  rema_final?: boolean;
  rema_family?: string;
}

/** One row of the Data page's Items store (non-equipment catalogue). */
export interface StoreItem {
  item_id: number;
  name: string;
  category: string;
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
  held: number;
  unique: boolean;
}

/** A filter chip in the Items store; `count` is the shelf size. */
export interface ItemCategory {
  name: string;
  count: number;
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

export interface AugmentCurrent {
  path: string;
  rank: number;
  tier: number;
  rp: number;
  curve: number;
  index: number;
}

export interface AugmentPath {
  key: string;
  label: string;
  bundle: number;
  rank: number;
  tier: number;
  rp: number;
  /** Lifetime RP for the cap, when the dataset tracks it (Oboro). */
  total_rp?: number;
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
  current: AugmentCurrent | null;
  paths: AugmentPath[];
}

/** One bag copy of an Oboro weapon plus the block it currently carries. */
export interface OboroCopy {
  container: number;
  slot: number;
  current: AugmentCurrent | null;
}

/** One Oboro weapon at one quality (NQ R15, HQ1 R20 or HQ2 R25). */
export interface OboroItem {
  item_id: number;
  name: string;
  slot: string;
  set: string;
  kind: "oboro";
  job: string;
  weapon: string;
  quality: string;
  quality_key: "nq" | "hq1" | "hq2";
  rank: number;
  tier: number;
  rp: number;
  total_rp: number;
  curve: number;
  price: number;
  owned: boolean;
  copies: OboroCopy[];
  paths: AugmentPath[];
}

/** The Data page's Oboro card: every family/quality, owned first. */
export interface OboroCatalog {
  source: string;
  note: string;
  max_rank: number;
  items: OboroItem[];
}

/** One decoded word in a cape's five-slot standard augment block. */
export interface CapeAugmentSlot {
  id: number;
  value: number;
  text: string;
}

/** The block currently stored on one cape copy. */
export interface CapeCopyAugments {
  text: string;
  /** The 198 preset build name, or null for a hand-built block. */
  build: string | null;
  slots: CapeAugmentSlot[];
}

/** A BG Wiki material choice found in one of the copy's slots. */
export interface CapeAugmentSelection {
  option: string;
  stage: number;
}

/** One bag/wardrobe copy of a job cape. */
export interface CapeCopy {
  container: number;
  slot: number;
  container_name: string;
  current: CapeCopyAugments;
  /** Material key -> the picker option currently in that slot, if recognised. */
  selection: Record<string, CapeAugmentSelection | null>;
}

/** One row of a BG Wiki Abdhaljs material table. */
export interface CapeAugmentOption {
  key: string;
  label: string;
  step: number;
  max_stage: number;
  max_value: number;
  /** Negative for reductions; the UI uses its sign for the value label. */
  multiplier: number;
  percent: boolean;
  hint: string;
  /** The client text at the maximum stage (e.g. "HP+60"). */
  max_text: string;
}

/** One of the five Abdhaljs materials, in client slot order. */
export interface CapeAugmentMaterial {
  key: string;
  label: string;
  slot: number;
  max_stage: number;
  items_to_max: number;
  hint: string;
  options: CapeAugmentOption[];
}

/** One of the 22 Ambuscade job capes. */
export interface AmbuscadeCape {
  job: string;
  job_number: number;
  item_id: number;
  name: string;
  /** Copies in the character's bags and wardrobes. */
  owned: number;
  /** Copies in the hidden locker. */
  locker: number;
  copies: CapeCopy[];
}

/** The Data page's Ambuscade card. */
export interface AmbuscadeCatalog {
  source: string;
  note: string;
  slots: number;
  materials: CapeAugmentMaterial[];
  capes: AmbuscadeCape[];
}

/** One stat row of a Nolan mezzotint path (already at its Rank 15 value). */
export interface NolanStat {
  key: string;
  value: number;
  text: string;
}

/** One decoded mezzotint block on an owned copy. */
export interface NolanCurrent {
  path: string;
  rank: number;
  rp: number;
  text: string;
  rows: NolanStat[];
}

/** One bag/wardrobe copy of an Escha item. */
export interface NolanCopy {
  container: number;
  container_name: string;
  slot: number;
  quantity: number;
  current: NolanCurrent | null;
}

/** One Escha item Nolan can mezzotint. */
export interface NolanItem {
  item_id: number;
  name: string;
  kind: string;
  slot: string;
  zone: string;
  group: string;
  /** Path letter A-D -> its three Rank 15 rows. */
  paths: Record<string, NolanStat[]>;
  copies: NolanCopy[];
}

/** The Data page's Nolan card. */
export interface NolanCatalog {
  note: string;
  levels: { max_rank: number; rp_total: number; slots: number };
  items: NolanItem[];
  catalog_size: number;
}

/** One stat the path can roll, with the largest value the editor can write. */
export interface GlypticStat {
  key: string;
  max: number;
  primary: boolean;
  text: string;
  clamped: boolean;
}

/** One path of an Arcane Glyptics table. */
export interface GlypticPath {
  label: string;
  stats: GlypticStat[];
  defaults: { key: string; value: number }[];
}

/** One bag/wardrobe copy of a Reisenjima piece. */
export interface GlypticCopy {
  container: number;
  container_name: string;
  slot: number;
  quantity: number;
  current: string;
  slots: string[];
  selection: ({ key: string; value: number } | null)[];
}

/** One Reisenjima armor piece or weapon Oseem can engrave. */
export interface GlypticItem {
  item_id: number;
  name: string;
  kind: string;
  slot: string;
  set: string;
  zone: string;
  /** Key into the catalog's path_sets (one table per armor set / weapon). */
  path_key: string;
  copies: GlypticCopy[];
  owned: boolean;
}

/** The Data page's Oseem card. */
export interface GlypticCatalog {
  note: string;
  slots: number;
  path_sets: Record<string, { label: string; paths: Record<string, GlypticPath> }>;
  items: GlypticItem[];
  catalog_size: number;
}

/** One row of a Skirmish item's augment table. */
export interface SkirmishOption {
  key: string;
  label: string;
  /** The tooltip text at the default value. */
  text: string;
  minimum: number;
  maximum: number;
  /** Values this row can hold step by this much (Save TP is 10, Pet: TP Bonus 20). */
  step: number;
  percent: boolean;
  /** The value the card starts from (the maximum for a beneficial row). */
  default: number;
}

/** One pickable row on a Skirmish item: a stone, DMG, or a bonus pool. */
export interface SkirmishSlot {
  key: string;
  label: string;
  /** A row retail always keeps: DMG on a weapon, PDT on Skirmish armor. */
  required: boolean;
  /** A clean copy starts with this row filled in (the Alluvion stones). */
  default_on: boolean;
  options: SkirmishOption[];
}

/** One bag/wardrobe copy of a Skirmish item. */
export interface SkirmishCopy {
  container: number;
  container_name: string;
  slot: number;
  quantity: number;
  current: string;
  slots: string[];
  selection: ({ key: string; value: number } | null)[];
}

/** One Skirmish weapon or armor piece Divainy-Gamainy augments. */
export interface SkirmishItem {
  item_id: number;
  name: string;
  kind: string;
  slot: string;
  group: string;
  family: string;
  quality: string;
  table: string;
  ranged: boolean;
  dmg_max: number;
  /** Key into the catalog's slot_sets (table + DMG cap + ranged). */
  slot_set: string;
  copies: SkirmishCopy[];
  owned: boolean;
}

/** The Data page's Divainy-Gamainy · Skirmish card. */
export interface SkirmishCatalog {
  note: string;
  sources: string[];
  slot_sets: Record<string, SkirmishSlot[]>;
  items: SkirmishItem[];
  catalog_size: number;
}

/** One maximum augment row on a Sinister Reign piece. */
export interface SinisterRow {
  key: string;
  value: number;
  /** The client tooltip text at this value (STR+10, "Dbl.Atk."+3%). */
  text: string;
}

/** One bag/wardrobe copy of a Sinister Reign piece. */
export interface SinisterCopy {
  container: number;
  container_name: string;
  slot: number;
  quantity: number;
  current: string;
  slots: string[];
  selection: ({ key: string; value: number } | null)[];
}

/** One Sinister Reign drop (Teodor, Morimar, Rosulatia, Arciela, Sajj'aka, August). */
export interface SinisterItem {
  item_id: number;
  name: string;
  slot: string;
  slot_name: string;
  kind: string;
  group: string;
  rows: SinisterRow[];
  copies: SinisterCopy[];
  owned: boolean;
}

/** The Data page's Sinister Reign card. */
export interface SinisterCatalog {
  note: string;
  sources: string[];
  items: SinisterItem[];
  catalog_size: number;
}

/** One fixed augment a Moonshade Earring can take. */
export interface MoonshadeOption {
  key: string;
  text: string;
  id: number;
  value: number;
}

export interface MoonshadeSet {
  key: string;
  label: string;
  options: MoonshadeOption[];
}

export interface MoonshadeCurrent {
  first: string | null;
  second: string | null;
  text: string[];
}

export interface MoonshadeCopy {
  container: number;
  container_name: string;
  slot: number;
  current: MoonshadeCurrent | null;
}

export interface MoonshadeCard {
  item_id: number;
  name: string;
  note: string;
  sets: MoonshadeSet[];
  copies: MoonshadeCopy[];
}

/** One Trial of the Magians step: what it turns the item into and the block it writes. */
export interface MagianTrial {
  id: number;
  reward: number;
  reward_name: string;
  num: number;
  text: string[];
}

export interface MagianCopy {
  container: number;
  slot: number;
  container_name: string;
  current: string;
}

export interface MagianItem {
  item_id: number;
  name: string;
  slot: string;
  level: number;
  kind: "weapon" | "armor";
  trials: MagianTrial[];
  copies: MagianCopy[];
}

export interface MagianCatalog {
  note: string;
  sources: string[];
  catalog_size: number;
  items: MagianItem[];
}

export interface TrustSummary {
  spells: number;
  key_items: string;
  summoning: boolean;
}

/** The Data page snapshot, as the server sends it (snake_case fields). */
/** One augment choice on a Shantotto's Ascension item. */
export interface AscensionOption {
  key: string;
  label: string;
  text: string;
}

/** One bag copy of an Ascension item with the rows it currently carries. */
export interface AscensionCopy {
  container: number;
  slot: number;
  container_name: string;
  text: string;
  choices: string[];
}

export interface AscensionItem {
  item_id: number;
  name: string;
  slot: string;
  copies: AscensionCopy[];
}

export interface AscensionCatalog {
  items: AscensionItem[];
  options: AscensionOption[];
}

/** One row of a merit menu: a rank and its in-game upgrade ladder. */
export interface MeritOption {
  id: number;
  name: string;
  max: number;
  value: number;
  costs: number[];
  upgrades: number;
  spent: number;
  next_cost: number;
}

/** One merit menu, either a general category or a job's Group 1/Group 2. */
export interface MeritCategory {
  id: number;
  name: string;
  hint: string;
  kind: "general" | "job";
  job: number;
  job_name: string;
  job_abbr: string;
  group: number;
  max: number;
  used: number;
  spent: number;
  merits: MeritOption[];
}

export interface CharacterData {
  character: {
    id: number;
    name: string;
    main_job: number;
    main_level: number;
    gil: number;
    mastery_rank: number;
  };
  merits: {
    points: number;
    cap: number;
    spent: number;
    categories: MeritCategory[];
  };
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
  mounts?: {
    count: number;
    all_available: boolean;
    last: string | null;
    current: string | null;
    names: string[];
  };
  currencies: { name: string; amount: number; updated_at: string }[];
  currency_catalog: string[];
  item_categories: ItemCategory[];
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
  oboro: OboroCatalog;
  capes: AmbuscadeCatalog;
  nolan: NolanCatalog;
  glyptics: GlypticCatalog;
  skirmish: SkirmishCatalog;
  sinister: SinisterCatalog;
  moonshade: MoonshadeCard;
  magian: MagianCatalog;
  ascension: AscensionCatalog;
}

export interface ArmoryAddResult {
  item: { item_id: number; name: string; quantity: number; price: number; purchased: boolean };
  data: CharacterData;
}

/** One saved place from `//warp mark`, numbered 1-1000. */
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
  | "battle"
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

/** One set the phase engine wore for an action, as the gear page's recent strip shows it. */
export type PhaseSwap = {
  /** The set path, e.g. "WS.Blitz"; null when the plan named it differently. */
  set: string | null;
  /** The action id behind it (78 = Blitz). */
  action: number;
  /** The action category: 3 magic, 7 weaponskill, 9 job ability. */
  category: number;
  /** How long the set was on (or has been on so far), in ms. */
  ms: number;
  /** True while the set is still worn. */
  active: boolean;
};

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
  /** Equipment slot indices (main 0 ... back 15) pinned by //gs lock. */
  lockedSlots?: number[];
  locked?: boolean;
  /** "engaged" | "movement" | "idle.town" | "idle.field" | "locked" */
  state?: string;
  /** The set path the host says is active, e.g. "idle.town". */
  set?: string | null;
  /** The action set on right now (e.g. "WS.Blitz") while an action holds it. */
  actionSet?: string | null;
  /** How long that action set has been on, in ms. */
  actionMs?: number;
  /** The action id behind it. */
  actionId?: number;
  /** The action sets the engine wore lately, newest first. */
  history?: PhaseSwap[];
  /** -1 before a zone is known, 1 in a town, 0 in the field. */
  town?: number;
  zone?: number;
  job?: number;
  path?: string;
  engaged_set?: string;
  kite_set?: string;
  rest_set?: string;
  focus_sets?: Record<string, string | null>;
  /** spell group key -> armed mode, mirrored from the host after //modes. */
  modes?: Record<string, string>;
  idle_town_set?: string;
  idle_field_set?: string;
  idle_set?: string;
  movement_set?: string;
};


/** One Battle hub profile, as the client stores it under <data>/battle/<character>/. */
export type BattleRole = "tank" | "puller" | "kiter" | "support" | "melee" | "ranged";
export type BattleSpellRow = { id: number; spell: string; below?: number; interval?: number; target?: "self" | "party" | "alliance" };
export type BattleRoster = {
  tank: string;
  puller: string;
  kiter: string;
  support: string[];
  melee: string[];
  ranged: string[];
};
export type BattleProfile = {
  version: number;
  name: string;
  zone: number;
  zone_name: string;
  updated: number;
  roster: BattleRoster;
  camp: { set: boolean; x: number; y: number; z: number; radius: number; show: boolean };
  support_camp: { set: boolean; x: number; y: number; z: number; radius: number; show: boolean };
  support: {
    geo: { enabled: boolean; indi: string; geo: string; indi_interval: number; geo_interval: number };
    brd: {
      enabled: boolean;
      tank_songs: string;
      support_songs: string;
      piano_tank: string;
      piano_support: string;
      nitro: "both" | "tank" | "support" | "off";
      interval: number;
    };
  };
  engage: {
    mode: "tank" | "puller" | "player" | "leader" | "always" | "none";
    player: string;
    wait_claim: boolean;
    camp_only: boolean;
    max_distance: number;
    switch_at: number;
    weapon_skill: string;
  };
  formation: { enabled: boolean; style: "tank" | "behind" | "side"; arc: number; spacing: number; side: "auto" | "left" | "right" };
  pull: {
    enabled: boolean;
    method: "ranged" | "spell" | "ability" | "melee";
    spell: string;
    ability: string;
    max_mobs: number;
    at_hp: number;
    leash: number;
    find_distance: number;
    mobs: string[];
    sleep_spell: string;
    bind_spell: string;
    sleep_extras: boolean;
  };
  heal: {
    enabled: boolean;
    observe: "party" | "alliance";
    emergency: number;
    mp_reserve: number;
    waltz: boolean;
    waltz_status: boolean;
    waltz_below: number;
    waltz_tp_reserve: number;
    cures: Array<{ id: number; spell: string; below: number }>;
    status: boolean;
    erase: boolean;
    raise_spell: string;
    avoid: string;
  };
  buffs: { enabled: boolean; rows: BattleSpellRow[] };
  enfeebles: { enabled: boolean; rows: BattleSpellRow[] };
  dispel: { enabled: boolean; spell: string; interval: number };
  death: { mode: "raise" | "homepoint"; wait: number; home_point: number };
  kiting: { enabled: boolean; mode: "circle" | "away" | "camp"; radius: number; below: number };
  loot: { mode: "free" | "lot" | "pass" | "leader" };
  priority: Array<"heal" | "buff" | "enfeeble" | "dispel">;
  paused: { melee: boolean; ranged: boolean; tank: boolean; support: boolean };
  ui: { x: number; y: number; opacity: number; show: boolean };
};

export type BattleProfileSummary = { file: string; name: string; zone: number; zone_name: string; updated: number };
export type BattleMember = {
  slot: number;
  name: string;
  job: number;
  level: number;
  /** The support job and its level, as the running client's party table reports them. */
  sub?: number;
  sub_level?: number;
  hpp: number;
  mpp: number;
  zone: number;
};
export type BattleMob = { name: string; hpp: number; distance: number; claimed: string | null };
export type BattleNote = { at: number; kind: "info" | "action" | "error"; text: string };
export type BattleStatus = {
  running: boolean;
  visible: boolean;
  role: BattleRole | null;
  role_label: string | null;
  paused: string[];
  dead: boolean;
  busy: boolean;
  camp: { x: number; y: number; z: number; radius: number; show: boolean } | null;
  support_camp: { x: number; y: number; z: number; radius: number; show: boolean } | null;
  in_camp: boolean;
  in_support_camp: boolean;
  target: { name: string; hpp: number; claimed_by: string | null } | null;
  last_action: string;
  last_action_at: number;
  name: string | null;
  role_names: BattleRoster | null;
  members?: BattleMember[];
  mobs?: BattleMob[];
  notes: BattleNote[];
  projection: boolean;
};
export type BattleState = {
  profile: BattleProfile;
  profiles: BattleProfileSummary[];
  status: BattleStatus;
  file: string | null;
  dirty: boolean;
  character: string | null;
  visible: boolean;
};
