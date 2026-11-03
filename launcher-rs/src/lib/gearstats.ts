import { useEffect, useState } from "react";
import { backend } from "./api";
import type { GearItemStats, GearStat, GearStatQuery } from "../types";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * Ask the running client for the selected set's item descriptions. The reply is kept only for the
 * request that produced it, so changing sets never leaves a slot showing another item's stats.
 */
export function useGearStats(port: number | null, queries: GearStatQuery[]) {
  const key = JSON.stringify(queries);
  const [state, setState] = useState<{
    key: string;
    items: GearItemStats[];
    updatedAt: number;
  }>({ key: "", items: [], updatedAt: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!port || queries.length === 0) {
      setState({ key, items: [], updatedAt: 0 });
      setLoading(false);
      setError("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    // A set switch while the user is browsing should not send a request for every click.
    const timer = window.setTimeout(() => {
      backend
        .gearItemStats(port, queries)
        .then((items) => {
          if (!cancelled) setState({ key, items, updatedAt: Date.now() });
        })
        .catch((caught) => {
          if (cancelled) return;
          setState({ key, items: [], updatedAt: 0 });
          setError(messageOf(caught));
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 140);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // queries is represented by key; the array itself is rebuilt every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, key, revision]);

  // A changed key clears the rows until its own reply arrives, and counts as loading so a
  // component never paints "no stats" for the frame before the effect sends the request.
  const pending = state.key !== key;
  return {
    items: pending ? [] : state.items,
    updatedAt: pending ? 0 : state.updatedAt,
    loading: loading || pending,
    error,
    reload: () => setRevision((value) => value + 1),
  };
}

/** One equipped slot's share of a stat, split by where the number came from. */
export interface GearStatSource {
  slot: string;
  name: string;
  base: number;
  augment: number;
}

/** A stat totaled across the set, with both sources and every contributing slot kept. */
export interface GearStatTotal {
  key: string;
  label: string;
  percent: boolean;
  order: number;
  base: number;
  augment: number;
  total: number;
  sources: GearStatSource[];
}

function statUnit(stat: Pick<GearStat, "key" | "percent">): string {
  return `${stat.key}\u0000${stat.percent ? "pct" : "flat"}`;
}

function sortTotals(totals: GearStatTotal[]): GearStatTotal[] {
  return totals.sort(
    (a, b) =>
      a.order - b.order ||
      a.label.localeCompare(b.label) ||
      Number(a.percent) - Number(b.percent),
  );
}

/**
 * Sum every stat by label and unit, keeping the tooltip and augment halves apart. Duplicate rings
 * and earrings count once per slot because the request list is per slot. `sources` preserves each
 * slot's contribution so the live sheet can explain any total instead of only showing it.
 */
export function totalGearStatsBySource(items: GearItemStats[]): GearStatTotal[] {
  const totals = new Map<string, GearStatTotal>();
  for (const item of items) {
    const contributions = new Map<
      string,
      { stat: GearStat; base: number; augment: number }
    >();
    const add = (stat: GearStat, field: "base" | "augment") => {
      const unit = statUnit(stat);
      const existing = contributions.get(unit);
      if (existing) {
        existing[field] += stat.value;
      } else {
        contributions.set(unit, { stat, base: 0, augment: 0, [field]: stat.value });
      }
    };
    for (const stat of item.baseStats ?? []) add(stat, "base");
    for (const stat of item.augmentStats ?? []) add(stat, "augment");

    for (const [unit, contribution] of contributions) {
      let total = totals.get(unit);
      if (!total) {
        total = {
          key: contribution.stat.key,
          label: contribution.stat.label,
          percent: contribution.stat.percent,
          order: contribution.stat.order,
          base: 0,
          augment: 0,
          total: 0,
          sources: [],
        };
        totals.set(unit, total);
      }
      total.base += contribution.base;
      total.augment += contribution.augment;
      total.total = total.base + total.augment;
      if (contribution.base !== 0 || contribution.augment !== 0) {
        total.sources.push({
          slot: item.slot,
          name: item.name,
          base: contribution.base,
          augment: contribution.augment,
        });
      }
    }
  }
  return sortTotals(Array.from(totals.values()).filter((stat) => stat.total !== 0));
}

/** Sum every stat by label and unit. Duplicate rings and earrings count once per slot. */
export function totalGearStats(items: GearItemStats[]): GearStat[] {
  return totalGearStatsBySource(items).map(({ key, label, percent, order, total }) => ({
    key,
    label,
    value: total,
    percent,
    order,
  }));
}

export function formatGearStatValue(stat: Pick<GearStat, "value" | "percent">): string {
  return `${stat.value}${stat.percent ? "%" : ""}`;
}

export type GearStatCapState = "at" | "over" | "under";

export interface GearStatCapStatus {
  /** The cap itself, in the stat's unit (percent stats only). */
  cap: number;
  state: GearStatCapState;
  /** How far past the cap (excess) or short of it (needed). Zero at the cap. */
  amount: number;
  /** `13 excess`, `13 needed` or `at cap`. */
  text: string;
  /** The full explanation for the row's title attribute. */
  title: string;
}

interface GearStatCapRule {
  cap: number;
  /** Higher is better for a normal bonus; lower is better for a reduction. */
  better: "higher" | "lower";
}

/**
 * Retail caps that apply to the client-tooltip totals.  Keep this list to caps that are
 * really hard caps on the printed stat; a stat without a rule (Accuracy, Magic Damage,
 * Store TP, ...) is shown plainly.  The values come from the game's own formulas and
 * BG Wiki's stat pages; they are percent stats, so only percent rows are annotated.
 */
const GEAR_STAT_CAPS: Record<string, GearStatCapRule> = {
  "fast cast": { cap: 80, better: "higher" },
  // The tooltip totals are equipment only; equipment Haste caps at 25%.
  haste: { cap: 25, better: "higher" },
  "quick magic": { cap: 10, better: "higher" },
  "skillchain bonus": { cap: 50, better: "higher" },
  "cure potency": { cap: 50, better: "higher" },
  "cure potency ii": { cap: 30, better: "higher" },
  // "Magic burst damage" is the capped modifier; "Magic burst damage II" is uncapped.
  "magic burst damage": { cap: 40, better: "higher" },
  // DT and the typed damage-taken rows share retail's -50% family cap.
  "damage taken": { cap: -50, better: "lower" },
  "physical damage taken": { cap: -50, better: "lower" },
  "magic damage taken": { cap: -50, better: "lower" },
  "breath damage taken": { cap: -50, better: "lower" },
  "ranged damage taken": { cap: -50, better: "lower" },
  "spell interruption rate": { cap: -102, better: "lower" },
  "casting time": { cap: -80, better: "lower" },
  snapshot: { cap: 70, better: "higher" },
  "subtle blow": { cap: 50, better: "higher" },
  "subtle blow ii": { cap: 50, better: "higher" },
  "conserve mp": { cap: 100, better: "higher" },
};

/** The cap state for a totaled stat, or null when the stat has no hard cap. */
export function gearStatCap(
  stat: Pick<GearStat, "key" | "value" | "percent">,
): GearStatCapStatus | null {
  if (!stat.percent) return null;
  const rule = GEAR_STAT_CAPS[stat.key.trim().toLowerCase()];
  if (!rule) return null;

  let state: GearStatCapState;
  let amount: number;
  if (rule.better === "higher") {
    if (stat.value >= rule.cap) {
      state = stat.value > rule.cap ? "over" : "at";
      amount = stat.value - rule.cap;
    } else {
      state = "under";
      amount = rule.cap - stat.value;
    }
  } else if (stat.value <= rule.cap) {
    state = stat.value < rule.cap ? "over" : "at";
    amount = rule.cap - stat.value;
  } else {
    state = "under";
    amount = stat.value - rule.cap;
  }

  const text = state === "at" ? "at cap" : state === "over" ? `${amount} excess` : `${amount} needed`;
  const title =
    state === "at"
      ? `Cap ${rule.cap}% — at the cap`
      : `Cap ${rule.cap}% — ${amount} ${state === "over" ? "past" : "to go"}`;
  return { cap: rule.cap, state, amount, text, title };
}

/** A short note for the totals card; the full command error stays in its title. */
export function gearStatsErrorHint(error: string): string {
  if (error.includes('no command "lua"')) {
    return "Rebuild host64 to read item stats.";
  }
  if (error.toLowerCase().includes("control") || error.toLowerCase().includes("game")) {
    return "Item stats need the running client.";
  }
  return "Item stats unavailable.";
}
