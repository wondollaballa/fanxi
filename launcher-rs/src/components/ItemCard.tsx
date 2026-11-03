import { useMemo, type CSSProperties } from "react";
import { JOB_ABBRS } from "../lib/format";
import type { GearItemStats } from "../types";
import { cn } from "./ui";

/**
 * The card the game (and BG Wiki) draw over an equipped item: the tooltip verbatim, the
 * augment rows the copy carries, then its level and jobs. `description` comes from the
 * client resource table, so `Set:`, `Unity Ranking:` and `Mastery Rank:` blocks render the
 * way the game prints them; augments come from the GearSwap set or the bag row, because the
 * client keeps those outside the item's description.
 */

/** The client's race mask: bit 1 is Hume male, bit 8 Galka. */
const RACES = [
  "Hume M",
  "Hume F",
  "Elve. M",
  "Elve. F",
  "Taru. M",
  "Taru. F",
  "Mithra",
  "Galka",
];
const ALL_RACES = 0x1fe;

/** Lines that are part of the tooltip but not always-on stats (styled apart, never totaled). */
const CONDITIONAL = /^(set|pet|avatar|automaton|wyvern|luopan|fellow|unity ranking|mastery rank)\s*:/i;

const CARD_WIDTH = 344;

export function jobNames(mask: number | undefined): string[] {
  if (!mask) return [];
  return JOB_ABBRS.filter((_, index) => (mask & (1 << index)) !== 0);
}

export function raceLabel(mask: number | undefined): string {
  if (!mask || (mask & ALL_RACES) === ALL_RACES) return "All Races";
  const names = RACES.filter((_, index) => (mask & (1 << (index + 1))) !== 0);
  return names.length ? names.join(" · ") : "All Races";
}

export interface CardAnchor {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export function ItemCard({
  name,
  slotLabel,
  augments,
  stats,
  loading = false,
  error = "",
  anchor,
}: {
  name: string;
  slotLabel: string;
  augments?: string[];
  stats?: GearItemStats | null;
  loading?: boolean;
  error?: string;
  anchor: CardAnchor;
}) {
  const lines = useMemo(() => {
    const description = stats?.description?.trim();
    if (description) {
      return description
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
    }
    // An older launcher build has no verbatim description; the stat-only lines still make a
    // useful card, and the augment rows below do not depend on the client.
    return stats?.baseLines ?? [];
  }, [stats]);

  const jobs = jobNames(stats?.jobs);
  const level = Number(stats?.level ?? 0);
  const itemLevel = Number(stats?.itemLevel ?? 0);
  // The library may use the server's name for the same item ("Opashoro 119 III"); once
  // the card has the client row, its own label is the one the game would print.  The
  // server suffix is a version description, not part of the item's display name.
  const title = stats?.name?.trim() || name;

  // Beside the cell when there is room, otherwise on its other side; never off the window.
  const width = Math.min(CARD_WIDTH, window.innerWidth - 16);
  let left = anchor.right + 12;
  if (left + width > window.innerWidth - 8) left = anchor.left - width - 12;
  left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
  // Keep the whole card on screen: anchor near the cell's top, then never taller than the
  // space below it (a long weapon tooltip scrolls inside the card instead of running off).
  const top = Math.max(8, Math.min(anchor.top - 10, window.innerHeight - 300));
  const maxHeight = Math.max(180, window.innerHeight - top - 8);

  const style = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    maxHeight: `${maxHeight}px`,
  } as CSSProperties;

  return (
    <div className="item-card" role="tooltip" style={style}>
      <div className="item-card-head">
        <strong className="item-card-name">{title}</strong>
        <span className="item-card-tags">
          <span className="item-card-slot">[{slotLabel}]</span>{" "}
          <span className="item-card-races">{raceLabel(stats?.races)}</span>
        </span>
      </div>
      {lines.length > 0 ? (
        <div className="item-card-lines">
          {lines.map((line, index) => (
            <span
              key={`${line}-${index}`}
              className={cn("item-card-line", CONDITIONAL.test(line) && "conditional")}
            >
              {line}
            </span>
          ))}
        </div>
      ) : loading ? (
        <span className="item-card-note">Reading the client tooltip…</span>
      ) : null}
      {augments && augments.length > 0 ? (
        <div className="item-card-augments">
          <span className="item-card-sect">Augments</span>
          {augments.map((line, index) => (
            <span key={`${line}-${index}`} className="item-card-augment">
              {line}
            </span>
          ))}
        </div>
      ) : null}
      {itemLevel > 0 || level > 0 || jobs.length > 0 ? (
        <div className="item-card-foot">
          <span>{itemLevel > 0 ? `iLv ${itemLevel}` : ""}</span>
          <span className="item-card-level">
            {level > 0 ? `Lv.${level}` : ""}
            {jobs.length > 0 ? <em>{jobs.join(" ")}</em> : null}
          </span>
        </div>
      ) : null}
      {loading && lines.length > 0 ? <span className="item-card-note">Reading…</span> : null}
      {error ? (
        <span className="item-card-error" title={error}>
          {error}
        </span>
      ) : null}
    </div>
  );
}
