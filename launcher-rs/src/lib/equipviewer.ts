import { useSyncExternalStore } from "react";
import type { GearSlot } from "../types";

/**
 * EquipViewer's exact grid, from Windower's addon:
 *
 *   main  sub  range ammo
 *   head  neck ear1  ear2
 *   body  hands ring1 ring2
 *   back  waist legs  feet
 *
 * The index in this array is also the equipment slot id that the client's 0x01B
 * Encumbrance Flags word uses, so bit `i` belongs to `VIEWER_SLOTS[i]`.
 */
export const VIEWER_SLOTS = [
  "main",
  "sub",
  "range",
  "ammo",
  "head",
  "neck",
  "ear1",
  "ear2",
  "body",
  "hands",
  "ring1",
  "ring2",
  "back",
  "waist",
  "legs",
  "feet",
] as const;

export type ViewerSlot = (typeof VIEWER_SLOTS)[number];

export const VIEWER_LABELS: Record<ViewerSlot, string> = {
  main: "Main",
  sub: "Sub",
  range: "Range",
  ammo: "Ammo",
  head: "Head",
  neck: "Neck",
  ear1: "Left ear",
  ear2: "Right ear",
  body: "Body",
  hands: "Hands",
  ring1: "Left ring",
  ring2: "Right ring",
  back: "Back",
  waist: "Waist",
  legs: "Legs",
  feet: "Feet",
};

/** Older control addons spell the paired slots the Windower way. */
const SLOT_ALIASES: Record<ViewerSlot, string> = {
  main: "main",
  sub: "sub",
  range: "range",
  ammo: "ammo",
  head: "head",
  neck: "neck",
  ear1: "left_ear",
  ear2: "right_ear",
  body: "body",
  hands: "hands",
  ring1: "left_ring",
  ring2: "right_ring",
  back: "back",
  waist: "waist",
  legs: "legs",
  feet: "feet",
};

export function slotOf(
  slots: Record<string, GearSlot> | undefined,
  slot: ViewerSlot,
): GearSlot | undefined {
  if (!slots) return undefined;
  return slots[slot] ?? slots[SLOT_ALIASES[slot]] ?? slots[String(VIEWER_SLOTS.indexOf(slot))];
}

export interface ViewerSettings {
  /** Pixels per slot; EquipViewer's `size` / `scale`. */
  size: number;
  /** Icon opacity, 0..255; EquipViewer's `alpha` / `transparency`. */
  alpha: number;
  /** Background colour and opacity, 0..255; EquipViewer's `background r g b a`. */
  background: number;
  red: number;
  green: number;
  blue: number;
  showAmmo: boolean;
  showEncumbrance: boolean;
  leftJustify: boolean;
}

export const DEFAULT_VIEWER_SETTINGS: ViewerSettings = {
  size: 32,
  alpha: 230,
  background: 72,
  red: 0,
  green: 0,
  blue: 0,
  showAmmo: true,
  showEncumbrance: true,
  leftJustify: false,
};

const STORAGE_KEY = "fanxi.equipviewer.v1";
const listeners = new Set<() => void>();

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

function read(): ViewerSettings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_VIEWER_SETTINGS };
    const saved = JSON.parse(raw) as Partial<ViewerSettings>;
    return {
      size: clamp(Number(saved.size ?? 32), 16, 64),
      alpha: clamp(Number(saved.alpha ?? 230), 0, 255),
      background: clamp(Number(saved.background ?? 72), 0, 255),
      red: clamp(Number(saved.red ?? 0), 0, 255),
      green: clamp(Number(saved.green ?? 0), 0, 255),
      blue: clamp(Number(saved.blue ?? 0), 0, 255),
      showAmmo: saved.showAmmo ?? true,
      showEncumbrance: saved.showEncumbrance ?? true,
      leftJustify: saved.leftJustify ?? false,
    };
  } catch {
    return { ...DEFAULT_VIEWER_SETTINGS };
  }
}

let current: ViewerSettings = read();

function emit() {
  for (const listener of listeners) listener();
}

function save(next: ViewerSettings) {
  current = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // A full or disabled localStorage should not break the viewer.
  }
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function snapshot() {
  return current;
}

export function useViewerSettings(): {
  settings: ViewerSettings;
  update: (patch: Partial<ViewerSettings>) => void;
  reset: () => void;
  background: string;
} {
  const settings = useSyncExternalStore(subscribe, snapshot, snapshot);
  const update = (patch: Partial<ViewerSettings>) => {
    const next = { ...current, ...patch };
    next.size = clamp(Number(next.size), 16, 64);
    next.alpha = clamp(Number(next.alpha), 0, 255);
    next.background = clamp(Number(next.background), 0, 255);
    next.red = clamp(Number(next.red), 0, 255);
    next.green = clamp(Number(next.green), 0, 255);
    next.blue = clamp(Number(next.blue), 0, 255);
    save(next);
  };
  const reset = () => save({ ...DEFAULT_VIEWER_SETTINGS });
  return {
    settings,
    update,
    reset,
    background: `rgba(${settings.red}, ${settings.green}, ${settings.blue}, ${(
      settings.background / 255
    ).toFixed(3)})`,
  };
}
