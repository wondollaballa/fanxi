import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, LockKeyhole, Server, Sparkles, UserRound } from "lucide-react";
import type { PublicView, SessionView } from "../types";
import { backend, LauncherError } from "../lib/api";
import { Badge, Button, ErrorBanner, Field, TextInput, cn } from "./ui";

export function AuthPage({
  initialApiUrl,
  initialUsername,
  notice,
  publicView,
  addMode,
  onAuthenticated,
  onBack,
}: {
  initialApiUrl: string;
  initialUsername?: string;
  notice?: string | null;
  publicView: PublicView;
  addMode?: boolean;
  onAuthenticated: (session: SessionView) => void;
  onBack?: () => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [apiUrl, setApiUrl] = useState(initialApiUrl);
  const [username, setUsername] = useState(initialUsername ?? "");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(notice ?? "");

  useEffect(() => {
    if (notice) setError(notice);
  }, [notice]);

  const status = publicView.status;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (!username.trim()) {
      setError("Enter your username.");
      return;
    }
    if (password.length < 8) {
      setError("A password needs at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      const session =
        mode === "login"
          ? await backend.login(username.trim(), password, apiUrl)
          : await backend.register(username.trim(), password, email || null, apiUrl);
      onAuthenticated(session);
    } catch (caught) {
      setError(caught instanceof LauncherError ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-visual">
        <div className="auth-visual-inner">
          <div className="auth-brand">
            <img src="/fanxi-icon.png" alt="" />
            <span>FANXI</span>
          </div>
          <div className="auth-copy">
            <div className="eyebrow">Your world, your rules</div>
            <h1>
              Vana'diel
              <br />
              is waiting.
            </h1>
            <p>
              Sign in to your own Fanxi server, build the client from your own game files, and
              bring the party together from one native launcher.
            </p>
          </div>
          <div className="auth-points">
            <div>
              <span className="point-icon">
                <Server size={15} />
              </span>
              <div>
                <strong>{status?.world?.name ?? "Fanxi"}</strong>
                <span>
                  {status
                    ? `${status.online ?? 0} adventurer${status.online === 1 ? "" : "s"} online · ${status.accounts ?? 0} account${status.accounts === 1 ? "" : "s"}`
                    : "Server status unavailable"}
                </span>
              </div>
            </div>
            <div>
              <span className="point-icon">
                <Sparkles size={15} />
              </span>
              <div>
                <strong>Native by design</strong>
                <span>Rust + Tauri. No Electron, no bundled browser runtime.</span>
              </div>
            </div>
          </div>
        </div>
        <div className="auth-grid" />
      </div>

      <div className="auth-panel">
        <div className="auth-panel-inner">
          {addMode && onBack && (
            <button className="back-link" onClick={onBack}>
              <ArrowLeft size={15} />
              Back to accounts
            </button>
          )}
          <div className="auth-heading">
            <div className="auth-heading-top">
              <h2>{addMode ? "Add an account" : mode === "login" ? "Welcome back" : "Create an account"}</h2>
              {status ? <Badge tone="success" dot>Online</Badge> : <Badge tone="warning" dot>Offline</Badge>}
            </div>
            <p>
              {addMode
                ? "Sign in to another Fanxi account. Its token is saved locally for multiboxing."
                : "Use your Fanxi account. Your password is never stored."}
            </p>
          </div>

          {!addMode && (
            <div className="segmented">
              <button className={cn(mode === "login" && "active")} onClick={() => setMode("login")}>
                Sign in
              </button>
              <button className={cn(mode === "register" && "active")} onClick={() => setMode("register")}>
                Create account
              </button>
            </div>
          )}

          {error && <ErrorBanner message={error} onClose={() => setError("")} />}

          <form onSubmit={submit} className="auth-form">
            <Field label="Server">
              <div className="input-with-icon">
                <Server size={15} />
                <TextInput
                  value={apiUrl}
                  onChange={(event) => setApiUrl(event.target.value)}
                  placeholder="http://127.0.0.1:8080"
                  spellCheck={false}
                  autoCapitalize="off"
                />
              </div>
            </Field>
            <Field label="Username">
              <div className="input-with-icon">
                <UserRound size={15} />
                <TextInput
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="aria"
                  autoComplete="username"
                  autoCapitalize="off"
                  spellCheck={false}
                  autoFocus
                />
              </div>
            </Field>
            {mode === "register" && (
              <Field label="Email" hint="Optional. Used only for account recovery.">
                <TextInput
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="aria@example.com"
                  autoComplete="email"
                />
              </Field>
            )}
            <Field label="Password" hint={mode === "register" ? "At least 8 characters." : undefined}>
              <div className="input-with-icon">
                <LockKeyhole size={15} />
                <TextInput
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="••••••••"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                />
              </div>
            </Field>

            <Button type="submit" size="lg" loading={busy} className="auth-submit">
              {mode === "login" ? "Sign in" : "Create account"}
              {!busy && <ArrowRight size={17} />}
            </Button>
          </form>

          <p className="auth-fineprint">
            The launcher stores a revocable session token, never your password. Registration can be
            closed by the server administrator.
          </p>
        </div>
      </div>
    </div>
  );
}
