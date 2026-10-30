import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Search, X } from "lucide-react";
import type { CharacterStat, CharacterStatReport } from "../types";
import { jobName, jobPairAbbr } from "../lib/format";
import { TextInput, cn } from "./ui";

export function formatStatNumber(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return String(Math.round(value * 100) / 100);
}

export function formatStatValue(stat: Pick<CharacterStat, "value" | "percent">): string {
  return `${formatStatNumber(stat.value)}${stat.percent ? "%" : ""}`;
}

function formatContribution(value: number, percent: boolean): string {
  if (value === 0) return "—";
  return `${value > 0 ? "+" : ""}${formatStatNumber(value)}${percent ? "%" : ""}`;
}

function formatTime(seconds: number): string {
  if (!seconds) return "never";
  return new Date(seconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function groupStats(stats: CharacterStat[]): { label: string; stats: CharacterStat[] }[] {
  const groups: { label: string; stats: CharacterStat[] }[] = [];
  const byLabel = new Map<string, CharacterStat[]>();
  for (const stat of stats) {
    let group = byLabel.get(stat.group);
    if (!group) {
      group = [];
      byLabel.set(stat.group, group);
      groups.push({ label: stat.group, stats: group });
    }
    group.push(stat);
  }
  return groups;
}

/**
 * The full-window `/checkparam` sheet. The left rail switches stats; the right panel
 * explains every contribution to the selected total, including each equipped item,
 * food, job traits, job abilities and buffs. It stays live while open because the
 * parent keeps polling and hands in the newest report.
 */
export function StatSheetModal({
  report,
  initialKey,
  onClose,
}: {
  report: CharacterStatReport;
  initialKey: string;
  onClose: () => void;
}) {
  const [selectedKey, setSelectedKey] = useState(initialKey);
  const [filter, setFilter] = useState("");
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setSelectedKey(initialKey);
  }, [initialKey]);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const stats = report.stats;
  const selected = stats.find((stat) => stat.key === selectedKey) ?? stats[0] ?? null;
  const primary = useMemo(() => stats.filter((stat) => stat.primary), [stats]);
  const others = useMemo(() => stats.filter((stat) => !stat.primary), [stats]);
  const needle = filter.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      needle
        ? stats.filter(
            (stat) =>
              stat.label.toLowerCase().includes(needle) ||
              stat.group.toLowerCase().includes(needle),
          )
        : [],
    [stats, needle],
  );
  const groups = useMemo(() => groupStats(primary), [primary]);

  const job = report.job;
  const pair = {
    main: job.main_job,
    mainLevel: job.main_level,
    sub: job.sub_job,
    subLevel: job.sub_level,
  };

  return createPortal(
    <div className="stat-modal" role="dialog" aria-modal="true" aria-labelledby="stat-modal-title">
      <header className="stat-modal-head">
        <div className="stat-modal-heading">
          <span className="eyebrow">Server stat sheet · checkparam</span>
          <h2 id="stat-modal-title">
            {report.name || "Character"}{" "}
            <span>
              {jobPairAbbr(pair)} · {jobName(job.main_job)}
              {job.sub_job ? ` / ${jobName(job.sub_job)}` : ""}
            </span>
          </h2>
          <div className="stat-modal-meta">
            <span>Read {formatTime(report.updated)}</span>
            <span className="dot-sep" />
            <span>Every source kept apart; totals are the values combat uses</span>
            {report.food.name ? (
              <>
                <span className="dot-sep" />
                <span className="stat-modal-food">Food · {report.food.name}</span>
              </>
            ) : null}
          </div>
        </div>
        <button
          ref={closeRef}
          type="button"
          className="icon-btn stat-modal-close"
          aria-label="Close the stat sheet"
          title="Close (Esc)"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>

      <div className="stat-modal-body">
        <aside className="stat-modal-list" aria-label="Stats">
          <label className="stat-modal-search">
            <Search size={12} />
            <TextInput
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter stats…"
              aria-label="Filter stats"
            />
          </label>

          {needle ? (
            <div className="stat-list-group">
              <span className="stat-list-heading">
                {filtered.length} result{filtered.length === 1 ? "" : "s"}
              </span>
              {filtered.map((stat) => (
                <StatListButton
                  key={stat.key}
                  stat={stat}
                  active={selected?.key === stat.key}
                  onSelect={() => setSelectedKey(stat.key)}
                />
              ))}
              {filtered.length === 0 ? <span className="stat-list-empty">No stat matches.</span> : null}
            </div>
          ) : (
            <>
              {groups.map((group) => (
                <div className="stat-list-group" key={group.label}>
                  <span className="stat-list-heading">{group.label}</span>
                  {group.stats.map((stat) => (
                    <StatListButton
                      key={stat.key}
                      stat={stat}
                      active={selected?.key === stat.key}
                      onSelect={() => setSelectedKey(stat.key)}
                    />
                  ))}
                </div>
              ))}
              {others.length > 0 ? (
                <div className="stat-list-group">
                  <span className="stat-list-heading">Other modifiers</span>
                  {others.map((stat) => (
                    <StatListButton
                      key={stat.key}
                      stat={stat}
                      active={selected?.key === stat.key}
                      onSelect={() => setSelectedKey(stat.key)}
                    />
                  ))}
                </div>
              ) : null}
            </>
          )}
        </aside>

        <main className="stat-modal-detail">
          {selected ? (
            <>
              <div className="stat-detail-head">
                <div>
                  <span className="eyebrow">{selected.group}</span>
                  <h3>{selected.label}</h3>
                  {selected.formula ? <p className="stat-formula">{selected.formula}</p> : null}
                </div>
                <strong className="stat-detail-total">{formatStatValue(selected)}</strong>
              </div>

              <div className="stat-source-table">
                <div className="stat-source-header">
                  <span>Source</span>
                  <span>Contribution</span>
                </div>
                {selected.sources.length === 0 ? (
                  <p className="stat-source-empty">
                    No active source adds this stat from gear, food, abilities or buffs.
                  </p>
                ) : (
                  selected.sources.map((source) => (
                    <div
                      className={cn("stat-source-block", source.key === "base" && "base")}
                      key={source.key}
                    >
                      <div className="stat-source-row">
                        <span>{source.label}</span>
                        <strong>{formatContribution(source.value, selected.percent)}</strong>
                      </div>
                      {source.details.length > 1 ||
                      (source.details.length === 1 &&
                        (source.details[0].label !== source.label ||
                          source.details[0].value !== source.value ||
                          !!source.details[0].note)) ||
                      source.details.some((detail) => !!detail.note) ? (
                        <div className="stat-source-details">
                          {source.details.map((detail, index) => (
                            <div className="stat-source-detail" key={`${detail.label}-${index}`}>
                              <span>
                                {detail.label}
                                {detail.note ? (
                                  <small className="stat-source-note">{detail.note}</small>
                                ) : null}
                              </span>
                              <em>{formatContribution(detail.value, selected.percent)}</em>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
                <div className="stat-source-total">
                  <span>Total</span>
                  <strong>{formatStatValue(selected)}</strong>
                </div>
              </div>
            </>
          ) : (
            <p className="stat-source-empty">The server has not reported any stats yet.</p>
          )}
        </main>
      </div>
    </div>,
    document.body,
  );
}

function StatListButton({
  stat,
  active,
  onSelect,
}: {
  stat: CharacterStat;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={cn("stat-list-button", active && "active")}
      aria-current={active ? "true" : undefined}
      onClick={onSelect}
    >
      <span>{stat.label}</span>
      <strong>{formatStatValue(stat)}</strong>
    </button>
  );
}
