import {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type FocusEvent,
  type MouseEvent,
} from "react";
import { createPortal } from "react-dom";
import { ImageOff, RotateCcw, Settings2 } from "lucide-react";
import type { GearSlot, GearStatQuery } from "../types";
import { backend } from "../lib/api";
import {
  VIEWER_LABELS,
  VIEWER_SLOTS,
  slotOf,
  useViewerSettings,
  type ViewerSlot,
} from "../lib/equipviewer";
import { augmentsForSlot, useBagAugments, useItemCard } from "../lib/itemcard";
import { ItemCard } from "./ItemCard";
import { cn } from "./ui";

/** The launcher's icon cache, keyed by item id. Shared by every EquipViewer on screen. */
const ICON_CACHE = new Map<number, string>();
/** Items the game's resources had no icon for; do not ask again this session. */
const NO_ICON = new Set<number>();
const ICON_CACHE_EVENT = "fanxi:equipviewer-icons-cleared";

/** Drop the in-memory icons so the next render asks the backend again. Settings calls this after
 * clearing the PNG cache. */
export function clearViewerIconCache() {
  ICON_CACHE.clear();
  NO_ICON.clear();
  window.dispatchEvent(new Event(ICON_CACHE_EVENT));
}

function messageOf(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

function useItemIcons(port: number | null, ids: number[]) {
  const idKey = ids.join(",");
  const [icons, setIcons] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const bump = () => setRevision((value) => value + 1);
    window.addEventListener(ICON_CACHE_EVENT, bump);
    return () => window.removeEventListener(ICON_CACHE_EVENT, bump);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const unique = Array.from(new Set(ids)).filter((id) => id > 0 && !NO_ICON.has(id));
    const fromCache = () => {
      const out: Record<number, string> = {};
      for (const id of unique) {
        const url = ICON_CACHE.get(id);
        if (url) out[id] = url;
      }
      return out;
    };

    const cached = fromCache();
    setIcons(cached);
    setError("");
    if (!port || unique.length === 0) {
      setLoading(false);
      return;
    }
    const missing = unique.filter((id) => !ICON_CACHE.has(id));
    if (missing.length === 0) {
      setLoading(false);
      return;
    }

    setLoading(true);
    backend
      .equipIcons(port, missing)
      .then((reply) => {
        if (cancelled) return;
        for (const [id, url] of Object.entries(reply.icons)) {
          ICON_CACHE.set(Number(id), url);
        }
        for (const id of reply.missing) NO_ICON.add(id);
        setIcons((current) => ({ ...current, ...fromCache() }));
        if (reply.error && Object.keys(reply.icons).length === 0) {
          setError(
            reply.error.includes('no command "icons"')
              ? "Rebuild host64 to enable item icons."
              : reply.error,
          );
        }
      })
      .catch((caught) => {
        if (!cancelled) setError(messageOf(caught));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // ids is represented by idKey; the array itself is rebuilt on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, idKey, revision]);

  return { icons, loading, error };
}

function rgbHex(red: number, green: number, blue: number): string {
  return `#${[red, green, blue]
    .map((value) => Math.max(0, Math.min(255, Math.round(value))).toString(16).padStart(2, "0"))
    .join("")}`;
}

function hexRgb(value: string): [number, number, number] {
  const match = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(value);
  if (!match) return [0, 0, 0];
  return [parseInt(match[1], 16), parseInt(match[2], 16), parseInt(match[3], 16)];
}

function EncumbranceMark() {
  return (
    <svg className="ev-x" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M6 6 L26 26 M26 6 L6 26" />
    </svg>
  );
}

export function EquipViewer({
  port,
  slots,
  encumbrance = 0,
  onSlotClick,
  showSettings = true,
  className,
  compact = false,
  emptyLabel,
  locked,
  augments,
  characterId,
  showCards = true,
}: {
  port: number | null;
  slots?: Record<string, GearSlot>;
  /** The client's 0x01B Encumbrance Flags word. */
  encumbrance?: number;
  /** Slots pinned by //gs lock; drawn with a red border. */
  locked?: string[];
  onSlotClick?: (slot: ViewerSlot) => void;
  showSettings?: boolean;
  className?: string;
  compact?: boolean;
  emptyLabel?: string;
  /** Augment rows per slot, from the GearSwap set or the equipped bag copy. */
  augments?: Record<string, string[] | undefined>;
  /** The character whose bags hold the equipped copies, when the caller has no augment map. */
  characterId?: number | null;
  /** Hovering a slot opens the item's full tooltip card (the game's equip-view card). */
  showCards?: boolean;
}) {
  const { settings, update, reset, background } = useViewerSettings();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [hover, setHover] = useState<{ slot: ViewerSlot; anchor: DOMRect } | null>(null);

  const ids = useMemo(
    () =>
      VIEWER_SLOTS.map((slot) => Number(slotOf(slots, slot)?.id ?? 0)).filter((id) => id > 0),
    [slots],
  );
  const { icons, loading, error } = useItemIcons(port, ids);

  const hoveredItem = hover && showCards ? slotOf(slots, hover.slot) : undefined;
  const hoveredName = String(hoveredItem?.name ?? "");
  // A caller with a GearSwap set hands over its augment rows. The Home and Control pages
  // watch a live grid without one, so their first hover asks the server for the bags instead.
  const bagRows = useBagAugments(
    characterId ?? null,
    showCards && !augments && !!hover && !!characterId,
  );
  const hoveredAugments = hover
    ? augments
      ? augments[hover.slot] ?? []
      : augmentsForSlot(bagRows, hoveredItem)
    : [];
  const hoveredQuery: GearStatQuery | null =
    hover && hoveredName
      ? {
          slot: hover.slot,
          name: hoveredName,
          augments: hoveredAugments,
          id: Number(hoveredItem?.id ?? 0),
        }
      : null;
  const card = useItemCard(port, hoveredQuery);

  // A fixed card pinned to the cell must go away when the page moves under it.
  useEffect(() => {
    if (!hover) return;
    const clear = () => setHover(null);
    window.addEventListener("scroll", clear, true);
    window.addEventListener("resize", clear);
    window.addEventListener("blur", clear);
    return () => {
      window.removeEventListener("scroll", clear, true);
      window.removeEventListener("resize", clear);
      window.removeEventListener("blur", clear);
    };
  }, [hover]);

  /** Point at a slot: the native title only names an empty cell, the card shows every line. */
  const hoverHandlers = (slot: ViewerSlot) => {
    if (!showCards) return {};
    const enter = (element: HTMLElement) =>
      setHover({ slot, anchor: element.getBoundingClientRect() });
    const leave = () =>
      setHover((current) => (current?.slot === slot ? null : current));
    return {
      onMouseEnter: (event: MouseEvent<HTMLElement>) => enter(event.currentTarget),
      onFocus: (event: FocusEvent<HTMLElement>) => enter(event.currentTarget),
      onMouseLeave: leave,
      onBlur: leave,
    };
  };

  const ammo = slotOf(slots, "ammo");
  const ammoCount = Number(ammo?.count ?? 0);
  const showAmmo = settings.showAmmo && ammoCount > 1;
  const flags = Number(encumbrance) >>> 0;
  const hasItems = VIEWER_SLOTS.some((slot) => (slotOf(slots, slot)?.id ?? 0) > 0);
  const lockedSet = new Set(locked ?? []);

  const style = {
    "--ev-size": `${compact ? Math.min(settings.size, 28) : settings.size}px`,
    "--ev-bg": background,
    "--ev-alpha": String(settings.alpha / 255),
  } as CSSProperties;

  return (
    <div className={cn("ev-wrap", className)}>
      <div className="ev-stage">
        <div className="ev-frame" style={style} role="group" aria-label="Equipped items">
          {VIEWER_SLOTS.map((slot, index) => {
            const item = slotOf(slots, slot);
            const id = Number(item?.id ?? 0);
            const icon = id > 0 ? icons[id] : undefined;
            const encumbered = settings.showEncumbrance && ((flags >>> index) & 1) === 1;
            const label = VIEWER_LABELS[slot];
            const pinned = lockedSet.has(slot) || (slot === "range" && lockedSet.has("ranged"));
            const title = `${label} — ${item?.name ?? "Empty"}${
              item?.count && item.count > 1 ? ` (${item.count})` : ""
            }${pinned ? " (locked)" : ""}`;
            const content = (
              <>
                {icon ? (
                  <img src={icon} alt="" draggable={false} />
                ) : id > 0 && !loading ? (
                  <span className="ev-fallback" aria-hidden="true">
                    {item?.name?.slice(0, 2).toUpperCase() ?? "?"}
                  </span>
                ) : null}
                {encumbered && <EncumbranceMark />}
              </>
            );
            const classes = cn(
              "ev-cell",
              !item?.name && "empty",
              id > 0 && !icon && "no-icon",
              loading && id > 0 && !icon && "loading",
              pinned && "locked",
            );
            const hovered = hoverHandlers(slot);
            // An item cell's tooltip is the card below; an empty cell keeps the native one.
            const nativeTitle = item?.name ? undefined : title;
            return onSlotClick ? (
              <button
                key={slot}
                type="button"
                className={classes}
                title={nativeTitle}
                aria-label={title}
                onClick={() => onSlotClick(slot)}
                {...hovered}
              >
                {content}
              </button>
            ) : (
              <div
                key={slot}
                className={classes}
                title={nativeTitle}
                aria-label={title}
                {...hovered}
              >
                {content}
              </div>
            );
          })}
          {showAmmo && (
            <span
              className={cn("ev-ammo", settings.leftJustify && "left")}
              title={`Ammo: ${ammoCount}`}
            >
              {ammoCount}
            </span>
          )}
        </div>
        {showSettings && (
          <div className="ev-tools">
            <button
              type="button"
              className={cn("ev-tool", settingsOpen && "active")}
              title="EquipViewer settings"
              aria-label="EquipViewer settings"
              aria-expanded={settingsOpen}
              onClick={() => setSettingsOpen((open) => !open)}
            >
              <Settings2 size={13} />
            </button>
          </div>
        )}
        {!hasItems && emptyLabel && <p className="ev-empty-label">{emptyLabel}</p>}
      </div>

      {settingsOpen && showSettings && (
        <div className="ev-settings">
          <div className="ev-settings-head">
            <strong>EquipViewer</strong>
            <span>Windower addon layout</span>
          </div>
          <label className="ev-setting">
            <span>Size</span>
            <input
              type="range"
              min={16}
              max={64}
              step={1}
              value={settings.size}
              onChange={(event) => update({ size: Number(event.target.value) })}
            />
            <b>{settings.size}px</b>
          </label>
          <label className="ev-setting">
            <span>Alpha</span>
            <input
              type="range"
              min={0}
              max={255}
              step={1}
              value={settings.alpha}
              onChange={(event) => update({ alpha: Number(event.target.value) })}
            />
            <b>{settings.alpha}</b>
          </label>
          <label className="ev-setting">
            <span>Background</span>
            <input
              type="range"
              min={0}
              max={255}
              step={1}
              value={settings.background}
              onChange={(event) => update({ background: Number(event.target.value) })}
            />
            <b>{settings.background}</b>
          </label>
          <div className="ev-setting">
            <span>Colour</span>
            <input
              type="color"
              value={rgbHex(settings.red, settings.green, settings.blue)}
              onChange={(event) => {
                const [red, green, blue] = hexRgb(event.target.value);
                update({ red, green, blue });
              }}
              aria-label="Background colour"
            />
            <b>{rgbHex(settings.red, settings.green, settings.blue)}</b>
          </div>
          <label className="ev-check">
            <input
              type="checkbox"
              checked={settings.showAmmo}
              onChange={(event) => update({ showAmmo: event.target.checked })}
            />
            <span>Ammo count</span>
          </label>
          <label className="ev-check">
            <input
              type="checkbox"
              checked={settings.showEncumbrance}
              onChange={(event) => update({ showEncumbrance: event.target.checked })}
            />
            <span>Encumbrance X</span>
          </label>
          <label className="ev-check">
            <input
              type="checkbox"
              checked={settings.leftJustify}
              onChange={(event) => update({ leftJustify: event.target.checked })}
            />
            <span>Left-justify ammo</span>
          </label>
          <div className="ev-settings-foot">
            <button type="button" className="link-btn" onClick={reset}>
              <RotateCcw size={12} /> Reset defaults
            </button>
            <span className="muted">32 px · alpha 230 · bg 72</span>
          </div>
        </div>
      )}

      {error && (
        <p className="ev-error" title={error}>
          <ImageOff size={12} /> {error}
        </p>
      )}

      {hover && hoveredName
        ? createPortal(
            <ItemCard
              name={hoveredName}
              slotLabel={VIEWER_LABELS[hover.slot]}
              augments={hoveredAugments}
              stats={card.stats}
              loading={card.loading}
              error={card.error}
              anchor={hover.anchor}
            />,
            document.body,
          )
        : null}
    </div>
  );
}
