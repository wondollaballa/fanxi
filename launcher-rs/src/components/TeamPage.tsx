import { useState } from "react";
import {
  Crown,
  Eye,
  Gamepad2,
  Plus,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Trash2,
  UserPlus,
  UserRound,
  UsersRound,
} from "lucide-react";
import type {
  Character,
  InstanceView,
  SessionView,
  SubAccount,
  TeamView,
  Tenant,
} from "../types";
import { JOBS, jobName } from "../lib/format";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  Field,
  Select,
  Spinner,
  TextInput,
} from "./ui";

export function TeamPage({
  session,
  team,
  activeCharacter,
  tenant,
  instances,
  loading,
  error,
  busy,
  onRefresh,
  onAdd,
  onRemove,
  onActivate,
  onCreateCharacter,
  onLaunchSub,
  onLaunchTeam,
  onViewTenant,
  onControl,
}: {
  session: SessionView;
  team: TeamView | null;
  activeCharacter: Character | null;
  tenant: Tenant | null;
  instances: InstanceView[];
  loading: boolean;
  error: string;
  busy: string | null;
  onRefresh: () => Promise<void>;
  onAdd: (character: Record<string, unknown> | null) => Promise<boolean>;
  onRemove: (subId: number, purge: boolean) => Promise<void>;
  onActivate: (sub: SubAccount) => Promise<void>;
  onCreateCharacter: (sub: SubAccount) => Promise<void>;
  onLaunchSub: (sub: SubAccount) => Promise<void>;
  onLaunchTeam: () => Promise<void>;
  onViewTenant: (characterId: number) => void;
  onControl: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [job, setJob] = useState(1);
  const [confirm, setConfirm] = useState<SubAccount | null>(null);

  const subs = team?.subs ?? [];
  const limit = team?.limit ?? 5;
  const runningAccounts = new Set(
    instances.filter((instance) => instance.alive).map((instance) => instance.account.toLowerCase()),
  );
  const openSlots = Math.max(0, limit - subs.length);
  const mainRunning = runningAccounts.has(session.account.username.toLowerCase());

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const input = name.trim();
    const character: Record<string, unknown> = { main_job: job };
    if (input) character.name = input;
    const created = await onAdd(character);
    if (created) {
      setAdding(false);
      setName("");
      setJob(1);
    }
  }

  return (
    <div className="page">
      <div className="section-header">
        <div>
          <div className="eyebrow">Party roster</div>
          <h1 className="page-title">Team</h1>
          <p className="page-subtitle">
            One main account and up to {limit} server-owned boxes. Every box is its own account
            with one character, launched by this launcher with the main account&apos;s session — no
            extra passwords, no extra tokens.
          </p>
        </div>
        <div className="section-actions">
          <Button variant="ghost" icon={<RefreshCw size={15} />} onClick={() => void onRefresh()}>
            Refresh
          </Button>
          <Button
            variant="secondary"
            icon={<Gamepad2 size={15} />}
            onClick={onControl}
            disabled={instances.length === 0}
          >
            Control room
          </Button>
          <Button
            icon={<Play size={15} fill="currentColor" />}
            loading={busy === "launch-team"}
            onClick={() => void onLaunchTeam()}
          >
            Launch team
          </Button>
        </div>
      </div>

      {error && <ErrorBanner message={error} />}

      <Card accent className="team-main-card">
        <div className="team-main-identity">
          <div className="avatar large">{session.account.username.slice(0, 1).toUpperCase()}</div>
          <div className="account-info">
            <div className="account-title">
              <strong>@{session.account.username}</strong>
              <Badge tone="accent" dot>
                Main account
              </Badge>
              {tenant?.kind === "main" &&
                tenant.character.id === activeCharacter?.id && (
                  <Badge tone="accent" dot>
                    Viewing
                  </Badge>
                )}
              {mainRunning && (
                <Badge tone="success" dot>
                  In game
                </Badge>
              )}
            </div>
            <div className="account-session">
              <ShieldCheck size={13} />
              This session creates and launches every box
            </div>
            <div className="team-character-line">
              <UserRound size={13} />
              {activeCharacter ? (
                <>
                  <strong>{activeCharacter.name}</strong>
                  <span>
                    {jobName(Number(activeCharacter.main_job))} · Lv{" "}
                    {Number(activeCharacter.main_level ?? 1)}
                  </span>
                </>
              ) : (
                <span>No character yet — create one on the Characters page.</span>
              )}
            </div>
          </div>
        </div>
        <div className="team-main-count">
          <Crown size={15} />
          <strong>
            {subs.length}/{limit}
          </strong>
          <span>boxes</span>
        </div>
      </Card>

      {adding && (
        <Card className="team-add-card">
          <form onSubmit={submit}>
            <div className="team-add-heading">
              <div>
                <strong>Add a box</strong>
                <p>
                  The server creates the account and its character together. Leave the name empty
                  and a unique one is generated.
                </p>
              </div>
              <Badge tone="neutral">{subs.length + 1} of {limit}</Badge>
            </div>
            <div className="team-add-fields">
              <Field label="Character name" hint="3–15 letters. Optional.">
                <TextInput
                  value={name}
                  onChange={(event) => setName(event.target.value.replace(/[^A-Za-z]/g, ""))}
                  placeholder="Generated if empty"
                  maxLength={15}
                  autoFocus
                />
              </Field>
              <Field label="Starting job">
                <Select value={job} onChange={(event) => setJob(Number(event.target.value))}>
                  {JOBS.map((label, index) => (
                    <option key={label} value={index + 1}>
                      {label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="team-add-actions">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setAdding(false);
                  setName("");
                  setJob(1);
                }}
              >
                Cancel
              </Button>
              <Button type="submit" loading={busy === "create-sub"} icon={<Plus size={15} />}>
                Create box
              </Button>
            </div>
          </form>
        </Card>
      )}

      {loading && !team ? (
        <Card>
          <Spinner label="Reading the team…" />
        </Card>
      ) : subs.length === 0 && !adding ? (
        <Card>
          <EmptyState
            icon={<UsersRound size={26} />}
            title="No boxes yet"
            body="Create up to five sub-accounts. Each one gets a fresh character and appears here as a slot you can launch."
            action={
              <Button icon={<Plus size={16} />} onClick={() => setAdding(true)}>
                Add the first box
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="team-grid">
          {subs.map((sub, index) => {
            const character = sub.character;
            const running = runningAccounts.has(sub.username.toLowerCase());
            const suspended = sub.status !== "active";
            return (
              <Card
                key={sub.id}
                className={`team-card${suspended ? " team-card-suspended" : ""}`}
              >
                <div className="team-slot-top">
                  <span className="team-slot-label">Box {index + 2}</span>
                  <span className="team-slot-badges">
                    {tenant?.sub?.id === sub.id && (
                      <Badge tone="accent" dot>
                        Viewing
                      </Badge>
                    )}
                    {suspended ? (
                      <Badge tone="warning" dot>
                        Suspended
                      </Badge>
                    ) : running ? (
                      <Badge tone="success" dot>
                        In game
                      </Badge>
                    ) : character ? (
                      <Badge tone="neutral" dot>
                        Ready
                      </Badge>
                    ) : (
                      <Badge tone="danger" dot>
                        No character
                      </Badge>
                    )}
                  </span>
                </div>
                <div className="team-identity">
                  <div className="avatar">
                    {(character?.name ?? sub.username).slice(0, 1).toUpperCase()}
                  </div>
                  <div>
                    <strong>{character?.name ?? "No character"}</strong>
                    <span>@{sub.username}</span>
                  </div>
                </div>
                <div className="team-meta">
                  {character ? (
                    <>
                      <span>
                        {jobName(Number(character.main_job))} · Lv{" "}
                        {Number(character.main_level ?? 1)}
                      </span>
                      <span>Character #{character.id}</span>
                    </>
                  ) : (
                    <span>This box has no character to launch.</span>
                  )}
                </div>
                <div className="team-card-actions">
                  {character && tenant?.sub?.id !== sub.id && (
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={<Eye size={13} />}
                      onClick={() => onViewTenant(Number(character.id))}
                    >
                      View
                    </Button>
                  )}
                  {!suspended && character && !running && (
                    <Button
                      size="sm"
                      icon={<Play size={13} fill="currentColor" />}
                      loading={busy === `launch-sub-${sub.id}`}
                      onClick={() => void onLaunchSub(sub)}
                    >
                      Launch
                    </Button>
                  )}
                  {running && (
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Gamepad2 size={13} />}
                      onClick={onControl}
                    >
                      Control
                    </Button>
                  )}
                  {!suspended && !character && (
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<UserPlus size={13} />}
                      loading={busy === `character-${sub.id}`}
                      onClick={() => void onCreateCharacter(sub)}
                    >
                      Create character
                    </Button>
                  )}
                  {suspended ? (
                    <>
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<RotateCcw size={13} />}
                        loading={busy === `activate-${sub.id}`}
                        onClick={() => void onActivate(sub)}
                      >
                        Reactivate
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        icon={<Trash2 size={13} />}
                        onClick={() => setConfirm(sub)}
                      >
                        Delete
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={<Trash2 size={13} />}
                      loading={busy === `remove-${sub.id}`}
                      onClick={() => void onRemove(sub.id, false)}
                    >
                      Suspend
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
          {Array.from({ length: openSlots }).map((_, index) => (
            <button
              key={`open-${index}`}
              className="team-card team-card-empty"
              onClick={() => setAdding(true)}
              type="button"
            >
              <span className="team-empty-plus">
                <Plus size={20} />
              </span>
              <strong>Open slot {subs.length + index + 2}</strong>
              <span>Add a box</span>
            </button>
          ))}
        </div>
      )}

      <p className="team-note">
        Sub-accounts have no password and no launcher token of their own. Suspending one keeps its
        character; deleting it permanently frees the slot.
      </p>

      {confirm && (
        <ConfirmDialog
          title={`Delete @${confirm.username}?`}
          body={`This permanently deletes the sub-account${
            confirm.character ? ` and ${confirm.character.name}` : ""
          }. The slot becomes available again.`}
          confirmLabel="Delete forever"
          danger
          onCancel={() => setConfirm(null)}
          onConfirm={() => {
            void onRemove(confirm.id, true);
            setConfirm(null);
          }}
        />
      )}
    </div>
  );
}
