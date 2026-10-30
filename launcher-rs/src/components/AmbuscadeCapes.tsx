import { useEffect, useRef, useState } from "react";
import { Check, Plus, RotateCcw, Sparkles, Wind } from "lucide-react";
import type {
  AmbuscadeCape,
  CapeAugmentMaterial,
  CapeAugmentOption,
  CapeAugmentSelection,
  CapeCopy,
  CharacterData,
} from "../types";
import { jobName } from "../lib/format";
import { Badge, Button, Card, ConfirmDialog, Select } from "./ui";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

type Draft = Record<string, CapeAugmentSelection | null>;

function amountLabel(option: CapeAugmentOption, stage: number): string {
  const amount = option.step * stage;
  const sign = option.multiplier < 0 ? "-" : "+";
  return `${option.label} ${sign}${amount}${option.percent ? "%" : ""}`;
}

function maxLabel(option: CapeAugmentOption): string {
  const sign = option.multiplier < 0 ? "-" : "+";
  return `${sign}${option.max_value}${option.percent ? "%" : ""}`;
}

function copyKeyOf(copy: CapeCopy): string {
  return `${copy.container}:${copy.slot}`;
}

function findOption(
  material: CapeAugmentMaterial,
  selection: CapeAugmentSelection | null | undefined,
): CapeAugmentOption | null {
  if (!selection) return null;
  return material.options.find((option) => option.key === selection.option) ?? null;
}

/** The Data page's Ambuscade cape editor.
 *
 * One card covers all 22 job capes. The five panels are the BG Wiki Abdhaljs
 * materials in the client's block order (Thread, Dust, Dye, Sap, Resin); each
 * panel offers that material's rows and cap, and "Finish augment" writes the
 * resulting five-slot block to the selected copy.  A slot the picker cannot
 * name (pet builds in particular) is left untouched unless the user explicitly
 * replaces or clears it.
 */
export function AmbuscadeCapes({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const catalog = data.capes;
  const capes = catalog?.capes ?? [];
  const materials = catalog?.materials ?? [];
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

  const selected: AmbuscadeCape | null =
    capes.find((cape) => cape.job_number === jobNumber) ?? capes[0] ?? null;
  const copy: CapeCopy | null = selected
    ? selected.copies.find((candidate) => copyKeyOf(candidate) === copyKey) ??
      selected.copies[0] ??
      null
    : null;

  // Reset the draft when the copy (or its stored block) changes.  The server
  // returns the freshly written block, so a successful apply re-seeds this with
  // the same values the user just chose.
  const sourceKey = copy
    ? `${selected?.item_id ?? 0}:${copy.container}:${copy.slot}:${copy.current.text}`
    : "";
  useEffect(() => {
    if (draftSource.current === sourceKey) return;
    draftSource.current = sourceKey;
    const next: Draft = {};
    if (copy) {
      for (const material of materials) {
        const found = copy.selection[material.key];
        if (found) next[material.key] = { option: found.option, stage: found.stage };
      }
    }
    setDraft(next);
  }, [sourceKey, copy, materials]);

  if (!catalog) return null;

  const draftSize = Object.keys(draft).length;
  const canFinish = Boolean(copy) && draftSize > 0 && busy === null;
  const canMax = Boolean(copy) && Object.values(draft).some(Boolean) && busy === null;
  const hasAugments = Boolean(copy) && copy!.current.text !== "not augmented";

  function changeCape(next: number) {
    setJobNumber(next);
    setCopyKey(null);
  }

  function chooseOption(material: CapeAugmentMaterial, optionKey: string) {
    setDraft((current) => {
      const next = { ...current };
      if (!optionKey) {
        // An explicit null clears this material's slot; an absent key would
        // keep whatever the copy already carries.
        next[material.key] = null;
        return next;
      }
      const option = material.options.find((candidate) => candidate.key === optionKey);
      if (option) next[material.key] = { option: option.key, stage: option.max_stage };
      return next;
    });
  }

  function chooseStage(material: CapeAugmentMaterial, stage: number) {
    setDraft((current) => {
      const selection = current[material.key];
      if (!selection) return current;
      return { ...current, [material.key]: { ...selection, stage } };
    });
  }

  function maxSelected() {
    setDraft((current) => {
      const next = { ...current };
      for (const material of materials) {
        const selection = current[material.key];
        const option = findOption(material, selection);
        if (option) next[material.key] = { option: option.key, stage: option.max_stage };
      }
      return next;
    });
  }

  function addCape() {
    if (!selected || busy !== null) return;
    setCopyKey(null);
    run(
      "progress",
      { op: "cape-add", item_id: selected.item_id },
      `${selected.name} added to the inventory`,
      "cape-add",
    );
  }

  function finish() {
    if (!copy || !selected || busy !== null) return;
    const choices: Record<string, { option: string; stage: number } | null> = {};
    for (const material of materials) {
      const selection = draft[material.key];
      if (selection) choices[material.key] = { option: selection.option, stage: selection.stage };
      else if (selection === null) choices[material.key] = null;
    }
    if (!Object.keys(choices).length) return;
    run(
      "progress",
      { op: "cape-augment", container: copy.container, slot: copy.slot, choices },
      `${selected.name} augments saved`,
      "cape-augment",
    );
  }

  function clearAll() {
    if (!copy || !selected || busy !== null) return;
    setConfirmClear(false);
    run(
      "progress",
      { op: "cape-clear", container: copy.container, slot: copy.slot },
      `${selected.name} augments cleared`,
      "cape-clear",
    );
  }

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <Wind size={17} />
        </div>
        <div className="data-card-title">
          <h3>Ambuscade capes</h3>
          <p>
            All 22 job capes · five augment slots · Abdhaljs Thread, Dust, Dye,
            Sap and Resin
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
            <Badge>No catalog</Badge>
          )}
        </div>
      </div>

      <p className="data-note">{catalog.note}</p>
      <p className="data-note cape-source">
        Rules: BG Wiki · JSE Capes. Each material caps at 20/20/10/10/5 items
        (Thread/Dust/Dye/Sap/Resin); each trade raises the chosen augment one
        stage.
      </p>

      <div className="cape-picker">
        <Select
          value={selected ? selected.job_number : jobNumber}
          onChange={(event) => changeCape(Number(event.target.value))}
          aria-label="Ambuscade cape"
        >
          {capes.map((cape) => (
            <option key={cape.job_number} value={cape.job_number}>
              {cape.job} · {cape.name}
              {cape.owned ? ` · ${cape.owned} in bags` : ""}
              {!cape.owned && cape.locker ? ` · ${cape.locker} in locker` : ""}
            </option>
          ))}
        </Select>
        {selected && selected.copies.length > 1 && (
          <Select
            value={copy ? copyKeyOf(copy) : ""}
            onChange={(event) => setCopyKey(event.target.value)}
            aria-label="Cape copy"
          >
            {selected.copies.map((candidate) => (
              <option key={copyKeyOf(candidate)} value={copyKeyOf(candidate)}>
                {candidate.container_name} #{candidate.slot}
                {candidate.current.build
                  ? ` · ${candidate.current.build}`
                  : candidate.current.text === "not augmented"
                    ? " · clean"
                    : " · custom"}
              </option>
            ))}
          </Select>
        )}
        {selected && (
          <Button
            variant="secondary"
            icon={<Plus size={15} />}
            loading={busy === "cape-add"}
            disabled={busy !== null && busy !== "cape-add"}
            onClick={addCape}
          >
            {selected.owned ? "Add another copy" : "Get this cape"}
          </Button>
        )}
      </div>

      {selected && (
        <p className="data-note cape-selected">
          {jobName(selected.job_number)} · {selected.name} · item #{selected.item_id}
          {selected.locker
            ? ` · ${selected.locker} preset build${selected.locker === 1 ? "" : "s"} in the locker`
            : ""}
        </p>
      )}

      {copy ? (
        <>
          <div className="cape-current">
            <div>
              <span>
                Current · {copy.container_name} #{copy.slot}
                {copy.current.build ? ` · ${copy.current.build} build` : ""}
              </span>
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
                icon={<RotateCcw size={14} />}
                loading={busy === "cape-clear"}
                disabled={busy !== null && busy !== "cape-clear"}
                onClick={() => setConfirmClear(true)}
              >
                Clear augments
              </Button>
            ) : null}
          </div>

          <div className="cape-materials">
            {materials.map((material) => {
              const selection = draft[material.key];
              const option = findOption(material, selection);
              const touched = Object.prototype.hasOwnProperty.call(draft, material.key);
              const slot = copy.current.slots[material.slot] ?? null;
              const custom = !touched && !copy.selection[material.key] && Boolean(slot?.id);
              return (
                <div
                  className={selection ? "cape-material is-set" : "cape-material"}
                  key={material.key}
                >
                  <div className="cape-material-head">
                    <strong>{material.label}</strong>
                    <span>{material.items_to_max} to cap</span>
                  </div>
                  <p className="cape-material-hint">{material.hint}</p>
                  <Select
                    value={selection?.option ?? ""}
                    onChange={(event) => chooseOption(material, event.target.value)}
                    aria-label={material.label}
                  >
                    <option value="">— none —</option>
                    {material.options.map((candidate) => (
                      <option key={candidate.key} value={candidate.key}>
                        {candidate.label} (max {maxLabel(candidate)})
                      </option>
                    ))}
                  </Select>
                  {option && selection ? (
                    <>
                      <Select
                        value={selection.stage}
                        onChange={(event) =>
                          chooseStage(material, Number(event.target.value))
                        }
                        aria-label={`${material.label} stage`}
                      >
                        {Array.from({ length: option.max_stage }, (_, index) => index + 1).map(
                          (stage) => (
                            <option key={stage} value={stage}>
                              Stage {stage}/{option.max_stage} · {amountLabel(option, stage)}
                            </option>
                          ),
                        )}
                      </Select>
                      <p className="cape-material-value">{amountLabel(option, selection.stage)}</p>
                    </>
                  ) : selection === null ? (
                    <p className="cape-material-empty is-cleared">Cleared on finish</p>
                  ) : custom ? (
                    <p className="cape-material-custom">
                      Keeping custom slot: <span>{slot?.text}</span>
                    </p>
                  ) : (
                    <p className="cape-material-empty">Empty slot</p>
                  )}
                </div>
              );
            })}
          </div>

          <div className="data-actions cape-actions">
            <Button
              variant="secondary"
              icon={<Sparkles size={15} />}
              disabled={!canMax}
              onClick={maxSelected}
            >
              Max selected
            </Button>
            <Button
              icon={<Check size={15} />}
              loading={busy === "cape-augment"}
              disabled={!canFinish}
              onClick={finish}
            >
              Finish augment
            </Button>
            <span className="cape-actions-note">
              {draftSize === 0
                ? "Choose an augment in the panels above to enable Finish."
                : "Untouched slots keep their current word."}
            </span>
          </div>
        </>
      ) : (
        <p className="data-note">
          No copy in the bags. <strong>Get this cape</strong> adds a fresh,
          unaugmented copy to the inventory; the preset builds stay in the hidden
          locker. A live client reloads with the new item.
        </p>
      )}

      {confirmClear && (
        <ConfirmDialog
          title="Clear this cape's augments?"
          body={`This writes an empty augment block to ${selected?.name ?? "the cape"}. All five slots are removed and can be rebuilt afterwards.`}
          confirmLabel="Clear augments"
          danger
          onConfirm={clearAll}
          onCancel={() => setConfirmClear(false)}
        />
      )}
    </Card>
  );
}
