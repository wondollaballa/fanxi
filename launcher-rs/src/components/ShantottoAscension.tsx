import { useEffect, useState } from "react";
import { Check, Eraser, Sparkles } from "lucide-react";
import type { AscensionCopy, CharacterData } from "../types";
import { Badge, Button, Card, Select } from "./ui";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

function copyKey(copy: AscensionCopy): string {
  return `${copy.container}:${copy.slot}`;
}

/** The Data page's Shantotto's Ascension card.
 *
 * The add-on's three leg pieces share one augment table; a copy carries two
 * different rows in the same standard 24-byte block the Ambuscade capes use.
 * Phantom Roll -5 is the Corsair row and is stored as (0x154, 4); the client
 * prints it as -5 seconds and the server subtracts it from the recast.
 */
export function ShantottoAscension({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const card = data.ascension;
  const items = card?.items ?? [];
  const options = card?.options ?? [];
  const [itemId, setItemId] = useState<number>(() => {
    const preferred = items.find((item) => item.item_id === 16370 && item.copies.length);
    return (preferred ?? items.find((item) => item.copies.length) ?? items[0])?.item_id ?? 0;
  });
  const [copyId, setCopyId] = useState<string | null>(null);
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");

  const item = items.find((entry) => entry.item_id === itemId) ?? items[0] ?? null;
  const copies = item?.copies ?? [];
  const copy = copies.find((entry) => copyKey(entry) === copyId) ?? copies[0] ?? null;

  useEffect(() => {
    if (!itemId && items.length) setItemId(items[0].item_id);
  }, [itemId, items]);

  useEffect(() => {
    setFirst(copy?.choices[0] ?? "");
    setSecond(copy?.choices[1] ?? "");
  }, [copy?.container, copy?.slot, copy?.choices]);

  if (!card) return null;

  const firstOption = options.find((option) => option.key === first) ?? null;
  const secondOption = options.find((option) => option.key === second) ?? null;
  const chosen = Boolean(firstOption || secondOption);
  const currentText = copy?.text && copy.text !== "not augmented"
    ? copy.text
    : "Not augmented";

  function applyAugments() {
    if (!item || !copy) return;
    const choices = [first, second].filter(Boolean);
    if (!choices.length) return;
    run(
      "ascension",
      { container: copy.container, slot: copy.slot, choices },
      `${item.name} — ${[firstOption?.label, secondOption?.label].filter(Boolean).join(" · ")}`,
      "ascension",
    );
  }

  function clearAugments() {
    if (!item || !copy) return;
    run(
      "ascension",
      { container: copy.container, slot: copy.slot, choices: [] },
      `${item.name} augments cleared`,
      "ascension-clear",
    );
  }

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <Sparkles size={17} />
        </div>
        <div className="data-card-title">
          <h3>Shantotto's Ascension</h3>
          <p>
            Blitzer Poleyn · Desultor Tassets · Tatsumaki Sitagoromo · two augments per copy
          </p>
        </div>
        <div className="data-card-badge">
          <Badge tone={items.some((entry) => entry.copies.length) ? "success" : "neutral"}>
            {items.reduce((total, entry) => total + entry.copies.length, 0)} in bags
          </Badge>
        </div>
      </div>

      <p className="data-note">
        Each copy carries the same standard 24-byte augment block as the Ambuscade capes.
        Pick two different rows; <strong>Phantom Roll -5</strong> is the Corsair choice and
        subtracts five seconds from the ability's recast.
      </p>

      <div className="ascension-items">
        {items.map((entry) => (
          <button
            type="button"
            key={entry.item_id}
            className={entry.item_id === item?.item_id ? "ascension-item active" : "ascension-item"}
            onClick={() => {
              setItemId(entry.item_id);
              setCopyId(null);
            }}
          >
            <strong>{entry.name}</strong>
            <small>
              {entry.slot} · {entry.copies.length} in bags
            </small>
          </button>
        ))}
      </div>

      {!item || copies.length === 0 ? (
        <p className="data-note">
          No {item?.name ?? "Ascension gear"} in the bags or wardrobes. The piece is
          Rare/Ex; obtain it from the add-on and it will show here.
        </p>
      ) : (
        <>
          {copies.length > 1 && (
            <div className="cape-picker">
              <Select
                value={copy ? copyKey(copy) : ""}
                onChange={(event) => setCopyId(event.target.value)}
                aria-label={`${item.name} copy`}
              >
                {copies.map((candidate) => (
                  <option key={copyKey(candidate)} value={copyKey(candidate)}>
                    {candidate.container_name} #{candidate.slot}
                    {candidate.choices.length ? ` · ${candidate.choices.length} augments` : " · clean"}
                  </option>
                ))}
              </Select>
            </div>
          )}

          {copy && (
            <div className="cape-current">
              <div>
                <span>
                  {copy.container_name} #{copy.slot} · current
                </span>
                <strong>{currentText}</strong>
              </div>
              {copy.choices.length > 0 && (
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Eraser size={14} />}
                  loading={busy === "ascension-clear"}
                  disabled={busy !== null && busy !== "ascension-clear"}
                  onClick={clearAugments}
                >
                  Clear augments
                </Button>
              )}
            </div>
          )}

          <div className="moonshade-picks">
            <div className="moonshade-set">
              <label htmlFor="ascension-first">Augment 1</label>
              <Select
                id="ascension-first"
                value={first}
                onChange={(event) => {
                  const next = event.target.value;
                  setFirst(next);
                  if (next && next === second) setSecond("");
                }}
              >
                <option value="">Choose an augment…</option>
                {options.map((option) => (
                  <option key={option.key} value={option.key} disabled={option.key === second}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="moonshade-set">
              <label htmlFor="ascension-second">Augment 2</label>
              <Select
                id="ascension-second"
                value={second}
                onChange={(event) => {
                  const next = event.target.value;
                  setSecond(next);
                  if (next && next === first) setFirst("");
                }}
              >
                <option value="">Choose an augment…</option>
                {options.map((option) => (
                  <option key={option.key} value={option.key} disabled={option.key === first}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="data-actions cape-actions">
            <div className="moonshade-preview">
              {firstOption ? <Badge tone="accent">{firstOption.label}</Badge> : null}
              {secondOption ? <Badge tone="accent">{secondOption.label}</Badge> : null}
              {!chosen && <span className="data-note">Choose at least one augment.</span>}
            </div>
            <Button
              icon={<Check size={15} />}
              loading={busy === "ascension"}
              disabled={!chosen || (busy !== null && busy !== "ascension")}
              onClick={applyAugments}
            >
              Apply augments
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
