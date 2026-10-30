import { useEffect, useMemo, useState } from "react";
import { Check, ScrollText } from "lucide-react";
import type { CharacterData, MagianCopy, MagianTrial } from "../types";
import { Badge, Button, Card, Select, TextInput } from "./ui";
import { slotLabel } from "../lib/format";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

function copyKeyOf(copy: MagianCopy): string {
  return `${copy.container}:${copy.slot}`;
}

/** The Data page's Magian Moogle card.
 *
 * Trial of the Magians is a chain: each trial turns the traded item into its
 * reward (a relic stage, an Empyrean +1/+2, another trial weapon) and writes
 * the Magian block with that trial's four augment slots and its trial id.  The
 * card lists every catalogue item with its immediate trials, so picking a path
 * completes that one step; repeat for the next step.  The i119 augment
 * weapons (Centovente, Fusetto and the rest) keep their item id and just pick
 * up the chosen augment block.
 */
export function MagianMoogle({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const catalog = data.magian;
  const items = useMemo(() => catalog?.items ?? [], [catalog]);
  const [itemId, setItemId] = useState(0);
  const [copyKey, setCopyKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [ownedOnly, setOwnedOnly] = useState(true);

  useEffect(() => {
    if (!items.length) return;
    if (!items.some((item) => item.item_id === itemId)) {
      const first = items.find((item) => item.copies.length > 0) ?? items[0];
      setItemId(first.item_id);
      setCopyKey(null);
    }
  }, [items, itemId]);

  const selected = items.find((item) => item.item_id === itemId) ?? null;
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter(
      (item) =>
        (!kind || item.kind === kind) &&
        (!ownedOnly || item.copies.length > 0) &&
        (!needle || item.name.toLowerCase().includes(needle)),
    );
  }, [items, kind, ownedOnly, query]);
  const options = useMemo(() => {
    const list = [...visible];
    if (selected && !list.some((item) => item.item_id === selected.item_id)) {
      list.unshift(selected);
    }
    return list.slice(0, 400);
  }, [visible, selected]);

  if (!catalog) return null;

  const copies = selected?.copies ?? [];
  const copy = copies.find((candidate) => copyKeyOf(candidate) === copyKey) ?? copies[0] ?? null;

  function complete(trial: MagianTrial) {
    if (!copy) return;
    setCopyKey(null);
    setItemId(trial.reward);
    run(
      "progress",
      { op: "magian", container: copy.container, slot: copy.slot, trial: trial.id },
      `Trial ${trial.id} complete — ${trial.reward_name}`,
      `magian-${trial.id}`,
    );
  }

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <ScrollText size={17} />
        </div>
        <div className="data-card-title">
          <h3>Magian Moogle · Trials</h3>
          <p>Ru&apos;Lude Gardens (H-5) · Trial of the Magians · weapons and Empyrean/Relic armor</p>
        </div>
        <div className="data-card-badge">
          <Badge tone="accent">{catalog.catalog_size} items</Badge>
        </div>
      </div>

      <p className="data-note">
        Pick a trial to complete it: the item is replaced by the trial&apos;s reward
        and its Magian block is written, carrying the augment rows and the trial id
        the client shows. The i119 augment weapons keep their item and only take
        the chosen block. The catalogue comes from the wiki category and
        LandSandBoat&apos;s trial table.
      </p>

      <div className="magian-filters">
        <TextInput
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter by name…"
          aria-label="Filter Magian items"
        />
        <Select value={kind} onChange={(event) => setKind(event.target.value)} aria-label="Gear kind">
          <option value="">All gear</option>
          <option value="weapon">Weapons</option>
          <option value="armor">Armor</option>
        </Select>
        <label className="check-row">
          <input
            type="checkbox"
            checked={ownedOnly}
            onChange={(event) => setOwnedOnly(event.target.checked)}
          />
          Owned only
        </label>
      </div>

      <div className="cape-picker">
        <Select
          value={selected?.item_id ?? ""}
          onChange={(event) => {
            setItemId(Number(event.target.value));
            setCopyKey(null);
          }}
          aria-label="Magian item"
        >
          {options.map((item) => (
            <option key={item.item_id} value={item.item_id}>
              {item.name}
              {item.copies.length ? ` · ${item.copies.length} in bags` : ""}
              {item.trials.length ? "" : " · no trials"}
            </option>
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
              </option>
            ))}
          </Select>
        )}
      </div>

      {visible.length > options.length && (
        <p className="data-note">
          Showing {options.length} of {visible.length} items — type a name to narrow the list.
        </p>
      )}

      {selected ? (
        <>
          <p className="data-note cape-selected">
            {selected.kind === "weapon" ? "Weapon" : "Armor"} ·
            {selected.slot ? ` ${slotLabel(selected.slot)}` : ""} · Lv. {selected.level} ·
            item #{selected.item_id}
            {copy ? ` · ${copy.container_name} #${copy.slot}` : ""}
          </p>

          {copy ? (
            <div className="cape-current">
              <div>
                <span>Current block</span>
                <strong>{copy.current}</strong>
              </div>
            </div>
          ) : (
            <p className="data-note">
              Preview only — this piece is not in the bags. Buy it in the{" "}
              <strong>Armory</strong> below, or trade the base item to the Magian
              Moogle in game, then it can be upgraded here.
            </p>
          )}

          {selected.trials.length === 0 ? (
            <p className="data-note">
              This item is the end of its trial chain; it has no further trials.
            </p>
          ) : (
            <div className="data-paths magian-trials">
              {selected.trials.map((trial) => {
                const key = `magian-${trial.id}`;
                const changesItem = trial.reward !== selected.item_id;
                return (
                  <div className="data-path" key={trial.id}>
                    <div className="data-path-head">
                      <strong>Trial {trial.id}</strong>
                      <span>{changesItem ? `→ ${trial.reward_name}` : "augment"}</span>
                    </div>
                    {trial.text.length > 0 ? (
                      <ul className="data-path-lines">
                        {trial.text.map((line, index) => (
                          <li key={index}>{line}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="data-note">
                        {changesItem
                          ? `Upgrades to ${trial.reward_name}; no augment rows.`
                          : "No augment rows."}
                      </p>
                    )}
                    {trial.num > 0 && (
                      <p className="data-note">
                        {trial.num.toLocaleString()} objective
                        {trial.num === 1 ? "" : "s"}.
                      </p>
                    )}
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Check size={14} />}
                      loading={busy === key}
                      disabled={!copy || (busy !== null && busy !== key)}
                      onClick={() => complete(trial)}
                    >
                      Complete trial
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <p className="data-note">No trial items match the filter.</p>
      )}
    </Card>
  );
}
