import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import type { CharacterStat, CharacterStatReport } from "../types";
import { statReportErrorHint } from "../lib/characterstats";
import { StatSheetModal, formatStatValue } from "./StatSheetModal";
import { cn } from "./ui";

/** The "read N seconds ago" line, isolated so its clock does not re-render the table. */
function UpdatedLabel({ updated, loading }: { updated: number; loading: boolean }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    setNow(Date.now() / 1000);
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [updated]);
  if (loading) return <span className="live-set-updated busy">reading…</span>;
  if (!updated) return <span className="live-set-updated">waiting for the server</span>;
  const seconds = Math.max(0, Math.round(now - updated));
  if (seconds <= 1) return <span className="live-set-updated">updated just now</span>;
  if (seconds < 60) return <span className="live-set-updated">updated {seconds}s ago</span>;
  return <span className="live-set-updated">updated {Math.round(seconds / 60)}m ago</span>;
}

function splitColumns(stats: CharacterStat[]): CharacterStat[][] {
  if (stats.length <= 8) return [stats];
  const cut = Math.ceil(stats.length / 2);
  return [stats.slice(0, cut), stats.slice(cut)];
}

/**
 * The compact server-total table under the EquipViewer: one stat and its Total, nothing
 * else. Opening a row hands the whole report to the full-window sheet, where every
 * gear/food/JT/JA/buff contribution is listed.
 */
export function LiveSetStats({
  characterName,
  report,
  loading,
  error,
  onReload,
}: {
  characterName: string;
  report: CharacterStatReport | null;
  loading: boolean;
  error: string;
  onReload: () => void;
}) {
  const [modalKey, setModalKey] = useState<string | null>(null);
  const stats = useMemo(() => report?.stats ?? [], [report]);
  const columns = useMemo(() => splitColumns(stats), [stats]);

  return (
    <section className="live-set-stats" aria-labelledby="live-set-stats-title">
      <div className="live-set-head">
        <div className="live-set-heading">
          <span
            className="eyebrow"
            id="live-set-stats-title"
            title="Totals computed by the game server from gear, food, job traits, job abilities, job points and buffs."
          >
            Live set stats
          </span>
          <span className="live-set-summary">
            {report ? (
              <>
                <b>{stats.length}</b> stats
                <span className="dot-sep" />
                <span>server totals</span>
                {report.food.name ? (
                  <>
                    <span className="dot-sep" />
                    <span className="live-set-food">Food · {report.food.name}</span>
                  </>
                ) : null}
              </>
            ) : (
              <span>{characterName}</span>
            )}
          </span>
        </div>
        <div className="live-set-actions">
          <UpdatedLabel updated={report?.updated ?? 0} loading={loading} />
          {report ? (
            <button
              type="button"
              className="link-btn live-set-all"
              onClick={() => setModalKey(report.stats[0]?.key ?? null)}
            >
              All sources
            </button>
          ) : null}
          <button
            type="button"
            className="icon-btn live-set-refresh"
            title="Read the server stat sheet again"
            aria-label="Read the server stat sheet again"
            disabled={loading}
            onClick={onReload}
          >
            <RefreshCw size={13} className={cn(loading && "spin")} />
          </button>
        </div>
      </div>

      {error ? (
        <div className={cn("live-set-message", report ? "warning" : "error")}>
          <span title={error}>
            {report
              ? "The last server sheet is shown; the latest read failed."
              : statReportErrorHint(error)}
          </span>
          <button type="button" className="link-btn" onClick={onReload}>
            Retry
          </button>
        </div>
      ) : null}

      {!report && !error ? (
        <p className="live-set-message">
          {loading ? "Reading the server's stat sheet…" : "No server stat sheet yet."}
        </p>
      ) : null}

      {report && stats.length > 0 ? (
        <div className={cn("live-set-grid", columns.length === 1 && "single")}>
          {columns.map((column, index) => (
            <CompactTable
              key={index}
              stats={column}
              onSelect={(key) => setModalKey(key)}
            />
          ))}
        </div>
      ) : null}

      {report && stats.length === 0 ? (
        <p className="live-set-message">The server reported no visible stats for this set.</p>
      ) : null}

      {report && modalKey ? (
        <StatSheetModal
          report={report}
          initialKey={modalKey}
          onClose={() => setModalKey(null)}
        />
      ) : null}
    </section>
  );
}

function CompactTable({
  stats,
  onSelect,
}: {
  stats: CharacterStat[];
  onSelect: (key: string) => void;
}) {
  return (
    <div className="live-set-table" aria-label="Server stat totals">
      <div className="live-set-table-head" aria-hidden="true">
        <span>Stat</span>
        <span>Total</span>
      </div>
      {stats.map((stat) => (
        <button
          key={stat.key}
          type="button"
          className="live-set-row"
          aria-label={`${stat.label} ${formatStatValue(stat)} — open every source`}
          onClick={() => onSelect(stat.key)}
        >
          <span>{stat.label}</span>
          <strong>{formatStatValue(stat)}</strong>
        </button>
      ))}
    </div>
  );
}
