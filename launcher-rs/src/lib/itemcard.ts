import { useEffect, useState } from "react";
import { backend } from "./api";
import type { CharacterBagItem, GearItemStats, GearSlot, GearStatQuery } from "../types";

/**
 * The hover card reads one item's client tooltip when the pointer lands on it. Replies are
 * cached for the whole session so moving across the same ring/earring pair, or coming back to
 * a slot, does not ask the client again — and a set with two copies of one item asks once.
 */
const CACHE = new Map<string, GearItemStats>();

function cardKey(query: GearStatQuery | null): string {
  if (!query) return "";
  return `${query.id ?? 0}\u0000${query.name}\u0000${(query.augments ?? []).join("\u0001")}`;
}

export interface ItemCardState {
  stats: GearItemStats | null;
  loading: boolean;
  error: string;
}

/** The client tooltip for the hovered slot, fetched on demand and cached by name + augments. */
export function useItemCard(port: number | null, query: GearStatQuery | null): ItemCardState {
  const key = cardKey(query);
  const [state, setState] = useState<{ key: string; stats: GearItemStats | null; error: string }>(
    { key: "", stats: null, error: "" },
  );

  useEffect(() => {
    if (!port || !query || !key) {
      setState({ key: "", stats: null, error: "" });
      return;
    }
    const cached = CACHE.get(key);
    if (cached) {
      setState({ key, stats: cached, error: "" });
      return;
    }
    let cancelled = false;
    // A quick pass over the grid should not queue a request per cell; only the slot the
    // pointer stops on asks the client, like the set totals' debounce.
    const timer = window.setTimeout(() => {
      backend
        .gearItemStats(port, [query])
        .then((items) => {
          const stats = items?.[0] ?? null;
          // Cache only a resolved item.  A found=false row is what an old or unready host
          // sends for a name it cannot see yet; keeping it would hide the tooltip after the
          // host is rebuilt, while the Set totals above refetched and show the item.
          if (stats?.found) CACHE.set(key, stats);
          if (!cancelled) setState({ key, stats, error: "" });
        })
        .catch((caught) => {
          if (cancelled) return;
          setState({
            key,
            stats: null,
            error: caught instanceof Error ? caught.message : String(caught),
          });
        });
    }, 120);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // query is represented by key; its object is rebuilt every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, key]);

  const ready = state.key === key;
  return {
    stats: ready ? state.stats : null,
    loading: !!query && !ready,
    error: ready ? state.error : "",
  };
}

/** A bag row's decoded augments are one ` | ` string; the card wants one line per augment. */
export function splitAugments(text: string | null | undefined): string[] {
  if (!text) return [];
  return text
    .split("|")
    .map((row) => row.trim())
    .filter(Boolean);
}

/**
 * Augment rows for a live equipped slot. The client's gear read names the item and the bag
 * slot it came from; the server's bag snapshot carries the decoded rows, which is the only
 * place two copies of the same item can be told apart.
 */
export function augmentsForSlot(
  rows: CharacterBagItem[],
  item: GearSlot | undefined,
): string[] {
  if (!item?.name || rows.length === 0) return [];
  const placed = rows.find(
    (row) => row.container === Number(item.bag ?? -1) && row.slot === Number(item.index ?? -1),
  );
  if (placed) return splitAugments(placed.augments);
  const sameItem = rows.filter((row) => row.item_id === Number(item.id ?? 0));
  const augmented = sameItem.find((row) => row.augments);
  return splitAugments((augmented ?? sameItem[0])?.augments);
}

/**
 * Augment rows for a GearSwap set slot. A library often names only the piece, while the
 * actual bag copy carries the Oseem/Ambuscade block; when the set itself does not spell
 * out the augments, show the matching copy the character owns. The first augmented copy
 * wins so two differently-rolled pieces remain distinguishable by their library entries.
 */
export function augmentsForSetItem(
  rows: CharacterBagItem[],
  name: string | undefined,
): string[] {
  if (!name || rows.length === 0) return [];
  const wanted = name.trim().toLowerCase();
  if (!wanted) return [];
  const matches = rows.filter((row) => row.name.trim().toLowerCase() === wanted);
  const augmented = matches.find((row) => (row.augments ?? "").trim());
  return splitAugments(augmented?.augments);
}

const BAGS = new Map<number, CharacterBagItem[]>();
const BAG_REQUESTS = new Map<number, Promise<CharacterBagItem[]>>();

/** One bag snapshot per character for the session; the first hover pays for it. */
function loadBags(characterId: number): Promise<CharacterBagItem[]> {
  const cached = BAGS.get(characterId);
  if (cached) return Promise.resolve(cached);
  const pending = BAG_REQUESTS.get(characterId);
  if (pending) return pending;
  const request = backend
    .characterBags(characterId)
    .then((result) => {
      const items = result.items ?? [];
      BAGS.set(characterId, items);
      BAG_REQUESTS.delete(characterId);
      return items;
    })
    .catch((error) => {
      BAG_REQUESTS.delete(characterId);
      throw error;
    });
  BAG_REQUESTS.set(characterId, request);
  return request;
}

/**
 * The bag rows the card needs when the caller has no augment map of its own (the Home and
 * Control pages watch a live grid without loading the bags). Only asked for once a card is
 * about to open, so a page that never hovers never pays for it.
 */
export function useBagAugments(characterId: number | null, enabled: boolean) {
  const [rows, setRows] = useState<CharacterBagItem[]>([]);
  useEffect(() => {
    if (!characterId || !enabled) return;
    let cancelled = false;
    loadBags(characterId)
      .then((items) => {
        if (!cancelled) setRows(items);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [characterId, enabled]);
  return rows;
}
