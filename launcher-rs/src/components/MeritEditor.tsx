import { useEffect, useMemo, useRef, useState } from "react";
import { Minus, Plus, RotateCcw, Save } from "lucide-react";
import type { CharacterData, MeritCategory, MeritOption } from "../types";
import { formatNumber } from "../lib/format";
import { Badge, Button, Card, cn } from "./ui";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

type Draft = Record<number, number>;

const MAX_MERIT_ID = 0x0044;

function rankMap(data: CharacterData): Draft {
  const ranks: Draft = {};
  for (const category of data.merits.categories ?? []) {
    for (const merit of category.merits) ranks[merit.id] = merit.upgrades;
  }
  return ranks;
}

/** The point cost of a merit at one rank, from its published ladder. */
function costOf(merit: MeritOption, rank: number): number {
  let total = 0;
  for (let step = 0; step < rank && step < merit.costs.length; step += 1) {
    total += merit.costs[step];
  }
  return total;
}

function effectLabel(category: MeritCategory, merit: MeritOption): string {
  if (category.kind === "job") return "";
  if (category.id === 0x0040) return `+${merit.value} maximum per rank`;
  if (category.id === 0x0080) return `+${merit.value} per rank`;
  if (category.id === 0x00c0 || category.id === 0x0100) {
    return `+${merit.value} skill per rank`;
  }
  if (category.id === 0x0140) {
    if (merit.id === 0x0144) return "+1% per rank";
    if (merit.id === 0x0146) return "-1% per rank";
    if (merit.id === 0x0148) return "-2% per rank";
    return `${merit.id === 0x0142 ? "-" : "+"}${merit.value} per rank`;
  }
  if (category.id === 0x0680) return "Unlocks at rank 1; later ranks raise its power";
  return "";
}

function MenuField({
  category,
  ranks,
  used,
  busy,
  onRank,
  onClear,
}: {
  category: MeritCategory;
  ranks: Draft;
  used: number;
  busy: boolean;
  onRank: (merit: MeritOption, rank: number) => void;
  onClear: () => void;
}) {
  const over = used > category.max;
  const full = used >= category.max;
  return (
    <fieldset className={cn("merit-menu", over && "is-over")}>
      <legend>
        <span>{category.name}</span>
        <span className={cn("merit-menu-count", over && "is-over")}>
          {formatNumber(used)} / {formatNumber(category.max)}
        </span>
      </legend>
      <p className="merit-menu-hint">{category.hint}</p>
      <div className="merit-rows">
        {category.merits.map((merit) => {
          const rank = ranks[merit.id] ?? merit.upgrades;
          const canRaise = rank < merit.max && !full;
          const effect = effectLabel(category, merit);
          const spent = costOf(merit, rank);
          return (
            <div className="merit-row" key={merit.id}>
              <div className="merit-row-name">
                <strong>{merit.name}</strong>
                <small>{effect || (rank > 0 ? `${formatNumber(spent)} points spent` : "Not learned")}</small>
              </div>
              <div className="merit-row-side">
                <div className="merit-stepper">
                  <button
                    type="button"
                    className="merit-step"
                    aria-label={`Lower ${merit.name}`}
                    disabled={busy || rank <= 0}
                    onClick={() => onRank(merit, rank - 1)}
                  >
                    <Minus size={13} />
                  </button>
                  <input
                    className="merit-rank-input"
                    type="number"
                    min={0}
                    max={merit.max}
                    value={rank}
                    disabled={busy}
                    aria-label={`${merit.name} rank`}
                    onChange={(event) => {
                      const parsed = Number(event.target.value);
                      onRank(merit, Number.isFinite(parsed) ? parsed : rank);
                    }}
                  />
                  <span className="merit-rank-max">/ {merit.max}</span>
                  <button
                    type="button"
                    className="merit-step"
                    aria-label={`Raise ${merit.name}`}
                    title={full ? "This menu is at its upgrade cap" : undefined}
                    disabled={busy || !canRaise}
                    onClick={() => onRank(merit, rank + 1)}
                  >
                    <Plus size={13} />
                  </button>
                </div>
                <span className="merit-row-cost">
                  {rank >= merit.max
                    ? "Max"
                    : over
                      ? "Menu over cap"
                      : `${formatNumber(merit.next_cost)} pts next`}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="merit-menu-foot">
        <span>
          {formatNumber(used)} upgrades · {formatNumber(
            category.merits.reduce((total, merit) => total + costOf(merit, ranks[merit.id] ?? merit.upgrades), 0),
          )}{" "}
          pts
        </span>
        <button
          type="button"
          className="merit-clear"
          disabled={busy || used === 0}
          onClick={onClear}
        >
          Clear menu
        </button>
      </div>
    </fieldset>
  );
}

export function MeritEditor({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const categories = data.merits.categories ?? [];
  const characterId = data.character.id;
  const [selectedJob, setSelectedJob] = useState(() => data.character.main_job || 0);
  const [draft, setDraft] = useState<Draft>(() => rankMap(data));
  const [spend, setSpend] = useState(false);
  const lastCharacter = useRef(characterId);

  useEffect(() => {
    setDraft(rankMap(data));
    if (lastCharacter.current !== characterId) {
      lastCharacter.current = characterId;
      setSelectedJob(data.character.main_job || 0);
      setSpend(false);
    }
  }, [data, characterId]);

  const usage = useMemo(() => {
    const values = new Map<number, { used: number; spent: number }>();
    for (const category of categories) {
      let used = 0;
      let spent = 0;
      for (const merit of category.merits) {
        const rank = draft[merit.id] ?? merit.upgrades;
        used += rank;
        spent += costOf(merit, rank);
      }
      values.set(category.id, { used, spent });
    }
    return values;
  }, [categories, draft]);

  const changes = useMemo(() => {
    const result: Record<string, number> = {};
    for (const category of categories) {
      for (const merit of category.merits) {
        const rank = draft[merit.id] ?? merit.upgrades;
        if (rank !== merit.upgrades) result[String(merit.id)] = rank;
      }
    }
    return result;
  }, [categories, draft]);

  const jobIds = useMemo(() => {
    const ids = new Set<number>();
    for (const category of categories) {
      if (category.kind === "job") ids.add(category.job);
    }
    return [...ids].sort((left, right) => left - right);
  }, [categories]);

  const jobs = useMemo(() => jobIds.map((job) => {
    const menus = categories.filter((category) => category.kind === "job" && category.job === job);
    const used = menus.reduce((total, category) => total + (usage.get(category.id)?.used ?? 0), 0);
    const max = menus.reduce((total, category) => total + category.max, 0);
    return {
      job,
      name: menus[0]?.job_name ?? `Job ${job}`,
      abbr: menus[0]?.job_abbr ?? String(job),
      used,
      max,
    };
  }), [categories, jobIds, usage]);

  const generalCategories = categories.filter((category) => category.kind === "general");
  const generalUsed = generalCategories.reduce(
    (total, category) => total + (usage.get(category.id)?.used ?? 0), 0,
  );
  const activeJob = selectedJob === 0 || !jobIds.includes(selectedJob) ? 0 : selectedJob;
  const activeCategories = activeJob === 0
    ? generalCategories
    : categories.filter((category) => category.kind === "job" && category.job === activeJob);
  const activeJobInfo = jobs.find((entry) => entry.job === activeJob) ?? null;
  const activeUsed = activeCategories.reduce(
    (total, category) => total + (usage.get(category.id)?.used ?? 0), 0,
  );
  const activeMax = activeCategories.reduce((total, category) => total + category.max, 0);
  const activeOver = activeCategories.some(
    (category) => (usage.get(category.id)?.used ?? 0) > category.max,
  );
  const oldSpent = data.merits.spent ?? 0;
  const newSpent = categories.reduce(
    (total, category) => total + (usage.get(category.id)?.spent ?? 0), 0,
  );
  const delta = newSpent - oldSpent;
  const dirtyCount = Object.keys(changes).length;
  const newCap = Math.min(255, 127 + (draft[MAX_MERIT_ID] ?? 0));
  const shortfall = spend && delta > data.merits.points ? delta - data.merits.points : 0;
  const projectedPoints = spend
    ? Math.min(newCap, Math.max(0, data.merits.points - delta))
    : data.merits.points;
  const busyNow = busy !== null;
  const applying = busy === "merit-apply";

  function setRank(category: MeritCategory, merit: MeritOption, requested: number) {
    const current = draft[merit.id] ?? merit.upgrades;
    const used = usage.get(category.id)?.used ?? 0;
    const others = used - current;
    let rank = Number.isFinite(requested) ? Math.trunc(requested) : current;
    rank = Math.max(0, Math.min(merit.max, rank));
    if (rank > current) {
      // Never push a menu over the cap the client enforces.  A character that
      // already sits above it (an older assignment) can only be lowered.
      rank = Math.min(rank, Math.max(current, category.max - others));
    }
    setDraft((previous) => ({ ...previous, [merit.id]: rank }));
  }

  function clearMenu(category: MeritCategory) {
    setDraft((previous) => {
      const next = { ...previous };
      for (const merit of category.merits) next[merit.id] = 0;
      return next;
    });
  }

  function apply() {
    if (!dirtyCount) return;
    run("merits", { upgrades: changes, spend }, "Merit ranks applied", "merit-apply");
  }

  if (!categories.length) {
    return (
      <div className="merit-editor span-2">
        <Card>
          <p className="data-note">
            This server does not expose the merit menu yet. Restart the server with the
            current build, then refresh the page.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="merit-editor span-2">
      <Card accent className="merit-summary">
        <div className="merit-summary-stats">
          <div className="merit-summary-stat">
            <span>Unspent points</span>
            <strong>{formatNumber(data.merits.points)}</strong>
            <small>
              {spend && dirtyCount > 0
                ? `${formatNumber(projectedPoints)} after apply`
                : `of ${formatNumber(newCap)} cap`}
            </small>
          </div>
          <div className="merit-summary-stat">
            <span>Rank cost</span>
            <strong>{formatNumber(newSpent)}</strong>
            <small>
              {delta === 0
                ? "no change"
                : `${delta > 0 ? "+" : ""}${formatNumber(delta)} from ${formatNumber(oldSpent)}`}
            </small>
          </div>
          <div className="merit-summary-stat">
            <span>Pending</span>
            <strong>{formatNumber(dirtyCount)}</strong>
            <small>{dirtyCount === 1 ? "row" : "rows"} across all menus</small>
          </div>
        </div>
        <div className="merit-summary-controls">
          <label className="merit-spend-toggle">
            <input
              type="checkbox"
              checked={spend}
              disabled={busyNow}
              onChange={(event) => setSpend(event.target.checked)}
            />
            <span>
              Spend points
              <small>Charge or refund the game's cost</small>
            </span>
          </label>
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw size={14} />}
            disabled={busyNow || dirtyCount === 0}
            onClick={() => setDraft(rankMap(data))}
          >
            Reset
          </Button>
          <Button
            size="sm"
            icon={<Save size={14} />}
            loading={applying}
            disabled={busyNow || dirtyCount === 0 || shortfall > 0}
            onClick={apply}
          >
            Apply ranks
          </Button>
        </div>
        <p className={cn("merit-summary-note", shortfall > 0 && "is-error")}>
          {shortfall > 0
            ? `This layout needs ${formatNumber(shortfall)} more unspent points. Untick Spend points or top off on the Overview tab.`
            : spend
              ? "The net cost is taken from the unspent pool, and lowering a rank refunds it."
              : "Ranks are assigned directly; the unspent merit pool stays as it is."}
        </p>
      </Card>

      <Card className="merit-workbench">
        <div className="merit-layout">
          <nav className="merit-rail" aria-label="Merit menus">
            <div className="merit-rail-head">
              <span>Menus</span>
              <small>General + 22 jobs</small>
            </div>
            <div className="merit-rail-list">
              <button
                type="button"
                className={cn("merit-rail-item", activeJob === 0 && "active")}
                onClick={() => setSelectedJob(0)}
              >
                <span className="merit-rail-abbr">GEN</span>
                <span className="merit-rail-text">
                  <strong>General</strong>
                  <small>
                    {generalCategories.length} menus · {formatNumber(generalUsed)} upgrades
                  </small>
                </span>
              </button>
              {jobs.map((entry) => (
                <button
                  type="button"
                  key={entry.job}
                  className={cn("merit-rail-item", activeJob === entry.job && "active")}
                  onClick={() => setSelectedJob(entry.job)}
                >
                  <span className="merit-rail-abbr">{entry.abbr}</span>
                  <span className="merit-rail-text">
                    <strong>{entry.name}</strong>
                    <small>
                      {formatNumber(entry.used)} / {formatNumber(entry.max)} upgrades
                    </small>
                  </span>
                  {data.character.main_job === entry.job && (
                    <span className="merit-rail-main">Main</span>
                  )}
                </button>
              ))}
            </div>
          </nav>

          <div className="merit-panels">
            <div className="merit-panel-head">
              <div>
                <div className="eyebrow">{activeJob === 0 ? "Shared merits" : "Job merits"}</div>
                <h3>
                  {activeJob === 0
                    ? "General"
                    : `${activeJobInfo?.name ?? "Job"} · Group 1 and Group 2`}
                </h3>
                <p>
                  {activeJob === 0
                    ? "The six menus every character can spend points in."
                    : "Only this job's Group 1 and Group 2 menus; the blue badge tracks each menu's 10-point cap."}
                </p>
              </div>
              <div className="merit-panel-badge">
                {activeJob === 0 ? (
                  <Badge tone={activeOver ? "warning" : "neutral"}>
                    {activeCategories.length} menus
                  </Badge>
                ) : (
                  <>
                    {data.character.main_job === activeJob && (
                      <Badge tone="success">Main job</Badge>
                    )}
                    <Badge tone={activeUsed > activeMax ? "warning" : "accent"}>
                      {formatNumber(activeUsed)} / {formatNumber(activeMax)}
                    </Badge>
                  </>
                )}
              </div>
            </div>

            <div className="merit-menus">
              {activeCategories.map((category) => (
                <MenuField
                  key={category.id}
                  category={category}
                  ranks={draft}
                  used={usage.get(category.id)?.used ?? 0}
                  busy={busyNow}
                  onRank={(merit, rank) => setRank(category, merit, rank)}
                  onClear={() => clearMenu(category)}
                />
              ))}
            </div>

            <div className="merit-panel-actions">
              <span>
                {dirtyCount === 0
                  ? "No unsaved changes"
                  : `${formatNumber(dirtyCount)} ${dirtyCount === 1 ? "row" : "rows"} pending`}
                {dirtyCount > 0 && (
                  <> · {delta > 0 ? "+" : ""}{formatNumber(delta)} pts</>
                )}
              </span>
              <Button
                variant="ghost"
                size="sm"
                icon={<RotateCcw size={14} />}
                disabled={busyNow || dirtyCount === 0}
                onClick={() => setDraft(rankMap(data))}
              >
                Reset
              </Button>
              <Button
                size="sm"
                icon={<Save size={14} />}
                loading={applying}
                disabled={busyNow || dirtyCount === 0 || shortfall > 0}
                onClick={apply}
              >
                Apply ranks
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
