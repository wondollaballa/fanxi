import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Eraser, Sparkles, Swords } from "lucide-react";
import type {
  CharacterData,
  SkirmishCopy,
  SkirmishItem,
  SkirmishOption,
  SkirmishSlot,
} from "../types";
import { Badge, Button, Card, ConfirmDialog, Select, TextInput } from "./ui";
import { slotLabel } from "../lib/format";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

type DraftPick = { key: string; value: number } | null;

function copyKeyOf(copy: SkirmishCopy): string {
  return `${copy.container}:${copy.slot}`;
}

const SECTIONS = [
  { value: "", label: "All Skirmish" },
  { value: "alluvion-weapon", label: "Alluvion weapons" },
  { value: "alluvion-armor", label: "Alluvion armor" },
  { value: "skirmish-weapon", label: "Skirmish weapons" },
  { value: "skirmish-armor", label: "Skirmish armor" },
];

function sectionOf(item: SkirmishItem): string {
  return `${item.family}-${item.kind}`;
}

function optionOf(slot: SkirmishSlot | undefined, key: string | null): SkirmishOption | null {
  if (!slot || !key) return null;
  return slot.options.find((option) => option.key === key) ?? null;
}

function clampOption(option: SkirmishOption, raw: number): number {
  const step = Math.max(1, option.step);
  const rounded = Math.round(raw / step) * step;
  const value = Math.min(option.maximum, Math.max(option.minimum, rounded));
  return value;
}

/** The Data page's Divainy-Gamainy card.
 *
 * Divainy-Gamainy, at Western Adoulin (J-10), augments every Skirmish item.
 * Alluvion weapons and armor take a Snow, Leaf and Dusk stone; the older
 * Skirmish weapons roll DMG plus one pick from each of two pools, and Skirmish
 * armor rolls Physical Damage Taken plus one (NQ) or two (+1) picks.  The card
 * writes one chosen row per slot, at its maximum by default, into the same
 * standard five-slot augment block the capes and Oseem use.
 */
export function SkirmishAugments({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const catalog = data.skirmish;
  const items = catalog?.items ?? [];
  const [itemId, setItemId] = useState(0);
  const [section, setSection] = useState("");
  const [copyKey, setCopyKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftPick[]>([]);
  const [confirmClear, setConfirmClear] = useState(false);
  const draftSource = useRef("");

  const visible = useMemo(
    () => items.filter((item) => !section || sectionOf(item) === section),
    [items, section],
  );

  useEffect(() => {
    if (!visible.length) return;
    if (!visible.some((item) => item.item_id === itemId)) {
      const first = visible.find((item) => item.copies.length > 0) ?? visible[0];
      setItemId(first.item_id);
      setCopyKey(null);
    }
  }, [visible, itemId]);

  const selected: SkirmishItem | null =
    visible.find((item) => item.item_id === itemId) ?? visible[0] ?? null;
  const slots = useMemo(
    () => (selected ? catalog?.slot_sets[selected.slot_set] ?? [] : []),
    [catalog, selected],
  );
  const copies = selected?.copies ?? [];
  const copy =
    copies.find((candidate) => copyKeyOf(candidate) === copyKey) ?? copies[0] ?? null;

  const ownedCount = items.filter((item) => item.copies.length > 0).length;
  const groups = useMemo(() => {
    const out: { group: string; items: SkirmishItem[] }[] = [];
    for (const item of visible) {
      const last = out[out.length - 1];
      if (last && last.group === item.group) last.items.push(item);
      else out.push({ group: item.group, items: [item] });
    }
    return out;
  }, [visible]);

  // Re-seed the rows when the piece or copy changes: an already augmented copy
  // seeds with its current rows (where the slot still offers that stat), a
  // clean one starts from each row's first sensible stat at its maximum.
  const sourceKey = selected
    ? `${selected.item_id}:${copy?.container ?? "x"}:${copy?.slot ?? "x"}`
    : "";
  useEffect(() => {
    if (!selected || draftSource.current === sourceKey) return;
    draftSource.current = sourceKey;
    const current = copy?.selection ?? [];
    const hasCurrent = current.some(Boolean);
    const next: DraftPick[] = slots.map((slot, index) => {
      const found = current[index] ?? null;
      if (found) {
        const option = slot.options.find((candidate) => candidate.key === found.key);
        if (option) {
          return { key: option.key, value: clampOption(option, found.value) };
        }
      }
      if (!slot.options.length) return null;
      // A clean copy starts from every suggested row; an already augmented one
      // only keeps the rows it actually carries (so Apply cannot add a stone
      // the player never used).
      if (!slot.required && !(slot.default_on && !hasCurrent)) return null;
      return { key: slot.options[0].key, value: slot.options[0].default };
    });
    setDraft(next);
  }, [sourceKey, selected, copy, slots]);

  if (!catalog) return null;

  const hasAugments = Boolean(copy && copy.current !== "not augmented");
  const requiredFilled = slots.every((slot, index) => !slot.required || Boolean(draft[index]));
  const hasPicks = draft.some(Boolean);
  const canApply =
    Boolean(copy) && slots.length > 0 && requiredFilled && hasPicks && busy === null;

  function chooseItem(next: number) {
    setItemId(next);
    setCopyKey(null);
  }

  function chooseOption(slot: number, key: string) {
    setDraft((current) => {
      const next = [...current];
      if (!key) {
        next[slot] = null;
        return next;
      }
      const option = optionOf(slots[slot], key);
      next[slot] = option ? { key, value: option.default } : null;
      return next;
    });
  }

  function changeValue(slot: number, raw: number) {
    setDraft((current) => {
      const pick = current[slot];
      if (!pick) return current;
      const option = optionOf(slots[slot], pick.key);
      if (!option) return current;
      const next = [...current];
      next[slot] = { key: pick.key, value: clampOption(option, raw) };
      return next;
    });
  }

  function maxAll() {
    setDraft((current) =>
      current.map((pick, index) => {
        if (!pick) return null;
        const option = optionOf(slots[index], pick.key);
        return option ? { key: pick.key, value: option.default } : pick;
      }),
    );
  }

  function apply() {
    if (!copy || busy !== null) return;
    const picks = draft.map((pick) => (pick ? { ...pick } : null));
    run(
      "progress",
      {
        op: "skirmish",
        container: copy.container,
        slot: copy.slot,
        picks,
      },
      `${selected?.name ?? "Item"} augments saved`,
      "skirmish-apply",
    );
  }

  function clear() {
    if (!copy || busy !== null) return;
    setConfirmClear(false);
    run(
      "progress",
      { op: "skirmish-clear", container: copy.container, slot: copy.slot },
      `${selected?.name ?? "Item"} augments cleared`,
      "skirmish-clear",
    );
  }

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <Swords size={17} />
        </div>
        <div className="data-card-title">
          <h3>Divainy-Gamainy · Skirmish</h3>
          <p>
            Western Adoulin (J-10) · Alluvion Skirmish weapons and armor · Cirdas
            Caverns, Rala Waterways and Yorcia Weald/Outer Ra&apos;Kaznar Skirmish
            sets
          </p>
        </div>
        <div className="data-card-badge">
          <Badge tone={ownedCount ? "success" : "neutral"}>{ownedCount} in bags</Badge>
        </div>
      </div>

      <p className="data-note">{catalog.note}</p>
      <p className="data-note">
        Retail rolls these rows at random and the player keeps or rerolls the piece.
        Here every row starts at its highest value: pick another stat, lower a
        number, or leave a stone/bonus row empty. Applying writes the standard
        augment block, so the client tooltip and the stat sheet both update.
      </p>

      {items.length === 0 ? (
        <p className="data-note">
          No Skirmish catalogue is loaded. The card ships with{" "}
          {catalog.catalog_size} items; restart the server and refresh.
        </p>
      ) : (
        <>
          <div className="cape-picker">
            <Select
              value={section}
              onChange={(event) => {
                setSection(event.target.value);
                setCopyKey(null);
              }}
              aria-label="Skirmish family"
            >
              {SECTIONS.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.label}
                </option>
              ))}
            </Select>
            <Select
              value={selected?.item_id ?? ""}
              onChange={(event) => chooseItem(Number(event.target.value))}
              aria-label="Skirmish item"
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
              {selected.kind === "weapon" ? "Weapon" : "Armor"} · {slotLabel(selected.slot)}
              {selected.quality ? ` · ${selected.quality}` : ""} · item #
              {selected.item_id}
              {selected.ranged ? " · ranged" : ""}
              {selected.dmg_max ? ` · DMG cap +${selected.dmg_max}` : ""}
              {copy ? ` · ${copy.container_name} #${copy.slot}` : ""}
            </p>
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
                  loading={busy === "skirmish-clear"}
                  disabled={busy !== null && busy !== "skirmish-clear"}
                  onClick={() => setConfirmClear(true)}
                >
                  Clear augments
                </Button>
              ) : null}
            </div>
          ) : (
            <p className="data-note">
              Preview only — this piece is not in the bags. Buy it in the{" "}
              <strong>Armory</strong> below and it can be augmented here.
            </p>
          )}

          <div className="skirmish-slots">
            {slots.map((slot, index) => {
              const pick = draft[index] ?? null;
              const option = optionOf(slot, pick?.key ?? null);
              return (
                <div className={pick ? "glyptic-slot is-set" : "glyptic-slot"} key={slot.key}>
                  <strong>{slot.label}</strong>
                  {slot.options.length === 1 ? (
                    <span className="skirmish-fixed">{slot.options[0].label}</span>
                  ) : (
                    <Select
                      value={pick?.key ?? ""}
                      onChange={(event) => chooseOption(index, event.target.value)}
                      aria-label={`${slot.label} augment`}
                    >
                      {!slot.required && <option value="">— empty —</option>}
                      {slot.options.map((candidate) => (
                        <option key={candidate.key} value={candidate.key}>
                          {candidate.label} · {candidate.default > 0 ? "+" : ""}
                          {candidate.default}
                          {candidate.percent ? "%" : ""}
                        </option>
                      ))}
                    </Select>
                  )}
                  <TextInput
                    type="number"
                    value={pick?.value ?? ""}
                    disabled={!pick}
                    min={option?.minimum}
                    max={option?.maximum}
                    step={option?.step ?? 1}
                    onChange={(event) => changeValue(index, Number(event.target.value))}
                    aria-label={`${slot.label} value`}
                  />
                  <span className="glyptic-slot-hint">
                    {option
                      ? `${option.text} · ${option.minimum}…${option.maximum}${
                          option.percent ? "%" : ""
                        }${option.step > 1 ? ` · step ${option.step}` : ""}`
                      : slot.required
                        ? "pick a stat"
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
              disabled={!draft.some(Boolean) || busy !== null}
              onClick={maxAll}
            >
              Max all
            </Button>
            <Button
              icon={<Check size={15} />}
              loading={busy === "skirmish-apply"}
              disabled={!canApply}
              onClick={apply}
            >
              Apply augments
            </Button>
            <span className="cape-actions-note">
              {!copy
                ? "Nothing to apply until the piece is in the bags."
                : !slots.length
                  ? "This item has no augment table."
                  : !requiredFilled
                    ? "Every required row needs a stat."
                    : !hasPicks
                      ? "Pick at least one stone or bonus row to enable Apply."
                      : "Rows left empty are written as empty."}
            </span>
          </div>
        </>
      )}

      {confirmClear && (
        <ConfirmDialog
          title="Clear this piece's augments?"
          body={`This writes an empty augment block to ${selected?.name ?? "the item"}. Every row is removed and can be rebuilt afterwards.`}
          confirmLabel="Clear augments"
          danger
          onConfirm={clear}
          onCancel={() => setConfirmClear(false)}
        />
      )}
    </Card>
  );
}
