import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Eraser, Sparkles, Wand2 } from "lucide-react";
import type {
  CharacterData,
  GlypticCopy,
  GlypticItem,
  GlypticPath,
  GlypticStat,
} from "../types";
import { Badge, Button, Card, ConfirmDialog, Select, TextInput } from "./ui";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

type DraftSlot = { key: string; value: number } | null;

function copyKeyOf(copy: GlypticCopy): string {
  return `${copy.container}:${copy.slot}`;
}

function statMapOf(path: GlypticPath | null): Map<string, GlypticStat> {
  return new Map((path?.stats ?? []).map((stat) => [stat.key, stat]));
}

function signedValue(stat: GlypticStat, raw: number): number {
  const limit = Math.abs(stat.max);
  let value = Math.trunc(Number(raw) || 0);
  value = Math.max(-limit, Math.min(limit, value));
  if (stat.max < 0 && value > 0) value = -value;
  if (stat.max > 0 && value < 0) value = Math.abs(value);
  return value;
}

/** The Data page's Oseem card.
 *
 * Oseem engraves Reisenjima armor and weapons at Norg with Arcane Glyptics.
 * Retail rolls the five slots at random; this editor writes a chosen stat and
 * value per slot instead, using the path table from BG Wiki.  Values default to
 * the highest the block can hold (the wiki's Fern/Taupe maximum, or 32 where the
 * client's five-bit field ends), and each pick is written into the item's
 * standard augment block.
 */
export function OseemGlyptics({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const catalog = data.glyptics;
  const items = catalog?.items ?? [];
  const slotCount = catalog?.slots ?? 5;
  const [itemId, setItemId] = useState(0);
  const [copyKey, setCopyKey] = useState<string | null>(null);
  const [pathKey, setPathKey] = useState("");
  const [draft, setDraft] = useState<DraftSlot[]>([]);
  const [confirmClear, setConfirmClear] = useState(false);
  const draftSource = useRef("");

  useEffect(() => {
    if (!items.length) return;
    if (!items.some((item) => item.item_id === itemId)) {
      const first = items.find((item) => item.copies.length > 0) ?? items[0];
      setItemId(first.item_id);
      setCopyKey(null);
      setPathKey("");
    }
  }, [items, itemId]);

  const selected: GlypticItem | null =
    items.find((item) => item.item_id === itemId) ?? items[0] ?? null;
  const paths = (selected && catalog?.path_sets[selected.path_key]?.paths) || {};
  const pathKeys = Object.keys(paths);
  const path: GlypticPath | null =
    (pathKey && paths[pathKey]) || (pathKeys.length ? paths[pathKeys[0]] : null) || null;
  const activePathKey = pathKey && paths[pathKey] ? pathKey : pathKeys[0] ?? "";
  const copies = selected?.copies ?? [];
  const copy =
    copies.find((candidate) => copyKeyOf(candidate) === copyKey) ?? copies[0] ?? null;

  const stats = useMemo(() => statMapOf(path), [path]);
  const ownedCount = items.filter((item) => item.copies.length > 0).length;
  const groups = useMemo(() => {
    const out: { set: string; items: GlypticItem[] }[] = [];
    for (const item of items) {
      const last = out[out.length - 1];
      if (last && last.set === item.set) last.items.push(item);
      else out.push({ set: item.set, items: [item] });
    }
    return out;
  }, [items]);

  // Re-seed the five picks when the piece/copy/path changes.  A copy that
  // already carries augments of this path seeds with them; a fresh one (or a
  // different path) starts from the path's recommended fill.
  const sourceKey = selected
    ? `${selected.item_id}:${activePathKey}:${copy?.container ?? "x"}:${copy?.slot ?? "x"}`
    : "";
  useEffect(() => {
    if (draftSource.current === sourceKey) return;
    draftSource.current = sourceKey;
    const allowed = new Set((path?.stats ?? []).map((stat) => stat.key));
    const fromCopy = (copy?.selection ?? []).filter(
      (pick): pick is { key: string; value: number } =>
        Boolean(pick) && allowed.has(pick!.key),
    );
    const seed = fromCopy.some(Boolean) ? fromCopy : (path?.defaults ?? []);
    const next: DraftSlot[] = [];
    for (let slot = 0; slot < slotCount; slot += 1) {
      const pick = seed[slot];
      next.push(pick ? { key: pick.key, value: pick.value } : null);
    }
    setDraft(next);
  }, [sourceKey, copy, path, slotCount]);

  if (!catalog) return null;

  const chosen = draft.filter(Boolean).length;
  const canApply = Boolean(copy) && chosen > 0 && busy === null;
  const hasAugments = Boolean(copy && copy.slots.some((text) => text));

  function chooseItem(next: number) {
    setItemId(next);
    setCopyKey(null);
    setPathKey("");
  }

  function choosePath(next: string) {
    setPathKey(next);
  }

  function chooseStat(slot: number, key: string) {
    setDraft((current) => {
      const next = [...current];
      if (!key) {
        next[slot] = null;
        return next;
      }
      const stat = stats.get(key);
      next[slot] = stat ? { key, value: stat.max } : null;
      return next;
    });
  }

  function changeValue(slot: number, raw: number) {
    setDraft((current) => {
      const pick = current[slot];
      if (!pick) return current;
      const stat = stats.get(pick.key);
      if (!stat) return current;
      const next = [...current];
      next[slot] = { key: pick.key, value: signedValue(stat, raw) };
      return next;
    });
  }

  function maxAll() {
    setDraft((current) =>
      current.map((pick) => {
        if (!pick) return null;
        const stat = stats.get(pick.key);
        return stat ? { key: pick.key, value: stat.max } : pick;
      }),
    );
  }

  function apply() {
    if (!copy || busy !== null) return;
    const choices = draft.map((pick) => (pick ? { ...pick } : null));
    run(
      "progress",
      {
        op: "glyptics",
        container: copy.container,
        slot: copy.slot,
        path: activePathKey,
        choices,
      },
      `${selected?.name ?? "Item"} augments saved`,
      "glyptics-apply",
    );
  }

  function clear() {
    if (!copy || busy !== null) return;
    setConfirmClear(false);
    run(
      "progress",
      { op: "glyptics-clear", container: copy.container, slot: copy.slot },
      `${selected?.name ?? "Item"} augments cleared`,
      "glyptics-clear",
    );
  }

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <Wand2 size={17} />
        </div>
        <div className="data-card-title">
          <h3>Oseem · Arcane Glyptics</h3>
          <p>
            Norg (I-7) · Reisenjima armor and weapons · {slotCount} slots · pick
            the stat and value for every slot
          </p>
        </div>
        <div className="data-card-badge">
          <Badge tone={ownedCount ? "success" : "neutral"}>
            {ownedCount} in bags
          </Badge>
        </div>
      </div>

      <p className="data-note">{catalog.note}</p>
      <p className="data-note">
        Retail rolls these augments at random. Here every slot starts at its
        highest value; lower a number or choose another stat. Values above 32 use
        the client&apos;s second id block where it has one.
      </p>

      {items.length === 0 ? (
        <p className="data-note">
          No Reisenjima gear in the bags yet. Buy a piece in the{" "}
          <strong>Armory</strong> below and it appears here; the catalog behind
          this card is {catalog.catalog_size} items.
        </p>
      ) : (
        <>
          <div className="cape-picker">
            <Select
              value={selected?.item_id ?? ""}
              onChange={(event) => chooseItem(Number(event.target.value))}
              aria-label="Reisenjima item"
            >
              {groups.map((group) => (
                <optgroup key={group.set} label={group.set}>
                  {group.items.map((item) => (
                    <option key={item.item_id} value={item.item_id}>
                      {item.name}
                      {item.copies.length > 1
                        ? ` · ${item.copies.length} copies`
                        : item.copies.length === 0
                          ? " · not in bags"
                          : ""}
                    </option>
                  ))}
                </optgroup>
              ))}
            </Select>
            {pathKeys.length > 1 && (
              <Select
                value={activePathKey}
                onChange={(event) => choosePath(event.target.value)}
                aria-label="Augment path"
              >
                {pathKeys.map((key) => (
                  <option key={key} value={key}>
                    {paths[key].label ?? key}
                  </option>
                ))}
              </Select>
            )}
            {copies.length > 1 && (
              <Select
                value={copy ? copyKeyOf(copy) : ""}
                onChange={(event) => setCopyKey(event.target.value)}
                aria-label="Item copy"
              >
                {copies.map((candidate) => (
                  <option key={copyKeyOf(candidate)} value={copyKeyOf(candidate)}>
                    {candidate.container_name} #{candidate.slot}
                    {candidate.slots.some(Boolean)
                      ? ` · ${candidate.slots.filter(Boolean).length} augments`
                      : " · clean"}
                  </option>
                ))}
              </Select>
            )}
          </div>

          {selected && (
            <p className="data-note cape-selected">
              {selected.kind === "weapon" ? "Weapon" : selected.set} · {selected.slot}{" "}
              · item #{selected.item_id}
              {copy ? ` · ${copy.container_name} #${copy.slot}` : ""}
            </p>
          )}

          {path ? (
            <>
              {copy ? (
                <div className="cape-current">
                  <div>
                    <span>
                      Current · {path.label}
                      {copy.slots.some(Boolean) ? "" : " · no augments"}
                    </span>
                    <strong>{copy.current}</strong>
                  </div>
                  {hasAugments ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={<Eraser size={14} />}
                      loading={busy === "glyptics-clear"}
                      disabled={busy !== null && busy !== "glyptics-clear"}
                      onClick={() => setConfirmClear(true)}
                    >
                      Clear augments
                    </Button>
                  ) : null}
                </div>
              ) : (
                <p className="data-note">
                  Preview only — this piece is not in the bags. Buy it in the{" "}
                  <strong>Armory</strong> below and it can be engraved here. The
                  slots start at this path&apos;s recommended fill.
                </p>
              )}

              <div className="glyptic-slots">
                {Array.from({ length: slotCount }, (_, slot) => {
                  const pick = draft[slot] ?? null;
                  const stat = pick ? stats.get(pick.key) ?? null : null;
                  return (
                    <div
                      className={pick ? "glyptic-slot is-set" : "glyptic-slot"}
                      key={slot}
                    >
                      <strong>Slot {slot + 1}</strong>
                      <Select
                        value={pick?.key ?? ""}
                        onChange={(event) => chooseStat(slot, event.target.value)}
                        aria-label={`Slot ${slot + 1} augment`}
                      >
                        <option value="">— empty —</option>
                        {path.stats.map((candidate) => (
                          <option
                            key={candidate.key}
                            value={candidate.key}
                            title={
                              candidate.clamped
                                ? "The wiki maximum is higher; the client's block caps here"
                                : undefined
                            }
                          >
                            {candidate.text}
                          </option>
                        ))}
                      </Select>
                      <TextInput
                        type="number"
                        value={pick?.value ?? ""}
                        disabled={!pick}
                        onChange={(event) => changeValue(slot, Number(event.target.value))}
                        aria-label={`Slot ${slot + 1} value`}
                      />
                      <span className="glyptic-slot-hint">
                        {stat
                          ? stat.clamped
                            ? `${stat.text} · max ${Math.abs(stat.max)} (client cap)`
                            : `${stat.text} · max ${Math.abs(stat.max)}`
                          : "empty"}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="data-actions cape-actions">
                <Button
                  variant="secondary"
                  icon={<Sparkles size={15} />}
                  disabled={!chosen || busy !== null}
                  onClick={maxAll}
                >
                  Max all
                </Button>
                <Button
                  icon={<Check size={15} />}
                  loading={busy === "glyptics-apply"}
                  disabled={!canApply}
                  onClick={apply}
                >
                  Apply augments
                </Button>
                <span className="cape-actions-note">
                  {!copy
                    ? "Nothing to apply until the piece is in the bags."
                    : chosen === 0
                      ? "Pick a stat in at least one slot to enable Apply."
                      : "Slots left empty are written as empty."}
                </span>
              </div>
            </>
          ) : (
            <p className="data-note">No augment table for that path.</p>
          )}
        </>
      )}

      {confirmClear && (
        <ConfirmDialog
          title="Clear this piece's augments?"
          body={`This writes an empty augment block to ${selected?.name ?? "the item"}. All ${slotCount} slots are removed and can be rebuilt afterwards.`}
          confirmLabel="Clear augments"
          danger
          onConfirm={clear}
          onCancel={() => setConfirmClear(false)}
        />
      )}
    </Card>
  );
}
