import { useEffect, useMemo, useState } from "react";
import { Check, Copy, Dices, Shuffle, UserRound } from "lucide-react";
import type { Character, InstanceView, Tenant } from "../types";
import { raceName } from "../lib/format";
import { Badge, Button, Card, EmptyState, ErrorBanner, SectionHeader } from "./ui";
import { CharacterPreview, hairSwatches } from "./CharacterPreview";

const DESIGN_RACES = [
  { value: 1, name: "Hume", gender: "Male" },
  { value: 2, name: "Hume", gender: "Female" },
  { value: 3, name: "Elvaan", gender: "Male" },
  { value: 4, name: "Elvaan", gender: "Female" },
  { value: 5, name: "Tarutaru", gender: "Male" },
  { value: 6, name: "Tarutaru", gender: "Female" },
  { value: 7, name: "Mithra", gender: "Female" },
  { value: 8, name: "Galka", gender: "Male" },
];

const FACE_NAMES = ["Calm", "Bold", "Keen", "Kind", "Grace", "Bright", "Free", "Stern"];
const SIZE_OPTIONS = [
  { value: 0, label: "Small", hint: "0.92×" },
  { value: 1, label: "Medium", hint: "1.00×" },
  { value: 2, label: "Large", hint: "1.08×" },
];

const RACE_COMMAND: Record<number, string> = {
  1: "hume",
  2: "humef",
  3: "elvaan",
  4: "elvaanf",
  5: "tarutaru",
  6: "tarutaruf",
  7: "mithra",
  8: "galka",
};

interface Draft {
  race: number;
  face: number;
  hair: number;
  size: number;
}

function designOf(character: Character): Draft {
  const design = character.design;
  if (design) {
    return { race: design.race, face: design.face, hair: design.hair, size: design.size };
  }
  // Older rows stored the client look byte in `face`; decode it so the page
  // still opens correctly against a server that has not been migrated yet.
  const raw = Number(character.face ?? 1);
  return {
    race: Number(character.race ?? 1),
    face: Math.floor(raw / 2) + 1,
    hair: raw % 2,
    size: Number(character.size ?? 1),
  };
}

function variantOf(draft: Draft): number {
  return ((draft.face - 1) * 2 + draft.hair) * 3 + draft.size + 1;
}

function sizeLabel(size: number): string {
  return SIZE_OPTIONS.find((option) => option.value === size)?.label ?? "Medium";
}

function sameDesign(a: Draft, b: Draft): boolean {
  return a.race === b.race && a.face === b.face && a.hair === b.hair && a.size === b.size;
}

export function DesignPage({
  tenant,
  instances,
  onSave,
  onTeam,
}: {
  tenant: Tenant | null;
  instances: InstanceView[];
  onSave: (characterId: number, data: Record<string, unknown>) => Promise<void>;
  onTeam: () => void;
}) {
  const character = tenant?.character ?? null;
  const saved = character ? designOf(character) : null;
  const signature = character
    ? `${character.id}:${character.race}:${character.face}:${character.hair}:${character.size}`
    : "none";
  const [draft, setDraft] = useState<Draft>(
    saved ?? { race: 1, face: 1, hair: 0, size: 1 },
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // Reset the form when the tenant (or its saved design) changes. Switching the tenant bar
  // therefore switches the character this form edits.
  useEffect(() => {
    if (saved) setDraft(saved);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  const changed = saved ? !sameDesign(draft, saved) : false;
  const variant = variantOf(draft);
  const rawFace = (draft.face - 1) * 2 + draft.hair;
  const command = `!character model ${RACE_COMMAND[draft.race] ?? "hume"} ${variant}`;
  const running = instances.some(
    (instance) =>
      instance.alive && Number(instance.character.id) === Number(character?.id),
  );
  const hairColors = useMemo(() => hairSwatches(draft.race), [draft.race]);

  function patch(next: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...next }));
    setError("");
    setCopied(false);
  }

  function randomize() {
    const race = DESIGN_RACES[Math.floor(Math.random() * DESIGN_RACES.length)].value;
    patch({
      race,
      face: 1 + Math.floor(Math.random() * 8),
      hair: Math.floor(Math.random() * 2),
      size: Math.floor(Math.random() * 3),
    });
  }

  function randomizeFace() {
    patch({
      face: 1 + Math.floor(Math.random() * 8),
      hair: Math.floor(Math.random() * 2),
      size: Math.floor(Math.random() * 3),
    });
  }

  async function apply() {
    if (!character || !changed) return;
    setBusy(true);
    setError("");
    try {
      await onSave(character.id, { ...draft });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function copyCommand() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Could not copy to the clipboard.");
    }
  }

  if (!tenant || !character) {
    return (
      <div className="page">
        <SectionHeader eyebrow="Appearance" title="Character design" />
        <Card>
          <EmptyState
            icon={<UserRound size={26} />}
            title="No tenant selected"
            body="Pick a character in the tenant bar, or create a box on the Team page, then come back to choose a race, face, hair colour and size."
            action={<Button onClick={onTeam}>Open Team</Button>}
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page design-page">
      <SectionHeader
        eyebrow={`Appearance · @${tenant.account}`}
        title="Character design"
        subtitle={`Editing ${character.name} (${tenant.label}). Race, face, hair colour and size — the same 384 looks as the client's character creator. Applying writes only to this tenant.`}
        actions={
          <>
            <Button variant="ghost" icon={<Shuffle size={15} />} onClick={randomizeFace}>
              Random face
            </Button>
            <Button variant="secondary" icon={<Dices size={16} />} onClick={randomize}>
              Surprise me
            </Button>
          </>
        }
      />

      <div className="design-layout">
          <Card className="design-stage-card" accent>
            <div className="design-stage-top">
              <div>
                <div className="eyebrow">Model preview</div>
                <div className="design-stage-name">{character.name}</div>
                <div className="design-stage-meta">
                  {raceName(draft.race)} · Face {draft.face} · Hair {draft.hair === 0 ? "A" : "B"} ·{" "}
                  {sizeLabel(draft.size)}
                </div>
              </div>
              <Badge tone={running ? "success" : "neutral"} dot>
                {running ? "In game" : "Offline"}
              </Badge>
            </div>

            <CharacterPreview
              race={draft.race}
              face={draft.face}
              hair={draft.hair}
              size={draft.size}
            />

            <div className="design-stage-footer">
              <div>
                <span>Variant</span>
                <strong>
                  {variant}
                  <small> / 48</small>
                </strong>
              </div>
              <div>
                <span>Look byte</span>
                <code>{rawFace}</code>
              </div>
              <div className="design-command">
                <span>In game</span>
                <button onClick={() => void copyCommand()} title="Copy the command">
                  <code>{command}</code>
                  {copied ? <Check size={13} /> : <Copy size={13} />}
                </button>
              </div>
            </div>
          </Card>

          <div className="design-controls">
            <Card>
              <div className="design-card-head">
                <div>
                  <div className="eyebrow">Step 1</div>
                  <strong>Race</strong>
                </div>
                <span className="muted">{draft.race <= 8 ? DESIGN_RACES[draft.race - 1]?.name : ""}</span>
              </div>
              <div className="design-race-grid">
                {DESIGN_RACES.map((race) => (
                  <button
                    key={race.value}
                    className={draft.race === race.value ? "design-race-tile active" : "design-race-tile"}
                    onClick={() => patch({ race: race.value })}
                  >
                    <span
                      className="design-race-dot"
                      style={{
                        background: `linear-gradient(135deg, ${hairSwatches(race.value)[0]}, ${hairSwatches(race.value)[1]})`,
                      }}
                    />
                    <span>
                      <strong>{race.name}</strong>
                      <small>{race.gender}</small>
                    </span>
                  </button>
                ))}
              </div>
            </Card>

            <Card>
              <div className="design-card-head">
                <div>
                  <div className="eyebrow">Step 2</div>
                  <strong>Face & hair</strong>
                </div>
                <span className="muted">{FACE_NAMES[draft.face - 1]}</span>
              </div>
              <div className="design-face-grid">
                {FACE_NAMES.map((name, index) => (
                  <button
                    key={name}
                    className={draft.face === index + 1 ? "design-face-tile active" : "design-face-tile"}
                    onClick={() => patch({ face: index + 1 })}
                    title={`Face ${index + 1} · ${name}`}
                  >
                    <span>{index + 1}</span>
                    <small>{name}</small>
                  </button>
                ))}
              </div>

              <div className="design-split">
                <div>
                  <span className="field-label">Hair colour</span>
                  <div className="design-hair-row">
                    {([0, 1] as const).map((colour) => (
                      <button
                        key={colour}
                        className={draft.hair === colour ? "design-hair-swatch active" : "design-hair-swatch"}
                        onClick={() => patch({ hair: colour })}
                        title={`Hair ${colour === 0 ? "A" : "B"}`}
                      >
                        <span
                          className="design-hair-dot"
                          style={{
                            background: `linear-gradient(135deg, ${hairColors[colour]}, ${hairColors[colour]} 55%, #0a1824)`,
                          }}
                        />
                        <span>Hair {colour === 0 ? "A" : "B"}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="field-label">Size</span>
                  <div className="design-size-row">
                    {SIZE_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        className={draft.size === option.value ? "design-size-button active" : "design-size-button"}
                        onClick={() => patch({ size: option.value })}
                      >
                        <strong>{option.label}</strong>
                        <small>{option.hint}</small>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            <Card className="design-summary-card">
              <div className="design-summary">
                <div>
                  <span className="field-label">New design</span>
                  <strong>
                    {raceName(draft.race)} · Face {draft.face} · Hair {draft.hair === 0 ? "A" : "B"} ·{" "}
                    {sizeLabel(draft.size)}
                  </strong>
                </div>
                <Badge tone={changed ? "warning" : "success"}>{changed ? "Unsaved" : "Saved"}</Badge>
              </div>
              {error && <ErrorBanner message={error} onClose={() => setError("")} />}
              <div className="design-actions">
                <Button variant="ghost" onClick={() => saved && setDraft(saved)} disabled={!changed}>
                  Reset
                </Button>
                <Button
                  icon={<Check size={16} />}
                  onClick={() => void apply()}
                  loading={busy}
                  disabled={!changed}
                >
                  Apply design
                </Button>
              </div>
              <p className="design-note">
                {running
                  ? "The running client repaints as soon as you apply."
                  : "The change is read the next time this character logs in."}{" "}
                Or type <code>{command}</code> in game.
              </p>
            </Card>
          </div>
        </div>
    </div>
  );
}
