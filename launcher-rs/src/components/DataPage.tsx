import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent, ReactNode } from "react";
import {
  Award,
  Coins,
  Gem,
  KeyRound,
  Loader2,
  MapPin,
  Package,
  PackagePlus,
  RefreshCw,
  Search,
  Sparkles,
  UserRoundCog,
} from "lucide-react";
import type { ArmoryItem, Character, CharacterData, InstanceView } from "../types";
import { backend, LauncherError } from "../lib/api";
import { ProgressCards } from "./ProgressCards";
import { formatNumber, jobName, pct, slotLabel } from "../lib/format";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  ProgressBar,
  SectionHeader,
  Select,
  TextInput,
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

/** BG Wiki stores each item's 32x32 icon next to its page, as <name>_icon.png.
 * Special:FilePath resolves the file name without us having to reproduce the
 * wiki's MD5 directory split. */
function bgwikiIcon(name: string): string {
  const file = `${name.trim().replace(/\s+/g, "_")}_icon.png`;
  return `https://www.bg-wiki.com/ffxi/Special:FilePath/${encodeURIComponent(file)}`;
}

function ItemIcon({ name, size = 32 }: { name: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [name]);
  if (failed) {
    return (
      <span
        className="armory-art armory-art-empty"
        style={{ width: size, height: size }}
        aria-hidden="true"
      >
        <Package size={Math.max(14, Math.round(size * 0.45))} />
      </span>
    );
  }
  return (
    <img
      className="armory-art"
      src={bgwikiIcon(name)}
      width={size}
      height={size}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
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
      backend
        .searchArmory(characterId, text, kind || null)
        .then((result) => {
          if (seq !== searchSeq.current) return;
          setItems(result.items);
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
      await backend.sendCommand(runningPort, "!reload");
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
      notify(messageOf(problem), "error");
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
      if (problem instanceof LauncherError && problem.code === "already_owned") {
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
        notify(problem.message, "error");
      } else {
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
  const selectedBlocked = Boolean(selected?.owned && selected.exclusive);
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
        subtitle="Assign merits, job points, profile values, ranks, levels, skills, travel, currencies, key items, Trusts, RP paths and Armory gear to the selected tenant."
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
              #{character.id} · {jobName(character.main_job)} Lv {character.main_level ?? "?"}
            </span>
          </div>
        </div>
        <p className="data-character-note">
          {runningPort !== null
            ? "The client is running: every apply also sends !reload so the change is visible immediately."
            : "The client is not running: values are written now and the next zone-in picks them up."}
        </p>
      </Card>

      {error && <ErrorBanner message={error} onClose={() => setError("")} />}

      {!data ? (
        <Card>
          <p className="data-note">{loading ? "Reading character data…" : "No data loaded."}</p>
        </Card>
      ) : (
        <div className="data-grid">
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
            <div className="data-actions">
              <Button
                loading={busy === "merits"}
                disabled={busy !== null && busy !== "merits"}
                onClick={() => void run("merits", { top_off: true }, "Merits topped off")}
              >
                Top off
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

          <ProgressCards data={data} run={run} busy={busy} />

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
                          </small>
                        </span>
                        {item.owned && item.exclusive ? (
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
                    <span>{jobMaskLabel(selected.jobs)}</span>
                  </div>
                  {selected.description && <p className="data-note">{selected.description}</p>}
                  {selectedBlocked ? (
                    <div className="armory-blocked">
                      <Badge tone="success">Currently owned</Badge>
                      <span>
                        Rare/Ex — only one copy can be held, so the Armory will not sell
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
                    {data.purchases.map((purchase) => (
                      <tr key={purchase.id}>
                        <td>
                          <strong>{purchase.name}</strong>
                          <span className="data-item-id">#{purchase.item_id}</span>
                        </td>
                        <td>{purchase.quantity}</td>
                        <td>{purchase.price > 0 ? `${formatNumber(purchase.price)} gil` : "—"}</td>
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
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
