import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Flag,
  ListChecks,
  Swords,
  Users,
  Wand2,
} from "lucide-react";
import type { CharacterData } from "../types";
import { formatNumber, JOB_ABBRS, jobName, NATIONS } from "../lib/format";
import { Badge, Button, Card, Select, TextInput } from "./ui";

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
  const [augmentKey, setAugmentKey] = useState<string | null>(() =>
    data.augments[0] ? `${data.augments[0].container}:${data.augments[0].slot}` : null,
  );

  useEffect(() => {
    setCrafts(Object.fromEntries(data.crafts.map((craft) => [craft.skill_id, craft.value])));
    setAugmentKey((current) => {
      if (current && data.augments.some((item) => `${item.container}:${item.slot}` === current)) {
        return current;
      }
      return data.augments[0] ? `${data.augments[0].container}:${data.augments[0].slot}` : null;
    });
  }, [data]);

  const selectedAugment =
    data.augments.find((item) => `${item.container}:${item.slot}` === augmentKey) ??
    data.augments[0] ??
    null;

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
          hint="Cap a path on augmentable gear in the inventory"
          badge={<Badge tone="accent">{data.augments.length} pieces</Badge>}
        />
        {data.augments.length === 0 ? (
          <p className="data-note">
            No augmentable gear in the inventory. Odyssey, Limbus and Unity pieces show here
            once they are in a bag.
          </p>
        ) : (
          <>
            <Select
              value={augmentKey ?? ""}
              onChange={(event) => setAugmentKey(event.target.value)}
              aria-label="Augmentable item"
            >
              {data.augments.map((item) => (
                <option key={`${item.container}:${item.slot}`} value={`${item.container}:${item.slot}`}>
                  {item.name} · {whereLabel(item.container)}#{item.slot}
                  {item.current ? ` · Rank ${item.current.rank}` : ""}
                </option>
              ))}
            </Select>
            {selectedAugment && (
              <>
                <div className="data-row" style={{ marginTop: 10 }}>
                  <span>
                    {selectedAugment.set || selectedAugment.kind} · {selectedAugment.slot_name}
                  </span>
                  <strong>
                    {selectedAugment.current
                      ? `Path ${selectedAugment.current.path} · Rank ${selectedAugment.current.rank} · ${formatNumber(selectedAugment.current.rp)} RP`
                      : "Not augmented"}
                  </strong>
                </div>
                <div className="data-paths">
                  {selectedAugment.paths.map((path) => {
                    const key = `augment-${selectedAugment.container}-${selectedAugment.slot}-${path.key}`;
                    return (
                      <div className="data-path" key={path.key}>
                        <div className="data-path-head">
                          <strong>{path.label}</strong>
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
                          disabled={busy !== null && busy !== key}
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
                          Cap path
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
    </>
  );
}
