import { invoke } from "@tauri-apps/api/core";
import type {
  ArmoryAddResult,
  ArmoryItem,
  Bootstrap,
  BuildResult,
  Character,
  CharacterData,
  ConfigView,
  ControlState,
  EquipIcons,
  FollowEvent,
  FollowStatus,
  GearDefaults,
  GearLibrary,
  GearLibrarySaveResult,
  GearSaveResult,
  GearSetResult,
  GearVersion,
  GearWeapon,
  HudPatch,
  HudState,
  InstanceView,
  JobAbility,
  JobInfo,
  JobSpell,
  LaunchAllResult,
  PhaseStatus,
  PublicView,
  ResolvedItem,
  SessionView,
  SubAccount,
  TeamMutation,
  TeamView,
  WarpList,
  WarpMutation,
} from "../types";

export class LauncherError extends Error {
  kind: string;
  status: number | null;
  code: string | null;

  constructor(message: string, kind = "error", status: number | null = null, code: string | null = null) {
    super(message);
    this.name = "LauncherError";
    this.kind = kind;
    this.status = status;
    this.code = code;
  }

  get unauthorized(): boolean {
    return this.status === 401;
  }
}

function toError(error: unknown): LauncherError {
  if (error && typeof error === "object") {
    const payload = error as Record<string, unknown>;
    if (typeof payload.message === "string") {
      return new LauncherError(
        payload.message,
        typeof payload.kind === "string" ? payload.kind : "error",
        typeof payload.status === "number" ? payload.status : null,
        typeof payload.code === "string" ? payload.code : null,
      );
    }
  }
  if (error instanceof Error) {
    return new LauncherError(error.message);
  }
  return new LauncherError(String(error));
}

export async function call<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw toError(error);
  }
}

export const backend = {
  bootstrap: () => call<Bootstrap>("bootstrap"),
  refreshPublic: () => call<PublicView>("refresh_public"),
  getConfig: () => call<ConfigView>("get_config"),

  login: (username: string, password: string, apiUrl?: string) =>
    call<SessionView>("login", { username, password, apiUrl: apiUrl || null }),
  register: (username: string, password: string, email: string | null, apiUrl?: string) =>
    call<SessionView>("register", { username, password, email, apiUrl: apiUrl || null }),
  logout: () => call<ConfigView>("logout"),
  switchAccount: (username: string) => call<SessionView>("switch_account", { username }),
  forgetAccount: (username: string) => call<ConfigView>("forget_account", { username }),

  createCharacter: (data: Record<string, unknown>) =>
    call<SessionView>("create_character", { data }),
  saveCharacterDesign: (characterId: number, data: Record<string, unknown>) =>
    call<SessionView>("save_character_design", { characterId, data }),
  characterData: (characterId: number) =>
    call<CharacterData>("character_data", { characterId }),
  characterAction: (
    characterId: number,
    action: string,
    payload: Record<string, unknown> = {},
  ) =>
    call<CharacterData & Partial<ArmoryAddResult>>("character_data_action", {
      characterId,
      action,
      payload,
    }),
  searchArmory: (characterId: number, query: string, kind: string | null) =>
    call<{ items: ArmoryItem[] }>("search_armory", { characterId, query, kind }),
  characterWarps: (characterId: number) =>
    call<WarpList>("character_warps", { characterId }),
  markCharacterWarp: (characterId: number, payload: Record<string, unknown>) =>
    call<WarpMutation>("character_warp_mark", { characterId, payload }),
  renameCharacterWarp: (characterId: number, slot: number, alias: string) =>
    call<WarpMutation>("character_warp_rename", { characterId, slot, alias }),
  deleteCharacterWarp: (characterId: number, slot: number) =>
    call<WarpMutation>("character_warp_delete", { characterId, slot }),
  selectCharacter: (characterId: number) =>
    call<ConfigView>("select_character", { characterId }),
  /** Persist the tenant bar's character; null clears it. */
  selectTenant: (characterId: number | null) =>
    call<ConfigView>("select_tenant", { characterId }),

  setLastPage: (page: string) => call<void>("set_last_page", { page }),

  saveSettings: (input: {
    apiUrl: string;
    gameDir: string;
    repoRoot: string;
    apiInsecure: boolean;
    autoLogin: boolean;
  }) => call<ConfigView>("save_settings", input),

  detectGameDir: (configured: string) =>
    call<string | null>("detect_game_dir", { configured }),
  findHost64: () => call<string | null>("find_host64"),
  defaultsDir: () => call<string | null>("defaults_dir"),

  buildGame: (gameDir: string) => call<BuildResult>("build_game", { gameDir }),
  buildLog: () => call<string[]>("build_log"),
  openDataDir: () => call<void>("open_data_dir"),

  launch: (account: string, characterId: number | null) =>
    call<InstanceView>("launch", { account, characterId }),
  launchAll: () => call<LaunchAllResult>("launch_all"),
  team: () => call<TeamView>("team"),
  createSub: (character: Record<string, unknown> | null) =>
    call<TeamMutation>("create_sub", { character }),
  activateSub: (subId: number) =>
    call<{ sub: SubAccount }>("activate_sub", { subId }),
  createSubCharacter: (subId: number, data: Record<string, unknown>) =>
    call<Character>("create_sub_character", { subId, data }),
  launchSub: (subId: number, characterId: number | null) =>
    call<InstanceView>("launch_sub", { subId, characterId }),
  launchTeam: () => call<LaunchAllResult>("launch_team"),
  deleteSub: (subId: number, purge: boolean) =>
    call<{ sub: SubAccount }>("delete_sub", { subId, purge }),
  listInstances: () => call<InstanceView[]>("list_instances"),
  stopInstance: (port: number) => call<void>("stop_instance", { port }),
  stopAll: () => call<number>("stop_all"),

  sendCommand: (port: number, line: string) =>
    call<unknown>("send_command", { port, line }),
  sendHud: (port: number, patch: HudPatch) => call<HudState>("send_hud", { port, patch }),
  sendChat: (port: number, line: string) => call<unknown>("send_chat", { port, line }),
  controlState: (port: number) => call<ControlState>("control_state", { port }),
  controlMetrics: (port: number) => call<Record<string, unknown>>("control_metrics", { port }),
  setFollow: (port: number, enabled: boolean, leader: string | null, distance = 1) =>
    call<FollowStatus>("set_follow", { port, enabled, leader, distance }),
  followStatus: (port: number) => call<FollowStatus>("follow_status", { port }),
  followEvents: (port: number) => call<FollowEvent[]>("follow_events", { port }),

  gearSlots: (port: number) => call<Record<string, unknown>>("gear_slots", { port }),
  equipIcons: (port: number, ids: number[]) =>
    call<EquipIcons>("equip_icons", { port, ids }),
  gearItemIds: (port: number, names: string[]) =>
    call<ResolvedItem[]>("gear_item_ids", { port, names }),
  clearIconCache: () => call<number>("clear_icon_cache"),
  gearJob: (port: number, savedCharacter: Character | null) =>
    call<JobInfo | null>("gear_job", { port, savedCharacter }),
  gearLoadDefault: (port: number, job: string | null) =>
    call<GearLibrary>("gear_load_default", { port, job }),
  gearLoadFile: (port: number, path: string) =>
    call<GearLibrary>("gear_load_file", { port, path }),
  gearEquip: (port: number, slot: string, item: string) =>
    call<unknown>("gear_equip", { port, slot, item }),
  gearWearSet: (port: number, items: Record<string, string>) =>
    call<unknown>("gear_wear_set", { port, items }),
  gearPhase: (
    port: number,
    enabled: boolean,
    path: string | null,
    engaged: string | null,
    idleTown: string | null,
    idleField: string | null,
    movement: string | null,
    options?: Record<string, unknown> | null,
  ) =>
    call<PhaseStatus>("gear_phase", {
      port,
      enabled,
      path,
      engaged,
      idleTown,
      idleField,
      movement,
      options: options ?? null,
    }),
  /** Clear the host's plan and stop holding action packets for this client. */
  gearPhaseOff: (port: number) =>
    call<PhaseStatus>("gear_phase", {
      port,
      enabled: false,
      path: null,
      engaged: null,
      idleTown: null,
      idleField: null,
      movement: null,
      options: null,
    }),
  gearPhaseStatus: (port: number) => call<PhaseStatus>("gear_phase_status", { port }),
  gearPhaseKiting: (port: number, on: boolean) =>
    call<{ kiting?: boolean; state?: string; set?: string | null; equipped?: number }>(
      "gear_phase_kiting",
      { port, on },
    ),
  gearPhaseResting: (port: number, on: boolean) =>
    call<{ resting?: boolean; state?: string; set?: string | null; equipped?: number }>(
      "gear_phase_resting",
      { port, on },
    ),
  gearPhaseFocus: (port: number, mode: string) =>
    call<{ focus?: number; state?: string; set?: string | null; equipped?: number }>(
      "gear_phase_focus",
      { port, mode },
    ),
  gearPhaseLockSlots: (port: number, mask: number) =>
    call<{
      lockedSlots?: number[];
      mask?: number;
      state?: string;
      set?: string | null;
      equipped?: number;
    }>("gear_phase_lock_slots", { port, mask }),
  gearJobSpells: (port: number) => call<{ spells: JobSpell[] }>("gear_job_spells", { port }),
  gearJobAbilities: (port: number) =>
    call<{
      abilities: JobAbility[];
      main?: number;
      main_level?: number;
      sub?: number;
      sub_level?: number;
    }>("gear_job_abilities", { port }),
  gearWeapons: (port: number) =>
    call<{ weapons: GearWeapon[]; main?: number; level?: number }>("gear_weapons", { port }),
  gearPhaseLock: (port: number, locked: boolean) =>
    call<{ locked?: boolean; state?: string; set?: string | null; equipped?: number }>(
      "gear_phase_lock",
      { port, locked },
    ),
  gearApplySet: (input: {
    sets: Record<string, Record<string, string>>;
    path: string;
    items: Record<string, string>;
    originalPath: string | null;
    keepOriginal: boolean;
  }) => call<GearSetResult>("gear_apply_set", input),
  gearSaveLibrary: (input: {
    path: string;
    sets: Record<string, Record<string, string>>;
    character: string;
    job: string;
    source: string;
  }) => call<GearLibrarySaveResult>("gear_save_library", input),
  gearSave: (input: {
    sets: Record<string, Record<string, string>>;
    base: string;
    character: string;
    job: string;
    source: string;
    folder: string | null;
  }) => call<GearSaveResult>("gear_save", input),
  gearVersions: () => call<GearVersion[]>("gear_versions"),
  gearDefaults: () => call<GearDefaults>("gear_defaults"),
  gameLog: (port: number, lines = 120) => call<string[]>("game_log", { port, lines }),
};
