import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import {
  Flag,
  ListChecks,
  Search,
  ShoppingCart,
  Swords,
  Users,
  Wand2,
} from "lucide-react";
import type { CharacterData, OboroCopy } from "../types";
import { formatNumber, JOB_ABBRS, jobName, NATIONS, pct } from "../lib/format";
import { Badge, Button, Card, ProgressBar, Select, TextInput } from "./ui";

type GearRow = CharacterData["augments"][number];

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

const CONTAINERS: Record<number, string> = {
  0: "Inventory",
  1: "Temporary",
  2: "Storage",
  5: "Safe",
  6: "Satchel",
  7: "Sack",
  8: "Wardrobe 1",
  10: "Wardrobe 2",
  11: "Wardrobe 3",
  12: "Wardrobe 4",
  13: "Wardrobe 5",
  14: "Wardrobe 6",
  15: "Wardrobe 7",
  16: "Wardrobe 8",
};

function whereLabel(container: number): string {
  return CONTAINERS[container] ?? `Bag ${container}`;
}

/** "capped · Rank 30" or "Rank 7" for the copy's current augment block. */
function currentRankLabel(item: GearRow): string {
  if (!item.current) return "";
  const maxRank = Math.max(...item.paths.map((path) => path.rank));
  return item.current.rank >= maxRank
    ? `capped · Rank ${item.current.rank}`
    : `Rank ${item.current.rank}`;
}

function rankFor(data: CharacterData, nation: number): number {
  if (nation === 1) return data.ranks.bastok;
  if (nation === 2) return data.ranks.windurst;
  return data.ranks.sandoria;
}

function Head({ icon, title, hint, badge }: {
  icon: ReactNode;
  title: string;
  hint: string;
  badge?: ReactNode;
}) {
  return (
    <div className="data-card-head">
      <div className="data-card-icon">{icon}</div>
      <div className="data-card-title">
        <h3>{title}</h3>
        <p>{hint}</p>
      </div>
      {badge && <div className="data-card-badge">{badge}</div>}
    </div>
  );
}

export function ProgressCards({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const [nation, setNation] = useState(data.ranks.nation);
  const [rank, setRank] = useState(rankFor(data, data.ranks.nation));
  const [rankPoints, setRankPoints] = useState(String(data.ranks.points));
  const [mogRank, setMogRank] = useState(String(data.ranks.mog_garden_rank));
  const [exemplar, setExemplar] = useState(String(data.exemplar.points));
  const [jobChoice, setJobChoice] = useState(1);
  const [jobMaster, setJobMaster] = useState(50);
  const [crafts, setCrafts] = useState<Record<number, number>>(() =>
    Object.fromEntries(data.crafts.map((craft) => [craft.skill_id, craft.value])),
  );
  const [augmentKey, setAugmentKey] = useState<string | null>(() => {
    const first = data.augments.find((item) => item.kind !== "oboro");
    return first ? `${first.container}:${first.slot}` : null;
  });
  const [gearQuery, setGearQuery] = useState("");
  const [gearOpen, setGearOpen] = useState(false);
  const [gearActive, setGearActive] = useState(0);
  const gearPickerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setCrafts(Object.fromEntries(data.crafts.map((craft) => [craft.skill_id, craft.value])));
    setAugmentKey((current) => {
      const gear = data.augments.filter((item) => item.kind !== "oboro");
      if (current && gear.some((item) => `${item.container}:${item.slot}` === current)) {
        return current;
      }
      return gear[0] ? `${gear[0].container}:${gear[0].slot}` : null;
    });
  }, [data]);

  const gear = data.augments.filter((item) => item.kind !== "oboro");
  const selectedAugment =
    gear.find((item) => `${item.container}:${item.slot}` === augmentKey) ??
    gear[0] ??
    null;
  /** The top rank any of the item's paths reaches; a current block at it is capped. */
  const selectedMaxRank = selectedAugment
    ? Math.max(...selectedAugment.paths.map((path) => path.rank))
    : 0;
  const selectedCapped = Boolean(
    selectedAugment?.current && selectedAugment.current.rank >= selectedMaxRank,
  );
  const filteredGear = useMemo(() => {
    const want = gearQuery.trim().toLocaleLowerCase();
    if (!want) return gear;
    return gear.filter((item) =>
      `${item.name} ${item.set} ${item.slot_name} ${item.kind} ${whereLabel(item.container)}`
        .toLocaleLowerCase()
        .includes(want),
    );
  }, [gear, gearQuery]);

  useEffect(() => {
    setGearActive(0);
  }, [gearQuery]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (gearPickerRef.current && !gearPickerRef.current.contains(event.target as Node)) {
        setGearOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  function chooseGear(item: GearRow) {
    setAugmentKey(`${item.container}:${item.slot}`);
    setGearQuery("");
    setGearOpen(false);
  }

  function onGearKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setGearOpen(true);
      setGearActive((index) => Math.min(Math.max(0, filteredGear.length - 1), index + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setGearOpen(true);
      setGearActive((index) => Math.max(0, index - 1));
    } else if (event.key === "Enter") {
      if (gearOpen && filteredGear.length) {
        event.preventDefault();
        chooseGear(filteredGear[Math.min(gearActive, filteredGear.length - 1)]);
      }
    } else if (event.key === "Escape" || event.key === "Tab") {
      setGearOpen(false);
    }
  }

  function saveRank() {
    run(
      "progress",
      { op: "rank", nation, rank, points: Number(rankPoints) || 0 },
      `Mission rank set to ${rank}`,
      "rank",
    );
  }

  function saveMogGarden() {
    run(
      "progress",
      { op: "mog-garden", rank: Number(mogRank) || 0 },
      "Mog Garden rank saved",
      "mog-garden",
    );
  }

  function saveCrafts() {
    const values: Record<string, number> = {};
    for (const craft of data.crafts) {
      values[String(craft.skill_id)] = Number(crafts[craft.skill_id] ?? 0);
    }
    run("progress", { op: "crafts", values }, "Crafting skills saved", "crafts");
  }

  return (
    <>
      <Card>
        <Head
          icon={<Flag size={17} />}
          title="Ranks"
          hint="Mission rank, Mog Garden rank and fame"
          badge={<Badge tone="gold">Rank {rankFor(data, data.ranks.nation)}</Badge>}
        />
        <div className="data-form-row">
          <Select
            value={nation}
            onChange={(event) => {
              const next = Number(event.target.value);
              setNation(next);
              setRank(rankFor(data, next));
            }}
            aria-label="Nation"
          >
            {NATIONS.map((entry) => (
              <option key={entry.value} value={entry.value}>
                {entry.label}
              </option>
            ))}
          </Select>
          <Select
            value={rank}
            onChange={(event) => setRank(Number(event.target.value))}
            aria-label="Mission rank"
          >
            {Array.from({ length: data.ranks.rank_max }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>
                Rank {value}
              </option>
            ))}
          </Select>
          <TextInput
            type="number"
            value={rankPoints}
            onChange={(event) => setRankPoints(event.target.value)}
            min={0}
            aria-label="Rank points"
          />
          <Button
            loading={busy === "rank"}
            disabled={busy !== null && busy !== "rank"}
            onClick={saveRank}
          >
            Set
          </Button>
        </div>
        <div className="data-row">
          <span>Rank points</span>
          <strong>{formatNumber(data.ranks.points)}</strong>
        </div>
        <div className="data-form-row" style={{ marginTop: 10 }}>
          <TextInput
            type="number"
            value={mogRank}
            onChange={(event) => setMogRank(event.target.value)}
            min={0}
            max={data.ranks.mog_garden_max}
            aria-label="Mog Garden rank"
          />
          <Button
            variant="secondary"
            loading={busy === "mog-garden"}
            disabled={busy !== null && busy !== "mog-garden"}
            onClick={saveMogGarden}
          >
            Set Mog Garden
          </Button>
        </div>
        <div className="data-row">
          <span>Mog Garden rank</span>
          <strong>
            {data.ranks.mog_garden_rank}/{data.ranks.mog_garden_max}
          </strong>
        </div>
        <div className="data-fame">
          {data.fame.map((entry) => (
            <span key={entry.city}>
              {entry.city} <b>{entry.value}</b>
            </span>
          ))}
        </div>
        <p className="data-note" style={{ marginTop: 10 }}>
          Mission rank is drawn in Status → Profile. Fame and the Mog Garden rank are
          server-side values; Fanxi has no client page for them yet.
        </p>
        <div className="data-actions">
          <Button
            variant="secondary"
            loading={busy === "fame"}
            disabled={busy !== null && busy !== "fame"}
            onClick={() =>
              run("progress", { op: "fame", all: true }, "Fame maxed in every city", "fame")
            }
          >
            Max all fame
          </Button>
        </div>
      </Card>

      <Card>
        <Head
          icon={<ListChecks size={17} />}
          title="Levels"
          hint="All jobs, Master Levels and Exemplar Points"
          badge={
            <Badge tone="success">
              {data.jobs.filter((job) => job.level >= 99).length}/22 at 99
            </Badge>
          }
        />
        <div className="data-actions" style={{ marginTop: 0 }}>
          <Button
            loading={busy === "jobs"}
            disabled={busy !== null && busy !== "jobs"}
            onClick={() =>
              run(
                "progress",
                { op: "jobs", all: true, level: 99 },
                "Every job unlocked at level 99",
                "jobs",
              )
            }
          >
            All jobs 99
          </Button>
          <Button
            variant="secondary"
            loading={busy === "master-all"}
            disabled={busy !== null && busy !== "master-all"}
            onClick={() =>
              run(
                "progress",
                { op: "master-level", all: true, level: 50 },
                "Every job set to Master Level 50",
                "master-all",
              )
            }
          >
            All ML 50
          </Button>
        </div>
        <div className="data-job-grid">
          {data.jobs.map((job) => (
            <span key={job.job} className="data-job">
              <b>{JOB_ABBRS[job.job - 1] ?? job.job}</b>
              <span>{job.level}</span>
              <i>ML {job.master_level}</i>
            </span>
          ))}
        </div>
        <div className="data-form-row" style={{ marginTop: 10 }}>
          <Select
            value={jobChoice}
            onChange={(event) => setJobChoice(Number(event.target.value))}
            aria-label="Job"
          >
            {data.jobs.map((job) => (
              <option key={job.job} value={job.job}>
                {jobName(job.job)}
              </option>
            ))}
          </Select>
          <Select
            value={jobMaster}
            onChange={(event) => setJobMaster(Number(event.target.value))}
            aria-label="Master level"
          >
            {Array.from({ length: 51 }, (_, index) => index).map((value) => (
              <option key={value} value={value}>
                ML {value}
              </option>
            ))}
          </Select>
          <Button
            variant="secondary"
            loading={busy === "master-one"}
            disabled={busy !== null && busy !== "master-one"}
            onClick={() =>
              run(
                "progress",
                { op: "master-level", all: false, job: jobChoice, level: jobMaster },
                `${jobName(jobChoice)} set to ML ${jobMaster}`,
                "master-one",
              )
            }
          >
            Set ML
          </Button>
        </div>
        <div className="data-form-row" style={{ marginTop: 10 }}>
          <TextInput
            type="number"
            value={exemplar}
            onChange={(event) => setExemplar(event.target.value)}
            min={0}
            aria-label="Exemplar Points"
          />
          <Button
            variant="secondary"
            loading={busy === "exemplar"}
            disabled={busy !== null && busy !== "exemplar"}
            onClick={() =>
              run(
                "progress",
                { op: "exemplar", points: Number(exemplar) || 0 },
                "Exemplar Points updated",
                "exemplar",
              )
            }
          >
            Set points
          </Button>
        </div>
        <p className="data-note">
          {formatNumber(data.exemplar.points)} Exemplar Points · next Master Level at{" "}
          {formatNumber(data.exemplar.next)}. Master Levels use the 0x01B job array; the
          points and the current job&apos;s ML drive the status HUD.
        </p>
      </Card>

      <Card>
        <Head
          icon={<Wand2 size={17} />}
          title="Skills"
          hint="Crafting and fishing"
          badge={<Badge tone="accent">{data.crafts.length}</Badge>}
        />
        <div className="data-craft-grid">
          {data.crafts.map((craft) => (
            <label key={craft.skill_id} className="data-craft">
              <span>{craft.name}</span>
              <TextInput
                type="number"
                min={0}
                max={data.craft_max}
                value={crafts[craft.skill_id] ?? 0}
                onChange={(event) =>
                  setCrafts((current) => ({
                    ...current,
                    [craft.skill_id]: Number(event.target.value),
                  }))
                }
                aria-label={craft.name}
              />
            </label>
          ))}
        </div>
        <div className="data-actions">
          <Button
            loading={busy === "crafts"}
            disabled={busy !== null && busy !== "crafts"}
            onClick={saveCrafts}
          >
            Save skills
          </Button>
          <Button
            variant="secondary"
            loading={busy === "crafts-max"}
            disabled={busy !== null && busy !== "crafts-max"}
            onClick={() =>
              run("progress", { op: "crafts", max_all: true }, "All crafts maxed", "crafts-max")
            }
          >
            Max all
          </Button>
        </div>
      </Card>

      <Card>
        <Head
          icon={<Users size={17} />}
          title="Trusts"
          hint={`${data.trusts.spells} Trust spells`}
          badge={
            <Badge tone={data.trusts.summoning ? "success" : "warning"}>
              {data.trusts.summoning ? "Ready" : "Menu only"}
            </Badge>
          }
        />
        <p className="data-note">
          Every permanent key item (including the cipher key items) is sent at zone-in, and
          0x0AA carries all {data.trusts.spells} Trust spell ids. Re-issuing refreshes the
          menu.{" "}
          {data.trusts.summoning
            ? "Casting one calls the alter ego beside you; it follows you and attacks your current target."
            : "Trust summoning is not implemented in this build yet: casting one will not spawn the ally."}
        </p>
        <div className="data-actions">
          <Button
            variant="secondary"
            loading={busy === "trusts"}
            disabled={busy !== null && busy !== "trusts"}
            onClick={() =>
              run("progress", { op: "trusts" }, "Trusts re-issued", "trusts")
            }
          >
            Get all trusts
          </Button>
        </div>
      </Card>

      <Card className="span-2">
        <Head
          icon={<Swords size={17} />}
          title="RP"
          hint="Cap a path on Odyssey, Limbus, Temenos or Unity gear in the inventory"
          badge={<Badge tone="accent">{gear.length} pieces</Badge>}
        />
        {gear.length === 0 ? (
          <p className="data-note">
            No Odyssey, Limbus, Temenos or Unity gear in the inventory. Those pieces show
            here once they are in a bag; Oboro weapons have their own card below.
          </p>
        ) : (
          <>
            <div className="armory-search" style={{ gridTemplateColumns: "minmax(0, 1fr)" }}>
              <div className="armory-typeahead" ref={gearPickerRef}>
                <div className="input-with-icon">
                  <Search size={15} />
                  <TextInput
                    value={gearQuery}
                    onChange={(event) => {
                      setGearQuery(event.target.value);
                      setGearOpen(true);
                    }}
                    onFocus={() => setGearOpen(true)}
                    onKeyDown={onGearKeyDown}
                    placeholder={
                      selectedAugment
                        ? `${selectedAugment.name} · ${whereLabel(selectedAugment.container)}#${selectedAugment.slot}`
                        : "Search RP gear…"
                    }
                    aria-label="Search augmentable item"
                    role="combobox"
                    aria-autocomplete="list"
                    aria-expanded={gearOpen}
                    aria-controls="rp-gear-list"
                    autoComplete="off"
                  />
                </div>
                {gearOpen && (
                  <div className="armory-menu" id="rp-gear-list" role="listbox" aria-label="RP gear">
                    {filteredGear.length === 0 && (
                      <p className="armory-menu-note">No gear matches “{gearQuery.trim()}”.</p>
                    )}
                    {filteredGear.map((item, index) => (
                      <button
                        key={`${item.container}:${item.slot}`}
                        type="button"
                        role="option"
                        aria-selected={index === gearActive}
                        className={index === gearActive ? "armory-option is-active" : "armory-option"}
                        onMouseEnter={() => setGearActive(index)}
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => chooseGear(item)}
                      >
                        <span className="armory-option-text">
                          <strong>{item.name}</strong>
                          <small>
                            {item.set || item.kind} · {whereLabel(item.container)}#{item.slot}
                            {item.current ? ` · ${currentRankLabel(item)}` : ""}
                          </small>
                        </span>
                      </button>
                    ))}
                    {filteredGear.length > 0 && (
                      <p className="armory-menu-foot">↑↓ to move · Enter to select</p>
                    )}
                  </div>
                )}
              </div>
            </div>
            {selectedAugment && (
              <>
                <div className="data-row" style={{ marginTop: 10 }}>
                  <span>
                    {selectedAugment.set || selectedAugment.kind} · {selectedAugment.slot_name}
                  </span>
                  <strong>
                    {selectedAugment.current ? (
                      <>
                        <Badge tone={selectedCapped ? "success" : "accent"}>
                          {selectedCapped ? "Capped" : "Augmented"}
                        </Badge>{" "}
                        Path {selectedAugment.current.path} · Rank{" "}
                        {selectedAugment.current.rank} ·{" "}
                        {formatNumber(selectedAugment.current.rp)} RP
                      </>
                    ) : (
                      "Not augmented"
                    )}
                  </strong>
                </div>
                <div className="data-paths">
                  {selectedAugment.paths.map((path) => {
                    const key = `augment-${selectedAugment.container}-${selectedAugment.slot}-${path.key}`;
                    const current = selectedAugment.current;
                    const onPath = Boolean(current && current.path === path.key);
                    const capped = Boolean(onPath && current && current.rank >= path.rank);
                    return (
                      <div className={onPath ? "data-path is-current" : "data-path"} key={path.key}>
                        <div className="data-path-head">
                          <strong>
                            {path.label}
                            {capped
                              ? " · capped"
                              : onPath && current
                                ? ` · current (R${current.rank})`
                                : ""}
                          </strong>
                          <span>
                            Rank {path.rank} · {formatNumber(path.rp)} RP
                          </span>
                        </div>
                        <ul className="data-path-lines">
                          {path.augments.map((line, index) => (
                            <li key={index}>{line}</li>
                          ))}
                        </ul>
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={busy === key}
                          disabled={capped || (busy !== null && busy !== key)}
                          title={
                            current && !onPath
                              ? `Replaces the current Path ${current.path} · Rank ${current.rank}`
                              : undefined
                          }
                          onClick={() =>
                            run(
                              "progress",
                              {
                                op: "augment",
                                container: selectedAugment.container,
                                slot: selectedAugment.slot,
                                path: path.key,
                              },
                              `${selectedAugment.name} → ${path.label}`,
                              key,
                            )
                          }
                        >
                          {capped ? "Capped" : onPath ? "Finish path" : current ? "Change path" : "Cap path"}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </>
        )}
      </Card>

      <OboroCard data={data} run={run} busy={busy} />
    </>
  );
}

function oboroCopyKey(copy: OboroCopy): string {
  return `${copy.container}:${copy.slot}`;
}

function OboroCard({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const items = data.oboro?.items ?? [];
  const owned = items.filter((item) => item.owned);
  const [itemId, setItemId] = useState<number>(() => (owned[0] ?? items[0])?.item_id ?? 0);
  const [copyKey, setCopyKey] = useState<string | null>(null);

  useEffect(() => {
    if (!items.some((item) => item.item_id === itemId)) {
      setItemId((items.find((item) => item.owned) ?? items[0])?.item_id ?? 0);
      setCopyKey(null);
    }
  }, [items, itemId]);

  const selected = items.find((item) => item.item_id === itemId) ?? items[0] ?? null;
  const copies = selected?.copies ?? [];
  const copy =
    copies.find((candidate) => oboroCopyKey(candidate) === copyKey) ?? copies[0] ?? null;

  useEffect(() => {
    if (copyKey && !copies.some((candidate) => oboroCopyKey(candidate) === copyKey)) {
      setCopyKey(null);
    }
  }, [copies, copyKey]);

  if (!data.oboro || !selected) return null;

  const current = copy?.current ?? null;
  const isCapped = Boolean(current && current.rank >= selected.rank);
  const buyKey = `oboro-buy-${selected.item_id}`;

  return (
    <Card className="span-2">
      <Head
        icon={<Swords size={17} />}
        title="Oboro"
        hint="Dynamis-Divergence JSE weapons · NQ R15 / HQ1 R20 / HQ2 R25 · Path A, B or C"
        badge={
          <Badge tone={owned.length ? "success" : "neutral"}>
            {owned.length} in bags
          </Badge>
        }
      />
      <p className="data-note">
        {data.oboro.note} Pick the weapon, then cap a path. Capping writes the client&apos;s
        24-byte augment block and sends <code>//reload</code> to a live client; changing a
        path overwrites the old block.
      </p>

      <div className="data-form-row" style={{ marginTop: 10 }}>
        <Select
          value={selected.item_id}
          onChange={(event) => {
            setItemId(Number(event.target.value));
            setCopyKey(null);
          }}
          aria-label="Oboro weapon"
        >
          {items.map((item) => (
            <option key={item.item_id} value={item.item_id}>
              {item.name} · {item.quality} · {item.job}
              {item.owned ? " · in bags" : ""}
            </option>
          ))}
        </Select>
        {copies.length > 1 && (
          <Select
            value={copy ? oboroCopyKey(copy) : ""}
            onChange={(event) => setCopyKey(event.target.value)}
            aria-label="Oboro copy"
          >
            {copies.map((candidate) => (
              <option key={oboroCopyKey(candidate)} value={oboroCopyKey(candidate)}>
                {whereLabel(candidate.container)} #{candidate.slot}
                {candidate.current
                  ? ` · Path ${candidate.current.path} · R${candidate.current.rank}`
                  : " · not augmented"}
              </option>
            ))}
          </Select>
        )}
        {!selected.owned && (
          <Button
            icon={<ShoppingCart size={15} />}
            loading={busy === buyKey}
            disabled={busy !== null && busy !== buyKey}
            onClick={() =>
              run(
                "armory",
                { item_id: selected.item_id, quantity: 1 },
                `${selected.name} bought for ${formatNumber(selected.price)} gil`,
                buyKey,
              )
            }
          >
            Buy for {formatNumber(selected.price)} gil
          </Button>
        )}
      </div>

      <div className="data-row" style={{ marginTop: 10 }}>
        <span>
          {selected.job} · {selected.weapon} · {selected.quality} ·{" "}
          {selected.slot === "range" ? "Ranged" : "Main hand"}
        </span>
        <strong>
          {current
            ? `Path ${current.path} · Rank ${current.rank}/${selected.rank}`
            : selected.owned
              ? "Not augmented"
              : "Not in bags"}
        </strong>
      </div>
      <div className="data-row">
        <span>Cap</span>
        <strong>
          R{selected.rank} (Max) · {formatNumber(selected.total_rp)} RP
        </strong>
      </div>
      <ProgressBar value={isCapped ? 100 : copy ? pct(current?.rank ?? 0, selected.rank) : 0} />

      <div className="data-paths data-paths-3">
        {selected.paths.map((path) => {
          const key = `oboro-${selected.item_id}-${copy?.container ?? "x"}-${
            copy?.slot ?? "x"
          }-${path.key}`;
          const active = Boolean(
            current && current.path === path.key && current.rank >= path.rank,
          );
          return (
            <div className={active ? "data-path is-current" : "data-path"} key={path.key}>
              <div className="data-path-head">
                <strong>
                  {path.label}
                  {active ? " · capped" : ""}
                </strong>
                <span>
                  R{path.rank} (Max) · {formatNumber(path.total_rp ?? path.rp)} RP
                </span>
              </div>
              <ul className="data-path-lines">
                {path.augments.map((line, index) => (
                  <li key={index}>{line}</li>
                ))}
              </ul>
              <Button
                size="sm"
                variant={active ? "secondary" : "primary"}
                loading={busy === key}
                disabled={!copy || (busy !== null && busy !== key) || active}
                onClick={() => {
                  if (!copy) return;
                  run(
                    "progress",
                    {
                      op: "augment",
                      container: copy.container,
                      slot: copy.slot,
                      path: path.key,
                    },
                    `${selected.name} → ${path.label} (R${path.rank})`,
                    key,
                  );
                }}
              >
                {active ? "Capped" : copy ? "Cap path" : "Add to bags first"}
              </Button>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
