import {
  ArrowUpRight,
  Clock3,
  Gamepad2,
  Play,
  RefreshCw,
  Server,
  UserPlus,
  Users,
  Wifi,
  WifiOff,
} from "lucide-react";
import type { ConfigView, Character, InstanceView, PublicView, SessionView } from "../types";
import {
  characterJob,
  formatDuration,
  nationName,
  prettyDate,
  raceName,
  SLOT_KEYS,
  slotLabel,
  zoneName,
} from "../lib/format";
import { EquipViewer } from "./EquipViewer";
import { Badge, Button, Card, EmptyState } from "./ui";

export function HomePage({
  session,
  config,
  publicView,
  character,
  instances,
  playBusy,
  onPlay,
  onControl,
  onCharacters,
  onNews,
  onRefresh,
  refreshing,
}: {
  session: SessionView;
  config: ConfigView;
  publicView: PublicView;
  character: Character | null;
  instances: InstanceView[];
  playBusy: boolean;
  onPlay: () => void;
  onControl: () => void;
  onCharacters: () => void;
  onNews: () => void;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const status = publicView.status;
  const running = instances.filter((instance) => instance.alive);
  const thisCharacterRunning = character
    ? running.find((instance) => instance.character.id === character.id)
    : undefined;
  const gearSlots = thisCharacterRunning?.metrics?.gear?.slots;
  // The saved character is the lobby's snapshot; while the client runs, its own control state
  // is the truth (a job change in the Mog House, a new zone) and the hero should follow it.
  const live = thisCharacterRunning?.state?.player;
  const liveZoneId = thisCharacterRunning?.state?.zone?.id;
  const liveZone = thisCharacterRunning?.state?.zone?.name ?? null;
  const shown: Character | null = character
    ? {
        ...character,
        ...(live?.job ? { main_job: live.job } : {}),
        ...(live?.level ? { main_level: live.level } : {}),
        ...(liveZoneId ? { zone: liveZoneId } : {}),
      }
    : null;

  return (
    <div className="page">
      <div className="home-head">
        <div>
          <div className="eyebrow">Adventure log</div>
          <h1 className="page-title">Welcome back, {session.account.username}.</h1>
          <p className="page-subtitle">Your world is ready when you are.</p>
        </div>
        <Button variant="ghost" size="sm" loading={refreshing} icon={<RefreshCw size={14} />} onClick={onRefresh}>
          Refresh
        </Button>
      </div>

      <div className="home-grid">
        <Card className="character-hero" accent>
          <div className="card-topline">
            <span className="eyebrow">Your character</span>
            {thisCharacterRunning && <Badge tone="success" dot>In game</Badge>}
          </div>
          {shown ? (
            <>
              <div className="hero-name">{shown.name}</div>
              <div className="hero-meta">
                <span>{raceName(shown.race)}</span>
                <span className="dot-sep" />
                <span>{nationName(shown.nation)}</span>
                <span className="dot-sep" />
                <span>{characterJob(shown)}</span>
              </div>
              <div className="hero-location">
                <span className="location-pin" />
                {thisCharacterRunning ? "In" : "Last seen in"}{" "}
                {liveZone ?? zoneName(shown.zone)}
              </div>
              <div className="hero-level">
                <div>
                  <span>Main job</span>
                  <strong>{characterJob(shown)}</strong>
                </div>
                <div>
                  <span>Level</span>
                  <strong>{shown.main_level ?? "—"}</strong>
                </div>
                <div>
                  <span>Gil</span>
                  <strong>{shown.gil?.toLocaleString() ?? "—"}</strong>
                </div>
              </div>
              <div className="hero-actions">
                <Button
                  size="lg"
                  loading={playBusy}
                  icon={<Play size={17} fill="currentColor" />}
                  onClick={onPlay}
                >
                  {thisCharacterRunning ? "Launch another client" : "Play"}
                </Button>
                <Button variant="secondary" size="lg" icon={<Gamepad2 size={17} />} onClick={onControl}>
                  Control room
                </Button>
              </div>
              <div className="hero-equipment">
                <div className="hero-equipment-head">
                  <span className="eyebrow">Equipment</span>
                  {thisCharacterRunning ? (
                    <Badge tone="success" dot>
                      EquipViewer · live
                    </Badge>
                  ) : (
                    <span className="muted">EquipViewer · no client</span>
                  )}
                </div>
                <div className="hero-equipment-body">
                  <EquipViewer
                    port={thisCharacterRunning?.port ?? null}
                    slots={gearSlots}
                    encumbrance={thisCharacterRunning?.metrics?.gear?.encumbrance ?? 0}
                    emptyLabel={
                      thisCharacterRunning
                        ? "The client has not sent its first gear read yet."
                        : `Launch ${shown.name} to watch the 4×4 grid update as gear changes.`
                    }
                  />
                  <div className="hero-equipment-list">
                    {gearSlots
                      ? SLOT_KEYS.filter((slot) => gearSlots[slot]?.name).map((slot) => (
                          <div key={slot} className="hero-equipment-row">
                            <span>{slotLabel(slot)}</span>
                            <strong>{gearSlots[slot]?.name}</strong>
                          </div>
                        ))
                      : null}
                    {!gearSlots && (
                      <p className="muted">
                        Ammo count, encumbrance X and item icons come from the running client's own
                        DATs, exactly like Windower's EquipViewer.
                      </p>
                    )}
                  </div>
                </div>
              </div>
              <div className="hero-foot">
                {session.characters.length} character{session.characters.length === 1 ? "" : "s"} on
                this account · {config.accounts.length} saved account
                {config.accounts.length === 1 ? "" : "s"}
              </div>
            </>
          ) : (
            <EmptyState
              icon={<UserPlus size={24} />}
              title="No character yet"
              body="Make a name for yourself before you enter Vana'diel."
              action={
                <Button icon={<UserPlus size={16} />} onClick={onCharacters}>
                  Create a character
                </Button>
              }
            />
          )}
        </Card>

        <div className="home-side">
          <Card className="server-card">
            <div className="card-topline">
              <span className="eyebrow">Server</span>
              {status ? <Badge tone="success" dot>Online</Badge> : <Badge tone="danger" dot>Offline</Badge>}
            </div>
            <div className="server-name">{status?.world?.name ?? status?.name ?? "Fanxi"}</div>
            <div className="server-state">
              {status ? <Wifi size={14} /> : <WifiOff size={14} />}
              {status ? "Connected" : publicView.error ?? "Cannot reach the server"}
            </div>
            <div className="stat-list">
              <div>
                <span>Players online</span>
                <strong>{status?.online ?? "—"}</strong>
              </div>
              <div>
                <span>Accounts</span>
                <strong>{status?.accounts ?? "—"}</strong>
              </div>
              <div>
                <span>Characters</span>
                <strong>{status?.characters ?? "—"}</strong>
              </div>
              <div>
                <span>Version</span>
                <strong>{status?.version ?? "—"}</strong>
              </div>
            </div>
            <div className="server-foot">
              <Server size={13} />
              <span>{config.apiUrl}</span>
            </div>
          </Card>

          <Card className="party-card">
            <div className="card-topline">
              <span className="eyebrow">Your party</span>
              <button className="link-btn" onClick={onControl}>
                Manage <ArrowUpRight size={13} />
              </button>
            </div>
            {running.length === 0 ? (
              <div className="party-empty">
                <Users size={18} />
                <span>No clients running.</span>
              </div>
            ) : (
              <div className="party-list">
                {running.map((instance) => (
                  <button key={instance.port} className="party-row" onClick={onControl}>
                    <span className="avatar small">{instance.name.slice(0, 1)}</span>
                    <span className="party-meta">
                      <strong>{instance.name}</strong>
                      <span>@{instance.account}</span>
                    </span>
                    <Badge tone="success" dot>
                      {formatDuration(instance.uptimeSeconds)}
                    </Badge>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      <div className="home-bottom">
        <Card className="news-preview">
          <div className="card-topline">
            <span className="eyebrow">Latest news</span>
            <button className="link-btn" onClick={onNews}>
              All news <ArrowUpRight size={13} />
            </button>
          </div>
          {publicView.news.length === 0 ? (
            <p className="muted">No news yet.</p>
          ) : (
            publicView.news.slice(0, 3).map((post) => (
              <button key={post.slug ?? post.title} className="news-row" onClick={onNews}>
                <div>
                  <strong>{post.title}</strong>
                  {post.body && <span>{post.body}</span>}
                </div>
                <span className="news-date">
                  <Clock3 size={12} />
                  {prettyDate(post.published_at)}
                </span>
              </button>
            ))
          )}
        </Card>

        <Card className="quick-card">
          <div className="card-topline">
            <span className="eyebrow">Quick actions</span>
          </div>
          <div className="quick-grid">
            <button onClick={onControl}>
              <Gamepad2 size={18} />
              <span>Control room</span>
            </button>
            <button onClick={onCharacters}>
              <UserPlus size={18} />
              <span>New character</span>
            </button>
            <button onClick={onNews}>
              <Clock3 size={18} />
              <span>News</span>
            </button>
            <button onClick={onRefresh}>
              <RefreshCw size={18} />
              <span>Refresh</span>
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}
