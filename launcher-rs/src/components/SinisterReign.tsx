import { useEffect, useMemo, useState } from "react";
import { Eraser, Sparkles } from "lucide-react";
import type { CharacterData, SinisterCopy, SinisterItem } from "../types";
import { Badge, Button, Card, ConfirmDialog, Select } from "./ui";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

function copyKeyOf(copy: SinisterCopy): string {
  return `${copy.container}:${copy.slot}`;
}

/** The Data page's Sinister Reign card.
 *
 * Sinister Reign's wave bosses carry the standard five-slot augment block.
 * Retail rolls each row at a random value, from nothing up to the maximum the
 * wiki table lists.  This card picks an owned copy and writes every listed row
 * at that maximum in one go: Samnuha Tights becomes STR+10 DEX+10
 * Dbl.Atk.+3% Triple Atk.+3%, and so on.
 */
export function SinisterReign({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const catalog = data.sinister;
  const items = catalog?.items ?? [];
  const [itemId, setItemId] = useState(0);
  const [copyKey, setCopyKey] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (!items.length) return;
    if (!items.some((item) => item.item_id === itemId)) {
      const first = items.find((item) => item.copies.length > 0) ?? items[0];
      setItemId(first.item_id);
      setCopyKey(null);
    }
  }, [items, itemId]);

  const selected: SinisterItem | null =
    items.find((item) => item.item_id === itemId) ?? items[0] ?? null;
  const copies = selected?.copies ?? [];
  const copy =
    copies.find((candidate) => copyKeyOf(candidate) === copyKey) ?? copies[0] ?? null;

  const ownedCount = items.filter((item) => item.copies.length > 0).length;
  const groups = useMemo(() => {
    const out: { group: string; items: SinisterItem[] }[] = [];
    for (const item of items) {
      const last = out[out.length - 1];
      if (last && last.group === item.group) last.items.push(item);
      else out.push({ group: item.group, items: [item] });
    }
    return out;
  }, [items]);

  if (!catalog) return null;

  const hasAugments = Boolean(copy && copy.current !== "not augmented");
  const canApply = Boolean(copy) && Boolean(selected?.rows.length) && busy === null;

  function chooseItem(next: number) {
    setItemId(next);
    setCopyKey(null);
    setConfirmClear(false);
  }

  function applyMax() {
    if (!copy || !selected || busy !== null) return;
    run(
      "progress",
      { op: "sinister", container: copy.container, slot: copy.slot },
      `${selected.name} augment rows maxed`,
      "sinister",
    );
  }

  function clear() {
    if (!copy || !selected || busy !== null) return;
    setConfirmClear(false);
    run(
      "progress",
      { op: "sinister-clear", container: copy.container, slot: copy.slot },
      `${selected.name} augments cleared`,
      "sinister-clear",
    );
  }

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <Sparkles size={17} />
        </div>
        <div className="data-card-title">
          <h3>Sinister Reign</h3>
          <p>
            Ra&apos;Kaznar Inner Court · Sinister Reign&apos;s wave bosses ·
            every listed augment row at its maximum
          </p>
        </div>
        <div className="data-card-badge">
          <Badge tone={ownedCount ? "success" : "neutral"}>{ownedCount} in bags</Badge>
        </div>
      </div>

      <p className="data-note">{catalog.note}</p>
      <p className="data-note">
        Retail rolls these rows at random: a piece may carry only some of them,
        each between one and its maximum. This card writes all of them at the
        top of their range. Applying reloads a live client so the tooltip and
        the stat sheet update.
      </p>

      {items.length === 0 ? (
        <p className="data-note">
          No Sinister Reign catalogue is loaded. The card ships with{" "}
          {catalog.catalog_size} pieces; restart the server and refresh.
        </p>
      ) : (
        <>
          <div className="cape-picker">
            <Select
              value={selected?.item_id ?? ""}
              onChange={(event) => chooseItem(Number(event.target.value))}
              aria-label="Sinister Reign item"
            >
              {groups.map((group) => (
                <optgroup key={group.group} label={group.group}>
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
            {copies.length > 1 && (
              <Select
                value={copy ? copyKeyOf(copy) : ""}
                onChange={(event) => setCopyKey(event.target.value)}
                aria-label="Item copy"
              >
                {copies.map((candidate) => (
                  <option key={copyKeyOf(candidate)} value={copyKeyOf(candidate)}>
                    {candidate.container_name} #{candidate.slot}
                    {candidate.current !== "not augmented"
                      ? ` · ${candidate.slots.filter(Boolean).length} augments`
                      : " · clean"}
                  </option>
                ))}
              </Select>
            )}
          </div>

          {selected && (
            <p className="data-note cape-selected">
              {selected.slot_name} · item #{selected.item_id}
              {copy ? ` · ${copy.container_name} #${copy.slot}` : ""}
            </p>
          )}

          {selected && selected.rows.length > 0 && (
            <div className="sinister-rows">
              {selected.rows.map((row) => (
                <div className="sinister-row" key={row.key}>
                  <strong>{row.text}</strong>
                  <span>Maximum</span>
                </div>
              ))}
            </div>
          )}

          {copy ? (
            <div className="cape-current">
              <div>
                <span>Current</span>
                <strong>{copy.current}</strong>
              </div>
              {hasAugments ? (
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Eraser size={14} />}
                  loading={busy === "sinister-clear"}
                  disabled={busy !== null && busy !== "sinister-clear"}
                  onClick={() => setConfirmClear(true)}
                >
                  Clear augments
                </Button>
              ) : null}
            </div>
          ) : (
            <p className="data-note">
              Preview only — this piece is not in the bags. Buy it in the{" "}
              <strong>Armory</strong> below and it can be maxed here.
            </p>
          )}

          <div className="data-actions cape-actions">
            <Button
              icon={<Sparkles size={15} />}
              loading={busy === "sinister"}
              disabled={!canApply}
              onClick={applyMax}
            >
              Give max augments
            </Button>
            <span className="cape-actions-note">
              {!selected?.rows.length
                ? "This piece has no augment rows."
                : !copy
                  ? "Nothing to apply until the piece is in the bags."
                  : hasAugments
                    ? "Rewrites every row at its maximum; existing values are replaced."
                    : "Writes every maximum row in one block."}
            </span>
          </div>
        </>
      )}

      {confirmClear && (
        <ConfirmDialog
          title="Clear this piece's augments?"
          body={`This writes an empty augment block to ${selected?.name ?? "the item"}. Every row is removed and can be rebuilt with Give max augments.`}
          confirmLabel="Clear augments"
          danger
          onConfirm={clear}
          onCancel={() => setConfirmClear(false)}
        />
      )}
    </Card>
  );
}
