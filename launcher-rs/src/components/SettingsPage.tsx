import { useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  CheckCircle2,
  FolderOpen,
  Hammer,
  RefreshCw,
  Save,
  Settings2,
  Terminal,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import type { BuildEvent, ConfigView } from "../types";
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
  TextInput,
  cn,
} from "./ui";

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
    repoRoot: string;
    apiInsecure: boolean;
    autoLogin: boolean;
  }) => Promise<void>;
  onBuild: (gameDir: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
}) {
  const [apiUrl, setApiUrl] = useState(config.apiUrl);
  const [gameFolder, setGameFolder] = useState(config.gameDir || gameDir || "");
  const [repo, setRepo] = useState(config.repoRoot || repoRoot || "");
  const [insecure, setInsecure] = useState(config.apiInsecure);
  const [autoLogin, setAutoLogin] = useState(config.autoLogin);
  const [saving, setSaving] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState("");
  const [confirmBuild, setConfirmBuild] = useState(false);
  const [clearingIcons, setClearingIcons] = useState(false);

  useEffect(() => {
    setApiUrl(config.apiUrl);
    setGameFolder(config.gameDir || gameDir || "");
    setRepo(config.repoRoot || repoRoot || "");
    setInsecure(config.apiInsecure);
    setAutoLogin(config.autoLogin);
  }, [
    config.apiUrl,
    config.gameDir,
    config.repoRoot,
    config.apiInsecure,
    config.autoLogin,
    gameDir,
    repoRoot,
  ]);

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

  async function save() {
    setSaving(true);
    setError("");
    try {
      await onSave({
        apiUrl,
        gameDir: gameFolder,
        repoRoot: repo,
        apiInsecure: insecure,
        autoLogin,
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
