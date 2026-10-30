import { useEffect, useMemo, useState } from "react";
import { Check, Eraser, Sparkles } from "lucide-react";
import type { CharacterData, MoonshadeCopy, MoonshadeOption } from "../types";
import { Badge, Button, Card, ConfirmDialog, Select } from "./ui";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

function copyKeyOf(copy: MoonshadeCopy): string {
  return `${copy.container}:${copy.slot}`;
}

/** The Data page's Moonshade Earring card.
 *
 * The Wings of the Goddess reward chooses one augment from each of two sets;
 * both are fixed options, so the card is two pickers rather than the numeric
 * rows the capes and Skirmish pieces use.  Applying writes the standard
 * five-slot block with the two chosen words -- the same ids and values the
 * mission hands to the item -- and a live client sees it on `//reload`.
 */
export function MoonshadeEarring({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const card = data.moonshade;
  const sets = useMemo(() => card?.sets ?? [], [card]);
  const copies = useMemo(() => card?.copies ?? [], [card]);
  const [copyKey, setCopyKey] = useState<string | null>(null);
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);

  const copy: MoonshadeCopy | null =
    copies.find((candidate) => copyKeyOf(candidate) === copyKey) ?? copies[0] ?? null;
  const firstSet = sets.find((group) => group.key === "first");
  const secondSet = sets.find((group) => group.key === "second");

  useEffect(() => {
    setFirst(copy?.current?.first ?? "");
    setSecond(copy?.current?.second ?? "");
  }, [copy?.container, copy?.slot, copy?.current?.first, copy?.current?.second]);

  if (!card) return null;

  const firstOption: MoonshadeOption | null =
    firstSet?.options.find((option) => option.key === first) ?? null;
  const secondOption: MoonshadeOption | null =
    secondSet?.options.find((option) => option.key === second) ?? null;
  const currentText = copy?.current?.text.length
    ? copy.current.text.join(" · ")
    : "not augmented";
  const chosen = Boolean(firstOption && secondOption);

  function applyAugments() {
    if (!copy || !firstOption || !secondOption) return;
    run(
      "progress",
      {
        op: "moonshade",
        container: copy.container,
        slot: copy.slot,
        first: firstOption.key,
        second: secondOption.key,
      },
      `${card.name} — ${firstOption.text} · ${secondOption.text}`,
      "moonshade",
    );
  }

  function clearAugments() {
    if (!copy) return;
    setConfirmClear(false);
    run(
      "progress",
      { op: "moonshade-clear", container: copy.container, slot: copy.slot },
      `${card.name} augments cleared`,
      "moonshade-clear",
    );
  }

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <Sparkles size={17} />
        </div>
        <div className="data-card-title">
          <h3>Moonshade Earring</h3>
          <p>Wings of the Goddess · Lest We Forget · one augment from each of two sets</p>
        </div>
        <div className="data-card-badge">
          <Badge tone={copies.length ? "success" : "neutral"}>{copies.length} in bags</Badge>
        </div>
      </div>

      <p className="data-note">
        The mission lets you pick one row from Set 1 and one from Set 2. Applying
        writes both into the same standard augment block the capes use; the client
        tooltip and the stat sheet both read it back.
      </p>

      {copies.length === 0 ? (
        <p className="data-note">
          No Moonshade Earring in the bags, wardrobe or storage. It is Rare/Ex, so buy
          one in the <strong>Armory</strong> below and it will show here.
        </p>
      ) : (
        <>
          {copies.length > 1 && (
            <div className="cape-picker">
              <Select
                value={copy ? copyKeyOf(copy) : ""}
                onChange={(event) => setCopyKey(event.target.value)}
                aria-label="Moonshade Earring copy"
              >
                {copies.map((candidate) => (
                  <option key={copyKeyOf(candidate)} value={copyKeyOf(candidate)}>
                    {candidate.container_name} #{candidate.slot}
                    {candidate.current ? ` · ${candidate.current.text.length} augments` : " · clean"}
                  </option>
                ))}
              </Select>
            </div>
          )}

          {copy && (
            <div className="cape-current">
              <div>
                <span>{copy.container_name} #{copy.slot} · current</span>
                <strong>{currentText}</strong>
              </div>
              {copy.current ? (
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Eraser size={14} />}
                  loading={busy === "moonshade-clear"}
                  disabled={busy !== null && busy !== "moonshade-clear"}
                  onClick={() => setConfirmClear(true)}
                >
                  Clear augments
                </Button>
              ) : null}
            </div>
          )}

          <div className="moonshade-picks">
            {[firstSet, secondSet].map((group, index) =>
              group ? (
                <div className="moonshade-set" key={group.key}>
                  <label htmlFor={`moonshade-${group.key}`}>{group.label}</label>
                  <Select
                    id={`moonshade-${group.key}`}
                    value={index === 0 ? first : second}
                    onChange={(event) =>
                      index === 0 ? setFirst(event.target.value) : setSecond(event.target.value)
                    }
                  >
                    <option value="">Choose an augment…</option>
                    {group.options.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.text}
                      </option>
                    ))}
                  </Select>
                </div>
              ) : null,
            )}
          </div>

          <div className="data-actions cape-actions">
            <div className="moonshade-preview">
              {chosen ? (
                <>
                  <Badge tone="accent">{firstOption?.text}</Badge>
                  <Badge tone="accent">{secondOption?.text}</Badge>
                </>
              ) : (
                <span className="data-note">Choose one augment from each set.</span>
              )}
            </div>
            <Button
              icon={<Check size={15} />}
              loading={busy === "moonshade"}
              disabled={!chosen || (busy !== null && busy !== "moonshade")}
              onClick={applyAugments}
            >
              Apply augments
            </Button>
          </div>
        </>
      )}

      {confirmClear && (
        <ConfirmDialog
          title={`Clear ${card.name}?`}
          body="This empties the earring's augment block. You can pick both rows again afterwards."
          confirmLabel="Clear augments"
          danger
          onCancel={() => setConfirmClear(false)}
          onConfirm={clearAugments}
        />
      )}
    </Card>
  );
}
