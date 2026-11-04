import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent, ReactNode } from "react";
import {
  Award,
  Coins,
  Gauge,
  Gem,
  KeyRound,
  ListChecks,
  Loader2,
  MapPin,
  Package,
  PackagePlus,
  RefreshCw,
  Search,
  ShoppingBasket,
  Sparkles,
  TrendingUp,
  UserRoundCog,
} from "lucide-react";
import type { ArmoryItem, Character, CharacterData, InstanceView } from "../types";
import { backend, LauncherError } from "../lib/api";
import { INVENTORY_FULL_MESSAGE, INVENTORY_FULL_TOAST, isInventoryFull } from "../lib/inventory";
import { useTablePagination } from "../lib/pagination";
import { AmbuscadeCapes } from "./AmbuscadeCapes";
import { InventoryFullDialog } from "./InventoryFullDialog";
import { NolanMezzotint } from "./NolanMezzotint";
import { OseemGlyptics } from "./OseemGlyptics";
import { SkirmishAugments } from "./SkirmishAugments";
import { SinisterReign } from "./SinisterReign";
import { ShantottoAscension } from "./ShantottoAscension";
import { MoonshadeEarring } from "./MoonshadeEarring";
import { MagianMoogle } from "./MagianMoogle";
import { MeritEditor } from "./MeritEditor";
import { ProgressCards } from "./ProgressCards";
import { ItemIcon } from "./ItemIcon";
import { ItemsCatalog } from "./ItemsCatalog";
import { characterJobLabel, formatNumber, pct, slotLabel } from "../lib/format";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  ProgressBar,
  SectionHeader,
  Select,
  TablePager,
  TextInput,
  cn,
} from "./ui";

type Notify = (message: string, kind?: "success" | "error" | "info") => void;

function messageOf(error: unknown): string {
  if (error instanceof LauncherError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}

function whenLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// The client abbreviates many item names to its 15-character limit
// ("Mdk. Crackows +1", "Pln. Crackows", ...).  Migration 0139 stores the
// untruncated BG Wiki name as an item alias; this generated map lets the
// typeahead use those full names against the currently running server too.
import itemAliases from "../lib/itemAliases.generated.json";

const ARMORY_FULL_NAME_ALIASES = itemAliases as Record<string, string>;

// A handful of client names are themselves better known by the full name than
// by the usual abbreviation (the other direction from the generated map).
const ARMORY_REVERSE_ALIASES: ReadonlyArray<readonly [string, string]> = [
  ["mou. gages", "mousai gages"],
  ["mou. turban", "mousai turban"],
];

function armorySearchQueries(text: string): string[] {
  const lower = text.toLowerCase();
  const queries = [text];
  const add = (query: string) => {
    if (query && !queries.some((entry) => entry.toLowerCase() === query.toLowerCase())) {
      queries.push(query);
    }
  };
  for (const [abbreviated, full] of ARMORY_REVERSE_ALIASES) {
    if (lower.startsWith(abbreviated)) {
      add(full + text.slice(abbreviated.length));
    }
  }
  // The full-name map is generated from the 2068 abbreviated gear rows.  Cap
  // the fan-out so a two-character query cannot fire hundreds of requests.
  if (lower.length >= 3) {
    let expanded = 0;
    for (const [full, clientName] of Object.entries(ARMORY_FULL_NAME_ALIASES)) {
      if (!full.startsWith(lower)) continue;
      add(clientName);
      if (++expanded >= 5) break;
    }
  }
  if (lower === "mousai") add("Mou.");
  return queries;
}

function mergeArmoryItems(groups: ArmoryItem[][]): ArmoryItem[] {
  const byId = new Map<number, ArmoryItem>();
  for (const group of groups) {
    for (const item of group) {
      if (!byId.has(item.item_id)) byId.set(item.item_id, item);
    }
  }
  return [...byId.values()].slice(0, 40);
}

function jobMaskLabel(mask: number): string {
  if (!mask) return "No jobs listed";
  if (mask === 0x3fffff) return "All jobs";
  let count = 0;
  for (let value = mask; value; value &= value - 1) count += 1;
  return `${count} job${count === 1 ? "" : "s"}`;
}

const ARMORY_KINDS = [
  { value: "", label: "All gear" },
  { value: "weapon", label: "Weapons" },
  { value: "armor", label: "Armor" },
  { value: "accessory", label: "Accessories" },
  { value: "ammo", label: "Ammo" },
];

const DATA_TABS = [
  {
    key: "overview",
    label: "Overview",
    hint: "Merits, job points, profile, gil, travel, key items, mounts and currencies.",
    icon: Gauge,
  },
  {
    key: "merits",
    label: "Merits",
    hint:
      "Every merit menu in the game's order: the six general categories and each job's Group 1 and Group 2, with per-menu caps and point costs.",
    icon: ListChecks,
  },
  {
    key: "progression",
    label: "Progression",
    hint: "Mission ranks, jobs and Master Levels, skills, Trusts, RP paths and Oboro weapons.",
    icon: TrendingUp,
  },
  {
    key: "augments",
    label: "Augments",
    hint:
      "Ambuscade capes, Nolan mezzotints, Oseem glyptics, Skirmish, Sinister Reign, Moonshade, Magian and Shantotto's Ascension.",
    icon: Sparkles,
  },
  {
    key: "armory",
    label: "Armory",
    hint: "Buy gear into the inventory and review every purchase.",
    icon: Package,
  },
  {
    key: "items",
    label: "Items",
    hint: "Buy ninja tools, jug pets, consumables, ingredients and other general items by the piece or by the stack.",
    icon: ShoppingBasket,
  },
] as const;

type DataTab = (typeof DATA_TABS)[number]["key"];

const DATA_TAB_KEY = "fanxi.data.tab";
/** One saved size per table, so a future table can page independently. */
const ARMORY_PURCHASES_PAGE_SIZE_KEY = "fanxi.data.armory.purchases.pageSize";

const NO_PURCHASES: CharacterData["purchases"] = [];

function readDataTab(): DataTab {
  try {
    const saved = window.localStorage.getItem(DATA_TAB_KEY);
    return DATA_TABS.some((tab) => tab.key === saved) ? (saved as DataTab) : "overview";
  } catch {
    return "overview";
  }
}

function saveDataTab(tab: DataTab) {
  try {
    window.localStorage.setItem(DATA_TAB_KEY, tab);
  } catch {
    // The page still switches tabs when storage is unavailable.
  }
}

function CardHead({
  icon,
  title,
  hint,
  badge,
}: {
  icon: ReactNode;
  title: string;
  hint: string;
  badge?: ReactNode;
}) {
  return (
    <div className="data-card-head">
      <div className="data-card-icon">{icon}</div>
      <div className="data-card-title">
        <h3>{title}</h3>
        <p>{hint}</p>
      </div>
      {badge && <div className="data-card-badge">{badge}</div>}
    </div>
  );
}

export function DataPage({
  character,
  instances,
  notify,
}: {
  character: Character | null;
  instances: InstanceView[];
  notify: Notify;
}) {
  const characterId = character?.id ?? null;
  const [data, setData] = useState<CharacterData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [tab, setTab] = useState<DataTab>(readDataTab);
  const purchasePager = useTablePagination(
    data?.purchases ?? NO_PURCHASES,
    ARMORY_PURCHASES_PAGE_SIZE_KEY,
  );

  const [rank, setRank] = useState(1);
  const [currencyName, setCurrencyName] = useState("Sparks of Eminence");
  const [customCurrency, setCustomCurrency] = useState("");
  const [currencyAmount, setCurrencyAmount] = useState("1000");

  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [items, setItems] = useState<ArmoryItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [selected, setSelected] = useState<ArmoryItem | null>(null);
  const [addingId, setAddingId] = useState<number | null>(null);
  /** The item whose purchase the server refused because the bag is full. */
  const [inventoryFailure, setInventoryFailure] = useState<ArmoryItem | null>(null);
  const searchSeq = useRef(0);
  const typeaheadRef = useRef<HTMLDivElement | null>(null);
  const activeOptionRef = useRef<HTMLButtonElement | null>(null);
  const listId = "armory-item-list";

  const load = useCallback(async () => {
    if (!characterId) return;
    setLoading(true);
    setError("");
    try {
      const next = await backend.characterData(characterId);
      setData(next);
      setRank(Math.max(1, Math.min(10, next.mastery_rank || 1)));
    } catch (problem) {
      setError(messageOf(problem));
    } finally {
      setLoading(false);
    }
  }, [characterId]);

  useEffect(() => {
    setData(null);
    setItems([]);
    setSearched(false);
    setSelected(null);
    setInventoryFailure(null);
    setOpen(false);
    setQuery("");
    searchSeq.current += 1;
    void load();
  }, [load]);

  // Typeahead: wait for a short pause so a fast typist does not fire a request per
  // keystroke, and ignore a response that belongs to an older query.
  useEffect(() => {
    const text = query.trim();
    if (!characterId || !text) {
      searchSeq.current += 1;
      setItems([]);
      setSearched(false);
      setSearching(false);
      return;
    }
    const seq = ++searchSeq.current;
    setSearching(true);
    const timer = window.setTimeout(() => {
      const queries = armorySearchQueries(text);
      Promise.all(
        queries.map((query) => backend.searchArmory(characterId, query, kind || null)),
      )
        .then((results) => {
          if (seq !== searchSeq.current) return;
          setItems(mergeArmoryItems(results.map((result) => result.items)));
          setSearched(true);
          setActive(0);
        })
        .catch((problem) => {
          if (seq !== searchSeq.current) return;
          notify(messageOf(problem), "error");
          setItems([]);
          setSearched(true);
        })
        .finally(() => {
          if (seq === searchSeq.current) setSearching(false);
        });
    }, 160);
    return () => window.clearTimeout(timer);
  }, [characterId, query, kind, notify]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (typeaheadRef.current && !typeaheadRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  useEffect(() => {
    if (open) activeOptionRef.current?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function openTab(next: DataTab) {
    setTab(next);
    saveDataTab(next);
  }

  function onTabKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = DATA_TABS.findIndex((entry) => entry.key === tab);
    let next: DataTab | null = null;
    if (event.key === "ArrowRight") {
      next = DATA_TABS[(current + 1) % DATA_TABS.length].key;
    } else if (event.key === "ArrowLeft") {
      next = DATA_TABS[(current - 1 + DATA_TABS.length) % DATA_TABS.length].key;
    } else if (event.key === "Home") {
      next = DATA_TABS[0].key;
    } else if (event.key === "End") {
      next = DATA_TABS[DATA_TABS.length - 1].key;
    }
    if (!next) return;
    event.preventDefault();
    openTab(next);
    document.getElementById(`data-tab-${next}`)?.focus();
  }

  const runningPort = useMemo(() => {
    if (!characterId) return null;
    const live = instances.find(
      (instance) => instance.alive && Number(instance.character?.id) === characterId,
    );
    return live?.port ?? null;
  }, [instances, characterId]);

  async function reloadClient(): Promise<boolean> {
    if (runningPort === null) return false;
    try {
      await backend.sendCommand(runningPort, "//reload");
      return true;
    } catch {
      return false;
    }
  }

  async function run(
    action: string,
    payload: Record<string, unknown>,
    message: string,
    key?: string,
  ) {
    if (!characterId || busy) return;
    setBusy(key ?? action);
    setError("");
    try {
      const next = await backend.characterAction(characterId, action, payload);
      setData(next);
      const live = await reloadClient();
      notify(
        live ? `${message} — client reloaded` : `${message} — applies on the next zone-in`,
        "success",
      );
    } catch (problem) {
      if (isInventoryFull(problem)) {
        // The Armory card has its own dialog; this covers the other Data-page
        // buy paths (the Oboro weapon card) with the same instructions.
        setError(INVENTORY_FULL_MESSAGE);
        notify(INVENTORY_FULL_TOAST, "error");
      } else {
        notify(messageOf(problem), "error");
      }
    } finally {
      setBusy(null);
    }
  }

  function changeKind(next: string) {
    setKind(next);
    setSelected(null);
    setItems([]);
    setSearched(false);
    setOpen(Boolean(query.trim()));
  }

  function changeQuery(next: string) {
    setQuery(next);
    setSelected(null);
    setOpen(true);
  }

  function chooseItem(item: ArmoryItem) {
    setSelected(item);
    setQuery(item.name);
    setOpen(false);
    setActive(0);
  }

  function onTypeaheadKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (items.length) setActive((index) => Math.min(items.length - 1, index + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (open && items.length) setActive((index) => Math.max(0, index - 1));
    } else if (event.key === "Enter") {
      if (open && items.length) {
        event.preventDefault();
        chooseItem(items[Math.min(active, items.length - 1)]);
      }
    } else if (event.key === "Escape" || event.key === "Tab") {
      setOpen(false);
    }
  }

  async function addArmoryItem(item: ArmoryItem) {
    if (!characterId || addingId !== null) return;
    setAddingId(item.item_id);
    try {
      const result = await backend.characterAction(characterId, "armory", {
        item_id: item.item_id,
        quantity: 1,
      });
      if (result.data) setData(result.data);
      setInventoryFailure(null);
      const live = await reloadClient();
      const paid = result.item?.price ?? item.price;
      setItems((current) =>
        current.map((row) => (row.item_id === item.item_id ? { ...row, owned: true } : row)),
      );
      setSelected((current) =>
        current && current.item_id === item.item_id ? { ...current, owned: true } : current,
      );
      notify(
        live
          ? `${item.name} purchased for ${formatNumber(paid)} gil — client reloaded`
          : `${item.name} purchased for ${formatNumber(paid)} gil — it appears at the next zone-in`,
        "success",
      );
    } catch (problem) {
      if (isInventoryFull(problem)) {
        setInventoryFailure(item);
        notify(INVENTORY_FULL_TOAST, "error");
      } else if (problem instanceof LauncherError && problem.code === "already_owned") {
        setInventoryFailure(null);
        notify(`${item.name} is already in the character's possession`, "info");
        setItems((current) =>
          current.map((row) =>
            row.item_id === item.item_id ? { ...row, owned: true } : row,
          ),
        );
        setSelected((current) =>
          current && current.item_id === item.item_id ? { ...current, owned: true } : current,
        );
      } else if (problem instanceof LauncherError && problem.code === "insufficient_gil") {
        setInventoryFailure(null);
        notify(problem.message, "error");
      } else {
        setInventoryFailure(null);
        notify(messageOf(problem), "error");
      }
    } finally {
      setAddingId(null);
    }
  }

  function addCurrency(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = currencyName === "__custom" ? customCurrency.trim() : currencyName;
    const amount = Number(currencyAmount);
    if (!name) {
      notify("Give the currency a name first", "error");
      return;
    }
    if (!Number.isFinite(amount) || amount === 0) {
      notify("Enter a non-zero amount", "error");
      return;
    }
    void run("currencies", { name, amount }, `${formatNumber(amount)} ${name}`);
  }

  const activeIndex = items.length ? Math.min(active, items.length - 1) : 0;
  const trimmedQuery = query.trim();
  const selectedBlocked = Boolean(selected?.owned && selected.unique);
  const canAfford = selected ? (data?.gil ?? 0) >= selected.price : false;

  if (!character) {
    return (
      <div className="page">
        <SectionHeader
          eyebrow="Data"
          title="Character data"
          subtitle="Assign value to the parts of a character the server normally derives."
        />
        <EmptyState
          icon={<Gem size={22} />}
          title="No tenant selected"
          body="Choose a tenant in the bar at the top, then come back to assign its data."
        />
      </div>
    );
  }

  return (
    <div className="page">
      <SectionHeader
        eyebrow="Data"
        title="Character data"
        subtitle="Assign merits, job points, profile values, ranks, levels, skills, travel, currencies, key items, Trusts, RP paths, Oboro weapon augments, Ambuscade cape augments, Nolan mezzotints, Oseem Arcane Glyptics, Skirmish, Sinister Reign, Moonshade and Magian trials, Armory gear and general items to the selected tenant. The tabs keep each group one click away."
        actions={
          <>
            <Button
              variant="ghost"
              icon={<RefreshCw size={15} />}
              loading={loading}
              onClick={() => void load()}
            >
              Refresh
            </Button>
            {runningPort !== null ? (
              <Badge tone="success" dot>
                Client live
              </Badge>
            ) : (
              <Badge tone="neutral">Applied at zone-in</Badge>
            )}
          </>
        }
      />

      <Card className="data-character-card">
        <div className="data-character-id">
          <div className="avatar">{character.name.slice(0, 1).toUpperCase()}</div>
          <div>
            <strong>{character.name}</strong>
            <span>
              #{character.id} · {characterJobLabel(character)}
            </span>
          </div>
        </div>
        <p className="data-character-note">
          {runningPort !== null
            ? "The client is running: every apply also sends //reload so the change is visible immediately."
            : "The client is not running: values are written now and the next zone-in picks them up."}
        </p>
      </Card>

      {error && <ErrorBanner message={error} onClose={() => setError("")} />}

      {!data ? (
        <Card>
          <p className="data-note">{loading ? "Reading character data…" : "No data loaded."}</p>
        </Card>
      ) : (
        <>
          <div className="data-tabs-row">
            <div
              className="data-tabs"
              role="tablist"
              aria-label="Character data sections"
              onKeyDown={onTabKeyDown}
            >
              {DATA_TABS.map((entry) => {
                const Icon = entry.icon;
                return (
                  <button
                    key={entry.key}
                    type="button"
                    id={`data-tab-${entry.key}`}
                    role="tab"
                    aria-selected={tab === entry.key}
                    aria-controls={`data-panel-${entry.key}`}
                    tabIndex={tab === entry.key ? 0 : -1}
                    className={cn("data-tab", tab === entry.key && "active")}
                    onClick={() => openTab(entry.key)}
                  >
                    <Icon size={15} />
                    {entry.label}
                    {entry.key === "armory" && data.purchases.length > 0 ? (
                      <span className="data-tab-count">
                        {formatNumber(data.purchases.length)}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
            <p className="data-tabs-hint">
              {DATA_TABS.find((entry) => entry.key === tab)?.hint}
            </p>
          </div>

          <div
            className="data-grid"
            id={`data-panel-${tab}`}
            role="tabpanel"
            aria-labelledby={`data-tab-${tab}`}
          >
            {tab === "merits" && (
              <MeritEditor data={data} run={run} busy={busy} />
            )}

            {tab === "overview" && (
              <>
                <Card accent>
                  <CardHead
                    icon={<Award size={17} />}
                    title="Merits"
                    hint="Unspent merit points"
                    badge={
                      <Badge tone="accent">
                        {formatNumber(data.merits.points)}/{formatNumber(data.merits.cap)}
                      </Badge>
                    }
                  />
                  <div className="data-value">
                    {formatNumber(data.merits.points)}
                    <span> / {formatNumber(data.merits.cap)} unspent</span>
                  </div>
                  <ProgressBar value={pct(data.merits.points, data.merits.cap)} />
                  <p className="data-note">
                    {formatNumber(data.merits.spent ?? 0)} points assigned across{" "}
                    {data.merits.categories?.length ?? 0} merit menus.
                  </p>
                  <div className="data-actions">
                    <Button
                      loading={busy === "merits"}
                      disabled={busy !== null && busy !== "merits"}
                      onClick={() => void run("merits", { top_off: true }, "Merits topped off")}
                    >
                      Top off
                    </Button>
                    <Button
                      variant="secondary"
                      icon={<ListChecks size={14} />}
                      onClick={() => openTab("merits")}
                    >
                      Edit ranks
                    </Button>
                  </div>
                </Card>

                <Card>
                  <CardHead
                    icon={<Sparkles size={17} />}
                    title="Job Points"
                    hint={`${data.job_points.jobs} jobs`}
                    badge={<Badge tone="success">Capped</Badge>}
                  />
                  <div className="data-value">
                    {formatNumber(data.job_points.current)}
                    <span> JP · {formatNumber(data.job_points.spent)} spent</span>
                  </div>
                  <p className="data-note">
                    Every job is sent the same {formatNumber(data.job_points.capacity)} capacity,{" "}
                    {formatNumber(data.job_points.current)} current and{" "}
                    {formatNumber(data.job_points.spent)} spent block — the three job-master stars.
                  </p>
                  <div className="data-actions">
                    <Button
                      variant="secondary"
                      loading={busy === "job-points"}
                      disabled={busy !== null && busy !== "job-points"}
                      onClick={() =>
                        void run("job-points", {}, "All jobs are capped at 500 JP")
                      }
                    >
                      Cap all jobs
                    </Button>
                  </div>
                </Card>

                <Card>
                  <CardHead
                    icon={<UserRoundCog size={17} />}
                    title="Profile"
                    hint="Status → Profile → Mastery Rank"
                    badge={<Badge tone="gold">Rank {data.mastery_rank}</Badge>}
                  />
                  <div className="data-form-row">
                    <Select
                      value={rank}
                      onChange={(event) => setRank(Number(event.target.value))}
                      aria-label="Mastery Rank"
                    >
                      {Array.from({ length: data.mastery_rank_max }, (_, index) => index + 1).map(
                        (value) => (
                          <option key={value} value={value}>
                            Mastery Rank {value}
                          </option>
                        ),
                      )}
                    </Select>
                    <Button
                      loading={busy === "mastery-rank"}
                      disabled={busy !== null && busy !== "mastery-rank"}
                      onClick={() =>
                        void run("mastery-rank", { rank }, `Mastery Rank set to ${rank}`)
                      }
                    >
                      Set rank
                    </Button>
                  </div>
                  <p className="data-note">
                    Retail keeps this 0–10. It is the byte the Profile page prints and the number
                    shown beside a mentor&apos;s name in the assist channel.
                  </p>
                </Card>

                <Card>
                  <CardHead
                    icon={<Coins size={17} />}
                    title="Gil"
                    hint="Character wallet"
                    badge={<Badge tone="gold">{formatNumber(data.gil)}</Badge>}
                  />
                  <div className="data-value">
                    {formatNumber(data.gil)}
                    <span> gil</span>
                  </div>
                  <p className="data-note">
                    Top off sets the wallet to {formatNumber(data.gil_max)} and rewrites the
                    inventory&apos;s gil row in the same transaction.
                  </p>
                  <div className="data-actions">
                    <Button
                      loading={busy === "gil"}
                      disabled={busy !== null && busy !== "gil"}
                      onClick={() => void run("gil", { top_off: true }, "Gil topped off")}
                    >
                      Top off
                    </Button>
                  </div>
                </Card>

                <Card>
                  <CardHead
                    icon={<MapPin size={17} />}
                    title="Travel"
                    hint="Home Points and Survival Guides"
                    badge={
                      <Badge tone={data.home_points.registered >= data.home_points.total ? "success" : "warning"}>
                        {formatNumber(data.home_points.registered)}/{formatNumber(data.home_points.total)}
                      </Badge>
                    }
                  />
                  <div className="data-row">
                    <span>Home Points registered</span>
                    <strong>
                      {formatNumber(data.home_points.registered)}/{formatNumber(data.home_points.total)}
                    </strong>
                  </div>
                  <div className="data-row">
                    <span>Survival Guides</span>
                    <strong>{formatNumber(data.survival_guides.total)} open</strong>
                  </div>
                  <p className="data-note">
                    Survival Guides are all open already; registering the Home Point network fills
                    the menu the client uses for warp and Retrace.
                  </p>
                  <div className="data-actions">
                    <Button
                      variant="secondary"
                      loading={busy === "home-points"}
                      disabled={busy !== null && busy !== "home-points"}
                      onClick={() =>
                        void run("home-points", {}, "Every Home Point registered")
                      }
                    >
                      Register all
                    </Button>
                  </div>
                </Card>

                <Card>
                  <CardHead
                    icon={<KeyRound size={17} />}
                    title="Key Items"
                    hint={`${data.key_items.tables} permanent tables`}
                    badge={<Badge tone="success">Granted</Badge>}
                  />
                  <p className="data-note">
                    The zone-in burst already sends both bitmaps for all{" "}
                    {data.key_items.tables} permanent key-item tables. Re-issue asks the server to
                    send them again to a live client.
                  </p>
                  <div className="data-actions">
                    <Button
                      variant="secondary"
                      loading={busy === "key-items"}
                      disabled={busy !== null && busy !== "key-items"}
                      onClick={() => void run("key-items", {}, "Key items re-issued")}
                    >
                      Re-issue
                    </Button>
                  </div>
                </Card>

                <Card>
                  <CardHead
                    icon={<Sparkles size={17} />}
                    title="Mounts"
                    hint={`${data.mounts?.count ?? 0} in the client's table`}
                    badge={<Badge tone="success">All available</Badge>}
                  />
                  <p className="data-note">
                    Every mount the client knows is unlocked when the box zones in
                    {data.mounts?.current ? ` — riding ${data.mounts.current} right now` : ""}.
                    Get all mounts re-sends the unlock table to a live client; an offline character
                    finds them all at its next zone-in.
                  </p>
                  <div className="data-actions">
                    <Button
                      variant="secondary"
                      loading={busy === "mounts"}
                      disabled={busy !== null && busy !== "mounts"}
                      onClick={() => void run("mounts", {}, "All mounts unlocked")}
                    >
                      Get all mounts
                    </Button>
                    {data.mounts?.last && (
                      <span className="data-note">Last called: {data.mounts.last}</span>
                    )}
                  </div>
                </Card>

                <Card>
                  <CardHead
                    icon={<Gem size={17} />}
                    title="Currencies"
                    hint="Named balances kept on the server"
                    badge={<Badge>{data.currencies.length}</Badge>}
                  />
                  {data.currencies.length === 0 ? (
                    <p className="data-note">No currencies added yet.</p>
                  ) : (
                    <ul className="data-list">
                      {data.currencies.map((currency) => (
                        <li key={currency.name}>
                          <span>{currency.name}</span>
                          <strong>{formatNumber(currency.amount)}</strong>
                        </li>
                      ))}
                    </ul>
                  )}
                  <form className="data-form" onSubmit={addCurrency}>
                    <Select
                      value={currencyName}
                      onChange={(event) => setCurrencyName(event.target.value)}
                      aria-label="Currency"
                    >
                      {data.currency_catalog.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                      <option value="__custom">Custom…</option>
                    </Select>
                    {currencyName === "__custom" && (
                      <TextInput
                        value={customCurrency}
                        onChange={(event) => setCustomCurrency(event.target.value)}
                        placeholder="Currency name"
                        maxLength={48}
                        aria-label="Custom currency name"
                      />
                    )}
                    <TextInput
                      type="number"
                      value={currencyAmount}
                      onChange={(event) => setCurrencyAmount(event.target.value)}
                      min={1}
                      step={1}
                      aria-label="Amount"
                    />
                    <Button
                      type="submit"
                      variant="secondary"
                      loading={busy === "currencies"}
                      disabled={busy !== null && busy !== "currencies"}
                    >
                      Add
                    </Button>
                  </form>
                </Card>
              </>
            )}

            {tab === "progression" && (
              <ProgressCards data={data} run={run} busy={busy} />
            )}

            {tab === "augments" && (
              <>
                <AmbuscadeCapes data={data} run={run} busy={busy} />

                <NolanMezzotint data={data} run={run} busy={busy} />

                <OseemGlyptics data={data} run={run} busy={busy} />

                <SkirmishAugments data={data} run={run} busy={busy} />

                <SinisterReign data={data} run={run} busy={busy} />

                <MoonshadeEarring data={data} run={run} busy={busy} />

                <MagianMoogle data={data} run={run} busy={busy} />

                <ShantottoAscension data={data} run={run} busy={busy} />
              </>
            )}

            {tab === "armory" && (
              <>
                <Card className="span-2">
                  <CardHead
                    icon={<PackagePlus size={17} />}
                    title="Armory"
                    hint="Search every gear item, check its BG Wiki icon and price, then buy it into the inventory"
                    badge={<Badge>{formatNumber(data.purchases.length)} purchased</Badge>}
                  />
                  <div className="armory-search">
                    <div className="armory-typeahead" ref={typeaheadRef}>
                      <div className="input-with-icon">
                        {searching ? <Loader2 className="spin" size={15} /> : <Search size={15} />}
                        <TextInput
                          value={query}
                          onChange={(event) => changeQuery(event.target.value)}
                          onFocus={() => {
                            if (trimmedQuery) setOpen(true);
                          }}
                          onKeyDown={onTypeaheadKeyDown}
                          placeholder="Start typing an item name…"
                          aria-label="Item name"
                          role="combobox"
                          aria-autocomplete="list"
                          aria-expanded={open}
                          aria-controls={listId}
                          aria-activedescendant={
                            open && items.length ? `${listId}-${items[activeIndex].item_id}` : undefined
                          }
                          autoComplete="off"
                        />
                      </div>
                      {open && trimmedQuery && (
                        <div className="armory-menu" id={listId} role="listbox" aria-label="Item suggestions">
                          {searching && items.length === 0 && (
                            <p className="armory-menu-note">Searching…</p>
                          )}
                          {!searching && searched && items.length === 0 && (
                            <p className="armory-menu-note">No items matched “{trimmedQuery}”.</p>
                          )}
                          {items.map((item, index) => (
                            <button
                              key={item.item_id}
                              id={`${listId}-${item.item_id}`}
                              ref={index === activeIndex ? activeOptionRef : undefined}
                              type="button"
                              role="option"
                              aria-selected={index === activeIndex}
                              className={
                                index === activeIndex ? "armory-option is-active" : "armory-option"
                              }
                              onMouseEnter={() => setActive(index)}
                              onMouseDown={(event) => event.preventDefault()}
                              onClick={() => chooseItem(item)}
                            >
                              <ItemIcon name={item.name} size={28} />
                              <span className="armory-option-text">
                                <strong>{item.name}</strong>
                                <small>
                                  {slotLabel(item.equip_slot)} · Lv. {item.level}
                                  {item.item_level > item.level ? ` · iLv ${item.item_level}` : ""}
                                  {item.prime_final
                                    ? ` · Prime final · stage ${item.prime_stage ?? 5} of ${item.prime_stages ?? 5}`
                                    : item.rema_final
                                      ? " · final afterglow form"
                                      : ""}
                                </small>
                              </span>
                              {(item.prime_final || item.rema_final) && (
                                <Badge tone="gold">Final</Badge>
                              )}
                              {item.owned && item.unique ? (
                                <Badge tone="success">Owned</Badge>
                              ) : item.owned ? (
                                <Badge>Owned</Badge>
                              ) : (
                                <span className="armory-option-price">
                                  {formatNumber(item.price)} gil
                                </span>
                              )}
                            </button>
                          ))}
                          {items.length > 0 && (
                            <p className="armory-menu-foot">
                              ↑↓ to move · Enter to select{searching ? " · searching…" : ""}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                    <Select
                      value={kind}
                      onChange={(event) => changeKind(event.target.value)}
                      aria-label="Item kind"
                    >
                      {ARMORY_KINDS.map((entry) => (
                        <option key={entry.value} value={entry.value}>
                          {entry.label}
                        </option>
                      ))}
                    </Select>
                  </div>

                  {selected ? (
                    <div className="armory-picked">
                      <div className="armory-picked-art">
                        <ItemIcon name={selected.name} size={72} />
                      </div>
                      <div className="armory-picked-info">
                        <div className="armory-picked-head">
                          <div>
                            <h4>{selected.name}</h4>
                            <span className="data-item-id">#{selected.item_id}</span>
                          </div>
                          <div className="data-flags">
                            {selected.prime_final && <Badge tone="gold">Prime final</Badge>}
                            {selected.rema_final && <Badge tone="gold">REMA final</Badge>}
                            {selected.rare === 1 && <Badge tone="warning">Rare</Badge>}
                            {selected.ex === 1 && <Badge>Ex</Badge>}
                            {selected.owned && <Badge tone="success">Owned</Badge>}
                          </div>
                        </div>
                        <div className="armory-picked-meta">
                          <span>{slotLabel(selected.equip_slot)}</span>
                          <span>Lv. {selected.level}</span>
                          {selected.item_level > selected.level && (
                            <span>iLv {selected.item_level}</span>
                          )}
                          {selected.prime_final && (
                            <span>
                              Stage {selected.prime_stage ?? 5} of {selected.prime_stages ?? 5}
                            </span>
                          )}
                          {selected.rema_final && <span>Afterglow · final upgrade</span>}
                          <span>{jobMaskLabel(selected.jobs)}</span>
                        </div>
                        {selected.description && <p className="data-note">{selected.description}</p>}
                        {selected.prime_final && (
                          <p className="data-note">
                            Prime weapons are sold only in their final iLvl 119 III form.
                            Earlier stages are upgraded to it at purchase.
                          </p>
                        )}
                        {selected.rema_final && (
                          <p className="data-note">
                            REMA weapons are sold only in their final afterglow form. Earlier
                            stages are upgraded to it at purchase.
                          </p>
                        )}
                        {selectedBlocked ? (
                          <div className="armory-blocked">
                            <Badge tone="success">Currently owned</Badge>
                            <span>
                              Rare — only one copy can be held, so the Armory will not sell
                              another.
                            </span>
                          </div>
                        ) : (
                          <div className="armory-buy">
                            <div className="armory-price">
                              <span>Purchase price</span>
                              <strong>
                                {formatNumber(selected.price)} <small>gil</small>
                              </strong>
                            </div>
                            <Button
                              loading={addingId === selected.item_id}
                              disabled={addingId !== null || !canAfford}
                              onClick={() => void addArmoryItem(selected)}
                            >
                              {selected.owned ? "Buy another" : "Purchase"}
                            </Button>
                            {!canAfford && (
                              <p className="data-note">
                                Not enough gil — top off the wallet above.
                              </p>
                            )}
                            {selected.owned && !selected.rare && selected.ex === 1 && (
                              <p className="data-note">
                                Ex — cannot be traded or sold, but you may hold more than one copy.
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="data-note">
                      Every weapon, shield, armour, accessory and ammo item is searchable. Pick one
                      to see its BG Wiki icon, level, price and whether the character already holds
                      it.
                    </p>
                  )}

                  <h4 className="data-subhead">Purchased</h4>
                  {data.purchases.length === 0 ? (
                    <p className="data-note">Nothing has been purchased yet.</p>
                  ) : (
                    <>
                      <div className="data-table-wrap">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Item</th>
                              <th>Qty</th>
                              <th>Price</th>
                              <th>When</th>
                              <th>Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {purchasePager.pageRows.map((purchase) => (
                              <tr key={purchase.id}>
                                <td>
                                  <strong>{purchase.name}</strong>
                                  <span className="data-item-id">#{purchase.item_id}</span>
                                  {purchase.prime_final && (
                                    <Badge tone="gold">
                                      Prime final · stage {purchase.prime_stage ?? 5}
                                    </Badge>
                                  )}
                                  {purchase.rema_final && (
                                    <Badge tone="gold">REMA final</Badge>
                                  )}
                                </td>
                                <td>{purchase.quantity}</td>
                                <td>
                                  {purchase.price > 0
                                    ? `${formatNumber(purchase.price)} gil`
                                    : "—"}
                                </td>
                                <td>{whenLabel(purchase.created_at)}</td>
                                <td>
                                  {purchase.owned ? (
                                    <Badge tone="success">In possession</Badge>
                                  ) : (
                                    <Badge tone="warning">Not in bags</Badge>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <TablePager
                        page={purchasePager.page}
                        pageCount={purchasePager.pageCount}
                        pageSize={purchasePager.pageSize}
                        total={purchasePager.total}
                        onPageChange={purchasePager.setPage}
                        onPageSizeChange={purchasePager.setPageSize}
                        label="Purchase history pages"
                      />
                    </>
                  )}
                </Card>
              </>
            )}

            {tab === "items" && characterId !== null && (
              <ItemsCatalog
                characterId={characterId}
                gil={data.gil}
                categories={data.item_categories ?? []}
                notify={notify}
                onData={setData}
                reloadClient={reloadClient}
              />
            )}
          </div>
        </>
      )}

      {inventoryFailure && (
        <InventoryFullDialog
          itemName={inventoryFailure.name}
          onRetry={() => void addArmoryItem(inventoryFailure)}
          retrying={addingId === inventoryFailure.item_id}
          onClose={() => setInventoryFailure(null)}
        />
      )}
    </div>
  );
}
