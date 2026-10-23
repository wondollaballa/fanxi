import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Crown, RefreshCw, Square, Users } from "lucide-react";
import type { FollowEvent, FollowStatus, InstanceView, SessionView } from "../types";
import { backend, LauncherError } from "../lib/api";
import { Badge, Button, Card, EmptyState, Select, Spinner, cn } from "./ui";

type Assignments = Record<string, string | null>;
type EnabledMap = Record<string, boolean>;

const COLORS = ["#59d8f2", "#ffd166", "#b9a7ff", "#5be49b", "#ff9f6e", "#ff7b72"];

function accountKey(value: string): string {
  return value.trim().toLowerCase();
}

function messageOf(error: unknown): string {
  if (error instanceof LauncherError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}

function savedState(username: string): { assignments: Assignments; enabled: EnabledMap } {
  try {
    const raw = localStorage.getItem(`fanxi.follow.${username.toLowerCase()}`);
    if (!raw) return { assignments: {}, enabled: {} };
    const value = JSON.parse(raw) as { assignments?: Assignments; enabled?: EnabledMap };
    return {
      assignments: value.assignments ?? {},
      enabled: value.enabled ?? {},
    };
  } catch {
    return { assignments: {}, enabled: {} };
  }
}

function stateLabel(state: string | undefined): string {
  switch (state) {
    case "following":
      return "Following";
    case "close":
      return "In position";
    case "waiting":
      return "Waiting";
    case "stuck":
      return "Stuck";
    case "off":
      return "Free";
    default:
      return "—";
  }
}

function stateTone(state: string | undefined): "neutral" | "success" | "warning" | "danger" {
  if (state === "following" || state === "close") return "success";
  if (state === "waiting") return "warning";
  if (state === "stuck") return "danger";
  return "neutral";
}

export function FollowCard({
  session,
  instances,
}: {
  session: SessionView;
  instances: InstanceView[];
}) {
  const saved = useMemo(() => savedState(session.account.username), [session.account.username]);
  const [assignments, setAssignments] = useState<Assignments>(saved.assignments);
  const [enabled, setEnabled] = useState<EnabledMap>(saved.enabled);
  const [statuses, setStatuses] = useState<Record<string, FollowStatus>>({});
  const [dragging, setDragging] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  /** Only a click on Refresh shows a spinner; the 2 s background poll stays silent. */
  const [refreshing, setRefreshing] = useState(false);
  const pollInFlight = useRef(false);
  const applied = useRef<Map<string, string>>(new Map());
  const eventHandler = useRef<
    (instance: InstanceView, event: FollowEvent) => Promise<void>
  >(async () => undefined);
  const badSince = useRef<Map<string, number>>(new Map());
  const recoveryAt = useRef<Map<string, number>>(new Map());
  const assignmentsRef = useRef(assignments);
  const enabledRef = useRef(enabled);

  const running = useMemo(() => instances.filter((instance) => instance.alive), [instances]);
  const byAccount = useMemo(() => {
    const map = new Map<string, InstanceView>();
    for (const instance of running) map.set(accountKey(instance.account), instance);
    return map;
  }, [running]);
  const mainKey = accountKey(session.account.username);
  const runningKey = running.map((instance) => `${instance.account}:${instance.port}`).join("|");
  const leaderOrder = useMemo(() => {
    const leaders = new Set<string>();
    for (const leader of Object.values(assignments)) if (leader) leaders.add(leader);
    return [...leaders].sort();
  }, [assignments]);
  const anyFollowing = Object.entries(enabled).some(
    ([key, on]) => on && Boolean(assignments[key]) && byAccount.has(key),
  );

  useEffect(() => {
    assignmentsRef.current = assignments;
    enabledRef.current = enabled;
    localStorage.setItem(
      `fanxi.follow.${session.account.username.toLowerCase()}`,
      JSON.stringify({ assignments, enabled }),
    );
  }, [assignments, enabled, session.account.username]);

  const characterName = useCallback(
    (key: string) => byAccount.get(key)?.character?.name ?? byAccount.get(key)?.name ?? "",
    [byAccount],
  );

  const send = useCallback(
    async (follower: string, leader: string | null, on: boolean) => {
      const instance = byAccount.get(follower);
      if (!instance) return;
      const leaderName = leader ? characterName(leader) : null;
      const status = await backend.setFollow(instance.port, on && Boolean(leaderName), leaderName, 1);
      setStatuses((current) => ({ ...current, [follower]: status }));
    },
    [byAccount, characterName],
  );

  const sendAll = useCallback(
    async (nextAssignments: Assignments, nextEnabled: EnabledMap) => {
      const jobs: Promise<void>[] = [];
      for (const [key, instance] of byAccount) {
        const leader = nextAssignments[key] ?? null;
        const on = Boolean(nextEnabled[key]) && Boolean(leader);
        const leaderName = leader ? characterName(leader) : null;
        jobs.push(
          backend
            .setFollow(instance.port, on, leaderName, 1)
            .then((status) => setStatuses((current) => ({ ...current, [key]: status })))
            .then(() => undefined)
            .catch((caught) => {
              setError(messageOf(caught));
            }),
        );
      }
      await Promise.all(jobs);
    },
    [byAccount, characterName],
  );

  const apply = useCallback(
    async (follower: string, leader: string | null, on: boolean) => {
      const nextAssignments = { ...assignmentsRef.current, [follower]: leader };
      const nextEnabled = { ...enabledRef.current, [follower]: on };
      assignmentsRef.current = nextAssignments;
      enabledRef.current = nextEnabled;
      setAssignments(nextAssignments);
      setEnabled(nextEnabled);
      setError("");
      try {
        await send(follower, leader, on);
      } catch (caught) {
        setError(messageOf(caught));
      }
    },
    [send],
  );

  const stopAll = useCallback(async () => {
    setBusy(true);
    setError("");
    const nextEnabled: EnabledMap = {};
    for (const key of byAccount.keys()) nextEnabled[key] = false;
    enabledRef.current = nextEnabled;
    setEnabled(nextEnabled);
    try {
      await sendAll(assignmentsRef.current, nextEnabled);
    } finally {
      setBusy(false);
    }
  }, [byAccount, sendAll]);

  const followLeader = useCallback(async () => {
    if (!byAccount.size) return;
    const leader = byAccount.has(mainKey) ? mainKey : [...byAccount.keys()][0];
    const nextAssignments: Assignments = { ...assignmentsRef.current };
    const nextEnabled: EnabledMap = { ...enabledRef.current };
    for (const key of byAccount.keys()) {
      if (key === leader) {
        nextAssignments[key] = null;
        nextEnabled[key] = false;
        continue;
      }
      nextAssignments[key] = leader;
      nextEnabled[key] = true;
    }
    assignmentsRef.current = nextAssignments;
    enabledRef.current = nextEnabled;
    setAssignments(nextAssignments);
    setEnabled(nextEnabled);
    setBusy(true);
    setError("");
    try {
      await sendAll(nextAssignments, nextEnabled);
    } finally {
      setBusy(false);
    }
  }, [byAccount, mainKey, sendAll]);

  const masterToggle = useCallback(async () => {
    if (anyFollowing) {
      await stopAll();
      return;
    }
    const hasAssignments = Object.values(assignmentsRef.current).some(Boolean);
    if (!hasAssignments) {
      await followLeader();
      return;
    }
    const nextEnabled: EnabledMap = {};
    for (const key of byAccount.keys()) nextEnabled[key] = Boolean(assignmentsRef.current[key]);
    enabledRef.current = nextEnabled;
    setEnabled(nextEnabled);
    setBusy(true);
    setError("");
    try {
      await sendAll(assignmentsRef.current, nextEnabled);
    } finally {
      setBusy(false);
    }
  }, [anyFollowing, byAccount, followLeader, sendAll, stopAll]);

  const assign = useCallback(
    async (follower: string, leader: string | null) => {
      if (!byAccount.has(follower)) return;
      if (leader === follower) return;
      if (leader) {
        // Reject a cycle: follower -> leader -> ... must not come back to follower.
        let cursor: string | null = leader;
        const seen = new Set<string>();
        while (cursor) {
          if (cursor === follower || seen.has(cursor)) {
            setError("That assignment would create a follow loop.");
            return;
          }
          seen.add(cursor);
          cursor = assignmentsRef.current[cursor] ?? null;
        }
      }
      await apply(follower, leader, Boolean(leader));
    },
    [apply, byAccount],
  );

  const maybeRecover = useCallback(
    async (key: string, instance: InstanceView, status: FollowStatus) => {
      const leaderKey = assignmentsRef.current[key];
      const leader = leaderKey ? byAccount.get(leaderKey) : null;
      if (!status.enabled || !leader || (status.state !== "waiting" && status.state !== "stuck")) {
        badSince.current.delete(key);
        return;
      }
      const now = Date.now();
      const since = badSince.current.get(key) ?? now;
      badSince.current.set(key, since);
      if (now - since < 7000 || now - (recoveryAt.current.get(key) ?? 0) < 15000) return;
      const leaderState = leader.state;
      const position = leaderState?.player?.position;
      const zone = leaderState?.zone?.id;
      const myZone = instance.state?.zone?.id;
      if (!position || !zone) return;
      const px = Number(position.x);
      const py = Number(position.y);
      const pz = Number(position.z);
      if (!Number.isFinite(px) || !Number.isFinite(py) || !Number.isFinite(pz)) return;
      const myPosition = instance.state?.player?.position;
      const myX = Number(myPosition?.x);
      const myY = Number(myPosition?.y);
      const far = Number.isFinite(myX) && Number.isFinite(myY) && Math.hypot(px - myX, py - myY) > 40;
      if (status.state !== "stuck" && !far && zone === myZone) return;
      recoveryAt.current.set(key, now);
      const line =
        zone !== myZone
          ? `!zone ${zone} ${px.toFixed(2)} ${py.toFixed(2)} ${pz.toFixed(2)}`
          : `!pos ${px.toFixed(2)} ${py.toFixed(2)} ${pz.toFixed(2)}`;
      try {
        await backend.sendCommand(instance.port, line);
        void backend
          .sendChat(instance.port, `/echo FOLLOW: recovering to ${leader.character?.name ?? leaderKey}`)
          .catch(() => undefined);
      } catch (caught) {
        setError(messageOf(caught));
      }
    },
    [byAccount],
  );

  const poll = useCallback(
    async (manual = false) => {
      if (!running.length || pollInFlight.current) return;
      // The interval below is silent, so it does not need to run against a hidden window.
      if (!manual && document.visibilityState !== "visible") return;
      pollInFlight.current = true;
      if (manual) setRefreshing(true);
      try {
        for (const instance of running) {
          const key = accountKey(instance.account);
          try {
            const [status, events] = await Promise.all([
              backend.followStatus(instance.port),
              backend.followEvents(instance.port),
            ]);
            setStatuses((current) => ({ ...current, [key]: status }));
            const list = Array.isArray(events) ? (events as FollowEvent[]) : [];
            for (const event of list) {
              await eventHandler.current(instance, event);
            }
            await maybeRecover(key, instance, status);
          } catch (caught) {
            const detail = messageOf(caught);
            if (detail.toLowerCase().includes("follow")) setError(detail);
          }
        }
      } finally {
        pollInFlight.current = false;
        if (manual) setRefreshing(false);
      }
      // The command handler is defined below and closes over the latest state refs.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [running, maybeRecover],
  );

  // The interval must not be rebuilt every time a poll returns: `running` is a fresh array after
  // every instances refresh, and a new callback used to re-run the effect and poll immediately.
  const pollRef = useRef(poll);
  pollRef.current = poll;

  const handleFollowEvent = useCallback(
    async (issuer: InstanceView, event: FollowEvent) => {
      const text = (event.line || "").trim();
      const tokens = text.split(/\s+/).filter(Boolean);
      const issuerKey = accountKey(issuer.account);
      const resolve = (token: string): string | null => {
        const wanted = token.toLowerCase().replace(/^@/, "");
        if (wanted === "me") return issuerKey;
        for (const [key, instance] of byAccount) {
          if (key === wanted) return key;
          const name = (instance.character?.name ?? instance.name ?? "").toLowerCase();
          if (name === wanted) return key;
        }
        return null;
      };
      const ack = (message: string) => {
        void backend.sendChat(issuer.port, `/echo FOLLOW: ${message}`).catch(() => undefined);
      };
      if (!tokens.length || tokens[0].toLowerCase() === "status") {
        const mine = statuses[issuerKey];
        ack(
          mine
            ? `${mine.state}${mine.leader ? ` · ${mine.leader}` : ""}`
            : "no follow state yet",
        );
        return;
      }
      if (tokens[0].toLowerCase() === "stopall") {
        await stopAll();
        ack("everyone stops");
        return;
      }
      if (tokens[0].toLowerCase() === "stop") {
        const target = resolve(tokens[1] ?? "");
        if (!target) {
          ack("unknown player");
          return;
        }
        await apply(target, assignmentsRef.current[target] ?? null, false);
        ack(`${characterName(target) || target} stops`);
        return;
      }
      if (tokens[0].toLowerCase() === "me") {
        if (!tokens[1] || tokens[1].toLowerCase() === "all") {
          const targets = [...byAccount.keys()].filter((key) => key !== issuerKey);
          const nextAssignments: Assignments = { ...assignmentsRef.current };
          const nextEnabled: EnabledMap = { ...enabledRef.current };
          // The sender becomes the root: if it was following someone, break that edge so
          // "everyone follows me" cannot make a cycle.
          nextAssignments[issuerKey] = null;
          nextEnabled[issuerKey] = false;
          for (const key of targets) {
            nextAssignments[key] = issuerKey;
            nextEnabled[key] = true;
          }
          assignmentsRef.current = nextAssignments;
          enabledRef.current = nextEnabled;
          setAssignments(nextAssignments);
          setEnabled(nextEnabled);
          await sendAll(nextAssignments, nextEnabled);
          ack(`everyone follows ${characterName(issuerKey) || issuerKey}`);
          return;
        }
        const target = resolve(tokens[1]);
        if (!target) {
          ack("unknown player");
          return;
        }
        await assign(target, issuerKey);
        ack(`${characterName(target) || target} follows ${characterName(issuerKey) || issuerKey}`);
        return;
      }
      const leader = resolve(tokens[0]);
      if (!leader) {
        ack("unknown leader");
        return;
      }
      const targets = tokens.slice(1).map(resolve).filter((key): key is string => Boolean(key));
      if (!targets.length) {
        ack("no followers named");
        return;
      }
      for (const target of targets) await assign(target, leader);
      ack(`${targets.map((key) => characterName(key) || key).join(", ")} follow ${characterName(leader) || leader}`);
    },
    [apply, assign, byAccount, characterName, sendAll, statuses, stopAll],
  );

  eventHandler.current = handleFollowEvent;

  useEffect(() => {
    void pollRef.current();
    const timer = window.setInterval(() => void pollRef.current(), 2000);
    return () => window.clearInterval(timer);
  }, [runningKey]);

  useEffect(() => {
    // A client that was launched while an assignment is stored gets it once it appears.
    for (const [key, instance] of byAccount) {
      if (!enabledRef.current[key]) continue;
      const leader = assignmentsRef.current[key];
      if (!leader) continue;
      const leaderName = characterName(leader);
      if (!leaderName) continue;
      const signature = `${instance.port}:${leader}:${leaderName}`;
      if (applied.current.get(key) === signature) continue;
      applied.current.set(key, signature);
      void backend.setFollow(instance.port, true, leaderName, 1).catch(() => undefined);
    }
  }, [byAccount, characterName, runningKey]);

  if (!running.length) {
    return (
      <Card className="follow-card">
        <div className="card-topline">
          <span className="eyebrow">Follow</span>
        </div>
        <EmptyState
          icon={<Users size={22} />}
          title="No clients to lead"
          body="Launch a character in the party above; follow controls appear for every running client."
        />
      </Card>
    );
  }

  return (
    <Card className="follow-card">
      <div className="card-topline">
        <span className="eyebrow">Follow</span>
        <div className="inline-actions">
          <button
            type="button"
            className={cn("follow-switch", anyFollowing && "on")}
            onClick={() => void masterToggle()}
            disabled={busy}
            title={anyFollowing ? "Stop following" : "Start following"}
          >
            <span className="follow-switch-dot" />
            {anyFollowing ? "Following" : "Follow"}
          </button>
          <Button
            size="sm"
            variant="secondary"
            icon={<Crown size={13} />}
            onClick={() => void followLeader()}
            loading={busy}
          >
            Follow the leader
          </Button>
          <Button
            size="sm"
            variant="ghost"
            icon={<Square size={12} fill="currentColor" />}
            onClick={() => void stopAll()}
            disabled={busy}
          >
            Stop all
          </Button>
          <Button
            size="sm"
            variant="ghost"
            icon={<RefreshCw size={13} />}
            onClick={() => void poll(true)}
            loading={refreshing}
          >
            Refresh
          </Button>
        </div>
      </div>
      <p className="follow-hint">
        Drag a box onto its line leader, or pick a leader. Followers replay the leader&apos;s exact
        trail at one yalm; leaders can follow other leaders.
      </p>
      {error && <div className="follow-error">{error}</div>}
      <div className="follow-list">
        {running.map((instance) => {
          const key = accountKey(instance.account);
          const leader = assignments[key] ?? null;
          const isLeader = leaderOrder.includes(key);
          const status = statuses[key];
          const color = leader ? COLORS[leaderOrder.indexOf(leader) % COLORS.length] : undefined;
          const candidates = [...byAccount.keys()].filter((candidate) => {
            if (candidate === key) return false;
            let cursor: string | null = candidate;
            const seen = new Set<string>();
            while (cursor) {
              if (cursor === key || seen.has(cursor)) return false;
              seen.add(cursor);
              cursor = assignmentsRef.current[cursor] ?? null;
            }
            return true;
          });
          return (
            <div
              key={instance.port}
              className={cn(
                "follow-row",
                isLeader && "follow-row-leader",
                dragging === key && "follow-row-dragging",
              )}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.setData("text/plain", key);
                event.dataTransfer.effectAllowed = "move";
                setDragging(key);
              }}
              onDragEnd={() => setDragging(null)}
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
              }}
              onDrop={(event) => {
                event.preventDefault();
                const source = event.dataTransfer.getData("text/plain") || dragging;
                setDragging(null);
                if (source) void assign(source, key);
              }}
              style={color ? ({ ["--group" as string]: color } as React.CSSProperties) : undefined}
            >
              <span className="follow-color" style={color ? { background: color } : undefined} />
              <div className="follow-who">
                <strong>
                  {instance.character?.name ?? instance.name}
                  {key === mainKey && <span className="follow-main">main</span>}
                </strong>
                <span>@{instance.account}</span>
              </div>
              <div className="follow-state">
                {status ? (
                  <Badge tone={stateTone(status.state)} dot>
                    {stateLabel(status.state)}
                  </Badge>
                ) : (
                  <Badge tone="neutral">—</Badge>
                )}
                {leader && (
                  <span className="follow-target">
                    → {byAccount.get(leader)?.character?.name ?? leader}
                  </span>
                )}
              </div>
              <Select
                className="follow-select"
                value={leader ?? ""}
                onChange={(event) => {
                  const next = event.target.value || null;
                  void assign(key, next);
                }}
                title="Line leader"
              >
                <option value="">Free / stop</option>
                {candidates.map((candidate) => (
                  <option key={candidate} value={candidate}>
                    {byAccount.get(candidate)?.character?.name ?? candidate}
                  </option>
                ))}
              </Select>
              {isLeader && (
                <span className="follow-leader-tag" title="Line leader">
                  <Crown size={12} />
                </span>
              )}
            </div>
          );
        })}
      </div>
      {busy && <Spinner label="Sending follow orders…" />}
    </Card>
  );
}
