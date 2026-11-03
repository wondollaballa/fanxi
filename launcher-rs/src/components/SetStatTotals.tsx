import { useMemo } from "react";
import type { GearItemStats } from "../types";
import {
  formatGearStatValue,
  gearStatCap,
  gearStatsErrorHint,
  totalGearStats,
} from "../lib/gearstats";
import { cn } from "./ui";

/**
 * The selected set's summed stats, shown in the empty space under the EquipViewer. The totals
 * include each item's base tooltip and the augments recorded on that slot, so comparing two cape
 * builds or two rings is a matter of switching the set and reading the same column.
 */
export function SetStatTotals({
  items,
  loading,
  error,
  onRetry,
}: {
  items: GearItemStats[];
  loading: boolean;
  error: string;
  onRetry?: () => void;
}) {
  const totals = useMemo(() => totalGearStats(items), [items]);

  return (
    <div className="set-totals" aria-live="polite">
      <div className="set-totals-head">
        <span
          className="eyebrow"
          title="Sums the base item stats and the GearSwap augments in this set. Blue values are at or past a known cap; gold notes show how much a stat still needs."
        >
          Set totals
        </span>
        {loading ? <span className="set-totals-note">reading…</span> : null}
      </div>
      {error ? (
        <div className="set-totals-error">
          <span className="set-totals-note" title={error}>
            {gearStatsErrorHint(error)}
          </span>
          {onRetry ? (
            <button type="button" className="link-btn" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
      {!error && !loading && totals.length === 0 ? (
        <span className="set-totals-note">No numeric stats.</span>
      ) : null}
      {totals.length > 0 ? (
        <div className="set-totals-list">
          {totals.map((stat) => {
            const cap = gearStatCap(stat);
            return (
              <div
                className={cn("set-total", cap && `cap-${cap.state}`)}
                key={`${stat.key}-${stat.percent ? "pct" : "flat"}`}
              >
                <span title={stat.label}>{stat.label}</span>
                <strong title={cap?.title}>
                  {formatGearStatValue(stat)}
                  {cap ? <em className="set-total-cap">({cap.text})</em> : null}
                </strong>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
