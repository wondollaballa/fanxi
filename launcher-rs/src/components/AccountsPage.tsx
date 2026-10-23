import { useState } from "react";
import { LogIn, Plus, ShieldCheck, Trash2, UserRound, Users } from "lucide-react";
import type { AccountView, ConfigView, InstanceView, SessionView } from "../types";
import { Badge, Button, Card, ConfirmDialog, EmptyState } from "./ui";

export function AccountsPage({
  config,
  session,
  instances,
  onSwitch,
  onForget,
  onAdd,
  onRelogin,
  onControl,
}: {
  config: ConfigView;
  session: SessionView;
  instances: InstanceView[];
  onSwitch: (username: string) => Promise<void>;
  onForget: (username: string) => Promise<void>;
  onAdd: () => void;
  onRelogin: (username: string) => void;
  onControl: () => void;
}) {
  const [confirm, setConfirm] = useState<AccountView | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const runningAccounts = new Set(
    instances.filter((instance) => instance.alive).map((instance) => instance.account.toLowerCase()),
  );

  async function switchAccount(username: string) {
    setBusy(username);
    try {
      await onSwitch(username);
    } finally {
      setBusy(null);
    }
  }

  async function forget(username: string) {
    setBusy(username);
    try {
      await onForget(username);
      setConfirm(null);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="page">
      <div className="section-header">
        <div>
          <div className="eyebrow">Account vault</div>
          <h1 className="page-title">Saved accounts</h1>
          <p className="page-subtitle">
            Each account can have one character online at a time. Add another account here, then
            launch both from the Control room.
          </p>
        </div>
        <div className="section-actions">
          <Button variant="ghost" icon={<Users size={15} />} onClick={onControl}>
            Control room
          </Button>
          <Button icon={<Plus size={16} />} onClick={onAdd}>
            Add account
          </Button>
        </div>
      </div>

      {config.accounts.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Users size={26} />}
            title="No saved accounts"
            body="Sign in to an account to keep its session in the vault."
            action={
              <Button icon={<Plus size={16} />} onClick={onAdd}>
                Add account
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="account-list">
          {config.accounts.map((entry) => {
            const active = entry.username.toLowerCase() === session.account.username.toLowerCase();
            const running = runningAccounts.has(entry.username.toLowerCase());
            return (
              <Card key={entry.username} className={active ? "account-card active" : "account-card"}>
                <div className="account-main">
                  <div className="avatar large">{entry.username.slice(0, 1).toUpperCase()}</div>
                  <div className="account-info">
                    <div className="account-title">
                      <strong>@{entry.username}</strong>
                      {active && <Badge tone="accent" dot>Active</Badge>}
                      {running && <Badge tone="success" dot>In game</Badge>}
                    </div>
                    <div className="account-session">
                      {entry.signedIn ? (
                        <>
                          <ShieldCheck size={13} />
                          Session saved
                          {entry.tokenExpiresAt ? ` · expires ${entry.tokenExpiresAt.slice(0, 10)}` : ""}
                        </>
                      ) : (
                        <>
                          <UserRound size={13} />
                          Sign in again to use this account
                        </>
                      )}
                    </div>
                    <div className="account-characters">
                      {entry.characters.length > 0 ? (
                        entry.characters.slice(0, 8).map((character) => (
                          <span key={character.id} className="character-chip">
                            {character.name}
                          </span>
                        ))
                      ) : (
                        <span className="muted">No characters yet</span>
                      )}
                      {entry.characters.length > 8 && (
                        <span className="character-chip">+{entry.characters.length - 8}</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="account-actions">
                  {!active && (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<LogIn size={14} />}
                      loading={busy === entry.username}
                      onClick={() => switchAccount(entry.username)}
                    >
                      Use
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => onRelogin(entry.username)}>
                    Sign in again
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Trash2 size={14} />}
                    onClick={() => setConfirm(entry)}
                  >
                    Remove
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {confirm && (
        <ConfirmDialog
          title={`Remove @${confirm.username}?`}
          body="This removes the saved session from this launcher. The server account and its characters stay."
          confirmLabel="Remove account"
          danger
          onCancel={() => setConfirm(null)}
          onConfirm={() => forget(confirm.username)}
        />
      )}
    </div>
  );
}
