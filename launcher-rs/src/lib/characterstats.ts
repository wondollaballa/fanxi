import { useEffect, useState } from "react";
import { backend } from "./api";
import type { CharacterStatReport } from "../types";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * The live checkparam-style sheet from the game server. The server builds it on demand
 * from the zone session, so buffs, food, job abilities and job traits are all current.
 * Polling is separate from the two-second equipment poll: the server already has the
 * gear the client is wearing, and this endpoint is the one source of truth for totals.
 */
export function useCharacterStatReport(
  characterId: number | null,
  enabled: boolean,
): {
  report: CharacterStatReport | null;
  loading: boolean;
  error: string;
  reload: () => void;
} {
  const [report, setReport] = useState<CharacterStatReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!characterId || !enabled) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    let timer: number | undefined;
    let inFlight = false;
    const load = async (first: boolean) => {
      if (inFlight) return;
      inFlight = true;
      if (first) {
        setLoading(true);
        setError("");
      }
      try {
        const next = await backend.characterStats(characterId);
        if (cancelled) return;
        setReport(next);
        setError("");
      } catch (caught) {
        if (cancelled) return;
        setError(messageOf(caught));
      } finally {
        inFlight = false;
        if (!cancelled && first) setLoading(false);
      }
    };

    void load(true);
    // Poll whenever the Sets tab is open, not only while the launcher is frontmost.  The
    // launcher is usually parked on a second display while the player swaps gear in the
    // game; on macOS WebKit reports that window as hidden as soon as another app is
    // active, and the old visibility test skipped every tick until the player clicked the
    // launcher.  The interval itself keeps running in the background, so dropping the
    // gate is all a visible-but-unfocused window needs to stay live.
    timer = window.setInterval(() => void load(false), 2000);
    // A minimised window or an app-napped webview can lose timer ticks.  Refresh at once
    // when the player brings the launcher back rather than waiting for the next tick.
    const refresh = () => void load(false);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [characterId, enabled, revision]);

  // A report is only meaningful for the character it was built for. During a tenant
  // switch the old report must not look like the new character's sheet.
  const current = report && report.character_id === characterId ? report : null;
  return {
    report: current,
    loading: enabled && (loading || (!!characterId && !current && !error)),
    error,
    reload: () => setRevision((value) => value + 1),
  };
}

/** A readable note for the frequent "not in a zone yet" case; the full error stays in a title. */
export function statReportErrorHint(error: string): string {
  const lower = error.toLowerCase();
  if (lower.includes("not in a zone")) {
    return "Waiting for the server's live stat sheet — the character has to be in the world.";
  }
  if (lower.includes("404") || lower.includes("unknown route") || lower.includes("not found")) {
    return "The server does not have the live stat endpoint yet — update and restart the server.";
  }
  if (lower.includes("sign in") || lower.includes("token")) {
    return "Sign in again to read the server stat sheet.";
  }
  if (lower.includes("control") || lower.includes("game")) {
    return "The server is not reachable right now.";
  }
  return "The server stat sheet is unavailable.";
}
