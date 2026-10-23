import { useState } from "react";
import { Check, Gamepad2, Palette, Play, Plus, UserPlus, Users } from "lucide-react";
import type { Character, ConfigView, InstanceView, SessionView } from "../types";
import {
  JOBS,
  NATIONS,
  RACES,
  characterJob,
  jobAbbr,
  jobName,
  nationName,
  raceName,
  zoneName,
} from "../lib/format";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Modal, Select, TextInput } from "./ui";

export function CharactersPage({
  session,
  config,
  instances,
  onSelect,
  onCreate,
  onPlay,
  playBusy,
  onControl,
  onDesign,
}: {
  session: SessionView;
  config: ConfigView;
  instances: InstanceView[];
  onSelect: (characterId: number) => Promise<void> | void;
  onCreate: (data: Record<string, unknown>) => Promise<void>;
  onPlay: (character: Character) => void;
  playBusy: boolean;
  onControl: () => void;
  onDesign: (characterId: number) => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [race, setRace] = useState(1);
  const [face, setFace] = useState(1);
  const [size, setSize] = useState(1);
  const [nation, setNation] = useState(0);
  const [mainJob, setMainJob] = useState(1);
  const [subJob, setSubJob] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function resetForm() {
    setName("");
    setRace(1);
    setFace(1);
    setSize(1);
    setNation(0);
    setMainJob(1);
    setSubJob(0);
    setError("");
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (!/^[A-Za-z]{3,15}$/.test(name)) {
      setError("A character name is 3–15 ASCII letters, with no spaces.");
      return;
    }
    setBusy(true);
    try {
      await onCreate({
        name,
        race,
        face,
        size,
        nation,
        main_job: mainJob,
        sub_job: subJob > 0 ? subJob : undefined,
      });
      setShowForm(false);
      resetForm();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  const activeId = config.characterId ?? session.characters[0]?.id ?? null;
  const runningCharacterIds = new Set(
    instances.filter((instance) => instance.alive).map((instance) => instance.character.id),
  );

  return (
    <div className="page">
      <div className="section-header">
        <div>
          <div className="eyebrow">@{session.account.username}</div>
          <h1 className="page-title">Characters</h1>
          <p className="page-subtitle">
            Every character is a mule. One character per account can be online at a time — add
            another account to multibox.
          </p>
        </div>
        <div className="section-actions">
          <Button variant="ghost" icon={<Users size={15} />} onClick={onControl}>
            Control room
          </Button>
          <Button icon={<Plus size={16} />} onClick={() => setShowForm(true)}>
            New character
          </Button>
        </div>
      </div>

      {session.characters.length === 0 ? (
        <Card>
          <EmptyState
            icon={<UserPlus size={26} />}
            title="No characters yet"
            body="Make your first adventurer and step into Vana'diel."
            action={
              <Button icon={<UserPlus size={16} />} onClick={() => setShowForm(true)}>
                Create a character
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="character-grid">
          {session.characters.map((character) => {
            const active = character.id === activeId;
            const running = runningCharacterIds.has(character.id);
            return (
              <Card key={character.id} className={active ? "character-card active" : "character-card"}>
                <div className="character-card-head">
                  <div className="avatar large">{character.name.slice(0, 1).toUpperCase()}</div>
                  <div className="character-card-title">
                    <div className="character-name">{character.name}</div>
                    <div className="character-sub">
                      {raceName(character.race)} · {nationName(character.nation)}
                    </div>
                  </div>
                  {active && (
                    <Badge tone="accent" dot>
                      Active
                    </Badge>
                  )}
                </div>
                <div className="character-stats">
                  <div>
                    <span>Job</span>
                    <strong>{characterJob(character)}</strong>
                  </div>
                  <div>
                    <span>Level</span>
                    <strong>{character.main_level ?? "—"}</strong>
                  </div>
                  <div>
                    <span>Zone</span>
                    <strong>{zoneName(character.zone)}</strong>
                  </div>
                  <div>
                    <span>Gil</span>
                    <strong>{character.gil?.toLocaleString() ?? "—"}</strong>
                  </div>
                </div>
                <div className="character-actions">
                  <Button
                    variant={active ? "primary" : "secondary"}
                    size="sm"
                    icon={running ? <Gamepad2 size={15} /> : <Play size={15} fill="currentColor" />}
                    onClick={() => onPlay(character)}
                    loading={playBusy}
                  >
                    {running ? "In game" : "Play"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Palette size={15} />}
                    onClick={() => onDesign(character.id)}
                  >
                    Design
                  </Button>
                  {!active && (
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Check size={15} />}
                      onClick={() => onSelect(character.id)}
                    >
                      Set active
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {showForm && (
        <Modal
          title="Create a character"
          subtitle="Choose the details you will see every time you log in."
          onClose={() => setShowForm(false)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
              <Button type="submit" form="character-form" loading={busy} icon={<UserPlus size={16} />}>
                Create character
              </Button>
            </>
          }
        >
          <form id="character-form" className="form-grid" onSubmit={create}>
            {error && <ErrorBanner message={error} onClose={() => setError("")} />}
            <Field label="Name" hint="3–15 ASCII letters, unique across the world.">
              <TextInput
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Aria"
                maxLength={15}
                autoFocus
              />
            </Field>
            <div className="form-grid two">
              <Field label="Race">
                <Select value={race} onChange={(event) => setRace(Number(event.target.value))}>
                  {RACES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Nation">
                <Select value={nation} onChange={(event) => setNation(Number(event.target.value))}>
                  {NATIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="form-grid three">
              <Field label="Face">
                <Select value={face} onChange={(event) => setFace(Number(event.target.value))}>
                  {Array.from({ length: 8 }, (_, index) => index + 1).map((value) => (
                    <option key={value} value={value}>
                      Face {value}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Size">
                <Select value={size} onChange={(event) => setSize(Number(event.target.value))}>
                  <option value={0}>Small</option>
                  <option value={1}>Medium</option>
                  <option value={2}>Large</option>
                </Select>
              </Field>
              <Field label="Main job">
                <Select value={mainJob} onChange={(event) => setMainJob(Number(event.target.value))}>
                  {JOBS.map((job, index) => (
                    <option key={job} value={index + 1}>
                      {jobAbbr(index + 1)} · {job}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Field label="Sub job" hint="Optional. The server can set it later through gameplay.">
              <Select value={subJob} onChange={(event) => setSubJob(Number(event.target.value))}>
                <option value={0}>None</option>
                {JOBS.map((job, index) => (
                  <option key={job} value={index + 1}>
                    {jobAbbr(index + 1)} · {job}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="form-summary">
              <span>Preview</span>
              <strong>
                {name || "New adventurer"} · {raceName(race)} · {nationName(nation)} ·{" "}
                {jobName(mainJob)}
              </strong>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
