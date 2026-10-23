import { useEffect, useState } from "react";
import { backend } from "../lib/api";
import { SLOT_KEYS } from "../lib/format";
import type { GearSlot } from "../types";
import type { ViewerSlot } from "../lib/equipviewer";
import { EquipViewer } from "./EquipViewer";

/** item name (lowercase) -> id. Set previews share this for the whole launcher session. */
const NAME_IDS = new Map<string, number>();

function normalize(name: string): string {
  return name.trim().toLowerCase();
}

/**
 * GearSwap sets store item names; icons are keyed by id. Ask the running client to resolve the
 * ones we have not seen, debounced so typing in the set editor does not spam the control port.
 */
function useResolvedNames(port: number | null, names: string[]) {
  const key = names.join("\u0000");
  const [resolved, setResolved] = useState<Record<string, number>>({});

  useEffect(() => {
    let cancelled = false;
    const unique = Array.from(new Set(names.map(normalize).filter(Boolean)));
    const apply = () => {
      const out: Record<string, number> = {};
      for (const name of unique) {
        if (NAME_IDS.has(name)) out[name] = NAME_IDS.get(name) ?? 0;
      }
      setResolved(out);
    };
    apply();
    if (!port || unique.length === 0) return;
    const missing = unique.filter((name) => !NAME_IDS.has(name));
    if (missing.length === 0) return;

    const timer = window.setTimeout(() => {
      backend
        .gearItemIds(port, missing)
        .then((items) => {
          for (const item of items) {
            NAME_IDS.set(normalize(item.name), item.id);
          }
          if (!cancelled) apply();
        })
        .catch(() => {
          // An old client or a name with no item simply renders the fallback tile.
        });
    }, 220);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // names is represented by key; the array itself is rebuilt on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, key]);

  return resolved;
}

export function SetEquipmentPreview({
  port,
  items,
  onSlotClick,
  compact = false,
  showSettings = false,
  emptyLabel = "This set is empty.",
}: {
  port: number | null;
  items: Record<string, string>;
  onSlotClick?: (slot: ViewerSlot) => void;
  compact?: boolean;
  showSettings?: boolean;
  emptyLabel?: string;
}) {
  const names = SLOT_KEYS.map((slot) => items[slot] ?? "").filter(Boolean);
  const resolved = useResolvedNames(port, names);

  const slots: Record<string, GearSlot> = {};
  for (const slot of SLOT_KEYS) {
    const name = items[slot];
    if (!name) continue;
    slots[slot] = { name, id: resolved[normalize(name)] ?? 0 };
  }

  return (
    <EquipViewer
      port={port}
      slots={slots}
      onSlotClick={onSlotClick}
      compact={compact}
      showSettings={showSettings}
      emptyLabel={emptyLabel}
    />
  );
}
