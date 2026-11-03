import type { GearItemStats, GearStat } from "../types";
import document from "../../../data/armor_set_bonuses.json";

/**
 * Set bonuses are printed as only `Set: ...` on each client item; the actual tiers live on
 * the wiki/set page, not in the item row.  ``data/armor_set_bonuses.json`` is shared with the
 * server so both sides add the same numbers.  The Set totals are built from the client
 * tooltips, so this is the launcher's half of that table: count the selected +1 pieces and
 * append one synthetic "set" item to the totals.
 *
 * The client row's id is the primary match; the client's display name is the fallback for a
 * row the alias resolver could not turn into an id.  Client names are truncated to the item
 * field width (``Souv. Handsch. +1``), so the table carries both spellings.
 */

interface RawPiece {
  id: number;
  name: string;
  /** The client's (possibly truncated) display name; the server name can be longer. */
  client_name?: string;
}

interface RawTier {
  pieces: number;
  mods: Record<string, number>;
}

interface RawSet {
  name: string;
  pieces: RawPiece[];
  tiers: RawTier[];
}

const SETS = (document as { sets: RawSet[] }).sets;

interface StatInfo {
  label: string;
  percent: boolean;
  order: number;
}

/** Label/unit/order for the modifier keys the shared table uses. */
const STAT_INFO: Record<string, StatInfo> = {
  "critical hit rate": { label: "Critical hit rate", percent: true, order: 1030 },
  "magic atk. bonus": { label: "Magic Atk. Bonus", percent: false, order: 140 },
  "blood pact damage": { label: "Blood Pact damage", percent: false, order: 9000 },
  "double attack": { label: "Double Attack", percent: true, order: 520 },
  accuracy: { label: "Accuracy", percent: false, order: 110 },
  "weapon skill damage": { label: "Weapon skill damage", percent: true, order: 570 },
  "martial arts": { label: "Martial Arts", percent: false, order: 9000 },
  attack: { label: "Attack", percent: false, order: 100 },
  "damage taken": { label: "Damage taken", percent: true, order: 370 },
  "cure potency ii": { label: "Cure potency II", percent: true, order: 460 },
};

export interface SetBonusSummary {
  name: string;
  pieces: number;
  stats: GearStat[];
  /** One line for the Set totals card, e.g. `Kaykaus Attire Set +1 (4 pieces): Cure potency II +8%`. */
  text: string;
}

function normalize(name: string): string {
  return name.trim().toLowerCase();
}

function statFor(key: string, value: number): GearStat | null {
  if (!value) return null;
  const info = STAT_INFO[key];
  if (!info) return null;
  return {
    key,
    label: info.label,
    value,
    percent: info.percent,
    order: info.order,
  };
}

/** The set bonuses reached by the supplied pieces, highest tier per set. */
export function setBonusSummaries(items: GearItemStats[]): SetBonusSummary[] {
  if (items.length === 0) return [];
  const wornIds = new Set(items.map((item) => item.id).filter((id) => id > 0));
  const wornNames = new Set(items.map((item) => normalize(item.name)).filter(Boolean));
  const out: SetBonusSummary[] = [];
  for (const set of SETS) {
    const count = set.pieces.filter((piece) =>
      wornIds.has(piece.id) ||
      wornNames.has(normalize(piece.client_name ?? piece.name)) ||
      wornNames.has(normalize(piece.name)),
    ).length;
    if (count < 2) continue;
    const tier = [...set.tiers]
      .sort((a, b) => b.pieces - a.pieces)
      .find((candidate) => count >= candidate.pieces);
    if (!tier) continue;
    const stats = Object.entries(tier.mods)
      .map(([key, value]) => statFor(key, value))
      .filter((stat): stat is GearStat => stat !== null);
    if (stats.length === 0) continue;
    const text = stats
      .map((stat) => `${stat.label} ${stat.value}${stat.percent ? "%" : ""}`)
      .join(", ");
    out.push({
      name: set.name,
      pieces: count,
      stats,
      text: `${set.name} (${count} pieces): ${text}`,
    });
  }
  return out;
}

/** The set bonuses as pseudo-items, so the existing per-slot total keeps them as a source. */
export function withSetBonuses(items: GearItemStats[]): GearItemStats[] {
  const bonuses = setBonusSummaries(items);
  if (bonuses.length === 0) return items;
  return [
    ...items,
    ...bonuses.map((bonus) => ({
      slot: "set",
      name: bonus.text,
      found: true,
      id: 0,
      level: 0,
      itemLevel: 0,
      baseLines: [],
      description: "",
      jobs: 0,
      races: 0,
      baseStats: bonus.stats,
      augmentStats: [],
      stats: bonus.stats,
    })),
  ];
}
