import { useMemo, useState } from "react";
import {
  FileText,
  Gamepad2,
  Play,
  RefreshCw,
  Send,
  Shirt,
  Square,
  Terminal,
  Users,
} from "lucide-react";
import type { ConfigView, InstanceView, SessionView } from "../types";
import {
  formatDuration,
  formatNumber,
  pct,
  stateZone,
} from "../lib/format";
import { backend } from "../lib/api";
import { EquipViewer } from "./EquipViewer";
import { FollowCard } from "./FollowCard";
import { Badge, Button, Card, EmptyState, Modal, Select, TextInput, cn } from "./ui";

const QUICK_COMMANDS = [
  ["Zone 100", "!zone 100"],
  ["Port Jeuno", "!zone 246"],
  ["Heal", "!heal"],
  ["Merits 5", "!merits 5"],
  ["Where", "!where"],
  ["Help", "!help"],
];

export function ControlPage({
  config,
  session,
  instances,
  onLaunch,
  onStop,
  onLaunchAll,
  onStopAll,
  onCommand,
  onChat,
  onGear,
  onRefresh,
  onAccounts,
  busy,
}: {
  config: ConfigView;
  session: SessionView;
  instances: InstanceView[];
  onLaunch: (account: string, characterId: number | null) => Promise<void>;
  onStop: (port: number) => Promise<void>;
  onLaunchAll: () => Promise<void>;
  onStopAll: () => void | Promise<void>;
  onCommand: (port: number, line: string) => Promise<void>;
  onChat: (port: number, line: string) => Promise<void>;
  onGear: (port: number) => void;
  onRefresh: () => Promise<void>;
  onAccounts: () => void;
  busy: string | null;
}) {
  const running = instances.filter((instance) => instance.alive);
  const [choices, setChoices] = useState<Record<string, number>>({});
  const [selectedPort, setSelectedPort] = useState<number | null>(null);
  const [mode, setMode] = useState<"command" | "chat">("command");
  const [line, setLine] = useState("!zone 100");
  const [sending, setSending] = useState(false);
  const [logPort, setLogPort] = useState<number | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logLoading, setLogLoading] = useState(false);

  const selected = useMemo(
    () => running.find((instance) => instance.port === selectedPort) ?? running[0] ?? null,
    [running, selectedPort],
  );

  const chosenCharacter = (username: string, accountId: number | null | undefined) => {
    const entry = config.accounts.find(
      (account) => account.username.toLowerCase() === username.toLowerCase(),
    );
    if (choices[username] !== undefined) return choices[username];
    if (accountId && entry?.characters.some((character) => character.id === accountId)) {
      return accountId;
    }
    return entry?.characterId ?? entry?.characters[0]?.id ?? null;
  };

  async function launch(username: string, accountId: number | null | undefined) {
    const characterId = chosenCharacter(username, accountId);
    if (!characterId) return;
    await onLaunch(username, characterId);
  }

  async function openLog(port: number) {
    setLogPort(port);
    setLogLoading(true);
    try {
      setLogLines(await backend.gameLog(port, 180));
    } catch (error) {
      setLogLines([error instanceof Error ? error.message : String(error)]);
    } finally {
      setLogLoading(false);
    }
  }

  async function send() {
    if (!selected || !line.trim() || sending) return;
    setSending(true);
    try {
      if (mode === "command") {
        await onCommand(selected.port, line.trim());
      } else {
        await onChat(selected.port, line.trim());
      }
      setLine("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="page">
      <div className="section-header">
        <div>
          <div className="eyebrow">Party management</div>
          <h1 className="page-title">Control room</h1>
          <p className="page-subtitle">
            One client per account. Launch them here, then send commands or watch EXP/hr and DPS
            without leaving the launcher.
          </p>
        </div>
        <div className="section-actions">
          <Button variant="ghost" icon={<RefreshCw size={15} />} onClick={() => void onRefresh()}>
            Refresh
          </Button>
          <Button
            variant="secondary"
            icon={<Square size={14} fill="currentColor" />}
            onClick={() => void onStopAll()}
            disabled={running.length === 0}
          >
            Stop all
          </Button>
          <Button
            icon={<Play size={15} fill="currentColor" />}
            loading={busy === "launch-all"}
            onClick={() => void onLaunchAll()}
            disabled={config.accounts.length === 0}
          >
            Launch all
          </Button>
        </div>
      </div>

      <Card className="party-manager">
        <div className="card-topline">
          <span className="eyebrow">Party</span>
          <button className="link-btn" onClick={onAccounts}>
            <Users size={13} /> {config.accounts.length} account
            {config.accounts.length === 1 ? "" : "s"}
          </button>
        </div>
        {config.accounts.length === 0 ? (
          <EmptyState
            icon={<Users size={22} />}
            title="No accounts yet"
            body="Add an account from the Accounts page to start a party."
          />
        ) : (
          <div className="party-manager-list">
            {config.accounts.map((account) => {
              const instance = running.find(
                (item) => item.account.toLowerCase() === account.username.toLowerCase(),
              );
              const characters = account.characters;
              const choice = chosenCharacter(account.username, account.characterId);
              return (
                <div className="party-manager-row" key={account.username}>
                  <div className="party-manager-name">
                    <span className="avatar small">{account.username.slice(0, 1).toUpperCase()}</span>
                    <div>
                      <strong>@{account.username}</strong>
                      <span>
                        {instance
                          ? `online · control :${instance.port}`
                          : account.signedIn
                            ? "offline"
                            : "sign in again"}
                      </span>
                    </div>
                  </div>
                  {characters.length > 0 ? (
                    <Select
                      className="character-select"
                      value={choice ?? ""}
                      onChange={(event) =>
                        setChoices((current) => ({
                          ...current,
                          [account.username]: Number(event.target.value),
                        }))
                      }
                    >
                      {characters.map((character) => (
                        <option key={character.id} value={character.id}>
                          {character.name}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <span className="muted">No characters</span>
                  )}
                  {instance ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Square size={13} fill="currentColor" />}
                      loading={busy === `stop-${instance.port}`}
                      onClick={() => void onStop(instance.port)}
                    >
                      Stop
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Play size={14} fill="currentColor" />}
                      loading={busy === `launch-${account.username}`}
                      disabled={!choice || !account.signedIn}
                      onClick={() => void launch(account.username, account.characterId)}
                    >
                      Launch
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <FollowCard session={session} instances={instances} />

      <Card className="live-party">
        <div className="card-topline">
          <span className="eyebrow">Live party</span>
          <div className="inline-actions">
            <button className="link-btn" onClick={() => selected && onGear(selected.port)}>
              <Shirt size={13} /> Gear & GearSwap
            </button>
            <button
              className="link-btn"
              onClick={() => selected && void openLog(selected.port)}
              disabled={!selected}
            >
              <FileText size={13} /> Log
            </button>
            <button className="link-btn" onClick={() => void onRefresh()}>
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
        </div>
        {running.length === 0 ? (
          <EmptyState
            icon={<Gamepad2 size={22} />}
            title="No clients running"
            body="Launch a character above and its live state will appear here."
          />
        ) : (
          <div className="live-party-body">
            <div className="live-table-wrap">
              <table className="live-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Character</th>
                  <th>Zone</th>
                  <th>HP</th>
                  <th>MP</th>
                  <th>EXP/hr</th>
                  <th>DPS</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {running.map((instance) => {
                  const state = instance.state;
                  const player = state?.player;
                  const kpi = instance.metrics?.kpi;
                  const hp = pct(player?.hp, player?.hpmax);
                  const mp = pct(player?.mp, player?.mpmax);
                  return (
                    <tr
                      key={instance.port}
                      className={cn(selected?.port === instance.port && "selected")}
                      onClick={() => setSelectedPort(instance.port)}
                    >
                      <td>
                        <span className="account-cell">@{instance.account}</span>
                      </td>
                      <td>
                        <strong>{instance.name}</strong>
                      </td>
                      <td>{stateZone(state)}</td>
                      <td>
                        <div className="bar-cell">
                          <span>
                            {player?.hp ?? "—"}/{player?.hpmax ?? "—"}
                          </span>
                          <div className="mini-bar">
                            <div className="mini-bar-fill hp" style={{ width: `${hp}%` }} />
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="bar-cell">
                          <span>
                            {player?.mp ?? "—"}/{player?.mpmax ?? "—"}
                          </span>
                          <div className="mini-bar">
                            <div className="mini-bar-fill mp" style={{ width: `${mp}%` }} />
                          </div>
                        </div>
                      </td>
                      <td>{formatNumber(kpi?.exp_per_hour)}</td>
                      <td>{formatNumber(kpi?.dps, 1)}</td>
                      <td>
                        {player ? (
                          <Badge tone="success" dot>
                            {formatDuration(instance.uptimeSeconds)}
                          </Badge>
                        ) : instance.error ? (
                          <Badge tone="warning" dot>
                            waiting
                          </Badge>
                        ) : (
                          <Badge tone="neutral" dot>
                            starting
                          </Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
            {selected && (
              <aside className="live-equipment">
                <div className="card-topline">
                  <span className="eyebrow">Equipment</span>
                  <button className="link-btn" onClick={() => onGear(selected.port)}>
                    <Shirt size={12} /> Open
                  </button>
                </div>
                <EquipViewer
                  port={selected.port}
                  slots={selected.metrics?.gear?.slots}
                  encumbrance={selected.metrics?.gear?.encumbrance ?? 0}
                  compact
                  showSettings={false}
                />
                <div className="live-equipment-meta">
                  <strong>{selected.name}</strong>
                  <span>{stateZone(selected.state)}</span>
                  <span className="muted">
                    {selected.metrics?.gear?.slots
                      ? "Live from the client"
                      : "Waiting for the first gear read"}
                  </span>
                </div>
              </aside>
            )}
          </div>
        )}
        {running.length > 0 && (
          <div className="live-summary">
            {running.map((instance) => {
              const kpi = instance.metrics?.kpi;
              return (
                <div key={instance.port} className="summary-item">
                  <span>{instance.name}</span>
                  <strong>
                    {formatNumber(kpi?.exp_per_hour)} EXP/hr · {formatNumber(kpi?.dps, 1)} DPS
                  </strong>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card className="console-card">
        <div className="card-topline">
          <span className="eyebrow">Command console</span>
          <div className="segmented small">
            <button className={cn(mode === "command" && "active")} onClick={() => setMode("command")}>
              <Terminal size={13} /> Command
            </button>
            <button className={cn(mode === "chat" && "active")} onClick={() => setMode("chat")}>
              <Send size={13} /> Chat
            </button>
          </div>
        </div>
        <div className="console-row">
          <Select
            className="target-select"
            value={selected?.port ?? ""}
            onChange={(event) => setSelectedPort(Number(event.target.value))}
            disabled={running.length === 0}
          >
            {running.length === 0 && <option value="">(no client)</option>}
            {running.map((instance) => (
              <option key={instance.port} value={instance.port}>
                {instance.account} — {instance.name} (:{instance.port})
              </option>
            ))}
          </Select>
          <TextInput
            className="console-input"
            value={line}
            onChange={(event) => setLine(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void send();
            }}
            placeholder={mode === "command" ? "!zone 100" : "Say something…"}
            disabled={!selected}
          />
          <Button
            icon={<Send size={15} />}
            loading={sending}
            disabled={!selected || !line.trim()}
            onClick={() => void send()}
          >
            Send
          </Button>
          <Button
            variant="ghost"
            icon={<Shirt size={15} />}
            disabled={!selected}
            onClick={() => selected && onGear(selected.port)}
          >
            Gear
          </Button>
        </div>
        <div className="quick-row">
          {QUICK_COMMANDS.map(([label, command]) => (
            <button
              key={command}
              className="quick-chip"
              onClick={() => {
                setMode("command");
                setLine(command);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="console-hint">
          Commands start with <code>!</code> or <code>/</code>. Chat sends a line through the game;
          the client's control addon executes commands as if typed.
        </p>
      </Card>

      {logPort !== null && (
        <Modal
          title={`Game log — ${running.find((item) => item.port === logPort)?.name ?? "client"}`}
          subtitle="The last lines host64 wrote to its account log."
          wide
          onClose={() => setLogPort(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setLogPort(null)}>
                Close
              </Button>
              <Button
                variant="secondary"
                icon={<RefreshCw size={14} />}
                loading={logLoading}
                onClick={() => void openLog(logPort)}
              >
                Refresh
              </Button>
            </>
          }
        >
          <pre className="game-log">{logLines.length ? logLines.join("\n") : "No log lines yet."}</pre>
        </Modal>
      )}
    </div>
  );
}
