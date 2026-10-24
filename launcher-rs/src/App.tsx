import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import type {
  Bootstrap,
  BuildEvent,
  Character,
  ConfigView,
  HudPatch,
  HudState,
  InstanceView,
  Page,
  SessionView,
  SubAccount,
  TeamView,
} from "./types";
import { backend, LauncherError } from "./lib/api";
import { JOB_ABBRS } from "./lib/format";
import { buildTenants, resolveTenant } from "./lib/tenant";
import {
  loadPhaseConfig,
  loadPhaseEnabled,
  phaseOptions,
  savePhaseEnabled,
} from "./lib/phase";
import { Sidebar } from "./components/Sidebar";
import { AuthPage } from "./components/AuthPage";
import { HomePage } from "./components/HomePage";
import { CharactersPage } from "./components/CharactersPage";
import { DesignPage } from "./components/DesignPage";
import { AccountsPage } from "./components/AccountsPage";
import { TeamPage } from "./components/TeamPage";
import { ControlPage } from "./components/ControlPage";
import { WarpsPage } from "./components/WarpsPage";
import { GearPage } from "./components/GearPage";
import { DataPage } from "./components/DataPage";
import { TenantBar } from "./components/TenantBar";
import { SettingsPage } from "./components/SettingsPage";
import { NewsPage } from "./components/NewsPage";
import { ConfirmDialog, Toast } from "./components/ui";
import "./styles.css";

type ToastState = { kind: "success" | "error" | "info"; message: string };

// The plan's library is stored from the last session. When the character logs in on another
// job, a job-named default (gearswap/NIN.lua) has to follow the live job, or the first push
// would keep the old job's sets until the Gear page is opened.
async function libraryForLiveJob(library: string, state: unknown): Promise<string> {
  const player = (state as { player?: { job?: number } } | null)?.player;
  const job = Number(player?.job ?? 0);
  if (!(job >= 1 && job <= JOB_ABBRS.length)) return library;
  const abbr = JOB_ABBRS[job - 1];
  const base = library.split(/[/\\]/).pop() ?? "";
  if (!/^[A-Za-z]{3}\.lua$/.test(base)) return library; // an imported custom library stays
  if (base.toLowerCase() === `${abbr.toLowerCase()}.lua`) return library;
  try {
    const defaults = await backend.gearDefaults();
    const file = defaults.files.find((item) => item.abbr.toUpperCase() === abbr);
    if (file?.path) return file.path;
  } catch {
    // Fall through to the sibling path; the client's host reloads the job file itself too.
  }
  return library.replace(/[^/\\]+$/, `${abbr}.lua`);
}
const PAGES: Page[] = [
  "home",
  "characters",
  "design",
  "accounts",
  "team",
  "control",
  "warps",
  "data",
  "gear",
  "news",
  "settings",
];

function messageOf(error: unknown): string {
  if (error instanceof LauncherError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}

export default function App() {
  const [boot, setBoot] = useState<Bootstrap | null>(null);
  const [session, setSession] = useState<SessionView | null>(null);
  const [page, setPage] = useState<Page>("home");
  const [addAccount, setAddAccount] = useState(false);
  const [reloginUsername, setReloginUsername] = useState<string | null>(null);
  const [instances, setInstances] = useState<InstanceView[]>([]);
  const [team, setTeam] = useState<TeamView | null>(null);
  const [teamLoading, setTeamLoading] = useState(false);
  const [teamError, setTeamError] = useState("");
  const [buildEvents, setBuildEvents] = useState<BuildEvent[]>([]);
  const [buildLog, setBuildLog] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [fatal, setFatal] = useState("");
  const [confirmStopAll, setConfirmStopAll] = useState(false);
  /** The global tenant bar's character. `null` while the saved choice is unknown or stale. */
  const [tenantCharacterId, setTenantCharacterId] = useState<number | null>(null);
  /** The saved tenant is read once, after the launcher config arrives. */
  const tenantSeeded = useRef(false);
  /** The master GearSwap switch. Every client follows it; the Gear page and Settings toggle the
   * same setting, and it is off until someone asks for automatic swapping. */
  const [gearSwapOn, setGearSwapOn] = useState(loadPhaseEnabled);
  /** Latest switch value for async pushes that started before a toggle. */
  const gearSwapOnRef = useRef(gearSwapOn);
  const toastTimer = useRef<number | null>(null);
  const initialPageDone = useRef(false);

  const notify = useCallback((message: string, kind: ToastState["kind"] = "info") => {
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    setToast({ message, kind });
    toastTimer.current = window.setTimeout(() => setToast(null), 5000);
  }, []);

  const setGearSwap = useCallback(
    (enabled: boolean) => {
      // Update the ref before the state so an in-flight enable sees the stop immediately.
      gearSwapOnRef.current = enabled;
      setGearSwapOn(enabled);
      notify(
        enabled
          ? "GearSwap on — auto-swap starts on every running client"
          : "GearSwap off — every client stopped auto-swapping",
        enabled ? "success" : "info",
      );
    },
    [notify],
  );

  // Keep the shared preference even while no client is running. It belongs to the launcher, not
  // to one Gear window: turning it off in Settings or on the Gear page means the same thing.
  useEffect(() => {
    savePhaseEnabled(gearSwapOn);
  }, [gearSwapOn]);

  const applyBootstrap = useCallback((value: Bootstrap) => {
    setBoot(value);
    setSession(value.session);
  }, []);

  const refreshInstances = useCallback(async () => {
    try {
      setInstances(await backend.listInstances());
    } catch {
      // A closed game or a control port that is still starting is not fatal.
    }
  }, []);

  const loadTeam = useCallback(async () => {
    if (!session) {
      setTeam(null);
      setTeamError("");
      return;
    }
    setTeamLoading(true);
    try {
      setTeam(await backend.team());
      setTeamError("");
    } catch (error) {
      setTeamError(messageOf(error));
    } finally {
      setTeamLoading(false);
    }
  }, [session]);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    try {
      const value = await backend.bootstrap();
      applyBootstrap(value);
      setFatal("");
      if (value.session) await refreshInstances();
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setRefreshing(false);
    }
  }, [applyBootstrap, notify, refreshInstances]);

  useEffect(() => {
    let cancelled = false;
    backend
      .bootstrap()
      .then((value) => {
        if (cancelled) return;
        setBoot(value);
        setSession(value.config.autoLogin ? value.session : null);
        backend.buildLog().then((lines) => !cancelled && setBuildLog(lines)).catch(() => undefined);
        if (value.session && value.config.autoLogin) {
          backend
            .listInstances()
            .then((list) => !cancelled && setInstances(list))
            .catch(() => undefined);
        }
      })
      .catch((error) => !cancelled && setFatal(messageOf(error)));
    return () => {
      cancelled = true;
    };
  }, [applyBootstrap]);

  useEffect(() => {
    if (!session) return;
    backend.setLastPage(page).catch(() => undefined);
  }, [page, session]);

  // The precast/midcast plan lives in the client's host, so it has to be pushed again for every
  // client that appears - not only while the Gear page happens to be open. Turning the master
  // switch off has to reach the hosts that already have a plan, not merely stop new pushes.
  const phasePushed = useRef<Set<number>>(new Set());
  const phaseTries = useRef<Map<number, number>>(new Map());
  const phaseRepush = useRef<Set<number>>(new Set());
  const phaseOffSent = useRef<Set<number>>(new Set());
  useEffect(() => {
    const alive = new Set(instances.filter((item) => item.alive).map((item) => item.port));
    for (const port of phasePushed.current) if (!alive.has(port)) phasePushed.current.delete(port);
    for (const port of phaseTries.current.keys()) if (!alive.has(port)) phaseTries.current.delete(port);
    for (const port of phaseRepush.current) if (!alive.has(port)) phaseRepush.current.delete(port);
    for (const port of phaseOffSent.current) if (!alive.has(port)) phaseOffSent.current.delete(port);

    if (!gearSwapOn) {
      // Hard stop: clear each host's plan, pending state and session overrides, not just our
      // copy. A client that is still signing in is disabled again once it appears.
      phasePushed.current.clear();
      phaseTries.current.clear();
      phaseRepush.current.clear();
      for (const port of alive) {
        if (phaseOffSent.current.has(port)) continue;
        phaseOffSent.current.add(port);
        void backend.gearPhaseOff(port).catch(() => {
          // The control port is probably still starting; try again on the next poll.
          phaseOffSent.current.delete(port);
        });
      }
      return;
    }

    phaseOffSent.current.clear();
    const library = localStorage.getItem("fanxi.phase.library");
    if (!library) return;
    const config = loadPhaseConfig();
    const engaged = config.engaged;
    const idleTown = config.idleTown;
    const idleField = config.idleField;
    const movement = config.movement;
    const options = phaseOptions(config);
    for (const port of alive) {
      if (phasePushed.current.has(port)) continue;
      if ((phaseTries.current.get(port) ?? 0) >= 60) continue;
      phaseTries.current.set(port, (phaseTries.current.get(port) ?? 0) + 1);
      void (async () => {
        try {
          // Wait until the character is in the world: before that the bags are empty and the
          // host would build a plan that equips nothing. The next poll tries again.
          const state = await backend.controlState(port);
          if (!(state as { player?: unknown }).player) return;
          // The switch can be turned off while this request is in flight; do not let a late
          // push re-arm a client the user just stopped.
          if (!gearSwapOnRef.current) return;
          const liveLibrary = await libraryForLiveJob(library, state);
          if (!gearSwapOnRef.current) return;
          if (liveLibrary !== library) localStorage.setItem("fanxi.phase.library", liveLibrary);
          const status = await backend.gearPhase(
            port,
            true,
            liveLibrary,
            engaged,
            idleTown,
            idleField,
            movement,
            options,
          );
          if (!gearSwapOnRef.current) {
            // The on request was already in flight when the user stopped GearSwap. Put the
            // stop after it so a slow reply cannot leave the host armed.
            void backend.gearPhaseOff(port).catch(() => undefined);
            return;
          }
          if (!status?.player || !(status.rules ?? 0)) return;
          phasePushed.current.add(port);
          // The first push can land while the client is still filling its bags, which leaves a
          // plan that wears only some of a set. A second push a few seconds later is complete.
          if (!phaseRepush.current.has(port)) {
            phaseRepush.current.add(port);
            window.setTimeout(() => {
              if (!gearSwapOnRef.current) return;
              void backend
                .gearPhase(
                  port,
                  true,
                  liveLibrary,
                  engaged,
                  idleTown,
                  idleField,
                  movement,
                  options,
                )
                .then(() => {
                  if (!gearSwapOnRef.current) {
                    void backend.gearPhaseOff(port).catch(() => undefined);
                  }
                })
                .catch(() => undefined);
            }, 6000);
          }
        } catch {
          // The control port is not up yet (or the bags are still loading): retry. If the user
          // stopped GearSwap while the call was outstanding, make sure the host is clear.
          if (!gearSwapOnRef.current) void backend.gearPhaseOff(port).catch(() => undefined);
        }
      })();
    }
  }, [instances, gearSwapOn]);

  useEffect(() => {
    if (!boot || initialPageDone.current) return;
    initialPageDone.current = true;
    if (boot.session && PAGES.includes(boot.config.lastPage as Page)) {
      setPage(boot.config.lastPage as Page);
    }
  }, [boot]);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;
    listen<BuildEvent>("build-progress", (event) => {
      if (cancelled) return;
      setBuildEvents((current) => [...current.slice(-400), event.payload]);
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten = fn;
    });
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    if (!session) {
      setInstances([]);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const list = await backend.listInstances();
        if (!cancelled) setInstances(list);
      } catch {
        // Keep the previous view; the next tick retries.
      }
    };
    void tick();
    const timer = window.setInterval(tick, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [session?.account.username]);

  useEffect(() => {
    if (!session) {
      setTeam(null);
      setTeamError("");
      return;
    }
    void loadTeam();
  }, [session?.account.username, loadTeam]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const index = Number(event.key);
      if (Number.isInteger(index) && index >= 1 && index <= PAGES.length) {
        event.preventDefault();
        setPage(PAGES[index - 1]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    return () => {
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
    };
  }, []);

  const config: ConfigView | null = boot?.config ?? null;
  const activeCharacter: Character | null =
    session?.characters.find((character) => character.id === config?.characterId) ??
    session?.characters[0] ??
    null;
  const running = instances.filter((instance) => instance.alive);

  // The tenant is the character the whole launcher is looking at. It is one of the main
  // account's characters or a sub-account box, and it is independent of `activeCharacter`
  // (which only decides who Play starts on the main account).
  const tenants = useMemo(() => buildTenants(session, team), [session, team]);
  const tenant = useMemo(
    () => resolveTenant(tenants, tenantCharacterId, activeCharacter?.id ?? null),
    [tenants, tenantCharacterId, activeCharacter],
  );

  const chooseTenant = useCallback(
    (characterId: number, quiet = false) => {
      setTenantCharacterId(characterId);
      void backend.selectTenant(characterId).catch((error) => {
        if (!quiet) notify(messageOf(error), "error");
      });
    },
    [notify],
  );

  // Read the saved tenant once the launcher config is in. Later bootstraps (a refresh, a
  // settings save) must not overwrite a choice the user just made.
  useEffect(() => {
    if (tenantSeeded.current || !boot) return;
    tenantSeeded.current = true;
    if (boot.config.tenantCharacterId != null) {
      setTenantCharacterId(boot.config.tenantCharacterId);
    }
  }, [boot]);

  // A stored tenant can disappear when its box is purged or the player signs into a different
  // account. Once the team roster is known, fall back to the active character and persist that.
  useEffect(() => {
    if (!session || !team || tenants.length === 0) return;
    const exists =
      tenantCharacterId !== null &&
      tenants.some((entry) => Number(entry.character.id) === Number(tenantCharacterId));
    if (exists) return;
    chooseTenant(activeCharacter?.id ?? tenants[0].character.id, true);
  }, [session, team, tenants, tenantCharacterId, activeCharacter, chooseTenant]);

  async function afterAuth(next: SessionView) {
    setTenantCharacterId(null);
    setSession(next);
    setAddAccount(false);
    setReloginUsername(null);
    setPage("home");
    try {
      const value = await backend.bootstrap();
      applyBootstrap(value);
      notify(`Signed in as @${next.account.username}`, "success");
    } catch (error) {
      notify(messageOf(error), "error");
    }
  }

  async function signOut() {
    setBusy("logout");
    try {
      const next = await backend.logout();
      setTenantCharacterId(null);
      setAddAccount(false);
      setReloginUsername(null);
      await refreshAll();
      setPage("home");
      notify(next.signedIn ? `Signed out; using @${next.username}` : "Signed out", "info");
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function switchAccount(username: string) {
    setBusy(`switch-${username}`);
    try {
      const next = await backend.switchAccount(username);
      setTenantCharacterId(null);
      setSession(next);
      const nextConfig = await backend.getConfig();
      setBoot((current) => (current ? { ...current, config: nextConfig } : current));
      notify(`Using @${username}`, "success");
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function forgetAccount(username: string) {
    setBusy(`forget-${username}`);
    try {
      await backend.forgetAccount(username);
      if (session?.account.username.toLowerCase() === username.toLowerCase()) {
        setTenantCharacterId(null);
      }
      await refreshAll();
      notify(`Removed @${username}`, "info");
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function createCharacter(data: Record<string, unknown>) {
    const next = await backend.createCharacter(data);
    setSession((current) =>
      current ? { ...next, account: { ...current.account, ...next.account } } : next,
    );
    const nextConfig = await backend.getConfig();
    setBoot((current) => (current ? { ...current, config: nextConfig } : current));
    notify("Character created", "success");
  }

  async function saveCharacterDesign(characterId: number, data: Record<string, unknown>) {
    const next = await backend.saveCharacterDesign(characterId, data);
    setSession(next);
    const nextConfig = await backend.getConfig();
    setBoot((current) => (current ? { ...current, config: nextConfig } : current));
    // A box character is not in the main session's character list. Refresh the team so the
    // tenant bar and the Design form immediately show the saved appearance.
    if (!next.characters.some((character) => Number(character.id) === Number(characterId))) {
      await loadTeam();
    }
    notify("Character design saved", "success");
  }

  async function selectCharacter(characterId: number) {
    try {
      const nextConfig = await backend.selectCharacter(characterId);
      setBoot((current) => (current ? { ...current, config: nextConfig } : current));
      notify("Active character changed", "info");
    } catch (error) {
      notify(messageOf(error), "error");
    }
  }

  async function launch(account: string, characterId: number | null) {
    setBusy(`launch-${account}`);
    try {
      const instance = await backend.launch(account, characterId);
      await refreshInstances();
      setPage("control");
      notify(`${instance.name} is running (control :${instance.port})`, "success");
    } catch (error) {
      if (error instanceof LauncherError && error.unauthorized) {
        await refreshAll();
      }
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function play(character: Character | null = activeCharacter) {
    if (!session || !character || !config) {
      setPage("characters");
      return;
    }
    await launch(session.account.username, character.id);
  }

  /** Play the tenant in the bar, whether it lives on the main account or on a box. */
  async function playTenant() {
    if (!tenant) {
      setPage("team");
      return;
    }
    if (tenant.kind === "sub" && tenant.sub) {
      await launchSub(tenant.sub);
      return;
    }
    await launch(tenant.account, tenant.character.id);
  }

  async function launchAll() {
    setBusy("launch-all");
    try {
      const result = await backend.launchAll();
      await refreshInstances();
      if (result.launched.length > 0) setPage("control");
      if (result.failed.length > 0) {
        notify(
          `Started ${result.launched.length}; ${result.failed.length} failed. ${result.failed[0]?.account}: ${result.failed[0]?.error}`,
          "error",
        );
      } else {
        notify(
          `Started ${result.launched.length} client${result.launched.length === 1 ? "" : "s"}`,
          "success",
        );
      }
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function addSub(character: Record<string, unknown> | null): Promise<boolean> {
    setBusy("create-sub");
    try {
      const result = await backend.createSub(character);
      setTeam((current) => ({
        limit: result.limit,
        subs: [...(current?.subs ?? []), result.sub],
      }));
      notify(`Added @${result.sub.username}`, "success");
      return true;
    } catch (error) {
      notify(messageOf(error), "error");
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function removeSub(subId: number, purge: boolean) {
    setBusy(`remove-${subId}`);
    try {
      await backend.deleteSub(subId, purge);
      await loadTeam();
      notify(purge ? "Box deleted" : "Box suspended", "info");
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function activateSub(sub: SubAccount) {
    setBusy(`activate-${sub.id}`);
    try {
      await backend.activateSub(sub.id);
      await loadTeam();
      notify(`@${sub.username} reactivated`, "success");
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function createSubCharacter(sub: SubAccount) {
    setBusy(`character-${sub.id}`);
    try {
      await backend.createSubCharacter(sub.id, {});
      await loadTeam();
      notify(`Character created for @${sub.username}`, "success");
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function launchSub(sub: SubAccount) {
    setBusy(`launch-sub-${sub.id}`);
    try {
      const instance = await backend.launchSub(sub.id, sub.character?.id ?? null);
      await refreshInstances();
      setPage("control");
      notify(`${instance.name} is running (control :${instance.port})`, "success");
    } catch (error) {
      if (error instanceof LauncherError && error.unauthorized) {
        await refreshAll();
      }
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function launchTeam() {
    setBusy("launch-team");
    try {
      const result = await backend.launchTeam();
      await refreshInstances();
      if (result.launched.length > 0) setPage("control");
      if (result.failed.length > 0) {
        notify(
          `Started ${result.launched.length}; ${result.failed.length} failed. ${result.failed[0]?.account}: ${result.failed[0]?.error}`,
          "error",
        );
      } else {
        notify(
          `Started ${result.launched.length} client${result.launched.length === 1 ? "" : "s"}`,
          "success",
        );
      }
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function stop(port: number) {
    setBusy(`stop-${port}`);
    try {
      await backend.stopInstance(port);
      await refreshInstances();
      notify("Client stopped", "info");
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function stopAll() {
    setConfirmStopAll(false);
    setBusy("stop-all");
    try {
      const count = await backend.stopAll();
      await refreshInstances();
      notify(`Stopped ${count} client${count === 1 ? "" : "s"}`, "info");
    } catch (error) {
      notify(messageOf(error), "error");
    } finally {
      setBusy(null);
    }
  }

  async function sendCommand(port: number, line: string) {
    try {
      await backend.sendCommand(port, line);
      const target = instances.find((instance) => instance.port === port);
      notify(`Sent to ${target?.name ?? "the game"}: ${line}`, "success");
    } catch (error) {
      notify(messageOf(error), "error");
      throw error;
    }
  }

  async function sendChat(port: number, line: string) {
    try {
      await backend.sendChat(port, line);
      notify(`Said: ${line}`, "success");
    } catch (error) {
      notify(messageOf(error), "error");
      throw error;
    }
  }

  async function sendHud(port: number, patch: HudPatch): Promise<HudState> {
    try {
      const next = await backend.sendHud(port, patch);
      await refreshInstances();
      return next;
    } catch (error) {
      notify(messageOf(error), "error");
      throw error;
    }
  }

  async function saveSettings(input: {
    apiUrl: string;
    gameDir: string;
    repoRoot: string;
    apiInsecure: boolean;
    autoLogin: boolean;
  }) {
    const next = await backend.saveSettings(input);
    setBoot((current) => (current ? { ...current, config: next } : current));
    await refreshAll();
  }

  async function buildGame(gameDir: string) {
    const result = await backend.buildGame(gameDir);
    await refreshAll();
    notify(`Built ${result.host64}`, "success");
  }

  if (fatal) {
    return (
      <div className="boot-screen">
        <img src="/fanxi-icon.png" alt="" />
        <h1>Fanxi Launcher</h1>
        <p>{fatal}</p>
        <button className="btn btn-primary" onClick={() => void refreshAll()}>
          Try again
        </button>
      </div>
    );
  }

  if (!boot) {
    return (
      <div className="boot-screen">
        <img src="/fanxi-icon.png" alt="" />
        <h1>Fanxi Launcher</h1>
        <div className="boot-spinner" />
        <p>Starting your world…</p>
      </div>
    );
  }

  if (!session || addAccount) {
    return (
      <>
        <AuthPage
          key={`${addAccount}-${reloginUsername ?? ""}`}
          initialApiUrl={boot.config.apiUrl}
          initialUsername={reloginUsername ?? boot.config.username ?? undefined}
          notice={boot.sessionError}
          publicView={boot.public}
          addMode={addAccount}
          onAuthenticated={(next) => void afterAuth(next)}
          onBack={addAccount ? () => setAddAccount(false) : undefined}
        />
        {toast && <Toast kind={toast.kind} message={toast.message} onClose={() => setToast(null)} />}
      </>
    );
  }

  const pages: Record<Page, React.ReactNode> = {
    home: (
      <HomePage
        session={session}
        config={boot.config}
        publicView={boot.public}
        character={tenant?.character ?? null}
        tenant={tenant}
        instances={instances}
        playBusy={busy?.startsWith("launch-") ?? false}
        onPlay={() => void playTenant()}
        onControl={() => setPage("control")}
        onCharacters={() => setPage("characters")}
        onNews={() => setPage("news")}
        onRefresh={() => void refreshAll()}
        refreshing={refreshing}
      />
    ),
    characters: (
      <CharactersPage
        session={session}
        config={boot.config}
        instances={instances}
        onSelect={(id) => void selectCharacter(id)}
        onCreate={createCharacter}
        onPlay={(character) => void play(character)}
        playBusy={busy?.startsWith("launch-") ?? false}
        onControl={() => setPage("control")}
        onDesign={(characterId) => {
          chooseTenant(characterId);
          setPage("design");
        }}
      />
    ),
    design: (
      <DesignPage
        tenant={tenant}
        instances={instances}
        onSave={saveCharacterDesign}
        onTeam={() => setPage("team")}
      />
    ),
    accounts: (
      <AccountsPage
        config={boot.config}
        session={session}
        instances={instances}
        onSwitch={switchAccount}
        onForget={forgetAccount}
        onAdd={() => {
          setReloginUsername(null);
          setAddAccount(true);
        }}
        onRelogin={(username) => {
          setReloginUsername(username);
          setAddAccount(true);
        }}
        onControl={() => setPage("control")}
      />
    ),
    team: (
      <TeamPage
        session={session}
        team={team}
        activeCharacter={activeCharacter}
        tenant={tenant}
        instances={instances}
        loading={teamLoading}
        error={teamError}
        busy={busy}
        onRefresh={loadTeam}
        onAdd={addSub}
        onRemove={removeSub}
        onActivate={activateSub}
        onCreateCharacter={createSubCharacter}
        onLaunchSub={launchSub}
        onLaunchTeam={launchTeam}
        onViewTenant={(characterId) => chooseTenant(characterId)}
        onControl={() => setPage("control")}
      />
    ),
    control: (
      <ControlPage
        config={boot.config}
        session={session}
        instances={instances}
        onLaunch={launch}
        onStop={stop}
        onLaunchAll={launchAll}
        onStopAll={() => setConfirmStopAll(true)}
        onCommand={sendCommand}
        onChat={sendChat}
        onHud={sendHud}
        onGear={(port) => {
          const target = instances.find((instance) => instance.port === port);
          const known = target
            ? tenants.find(
                (entry) => Number(entry.character.id) === Number(target.character.id),
              ) ?? null
            : null;
          if (target && !known) {
            notify(
              `@${target.account} is not a team tenant — switch to it in Accounts to view its gear.`,
              "info",
            );
            return;
          }
          if (known) chooseTenant(Number(known.character.id));
          setPage("gear");
        }}
        onRefresh={refreshInstances}
        onAccounts={() => setPage("accounts")}
        onWarps={() => setPage("warps")}
        busy={busy}
      />
    ),
    warps: (
      <WarpsPage
        session={session}
        tenant={tenant}
        team={team}
        instances={instances}
        notify={notify}
        onControl={() => setPage("control")}
        onCharacters={() => setPage("characters")}
        onTeam={() => setPage("team")}
      />
    ),
    data: (
      <DataPage
        character={tenant?.character ?? null}
        instances={instances}
        notify={notify}
      />
    ),
    gear: (
      <GearPage
        instances={instances}
        tenant={tenant}
        onControl={() => setPage("control")}
        onTeam={() => setPage("team")}
        notify={notify}
        phaseOn={gearSwapOn}
        onTogglePhase={() => setGearSwap(!gearSwapOnRef.current)}
      />
    ),
    news: <NewsPage publicView={boot.public} onRefresh={() => void refreshAll()} />,
    settings: (
      <SettingsPage
        config={boot.config}
        host64={boot.host64}
        repoRoot={boot.repoRoot}
        gameDir={boot.gameDir}
        gearswapDir={boot.gearswapDir}
        gearSwapOn={gearSwapOn}
        onGearSwapChange={setGearSwap}
        buildLog={buildLog}
        buildEvents={buildEvents}
        onSave={saveSettings}
        onBuild={buildGame}
        onRefresh={refreshAll}
        notify={notify}
      />
    ),
  };

  return (
    <div className="app-shell">
      <Sidebar
        page={page}
        onNavigate={setPage}
        session={session}
        online={running.length}
        status={boot.public.status}
        version={boot.version}
        onSignOut={() => void signOut()}
      />
      <main className="main-pane">
        <TenantBar
          tenants={tenants}
          tenant={tenant}
          instances={instances}
          loading={teamLoading}
          onSelect={(characterId) => chooseTenant(characterId)}
          onTeam={() => setPage("team")}
        />
        {!boot.public.status && (
          <div className="offline-banner">
            Server offline — start the Fanxi server or change its address in Settings.
          </div>
        )}
        <div className="page-scroll" key={page}>{pages[page]}</div>
      </main>
      {toast && <Toast kind={toast.kind} message={toast.message} onClose={() => setToast(null)} />}
      {confirmStopAll && (
        <ConfirmDialog
          title="Stop the whole party?"
          body={`Stop ${running.length} running client${running.length === 1 ? "" : "s"} gracefully, then release their control ports.`}
          confirmLabel="Stop all"
          danger
          onCancel={() => setConfirmStopAll(false)}
          onConfirm={() => void stopAll()}
        />
      )}
    </div>
  );
}
