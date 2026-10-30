import { useMemo } from "react";
import type { GearItemStats } from "../types";
import {
  formatGearStatValue,
  gearStatsErrorHint,
  totalGearStats,
} from "../lib/gearstats";

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
          title="Sums the base item stats and the GearSwap augments in this set"
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
          {totals.map((stat) => (
            <div
              className="set-total"
              key={`${stat.key}-${stat.percent ? "pct" : "flat"}`}
            >
              <span title={stat.label}>{stat.label}</span>
              <strong>{formatGearStatValue(stat)}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
