import { UsersRound } from "lucide-react";
import { jobAbbr, jobName, jobPairName } from "../lib/format";
import type { TeamJobEntry, TeamJobStatus } from "../lib/teamJobs";
import { coveredTeamJobs } from "../lib/teamJobs";
import { Badge, Card, cn } from "./ui";

const STATUS_TONES: Record<
  TeamJobStatus,
  "neutral" | "accent" | "success" | "warning" | "danger"
> = {
  "in-game": "success",
  sleeping: "warning",
  orphaned: "warning",
  "logged-out": "neutral",
  offline: "neutral",
  suspended: "warning",
  "no-character": "danger",
};

/**
 * The whole party's current jobs in one card. It is shared by the Team and Control pages so the
 * main account and every box use the same rows: main job, support job, level and live state.
 */
export function TeamJobs({
  entries,
  title = "Team jobs",
  eyebrow = "Party roster",
  hint = "Every main and support job on the team. A running client is read live; an offline box uses its saved character.",
}: {
  entries: TeamJobEntry[];
  title?: string;
  eyebrow?: string;
  hint?: string;
}) {
  const coverage = coveredTeamJobs(entries);
  const characters = entries.filter((entry) => entry.character).length;
  const live = entries.filter((entry) => entry.live).length;

  return (
    <Card className="team-jobs-card">
      <div className="card-topline">
        <span className="eyebrow">{eyebrow}</span>
        <div className="team-jobs-badges">
          <Badge tone="neutral">
            {characters} character{characters === 1 ? "" : "s"}
          </Badge>
          <Badge tone="accent">
            {coverage.length} job{coverage.length === 1 ? "" : "s"}
          </Badge>
          {live > 0 && (
            <Badge tone="success" dot>
              {live} live
            </Badge>
          )}
        </div>
      </div>

      <div className="team-jobs-heading">
        <div>
          <strong>{title}</strong>
          <p>{hint}</p>
        </div>
        <UsersRound size={18} />
      </div>

      {coverage.length > 0 ? (
        <div className="team-jobs-strip" aria-label="Jobs the team covers">
          {coverage.map(({ job, count }) => (
            <span
              key={job}
              className="team-job-chip"
              title={`${jobName(job)} · ${count} team member${count === 1 ? "" : "s"}`}
            >
              <b>{jobAbbr(job)}</b>
              {count > 1 && <em>×{count}</em>}
            </span>
          ))}
        </div>
      ) : (
        <p className="team-jobs-empty">
          No character has a job yet — create one on Characters or add a box below.
        </p>
      )}

      <div className="team-jobs-list" role="table" aria-label={title}>
        <div className="team-jobs-row team-jobs-row-head" role="row">
          <span role="columnheader">Character</span>
          <span role="columnheader">Main job</span>
          <span role="columnheader">Support job</span>
          <span role="columnheader">Status</span>
        </div>
        {entries.map((entry) => {
          const pairTitle = entry.job.main ? jobPairName(entry.job) : "No character";
          return (
            <div
              key={entry.key}
              className={cn("team-jobs-row", entry.isTenant && "current")}
              role="row"
            >
              <div className="team-jobs-who" role="cell">
                <span className="avatar small">
                  {(entry.character ? entry.name : entry.account).slice(0, 1).toUpperCase()}
                </span>
                <div>
                  <strong>{entry.name}</strong>
                  <small>
                    @{entry.account} · {entry.slotLabel}
                  </small>
                </div>
              </div>
              <div className="team-jobs-job" title={pairTitle} role="cell">
                {entry.job.main ? (
                  <>
                    <b>{jobAbbr(entry.job.main)}</b>
                    <span>{jobName(entry.job.main)}</span>
                    {entry.job.mainLevel ? <em>Lv {entry.job.mainLevel}</em> : null}
                  </>
                ) : (
                  <span className="team-jobs-none">No job</span>
                )}
              </div>
              <div className="team-jobs-job" title={pairTitle} role="cell">
                {entry.job.sub ? (
                  <>
                    <b>{jobAbbr(entry.job.sub)}</b>
                    <span>{jobName(entry.job.sub)}</span>
                    {entry.job.subLevel ? <em>Lv {entry.job.subLevel}</em> : null}
                  </>
                ) : (
                  <span className="team-jobs-none">No support job</span>
                )}
              </div>
              <div className="team-jobs-state" role="cell">
                {entry.isTenant && (
                  <Badge tone="accent" dot>
                    Viewing
                  </Badge>
                )}
                <Badge tone={STATUS_TONES[entry.status]} dot={entry.live}>
                  {entry.statusLabel}
                </Badge>
                {entry.instance?.remote && <span className="team-jobs-remote">remote</span>}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
