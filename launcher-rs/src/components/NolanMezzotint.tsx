import { useEffect, useMemo, useState } from "react";
import { Check, Hammer, RotateCcw } from "lucide-react";
import type { CharacterData, NolanCopy, NolanItem, NolanStat } from "../types";
import { Badge, Button, Card, Select } from "./ui";

type RunAction = (
  action: string,
  payload: Record<string, unknown>,
  message: string,
  key?: string,
) => void;

function copyKeyOf(copy: NolanCopy): string {
  return `${copy.container}:${copy.slot}`;
}

const PATH_ORDER = ["A", "B", "C", "D"];

/** The Data page's Nolan card.
 *
 * Nolan mezzotints Escha - Zi'Tah and Escha - Ru'Aun gear in Norg.  Every owned
 * piece offers paths A-D; the BG Wiki page lists the Rank 15 maximum for each.
 * Applying a path writes that block in one step (retail would climb the fifteen
 * ranks with Eschalixirs), and a live client picks the new tooltip up on
 * ``//reload``.  The catalog is the 183 items the wiki lists; only the copies
 * the character actually holds are shown.
 */
export function NolanMezzotint({
  data,
  run,
  busy,
}: {
  data: CharacterData;
  run: RunAction;
  busy: string | null;
}) {
  const catalog = data.nolan;
  const items = catalog?.items ?? [];
  const [itemId, setItemId] = useState(0);
  const [copyKey, setCopyKey] = useState<string | null>(null);

  useEffect(() => {
    if (!items.length) return;
    if (!items.some((item) => item.item_id === itemId)) {
      setItemId(items[0].item_id);
      setCopyKey(null);
    }
  }, [items, itemId]);

  const selected: NolanItem | null =
    items.find((item) => item.item_id === itemId) ?? items[0] ?? null;
  const copies = selected?.copies ?? [];
  const copy =
    copies.find((candidate) => copyKeyOf(candidate) === copyKey) ?? copies[0] ?? null;

  const groups = useMemo(() => {
    const out: { group: string; items: NolanItem[] }[] = [];
    for (const item of items) {
      const last = out[out.length - 1];
      if (last && last.group === item.group) last.items.push(item);
      else out.push({ group: item.group, items: [item] });
    }
    return out;
  }, [items]);

  if (!catalog) return null;

  const current = copy?.current ?? null;

  function applyPath(path: string) {
    if (!copy || !selected || busy !== null) return;
    run(
      "progress",
      { op: "nolan", container: copy.container, slot: copy.slot, path },
      `${selected.name} → path ${path} (Rank ${catalog.levels.max_rank})`,
      `nolan-${selected.item_id}-${copy.container}-${copy.slot}-${path}`,
    );
  }

  return (
    <Card className="span-2">
      <div className="data-card-head">
        <div className="data-card-icon">
          <Hammer size={17} />
        </div>
        <div className="data-card-title">
          <h3>Nolan · Escha mezzotint</h3>
          <p>
            Norg (I-7) · every Escha - Zi&apos;Tah, Escha - Ru&apos;Aun and
            abjuration piece · paths A-D · Rank {catalog.levels.max_rank} maximum
          </p>
        </div>
        <div className="data-card-badge">
          <Badge tone={items.length ? "success" : "neutral"}>
            {items.length} in bags
          </Badge>
        </div>
      </div>

      <p className="data-note">{catalog.note}</p>
      <p className="data-note">
        Paths A/B/C are shared by every piece of an armor set; path D is per
        piece. Applying writes the Rank {catalog.levels.max_rank} block
        ({catalog.levels.rp_total.toLocaleString()} RP) in one step. Switching a
        path overwrites the old one.
      </p>

      {items.length === 0 ? (
        <p className="data-note">
          No Escha gear in the bags yet. Buy a piece in the <strong>Armory</strong>{" "}
          below (or trade it to the character) and it appears here; the catalog
          behind this card is {catalog.catalog_size} items.
        </p>
      ) : (
        <>
          <div className="cape-picker">
            <Select
              value={selected?.item_id ?? ""}
              onChange={(event) => {
                setItemId(Number(event.target.value));
                setCopyKey(null);
              }}
              aria-label="Escha item"
            >
              {groups.map((group) => (
                <optgroup key={group.group} label={group.group}>
                  {group.items.map((item) => (
                    <option key={item.item_id} value={item.item_id}>
                      {item.name} · {item.zone}
                      {item.copies.length > 1 ? ` · ${item.copies.length} copies` : ""}
                    </option>
                  ))}
                </optgroup>
              ))}
            </Select>
            {copies.length > 1 && (
              <Select
                value={copy ? copyKeyOf(copy) : ""}
                onChange={(event) => setCopyKey(event.target.value)}
                aria-label="Item copy"
              >
                {copies.map((candidate) => (
                  <option key={copyKeyOf(candidate)} value={copyKeyOf(candidate)}>
                    {candidate.container_name} #{candidate.slot}
                    {candidate.current
                      ? ` · path ${candidate.current.path} R${candidate.current.rank}`
                      : " · not augmented"}
                  </option>
                ))}
              </Select>
            )}
          </div>

          {selected && (
            <p className="data-note cape-selected">
              {selected.slot} · {selected.zone} · item #{selected.item_id}
              {current
                ? ` · current: ${current.text}`
                : " · not augmented yet"}
            </p>
          )}

          {copy && selected ? (
            <div className="data-paths">
              {PATH_ORDER.map((path) => {
                const rows: NolanStat[] = selected.paths[path] ?? [];
                const active = current?.path === path;
                const key = `nolan-${selected.item_id}-${copy.container}-${copy.slot}-${path}`;
                return (
                  <div
                    className={active ? "data-path is-current" : "data-path"}
                    key={path}
                  >
                    <div className="data-path-head">
                      <strong>
                        Path {path}
                        {active ? " · active" : ""}
                      </strong>
                      <span>Rank {catalog.levels.max_rank}</span>
                    </div>
                    <ul className="data-path-lines">
                      {rows.map((row, index) => (
                        <li key={index}>{row.text}</li>
                      ))}
                    </ul>
                    <Button
                      size="sm"
                      variant={active ? "secondary" : "primary"}
                      icon={active ? <RotateCcw size={14} /> : <Check size={14} />}
                      loading={busy === key}
                      disabled={busy !== null && busy !== key}
                      onClick={() => applyPath(path)}
                    >
                      {active ? "Re-apply path" : "Apply path"}
                    </Button>
                  </div>
                );
              })}
            </div>
          ) : null}
        </>
      )}
    </Card>
  );
}
