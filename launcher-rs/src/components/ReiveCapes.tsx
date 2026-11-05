import { useEffect, useRef, useState } from "react";
import { Check, Eraser, Wind } from "lucide-react";
import type { CharacterData, ReiveCape, ReiveCopy, ReiveRow } from "../types";
import { jobName } from "../lib/format";
import { Badge, Button, Card, ConfirmDialog, Select } from "./ui";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

type Draft = Record<string, number | null>;

function copyKeyOf(copy: ReiveCopy): string {
  return `${copy.container}:${copy.slot}`;
}

/** The Data page's Reive and Incursion cape editor.
 *
 * Detrovio at the Inventors' Coalition takes a Refractive Crystal and Bayld for
 * one roll on a level-99 job cape.  Each cape has four BG Wiki rows, and one
 * trade can fill any subset of them at independent potencies.  The card lets
 * the player choose what to write, including leaving a row empty.
 *
 * The block is the client's standard five-slot block with the four rows in
 * slots 0-3 and slot 4 empty, so a live client prints the tooltip and the stat
 * sheet reads the same words.
 */
export function ReiveCapes({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const catalog = data.reive;
  const capes = catalog?.capes ?? [];
  const defaultJob = data.character.main_job || 1;

  const [jobNumber, setJobNumber] = useState(defaultJob);
  const [copyKey, setCopyKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  const [confirmClear, setConfirmClear] = useState(false);
  const draftSource = useRef("");

  useEffect(() => {
    if (!capes.length) return;
    if (!capes.some((cape) => cape.job_number === jobNumber)) {
      setJobNumber(capes[0].job_number);
    }
  }, [capes, jobNumber]);

  const selected: ReiveCape | null =
    capes.find((cape) => cape.job_number === jobNumber) ?? capes[0] ?? null;
  const copies = selected?.copies ?? [];
  const copy: ReiveCopy | null =
    copies.find((candidate) => copyKeyOf(candidate) === copyKey) ?? copies[0] ?? null;

  // Re-seed the four row pickers whenever the cape or its stored block changes.
  // A recognised row keeps its current value; an empty row on an already
  // augmented cape starts as "none"; a clean cape starts at every row's top.
  const sourceKey = copy && selected
    ? `${selected.item_id}:${copy.container}:${copy.slot}:${copy.current.text}`
    : "";
  useEffect(() => {
    if (draftSource.current === sourceKey) return;
    draftSource.current = sourceKey;
    if (!selected) return;
    const augmented = Boolean(copy && copy.current.text !== "not augmented");
    const current = copy?.current.selection ?? {};
    const next: Draft = {};
    for (const row of selected.rows) {
      const found = current[row.key];
      next[row.key] = typeof found === "number"
        ? found
        : augmented
          ? null
          : row.best;
    }
    setDraft(next);
  }, [sourceKey, selected, copy]);

  if (!catalog) return null;

  const hasAugments = Boolean(copy && copy.current.text !== "not augmented");
  const chosenRows = selected
    ? selected.rows.filter((row) => typeof draft[row.key] === "number")
    : [];
  const canApply = Boolean(copy && selected && chosenRows.length) && busy === null;

  function changeCape(next: number) {
    setJobNumber(next);
    setCopyKey(null);
    setConfirmClear(false);
    setDraft({});
  }

  function setRow(row: ReiveRow, next: string) {
    setDraft((current) => ({
      ...current,
      [row.key]: next === "" ? null : Number(next),
    }));
  }

  function maxAll() {
    if (!selected) return;
    const next: Draft = {};
    for (const row of selected.rows) next[row.key] = row.best;
    setDraft(next);
  }

  function apply() {
    if (!copy || !selected || !chosenRows.length || busy !== null) return;
    const choices: Draft = {};
    for (const row of selected.rows) choices[row.key] = draft[row.key] ?? null;
    run(
      "progress",
      {
        op: "reive-augment",
        container: copy.container,
        slot: copy.slot,
        choices,
      },
      `${selected.name} augments saved`,
      "reive-augment",
    );
  }

  function clear() {
    if (!copy || !selected || busy !== null) return;
    setConfirmClear(false);
    run(
      "progress",
      { op: "reive-clear", container: copy.container, slot: copy.slot },
      `${selected.name} augments cleared`,
      "reive-clear",
    );
  }

  const owned = capes.filter((cape) => cape.owned > 0).length;

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <Wind size={17} />
        </div>
        <div className="data-card-title">
          <h3>Reive &amp; Incursion capes</h3>
          <p>
            Detrovio · Western Adoulin (J-10) · Refractive Crystal · four rows
            per cape
          </p>
        </div>
        <div className="data-card-badge">
          {selected ? (
            <Badge tone={copy ? "success" : "warning"}>
              {copy
                ? selected.owned > 1
                  ? `${selected.owned} copies`
                  : "In bags"
                : "No copy"}
            </Badge>
          ) : (
            <Badge>{owned} in bags</Badge>
          )}
        </div>
      </div>

      <p className="data-note">{catalog.note}</p>
      <p className="data-note cape-source">
        Rules: BG Wiki · JSE Capes. Each trade can roll any of the four rows, so
        a cape may show several augments at once. Set a row to{" "}
        <strong>— none —</strong> to leave it empty; Clear removes all four the
        same way Makel-Pakel does.
      </p>

      <div className="cape-picker">
        <Select
          value={selected ? selected.job_number : jobNumber}
          onChange={(event) => changeCape(Number(event.target.value))}
          aria-label="Reive or Incursion cape"
        >
          {capes.map((cape) => (
            <option key={cape.job_number} value={cape.job_number}>
              {cape.job} · {cape.name}
              {cape.owned ? ` · ${cape.owned} in bags` : ""}
            </option>
          ))}
        </Select>
        {copies.length > 1 && (
          <Select
            value={copy ? copyKeyOf(copy) : ""}
            onChange={(event) => setCopyKey(event.target.value)}
            aria-label="Cape copy"
          >
            {copies.map((candidate) => (
              <option key={copyKeyOf(candidate)} value={copyKeyOf(candidate)}>
                {candidate.container_name} #{candidate.slot}
                {candidate.current.text !== "not augmented"
                  ? ` · ${candidate.current.text}`
                  : " · clean"}
              </option>
            ))}
          </Select>
        )}
      </div>

      {selected && (
        <p className="data-note cape-selected">
          {jobName(selected.job_number)} · {selected.name} · item #{selected.item_id}
          {copy ? ` · ${copy.container_name} #${copy.slot}` : ""}
        </p>
      )}

      {copy && selected ? (
        <>
          <div className="cape-current">
            <div>
              <span>Current</span>
              <strong>
                {copy.current.text === "not augmented"
                  ? "Not augmented"
                  : copy.current.text}
              </strong>
            </div>
            {hasAugments ? (
              <Button
                size="sm"
                variant="ghost"
                icon={<Eraser size={14} />}
                loading={busy === "reive-clear"}
                disabled={busy !== null && busy !== "reive-clear"}
                onClick={() => setConfirmClear(true)}
              >
                Clear augments
              </Button>
            ) : null}
          </div>

          <div className="reive-rows">
            {selected.rows.map((row) => {
              const value = draft[row.key] ?? null;
              const shown = row.values.find((candidate) => candidate.value === value);
              return (
                <div
                  className={value === null ? "cape-material" : "cape-material is-set"}
                  key={row.key}
                >
                  <div className="cape-material-head">
                    <strong>{row.label}</strong>
                    <span>
                      {row.minimum}..{row.maximum}
                      {row.step > 1 ? ` · step ${row.step}` : ""}
                    </span>
                  </div>
                  <p className="cape-material-hint">
                    Slot {row.slot + 1} · max {row.best_text}
                  </p>
                  <Select
                    value={value === null ? "" : value}
                    onChange={(event) => setRow(row, event.target.value)}
                    aria-label={row.label}
                  >
                    <option value="">— none —</option>
                    {row.values.map((candidate) => (
                      <option key={candidate.value} value={candidate.value}>
                        {candidate.text}
                        {candidate.value === row.best ? " (max)" : ""}
                      </option>
                    ))}
                  </Select>
                  <p className="cape-material-value">
                    {shown ? shown.text : "Empty slot"}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="data-actions cape-actions">
            <Button variant="secondary" onClick={maxAll} disabled={busy !== null}>
              Max all
            </Button>
            <Button
              icon={<Check size={15} />}
              loading={busy === "reive-augment"}
              disabled={!canApply}
              onClick={apply}
            >
              Apply augments
            </Button>
            <span className="cape-actions-note">
              {chosenRows.length
                ? `${chosenRows.length} of ${selected.rows.length} rows set.`
                : "Choose at least one row to enable Apply."}
            </span>
          </div>
        </>
      ) : (
        <p className="data-note">
          No copy in the bags. Reive capes drop from Colonization Reives, Lair
          Reives, Wildskeeper Reives and Incursion coffers in Marjami Ravine,
          Yorcia Weald, Kamihr Drifts and Ra&apos;Kaznar; Makel-Pakel at the
          Celennia Memorial Library also trades three capes for one.
        </p>
      )}

      {confirmClear && (
        <ConfirmDialog
          title="Clear this cape's augments?"
          body={`This writes an empty augment block to ${selected?.name ?? "the cape"}. Every Detrovio row is removed, the same state Makel-Pakel returns.`}
          confirmLabel="Clear augments"
          danger
          onConfirm={clear}
          onCancel={() => setConfirmClear(false)}
        />
      )}
    </Card>
  );
}
