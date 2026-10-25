import { useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  CheckCircle2,
  FolderOpen,
  Hammer,
  Maximize2,
  Monitor,
  RefreshCw,
  Save,
  Settings2,
  Terminal,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import type {
  BuildEvent,
  ConfigView,
  DisplayInfo,
  DisplayMonitor,
  GameWindowMode,
} from "../types";
import { backend } from "../lib/api";
import { clearViewerIconCache } from "./EquipViewer";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  ErrorBanner,
  Field,
  ProgressBar,
  Select,
  TextInput,
  cn,
} from "./ui";

const MIN_WIDTH = 640;
const MIN_HEIGHT = 480;
const MAX_DIMENSION = 16384;
const UI_SCALES = Array.from({ length: 11 }, (_, index) => 0.5 + index * 0.25);
const STANDARD_RESOLUTIONS: ReadonlyArray<readonly [number, number]> = [
  [1280, 720],
  [1600, 900],
  [1920, 1080],
  [2560, 1080],
  [2560, 1440],
  [3440, 1440],
  [3840, 1600],
  [3840, 2160],
];

const WINDOW_MODES: ReadonlyArray<{ value: GameWindowMode; label: string }> = [
  { value: "windowed", label: "Windowed" },
  { value: "borderless", label: "Borderless window" },
  { value: "fullscreen", label: "Full screen" },
  { value: "borderless-fullscreen", label: "Borderless full screen" },
];

function isFullscreen(mode: GameWindowMode): boolean {
  return mode === "fullscreen" || mode === "borderless-fullscreen";
}

function even(value: number): number {
  return Math.max(2, Math.round(value / 2) * 2);
}

function dimension(value: number, minimum: number): number {
  return Math.min(MAX_DIMENSION, Math.max(minimum, even(value)));
}

/** A window that leaves a little breathing room inside the usable area. */
function fittingWindow(monitor: DisplayMonitor): { width: number; height: number } {
  return {
    width: dimension(monitor.workWidth * 0.92, MIN_WIDTH),
    height: dimension(monitor.workHeight * 0.92, MIN_HEIGHT),
  };
}

/** Full screen follows the display, so that is what the menu scale is calculated from. */
function displaySize(monitor: DisplayMonitor): { width: number; height: number } {
  return {
    width: dimension(monitor.width, MIN_WIDTH),
    height: dimension(monitor.height, MIN_HEIGHT),
  };
}

function scaleLabel(scale: number): string {
  const label = Number.isInteger(scale) ? String(scale) : String(Math.round(scale * 100) / 100);
  return `${label}×${scale === 2 ? " (recommended)" : ""}`;
}

export function SettingsPage({
  config,
  host64,
  repoRoot,
  gameDir,
  gearswapDir,
  gearSwapOn,
  onGearSwapChange,
  buildLog,
  buildEvents,
  onSave,
  onBuild,
  onRefresh,
  notify,
}: {
  config: ConfigView;
  host64: string | null;
  repoRoot: string | null;
  gameDir: string | null;
  gearswapDir: string | null;
  /** Launcher-wide GearSwap master switch, shared with the Gear page. */
  gearSwapOn: boolean;
  onGearSwapChange: (enabled: boolean) => void;
  buildLog: string[];
  buildEvents: BuildEvent[];
  onSave: (input: {
    apiUrl: string;
    gameDir: string;
    headlessGameDir: string;
    remoteSsh: string;
    repoRoot: string;
    apiInsecure: boolean;
    autoLogin: boolean;
    limitMainFps: boolean;
    gameWindowMode: GameWindowMode;
    gameWidth: number;
    gameHeight: number;
    gameUiScale: number;
  }) => Promise<void>;
  onBuild: (gameDir: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
}) {
  const [apiUrl, setApiUrl] = useState(config.apiUrl);
  const [gameFolder, setGameFolder] = useState(config.gameDir || gameDir || "");
  const [headlessFolder, setHeadlessFolder] = useState(config.headlessGameDir || "");
  const [remoteSsh, setRemoteSsh] = useState(config.remoteSsh || "");
  const [repo, setRepo] = useState(config.repoRoot || repoRoot || "");
  const [insecure, setInsecure] = useState(config.apiInsecure);
  const [autoLogin, setAutoLogin] = useState(config.autoLogin);
  const [limitMainFps, setLimitMainFps] = useState(config.limitMainFps);
  const [windowMode, setWindowMode] = useState<GameWindowMode>(config.gameWindowMode ?? "windowed");
  const [gameWidth, setGameWidth] = useState(String(config.gameWidth ?? 1280));
  const [gameHeight, setGameHeight] = useState(String(config.gameHeight ?? 720));
  const [uiScale, setUiScale] = useState(config.gameUiScale ?? 2);
  const [display, setDisplay] = useState<DisplayInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState("");
  const [confirmBuild, setConfirmBuild] = useState(false);
  const [clearingIcons, setClearingIcons] = useState(false);

  useEffect(() => {
    setApiUrl(config.apiUrl);
    setGameFolder(config.gameDir || gameDir || "");
    setHeadlessFolder(config.headlessGameDir || "");
    setRemoteSsh(config.remoteSsh || "");
    setRepo(config.repoRoot || repoRoot || "");
    setInsecure(config.apiInsecure);
    setAutoLogin(config.autoLogin);
    setLimitMainFps(config.limitMainFps);
    setWindowMode(config.gameWindowMode ?? "windowed");
    setGameWidth(String(config.gameWidth ?? 1280));
    setGameHeight(String(config.gameHeight ?? 720));
    setUiScale(config.gameUiScale ?? 2);
  }, [
    config.apiUrl,
    config.gameDir,
    config.headlessGameDir,
    config.remoteSsh,
    config.repoRoot,
    config.apiInsecure,
    config.autoLogin,
    config.limitMainFps,
    config.gameWindowMode,
    config.gameWidth,
    config.gameHeight,
    config.gameUiScale,
    gameDir,
    repoRoot,
  ]);

  // Read the displays once per visit. They only change when a monitor is plugged in, and the
  // settings themselves do not need a round trip to the core.
  useEffect(() => {
    let cancelled = false;
    backend
      .displayInfo()
      .then((info) => {
        if (!cancelled) setDisplay(info);
      })
      .catch(() => {
        if (!cancelled) setDisplay(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const primary = useMemo(() => {
    const monitors = display?.monitors ?? [];
    return monitors.find((monitor) => monitor.primary) ?? monitors[0] ?? null;
  }, [display]);

  const fullscreen = isFullscreen(windowMode);
  const exceedsDisplay =
    primary !== null &&
    !fullscreen &&
    (Number(gameWidth) > primary.width || Number(gameHeight) > primary.height);

  const presets = useMemo(() => {
    if (!primary) return STANDARD_RESOLUTIONS;
    return STANDARD_RESOLUTIONS.filter(
      ([width, height]) => width <= primary.workWidth && height <= primary.workHeight,
    );
  }, [primary]);

  // A migrated saved.reg can carry a ratio that is not one of the quarter steps. Keep it as the
  // selected option so opening and saving Settings does not silently change the interface size.
  const scaleOptions = useMemo(() => {
    const options = [...UI_SCALES];
    if (!options.some((scale) => Math.abs(scale - uiScale) < 1e-9)) options.push(uiScale);
    return options.sort((a, b) => a - b);
  }, [uiScale]);

  // A full screen window is the display's size. Keep the stored resolution in step with it so the
  // interface scale (window / menu) is calculated from the size the game actually opens at.
  useEffect(() => {
    if (!primary || !isFullscreen(windowMode)) return;
    const size = displaySize(primary);
    setGameWidth(String(size.width));
    setGameHeight(String(size.height));
  }, [primary, windowMode]);

  const latest = buildEvents[buildEvents.length - 1];
  const progress = latest?.percent ?? null;
  const building = latest?.phase !== "done" && buildEvents.length > 0 && progress !== 100;
  const lines = useMemo(() => {
    const fromEvents = buildEvents.map((event) => event.line);
    const merged = [...buildLog, ...fromEvents];
    return merged.slice(-120);
  }, [buildLog, buildEvents]);

  async function browseGame() {
    const folder = await open({ directory: true, multiple: false, title: "Choose your FINAL FANTASY XI folder" });
    if (typeof folder === "string") setGameFolder(folder);
  }

  async function browseHeadless() {
    const folder = await open({
      directory: true,
      multiple: false,
      title: "Choose the FINAL FANTASY XI folder for headless boxes",
    });
    if (typeof folder === "string") setHeadlessFolder(folder);
  }

  async function browseRepo() {
    const folder = await open({ directory: true, multiple: false, title: "Choose the Fanxi checkout" });
    if (typeof folder === "string") setRepo(folder);
  }

  async function clearIcons() {
    setClearingIcons(true);
    try {
      const removed = await backend.clearIconCache();
      clearViewerIconCache();
      notify(
        `Cleared ${removed} cached item icon${removed === 1 ? "" : "s"}; the next gear read regenerates them`,
        "info",
      );
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : String(caught), "error");
    } finally {
      setClearingIcons(false);
    }
  }

  async function detect() {
    setDetecting(true);
    setError("");
    try {
      const found = await backend.detectGameDir(gameFolder);
      if (found) {
        setGameFolder(found);
        notify(`Found ${found}`, "success");
      } else {
        setError("No FINAL FANTASY XI folder found. Choose it with Browse.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setDetecting(false);
    }
  }

  function chooseWindowMode(next: GameWindowMode) {
    if (next === windowMode) return;
    // Leaving full screen gives back a window that fits the display; entering it is handled by the
    // effect above, once the display's own size is known.
    if (!isFullscreen(next) && isFullscreen(windowMode) && primary) {
      const size = fittingWindow(primary);
      setGameWidth(String(size.width));
      setGameHeight(String(size.height));
    }
    setWindowMode(next);
  }

  function fitToDisplay() {
    if (!primary) return;
    const size = fullscreen ? displaySize(primary) : fittingWindow(primary);
    setGameWidth(String(size.width));
    setGameHeight(String(size.height));
  }

  function choosePreset(width: number, height: number) {
    setGameWidth(String(width));
    setGameHeight(String(height));
  }

  async function save() {
    const width = Math.round(Number(gameWidth));
    const height = Math.round(Number(gameHeight));
    if (!Number.isFinite(width) || width < MIN_WIDTH || width > MAX_DIMENSION) {
      setError(`Game width must be between ${MIN_WIDTH} and ${MAX_DIMENSION} pixels.`);
      return;
    }
    if (!Number.isFinite(height) || height < MIN_HEIGHT || height > MAX_DIMENSION) {
      setError(`Game height must be between ${MIN_HEIGHT} and ${MAX_DIMENSION} pixels.`);
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave({
        apiUrl,
        gameDir: gameFolder,
        headlessGameDir: headlessFolder,
        remoteSsh,
        repoRoot: repo,
        apiInsecure: insecure,
        autoLogin,
        limitMainFps,
        gameWindowMode: windowMode,
        gameWidth: width,
        gameHeight: height,
        gameUiScale: uiScale,
      });
      notify("Settings saved", "success");
      await onRefresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setSaving(false);
    }
  }

  async function build() {
    setConfirmBuild(false);
    setError("");
    try {
      await onBuild(gameFolder);
      await onRefresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <div className="page">
      <div className="section-header">
        <div>
          <div className="eyebrow">Configuration</div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">
            The launcher talks to one Fanxi server and builds the client from your own game files.
          </p>
        </div>
        <div className="section-actions">
          <Button variant="ghost" icon={<RefreshCw size={15} />} onClick={() => void onRefresh()}>
            Refresh status
          </Button>
          <Button icon={<Save size={15} />} loading={saving} onClick={() => void save()}>
            Save settings
          </Button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError("")} />}

      <div className="settings-grid">
        <Card className="settings-card">
          <div className="card-topline">
            <span className="eyebrow">Connection</span>
            <Badge tone={config.signedIn ? "success" : "warning"} dot>
              {config.signedIn ? "Signed in" : "Signed out"}
            </Badge>
          </div>
          <Field label="Server URL" hint="The launcher appends /api/v1 automatically.">
            <TextInput
              value={apiUrl}
              onChange={(event) => setApiUrl(event.target.value)}
              placeholder="http://127.0.0.1:8080"
              spellCheck={false}
            />
          </Field>
          <label className="check-row">
            <input type="checkbox" checked={insecure} onChange={(event) => setInsecure(event.target.checked)} />
            <span>
              <strong>Allow a self-signed HTTPS certificate</strong>
              <small>Only for a server you control and trust.</small>
            </span>
          </label>
          <label className="check-row">
            <input type="checkbox" checked={autoLogin} onChange={(event) => setAutoLogin(event.target.checked)} />
            <span>
              <strong>Restore the saved session on launch</strong>
              <small>Tokens are stored locally in a mode-0600 file.</small>
            </span>
          </label>
          {apiUrl.trim() !== config.apiUrl && (
            <div className="banner banner-warning">
              <TriangleAlert size={16} />
              <span>Changing the server clears saved sessions, so sign in again after saving.</span>
            </div>
          )}
        </Card>

        <Card className="settings-card">
          <div className="card-topline">
            <span className="eyebrow">Game & build</span>
            <Settings2 size={14} />
          </div>
          <Field label="FINAL FANTASY XI folder" hint="Contains FFXiMain.dll, FFXi.dll and ROM.">
            <div className="input-row">
              <TextInput
                value={gameFolder}
                onChange={(event) => setGameFolder(event.target.value)}
                placeholder="/Applications/FINAL FANTASY XI"
                spellCheck={false}
              />
              <Button variant="ghost" icon={<FolderOpen size={15} />} onClick={() => void browseGame()}>
                Browse
              </Button>
            </div>
          </Field>
          <Field
            label="Headless game folder"
            hint="Optional install for windowless boxes; it must match the host64-headless build. Leave empty to use the folder above."
          >
            <div className="input-row">
              <TextInput
                value={headlessFolder}
                onChange={(event) => setHeadlessFolder(event.target.value)}
                placeholder="Same as the folder above"
                spellCheck={false}
              />
              <Button variant="ghost" icon={<FolderOpen size={15} />} onClick={() => void browseHeadless()}>
                Browse
              </Button>
            </div>
          </Field>
          <Field
            label="Remote Linux host (SSH)"
            hint="Optional. Starts headless boxes on this host with scripts/linux_boxes.py, keeping the Mac light. Leave empty to run them locally."
          >
            <TextInput
              value={remoteSsh}
              onChange={(event) => setRemoteSsh(event.target.value)}
              placeholder="user@192.168.1.20"
              spellCheck={false}
            />
          </Field>
          <label className="check-row">
            <input type="checkbox" checked={limitMainFps} onChange={(event) => setLimitMainFps(event.target.checked)} />
            <span>
              <strong>Cap the main client at 30 fps</strong>
              <small>Leaves headroom for the box pollers and the rest of the desktop. Relaunch the main to apply.</small>
            </span>
          </label>
          <Field label="Fanxi checkout" hint="Needed to run the recompiler and build host64. Leave empty to auto-detect.">
            <div className="input-row">
              <TextInput
                value={repo}
                onChange={(event) => setRepo(event.target.value)}
                placeholder="/path/to/fanxi"
                spellCheck={false}
              />
              <Button variant="ghost" icon={<FolderOpen size={15} />} onClick={() => void browseRepo()}>
                Browse
              </Button>
            </div>
          </Field>
          <div className="settings-actions">
            <Button variant="ghost" loading={detecting} onClick={() => void detect()}>
              Detect game
            </Button>
            <Button
              icon={<Hammer size={15} />}
              disabled={!gameFolder.trim() || building}
              onClick={() => setConfirmBuild(true)}
            >
              Build game
            </Button>
            <Button variant="ghost" icon={<FolderOpen size={15} />} onClick={() => void backend.openDataDir()}>
              Open data folder
            </Button>
            <Button
              variant="ghost"
              icon={<Trash2 size={15} />}
              loading={clearingIcons}
              onClick={() => void clearIcons()}
            >
              Clear icon cache
            </Button>
          </div>
        </Card>

        <Card className="settings-card game-window-settings">
          <div className="card-topline">
            <span className="eyebrow">Game window</span>
            <Badge tone={primary ? "neutral" : "warning"} dot={Boolean(primary)}>
              {primary ? `${primary.width} × ${primary.height}` : "Display size unavailable"}
            </Badge>
          </div>
          <div className="form-grid three">
            <Field label="Window mode" hint="Used every time the launcher starts a visible client.">
              <Select
                value={windowMode}
                onChange={(event) => chooseWindowMode(event.target.value as GameWindowMode)}
              >
                {WINDOW_MODES.map((mode) => (
                  <option key={mode.value} value={mode.value}>
                    {mode.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="Resolution"
              hint={
                fullscreen
                  ? "Full screen follows the display's own resolution."
                  : "The size of Windowed and Borderless windows."
              }
            >
              <div className="resolution-row">
                <TextInput
                  type="number"
                  inputMode="numeric"
                  min={MIN_WIDTH}
                  max={MAX_DIMENSION}
                  step={2}
                  value={gameWidth}
                  disabled={fullscreen && Boolean(primary)}
                  aria-label="Game window width"
                  onChange={(event) => setGameWidth(event.target.value)}
                />
                <span className="resolution-times">×</span>
                <TextInput
                  type="number"
                  inputMode="numeric"
                  min={MIN_HEIGHT}
                  max={MAX_DIMENSION}
                  step={2}
                  value={gameHeight}
                  disabled={fullscreen && Boolean(primary)}
                  aria-label="Game window height"
                  onChange={(event) => setGameHeight(event.target.value)}
                />
              </div>
            </Field>
            <Field
              label="Interface scale"
              hint="Menus are drawn at the window divided by this. 2× matches the sign-in screen."
            >
              <Select value={String(uiScale)} onChange={(event) => setUiScale(Number(event.target.value))}>
                {scaleOptions.map((scale) => (
                  <option key={scale} value={String(scale)}>
                    {scaleLabel(scale)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {!fullscreen && (
            <div className="display-presets">
              <Button
                size="sm"
                variant="ghost"
                icon={<Maximize2 size={14} />}
                disabled={!primary}
                onClick={fitToDisplay}
              >
                Fit this display
              </Button>
              {presets.map(([width, height]) => {
                const active = Number(gameWidth) === width && Number(gameHeight) === height;
                return (
                  <Button
                    key={`${width}x${height}`}
                    size="sm"
                    variant={active ? "secondary" : "ghost"}
                    onClick={() => choosePreset(width, height)}
                  >
                    {width} × {height}
                  </Button>
                );
              })}
            </div>
          )}
          <p className="display-note">
            <Monitor size={13} />
            <span>
              {primary
                ? `${primary.name ?? "Primary display"} · ${primary.width} × ${primary.height}${
                    primary.scaleFactor > 1 ? ` at ${primary.scaleFactor}× display scale` : ""
                  } · ${primary.workWidth} × ${primary.workHeight} usable`
                : "Display details are unavailable; the resolution can still be typed in."}
            </span>
          </p>
          {exceedsDisplay && (
            <p className="display-note display-warning">
              <TriangleAlert size={13} />
              <span>Larger than the primary display; part of the window may open off-screen.</span>
            </p>
          )}
          <p className="console-hint">
            Applied the next time the launcher starts the game. Windowed and borderless windows
            use the resolution above; full screen and borderless full screen cover the primary
            display. Interface scale sets the game's menu resolution independently.
          </p>
        </Card>

        <Card className="settings-card gearswap-settings">
          <div className="card-topline">
            <span className="eyebrow">GearSwap</span>
            <Badge tone={gearSwapOn ? "accent" : "neutral"} dot={gearSwapOn}>
              {gearSwapOn ? "Auto-swap on" : "Off"}
            </Badge>
          </div>
          <label className="check-row">
            <input
              type="checkbox"
              checked={gearSwapOn}
              onChange={(event) => onGearSwapChange(event.target.checked)}
            />
            <span>
              <strong>Automatic gear swapping</strong>
              <small>
                Off is the default. Turning it off clears the precast, midcast and idle plan in
                every running client immediately, so no action packet is held and no automatic
                set is worn. Manual gear changes on the Gear page still work.
              </small>
            </span>
          </label>
          <p className="gear-hint">
            Turn it on after loading a GearSwap library on the Gear page; the launcher pushes
            that plan to every running client and remembers the choice for the next launch.
          </p>
        </Card>
      </div>

      <Card className="status-card">
        <div className="card-topline">
          <span className="eyebrow">Runtime status</span>
          {host64 ? <Badge tone="success" dot>Client ready</Badge> : <Badge tone="warning" dot>Client not built</Badge>}
        </div>
        <div className="status-grid">
          <StatusRow label="host64" value={host64 ?? "not built yet"} ok={Boolean(host64)} mono />
          <StatusRow label="Game folder" value={gameDir ?? (gameFolder || "not found")} ok={Boolean(gameDir || gameFolder)} mono />
          <StatusRow label="Fanxi checkout" value={repoRoot ?? (repo || "not found")} ok={Boolean(repoRoot || repo)} mono />
          <StatusRow label="GearSwap defaults" value={gearswapDir ?? "not found"} ok={Boolean(gearswapDir)} mono />
        </div>
      </Card>

      <Card className="build-card">
        <div className="card-topline">
          <span className="eyebrow">Build log</span>
          <div className="inline-actions">
            {progress !== null && <span className="progress-label">{progress}%</span>}
            <Terminal size={14} />
          </div>
        </div>
        <ProgressBar value={progress ?? 0} indeterminate={building && progress === null} />
        <pre className="build-log">{lines.length ? lines.join("\n") : "Build output appears here."}</pre>
        <p className="console-hint">
          The build still uses the repository's Python recompiler and your local clang toolchain.
          The Rust launcher drives it and streams the output; it does not replace it.
        </p>
      </Card>

      {confirmBuild && (
        <ConfirmDialog
          title="Build host64?"
          body="This translates the game's code and compiles host64 from your own files. The first build takes several minutes."
          confirmLabel="Build game"
          onCancel={() => setConfirmBuild(false)}
          onConfirm={() => void build()}
        />
      )}
    </div>
  );
}

function StatusRow({
  label,
  value,
  ok,
  mono = false,
}: {
  label: string;
  value: string;
  ok: boolean;
  mono?: boolean;
}) {
  return (
    <div className="status-row">
      <span className="status-label">{label}</span>
      <span className={cn("status-value", mono && "mono")} title={value}>
        {ok ? <CheckCircle2 size={14} className="ok-icon" /> : <TriangleAlert size={14} className="warn-icon" />}
        {value}
      </span>
    </div>
  );
}
