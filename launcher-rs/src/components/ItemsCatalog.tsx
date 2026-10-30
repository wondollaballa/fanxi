import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import {
  Loader2,
  PackageSearch,
  Search,
  ShoppingBasket,
  Sparkles,
  X,
} from "lucide-react";
import type { CharacterData, ItemCategory, StoreItem } from "../types";
import { backend, LauncherError } from "../lib/api";
import { formatNumber } from "../lib/format";
import { ItemIcon } from "./ItemIcon";
import { Badge, Button, Card, TextInput, cn } from "./ui";

type Notify = (message: string, kind?: "success" | "error" | "info") => void;

function messageOf(error: unknown): string {
  if (error instanceof LauncherError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}

const ALL_ITEMS = "";

export function ItemsCatalog({
  characterId,
  gil,
  categories,
  notify,
  onData,
  reloadClient,
}: {
  characterId: number;
  gil: number;
  categories: ItemCategory[];
  notify: Notify;
  onData: (data: CharacterData) => void;
  reloadClient: () => Promise<boolean>;
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState(ALL_ITEMS);
  const [browseAll, setBrowseAll] = useState(false);
  const [items, setItems] = useState<StoreItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selected, setSelected] = useState<StoreItem | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const searchSeq = useRef(0);

  const trimmedQuery = query.trim();
  const browsing = Boolean(trimmedQuery || category || browseAll);
  const totalItems = categories.reduce((total, entry) => total + entry.count, 0);

  useEffect(() => {
    if (!characterId || !browsing) {
      searchSeq.current += 1;
      setItems([]);
      setSearched(false);
      setSearching(false);
      return;
    }
    const seq = ++searchSeq.current;
    setSearching(true);
    const timer = window.setTimeout(() => {
      backend
        .searchItems(characterId, trimmedQuery, category || null)
        .then((result) => {
          if (seq !== searchSeq.current) return;
          setItems(result.items);
          setSearched(true);
        })
        .catch((problem) => {
          if (seq !== searchSeq.current) return;
          notify(messageOf(problem), "error");
          setItems([]);
          setSearched(true);
        })
        .finally(() => {
          if (seq === searchSeq.current) setSearching(false);
        });
    }, 160);
    return () => window.clearTimeout(timer);
  }, [characterId, trimmedQuery, category, browsing, notify]);

  function chooseCategory(next: string) {
    setQuery("");
    setSelected(null);
    if (next === ALL_ITEMS) {
      setCategory(ALL_ITEMS);
      setBrowseAll(true);
    } else {
      setCategory((current) => (current === next ? ALL_ITEMS : next));
      setBrowseAll(false);
    }
  }

  function changeQuery(next: string) {
    setQuery(next);
    setSelected(null);
    setBrowseAll(false);
  }

  function pick(item: StoreItem) {
    setSelected(item);
  }

  function onSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && items.length > 0 && !selected) {
      event.preventDefault();
      setSelected(items[0]);
    } else if (event.key === "Escape") {
      setQuery("");
      setSelected(null);
    }
  }

  async function buy(item: StoreItem, quantity: number) {
    if (!characterId || busy) return;
    const key = `${item.item_id}:${quantity}`;
    setBusy(key);
    try {
      const result = await backend.characterAction(characterId, "items", {
        item_id: item.item_id,
        quantity,
      });
      if (result.data) onData(result.data);
      const live = await reloadClient();
      const paid = result.item?.price ?? item.price * quantity;
      setItems((current) =>
        current.map((row) =>
          row.item_id === item.item_id
            ? { ...row, held: row.held + quantity, owned: true }
            : row,
        ),
      );
      setSelected((current) =>
        current && current.item_id === item.item_id
          ? { ...current, held: current.held + quantity, owned: true }
          : current,
      );
      notify(
        live
          ? `${formatNumber(quantity)}× ${item.name} purchased for ${formatNumber(paid)} gil — client reloaded`
          : `${formatNumber(quantity)}× ${item.name} purchased for ${formatNumber(paid)} gil — it appears at the next zone-in`,
        "success",
      );
    } catch (problem) {
      if (problem instanceof LauncherError && problem.code === "already_owned") {
        notify(`${item.name} is already in the character's possession`, "info");
        const mark = (row: StoreItem) => ({ ...row, owned: true, held: Math.max(1, row.held) });
        setItems((current) =>
          current.map((row) => (row.item_id === item.item_id ? mark(row) : row)),
        );
        setSelected((current) =>
          current && current.item_id === item.item_id ? mark(current) : current,
        );
      } else {
        notify(messageOf(problem), "error");
      }
    } finally {
      setBusy(null);
    }
  }

  const stackSize = selected ? Math.max(1, selected.stack) : 1;
  const rareOwned = Boolean(selected && selected.rare === 1 && selected.held > 0);
  const canAffordOne = Boolean(selected && gil >= selected.price);
  const canAffordStack = Boolean(selected && gil >= selected.price * stackSize);
  const canBuyStack = Boolean(selected && stackSize > 1 && selected.rare !== 1);
  const busyKey = busy ?? "";

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <ShoppingBasket size={17} />
        </div>
        <div className="data-card-title">
          <h3>Item store</h3>
          <p>
            Buy ninja tools, jug pets, consumables, ingredients and other general items one
            at a time or by the full stack.
          </p>
        </div>
        <div className="data-card-badge">
          <Badge>{formatNumber(totalItems)} items</Badge>
        </div>
      </div>

      <div className="store-search">
        <div className="input-with-icon">
          {searching ? <Loader2 className="spin" size={15} /> : <Search size={15} />}
          <TextInput
            value={query}
            onChange={(event) => changeQuery(event.target.value)}
            onKeyDown={onSearchKeyDown}
            placeholder="Search shihei, carrot broth, fire crystal…"
            aria-label="Search the item store"
            autoComplete="off"
          />
        </div>
        {query && (
          <Button variant="ghost" size="sm" icon={<X size={14} />} onClick={() => changeQuery("")}>
            Clear
          </Button>
        )}
      </div>

      <div className="store-categories" role="group" aria-label="Item category">
        <button
          type="button"
          className={cn("store-category", browseAll && "active")}
          aria-pressed={browseAll}
          onClick={() => chooseCategory(ALL_ITEMS)}
        >
          All items
          <span className="store-category-count">{formatNumber(totalItems)}</span>
        </button>
        {categories.map((entry) => (
          <button
            key={entry.name}
            type="button"
            className={cn("store-category", category === entry.name && "active")}
            aria-pressed={category === entry.name}
            onClick={() => chooseCategory(entry.name)}
          >
            {entry.name}
            <span className="store-category-count">{formatNumber(entry.count)}</span>
          </button>
        ))}
      </div>

      <div className="store-layout">
        <div className="store-list">
          {!browsing ? (
            <div className="store-prompt">
              <PackageSearch size={24} />
              <strong>Search by name or pick a shelf above.</strong>
              <span>
                The store holds every non-equipment item the server can sell: shihei and
                toolbags, Call Beast jugs and pet food, potions, food, crystals, crafting
                materials, arrows and more.
              </span>
            </div>
          ) : searching && items.length === 0 ? (
            <p className="store-note">Searching the shelves…</p>
          ) : searched && items.length === 0 ? (
            <p className="store-note">
              No items matched{trimmedQuery ? ` “${trimmedQuery}”` : " this shelf"}.
            </p>
          ) : (
            <>
              <div className="store-results">
                {items.map((item) => (
                  <button
                    key={item.item_id}
                    type="button"
                    className={cn("store-result", selected?.item_id === item.item_id && "is-selected")}
                    onClick={() => pick(item)}
                  >
                    <ItemIcon name={item.name} size={30} />
                    <span className="store-result-text">
                      <strong>{item.name}</strong>
                      <small>
                        {item.category} · Stack {formatNumber(Math.max(1, item.stack))}
                        {item.held > 0 ? ` · Held ${formatNumber(item.held)}` : ""}
                      </small>
                    </span>
                    <span className="store-result-price">
                      {formatNumber(item.price)}
                      <small> gil / ea</small>
                    </span>
                  </button>
                ))}
              </div>
              {items.length >= 80 && (
                <p className="store-note">
                  Showing the first 80 matches — refine the search or pick a narrower shelf.
                </p>
              )}
            </>
          )}
        </div>

        <aside className="store-detail" aria-live="polite">
          {selected ? (
            <>
              <div className="store-detail-head">
                <ItemIcon name={selected.name} size={64} />
                <div className="store-detail-title">
                  <h4>{selected.name}</h4>
                  <span>
                    #{selected.item_id} · {selected.category}
                  </span>
                  <div className="data-flags">
                    {selected.rare === 1 && <Badge tone="warning">Rare</Badge>}
                    {selected.ex === 1 && <Badge>Ex</Badge>}
                    {selected.held > 0 && (
                      <Badge tone="success">Held {formatNumber(selected.held)}</Badge>
                    )}
                  </div>
                </div>
              </div>

              {selected.description && <p className="data-note">{selected.description}</p>}

              <div className="store-facts">
                <span>
                  Unit price
                  <strong>{formatNumber(selected.price)} gil</strong>
                </span>
                <span>
                  Stack size
                  <strong>{formatNumber(stackSize)}</strong>
                </span>
                <span>
                  Full stack
                  <strong>{formatNumber(selected.price * stackSize)} gil</strong>
                </span>
              </div>

              {rareOwned ? (
                <div className="armory-blocked">
                  <Badge tone="success">Currently owned</Badge>
                  <span>Rare — only one copy can be held, so the store will not sell another.</span>
                </div>
              ) : (
                <div className={cn("store-buy-options", !canBuyStack && "single")}>
                  <button
                    type="button"
                    className="store-buy-option"
                    disabled={busy !== null || !canAffordOne}
                    onClick={() => void buy(selected, 1)}
                  >
                    <span>Single</span>
                    <strong>
                      {busyKey === `${selected.item_id}:1` ? (
                        <Loader2 className="spin" size={15} />
                      ) : (
                        "Buy 1"
                      )}
                    </strong>
                    <small>{formatNumber(selected.price)} gil</small>
                  </button>
                  {canBuyStack && (
                    <button
                      type="button"
                      className="store-buy-option"
                      disabled={busy !== null || !canAffordStack}
                      onClick={() => void buy(selected, stackSize)}
                    >
                      <span>Full stack</span>
                      <strong>
                        {busyKey === `${selected.item_id}:${stackSize}` ? (
                          <Loader2 className="spin" size={15} />
                        ) : (
                          `Buy ${formatNumber(stackSize)}`
                        )}
                      </strong>
                      <small>{formatNumber(selected.price * stackSize)} gil</small>
                    </button>
                  )}
                </div>
              )}

              {!canAffordOne && !rareOwned && (
                <p className="data-note">Not enough gil — top off the wallet in Overview.</p>
              )}
              {canAffordOne && !canAffordStack && canBuyStack && !rareOwned && (
                <p className="data-note">You can afford one, but not a full stack.</p>
              )}
              {selected.rare === 1 && selected.held === 0 && (
                <p className="data-note">Rare — the store will sell only one copy.</p>
              )}
              {selected.ex === 1 && (
                <p className="data-note">
                  Ex — cannot be traded or sold, but you may hold more than one copy.
                </p>
              )}
            </>
          ) : (
            <div className="store-prompt store-prompt-detail">
              <Sparkles size={22} />
              <strong>Pick an item to buy it.</strong>
              <span>
                Choose a result on the left to see its unit price, stack price and how many
                you already hold.
              </span>
            </div>
          )}
        </aside>
      </div>
    </Card>
  );
}
