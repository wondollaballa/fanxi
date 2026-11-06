import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import type { JobAbility, JobSpell } from "../types";
import { Button, ErrorBanner, Field, Modal, TextInput, cn } from "./ui";

/** The three kinds of action the Battle page can pick: a spell, a Bard song or a job ability. */
export type BattleActionKind = "spell" | "song" | "ability" | "weapon_skill" | "move";

export type BattleActionEntry = {
  name: string;
  kind: BattleActionKind;
  /** A short line under the name: the spell's skill and level, or the ability's type. */
  detail: string;
};

const SONG_SKILLS = new Set(["Singing", "String Instrument", "Wind Instrument"]);
const KIND_FILTER_LABELS: Record<BattleActionKind, string> = {
  spell: "Spells",
  song: "Songs",
  ability: "Abilities",
  weapon_skill: "Weapon skills",
  move: "Mob moves",
};
const KIND_PLURALS: Record<BattleActionKind, string> = {
  spell: "spells",
  song: "songs",
  ability: "abilities",
  weapon_skill: "weapon skills",
  move: "mob moves",
};
const KIND_ORDER: BattleActionKind[] = [
  "spell",
  "song",
  "ability",
  "weapon_skill",
  "move",
];

function searchPlaceholder(kinds: BattleActionKind[]): string {
  if (kinds.length === 0) return "Search by name…";
  if (kinds.length === 1) return `Search ${KIND_PLURALS[kinds[0]]}…`;
  const last = kinds[kinds.length - 1];
  return `Search ${kinds.slice(0, -1).map((kind) => KIND_PLURALS[kind]).join(", ")} or ${KIND_PLURALS[last]}…`;
}

function isSong(spell: JobSpell): boolean {
  return spell.categories?.includes("songs") === true || SONG_SKILLS.has(spell.skill);
}

/** The spells and songs one job pair can cast, deduplicated by name and sorted for the dialog. */
export function spellActionEntries(spells: JobSpell[]): BattleActionEntry[] {
  const seen = new Set<string>();
  const out: BattleActionEntry[] = [];
  for (const spell of spells) {
    const name = (spell.name ?? "").trim();
    if (!name) continue;
    const key = name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    const song = isSong(spell);
    const detail = [
      song ? "Song" : spell.skill || "Spell",
      spell.level > 0 ? `Lv ${spell.level}` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    out.push({ name, kind: song ? "song" : "spell", detail });
  }
  out.sort((a, b) => a.name.localeCompare(b.name) || a.kind.localeCompare(b.kind));
  return out;
}

/** The job abilities one job pair can use, deduplicated by name and sorted for the dialog. */
export function abilityActionEntries(abilities: JobAbility[]): BattleActionEntry[] {
  const seen = new Set<string>();
  const out: BattleActionEntry[] = [];
  for (const ability of abilities) {
    const name = (ability.name ?? "").trim();
    if (!name) continue;
    const key = name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    const type = ability.type && ability.type !== "JobAbility" ? ability.type : "Job ability";
    out.push({ name, kind: "ability", detail: type });
  }
  out.sort((a, b) => a.name.localeCompare(b.name));
  return out;
}

/** The clickable field that opens the dialog.  The value is always picked, never typed. */
export function BattleActionPick({
  value,
  label,
  placeholder,
  onClick,
}: {
  value: string;
  label?: string;
  placeholder: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn("battle-action-pick", value && "filled")}
      onClick={onClick}
      aria-haspopup="dialog"
      title={value ? `${value} — click to choose another` : placeholder}
    >
      <span className="battle-action-pick-name">{label ?? (value || placeholder)}</span>
      <span className="battle-action-pick-hint">{value ? "Change" : "Choose"}</span>
    </button>
  );
}

export function BattleActionDialog({
  title,
  subtitle,
  value = "",
  values = [],
  mode = "single",
  entries,
  loading,
  error,
  emptyHint,
  onRefresh,
  onSelect,
  onConfirm,
  onClose,
}: {
  title: string;
  subtitle: string;
  value?: string;
  values?: string[];
  mode?: "single" | "multi";
  entries: BattleActionEntry[];
  loading: boolean;
  error: string;
  emptyHint?: string;
  onRefresh: () => void;
  onSelect?: (name: string, kind: BattleActionKind) => void;
  onConfirm?: (names: string[]) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [wantedKind, setWantedKind] = useState<"all" | BattleActionKind>("all");
  const [picked, setPicked] = useState<Set<string>>(() => new Set(values));
  const multi = mode === "multi";

  const counts = useMemo(() => {
    const out: Record<BattleActionKind, number> = {
      spell: 0,
      song: 0,
      ability: 0,
      weapon_skill: 0,
      move: 0,
    };
    for (const entry of entries) out[entry.kind] += 1;
    return out;
  }, [entries]);

  // A filter whose kind disappeared (job change, or a partial spell list) falls back to All.
  const kind = wantedKind !== "all" && counts[wantedKind] > 0 ? wantedKind : "all";
  const kinds = KIND_ORDER.filter((entry) => counts[entry] > 0);
  const needle = query.trim().toLowerCase();
  const visible = useMemo(
    () =>
      entries.filter((entry) => {
        if (kind !== "all" && entry.kind !== kind) return false;
        if (!needle) return true;
        return (
          entry.name.toLowerCase().includes(needle) ||
          entry.detail.toLowerCase().includes(needle)
        );
      }),
    [entries, kind, needle],
  );

  const wanted = value.trim().toLowerCase();
  const selected = wanted ? entries.find((entry) => entry.name.toLowerCase() === wanted) : undefined;
  const missing = !multi && !loading && wanted !== "" && selected === undefined;

  function choose(entry: BattleActionEntry) {
    if (!multi) {
      onSelect?.(entry.name, entry.kind);
      return;
    }
    setPicked((previous) => {
      const next = new Set(previous);
      if (next.has(entry.name)) next.delete(entry.name);
      else next.add(entry.name);
      return next;
    });
  }

  function isPicked(entry: BattleActionEntry): boolean {
    return multi ? picked.has(entry.name) : selected?.name === entry.name;
  }

  return (
    <Modal
      title={title}
      subtitle={subtitle}
      wide
      onClose={onClose}
      footer={
        <>
          <Button
            variant="ghost"
            icon={<RefreshCw size={14} />}
            loading={loading}
            onClick={onRefresh}
          >
            Refresh list
          </Button>
          <Button
            variant="ghost"
            disabled={multi ? picked.size === 0 : !value}
            onClick={() => (multi ? setPicked(new Set()) : onSelect?.("", "spell"))}
          >
            Clear
          </Button>
          {multi ? (
            <Button
              variant="primary"
              disabled={!onConfirm}
              onClick={() => onConfirm?.([...picked])}
            >
              Apply {picked.size > 0 ? `(${picked.size})` : ""}
            </Button>
          ) : (
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
          )}
        </>
      }
    >
      {error ? (
        <div className="picker-error">
          <ErrorBanner message={error} />
        </div>
      ) : null}
      <Field
        label="Search"
        hint={
          multi
            ? "Click rows to add or remove them, then Apply. Search filters the table."
            : "Type part of a name, a skill or a type."
        }
      >
        <TextInput
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={searchPlaceholder(kinds)}
          autoFocus
        />
      </Field>
      {kinds.length > 1 ? (
        <div className="battle-picker-filters">
          <button
            type="button"
            className={cn("battle-picker-filter", kind === "all" && "on")}
            onClick={() => setWantedKind("all")}
          >
            All {entries.length}
          </button>
          {kinds.map((entry) => (
            <button
              type="button"
              key={entry}
              className={cn("battle-picker-filter", kind === entry && "on")}
              onClick={() => setWantedKind(entry)}
            >
              {KIND_FILTER_LABELS[entry]} {counts[entry]}
            </button>
          ))}
        </div>
      ) : null}
      {missing ? (
        <p className="battle-picker-note">
          The saved value “{value}” is not in this character's current list. Pick another one, or
          clear it.
        </p>
      ) : null}
      <div className="item-picker-list">
        {visible.map((entry) => {
          const active = isPicked(entry);
          return (
            <button
              type="button"
              key={`${entry.kind}:${entry.name}`}
              className={cn("item-picker-row", active && "on")}
              aria-pressed={active}
              onClick={() => choose(entry)}
            >
              <span className="item-picker-head">
                <strong>{entry.name}</strong>
                <span className="muted">
                  {entry.detail}
                  {active ? " · selected" : ""}
                </span>
              </span>
            </button>
          );
        })}
        {visible.length === 0 ? (
          <div className="muted padded">
            {loading && entries.length === 0
              ? "Reading this character's lists from the client…"
              : entries.length === 0
                ? emptyHint ??
                  "The client has not reported a list for this job yet. Zone in with this character, then choose Refresh list."
                : `No ${kind === "all" ? "entries" : KIND_PLURALS[kind]} match this search.`}
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
