//! Item stats for the Gear page: GearSwap set previews and the live worn set.
//!
//! GearSwap stores item names, and the client's item resources carry the same tooltip the game
//! shows. The launcher asks the running client for those descriptions (through the control port's
//! generic `lua` command), keeps the readable `DEF:121 / HP+74 / Accuracy+64` lines for the slot
//! cards, and normalizes every numeric line plus the set's augment strings into a flat stat list
//! the Gear page can total. Augments are only strings in a library, so this is the one place that
//! knows both sides of an item's stats. The live EquipViewer asks by equipped item id and reads
//! each copy's augment text from the character's bag rows, so the sheet follows the actual copy
//! instead of a same-named item elsewhere.

use std::sync::LazyLock;

use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// One requested slot, either from a GearSwap set or the live worn gear. The same item can appear
/// in two slots (earrings, rings) with different augments, so requests are kept per slot rather
/// than deduplicated by name.
#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GearStatRequest {
    pub slot: String,
    pub name: String,
    #[serde(default)]
    pub augments: Vec<String>,
    /// The equipped item's id, when the caller has one (the live EquipViewer does). Asking the
    /// resource table by id avoids a name lookup that can miss a localized or suffixed line.
    #[serde(default)]
    pub id: u32,
}

/// One normalized stat line, either from the item's own description or an augment string.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearStat {
    /// Stable, case-insensitive key used to total the same stat across items.
    pub key: String,
    /// The label shown in the UI.
    pub label: String,
    pub value: i64,
    /// Percent stats are kept apart from flat stats with the same label (`HP+80` vs `HP+10%`).
    pub percent: bool,
    /// Preferred display order; lower comes first.
    pub order: i32,
}

/// Per-slot result. `found` is false when the client has no item with that name; the augment stats
/// still make it into `stats`, so a custom item does not disappear from the totals.
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GearItemStats {
    pub slot: String,
    pub name: String,
    pub found: bool,
    pub id: u32,
    pub level: i64,
    pub item_level: i64,
    /// Readable base-stat lines from the client tooltip, excluding conditional Set/Pet/Unity lines.
    pub base_lines: Vec<String>,
    /// The tooltip's numeric stats on their own.
    pub base_stats: Vec<GearStat>,
    /// The numeric stats the slot's augment strings add.
    pub augment_stats: Vec<GearStat>,
    /// Base stats and augment stats together, normalized for totaling.
    pub stats: Vec<GearStat>,
}

#[derive(Clone, Debug, Default)]
pub struct ClientItem {
    pub id: u32,
    pub name: String,
    pub description: String,
    pub level: i64,
    pub item_level: i64,
}

/// A tooltip stat: a label, an optional sign, a whole number and an optional percent. The label may
/// contain spaces, periods, quotes, parentheses and slashes, but never a digit or a sign, so the
/// expression cannot swallow the next stat on the same line.
static SIGNED_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r#"(?i)(?P<label>["A-Za-z][A-Za-z .,'"()/&_-]*?)\s*(?P<sign>[+-])\s*(?P<value>\d+)\s*(?P<pct>%)?"#,
    )
    .expect("valid signed-stat regular expression")
});

/// A colon stat (`DEF:121`, `DMG:40`, `Delay:224`), with an optional sign for older tooltips.
static COLON_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r#"(?i)(?P<label>["A-Za-z][A-Za-z .,'"()/&_-]*?)\s*:\s*(?P<sign>[+-])?\s*(?P<value>\d+)\s*(?P<pct>%)?"#,
    )
    .expect("valid colon-stat regular expression")
});

/// Tooltips sometimes spell a penalty out ("Spell interruption rate down 5%"). Turn the word into
/// the sign the other lines use before matching.
static DOWN_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:down|lower(?:ed)?|reduced?|decreas(?:e|ed))(?:\s+by)?\s+(\d+)")
        .expect("valid negative-stat regular expression")
});

/// `Set:` bonuses depend on other pieces, the pet/avatar lines belong to another entity and
/// `Unity Ranking:` values depend on Unity standing. They are not one piece's player stats, so the
/// card stops before them and the totals never see them.
static MARKER_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)(?:^|\s)(Set:|Pet:|Avatar:|Automaton:|Wyvern:|Luopan:|Fellow:|Unity Ranking:)")
        .expect("valid conditional-stat regular expression")
});

/// The `lua` code that asks the client for every item description in one game-thread call.
/// Slots with an item id ask the resource table by id; library sets fall back to the name. Names
/// are escaped as Lua strings; a name cannot break out of the list.
pub fn item_query_code(items: &[GearStatRequest]) -> String {
    let mut code = String::from(
        "local res = xi and xi.res\n\
         if not res then return {} end\n\
         local keys = {",
    );
    for (index, item) in items.iter().enumerate() {
        if index > 0 {
            code.push(',');
        }
        if item.id > 0 {
            code.push_str(&item.id.to_string());
        } else {
            code.push_str(&lua_quote(&item.name));
        }
    }
    code.push_str(
        "}\n\
         local out = {}\n\
         for i, key in ipairs(keys) do\n\
           local ok, item\n\
           if type(key) == 'number' then\n\
             ok, item = pcall(res.item, key)\n\
           else\n\
             ok, item = pcall(res.item_by_name, key, 2)\n\
           end\n\
           if ok and item then\n\
             local name = type(key) == 'string' and key or ''\n\
             if item.name_utf8 and item.name_utf8.en then name = item.name_utf8.en end\n\
             local description = ''\n\
             if item.description_utf8 and item.description_utf8.en then description = item.description_utf8.en end\n\
             out[i] = { id = item.id or 0, name = name, description = description, level = item.level or 0, item_level = item.item_level or 0 }\n\
           elseif type(key) == 'string' then\n\
             out[i] = { name = key }\n\
           else\n\
             out[i] = { name = '' }\n\
           end\n\
         end\n\
         return out",
    );
    code
}

fn lua_quote(value: &str) -> String {
    let mut out = String::from("\"");
    for ch in value.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            ch if ch.is_control() => {
                // The addon's Lua 5.1 does not support \x; drop uncommon control characters.
                out.push(' ');
            }
            other => out.push(other),
        }
    }
    out.push('"');
    out
}

/// Read the client's `lua` reply into one optional entry per request, preserving order. A missing
/// item answers `{name = "..."}` and becomes `None`.
pub fn parse_lua_reply(reply: &Value) -> Vec<Option<ClientItem>> {
    let Some(rows) = reply.as_array() else {
        return Vec::new();
    };
    rows.iter()
        .map(|row| {
            let id = row.get("id").and_then(Value::as_u64).unwrap_or(0) as u32;
            let description = row
                .get("description")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            if id == 0 && description.is_empty() {
                return None;
            }
            Some(ClientItem {
                id,
                name: row
                    .get("name")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                description,
                level: row.get("level").and_then(value_i64).unwrap_or(0),
                item_level: row.get("item_level").and_then(value_i64).unwrap_or(0),
            })
        })
        .collect()
}

fn value_i64(value: &Value) -> Option<i64> {
    value
        .as_i64()
        .or_else(|| value.as_u64().and_then(|number| i64::try_from(number).ok()))
        .or_else(|| value.as_str().and_then(|text| text.parse().ok()))
}

/// Combine the client descriptions with each slot's augment strings.
pub fn build_stats(
    requests: &[GearStatRequest],
    resolved: &[Option<ClientItem>],
) -> Vec<GearItemStats> {
    requests
        .iter()
        .enumerate()
        .map(|(index, request)| {
            let client = resolved.get(index).and_then(|item| item.as_ref());
            let (base_lines, base_stats) = client
                .map(|item| parse_description(&item.description))
                .unwrap_or_default();
            let augment_stats: Vec<GearStat> = request
                .augments
                .iter()
                .flat_map(|augment| parse_augment(augment))
                .collect();
            let mut stats = base_stats.clone();
            stats.extend(augment_stats.iter().cloned());
            GearItemStats {
                slot: request.slot.clone(),
                name: client
                    .map(|item| item.name.trim().to_string())
                    .filter(|name| !name.is_empty())
                    .unwrap_or_else(|| request.name.clone()),
                found: client.is_some(),
                id: client.map(|item| item.id).unwrap_or(0),
                level: client.map(|item| item.level).unwrap_or(0),
                item_level: client.map(|item| item.item_level).unwrap_or(0),
                base_lines,
                base_stats,
                augment_stats,
                stats,
            }
        })
        .collect()
}

/// The client tooltip without its conditional trailing blocks, plus every numeric stat it lists.
pub fn parse_description(text: &str) -> (Vec<String>, Vec<GearStat>) {
    let lines = player_lines(text);
    let mut stats = Vec::new();
    for line in &lines {
        // Aftermath and Latent Effect lines belong on the card but are conditional bonuses, not
        // stats the set always has. Excluding them keeps the totals honest.
        if is_conditional_line(line) {
            continue;
        }
        stats.extend(parse_stat_text(line));
    }
    (lines, stats)
}

fn is_conditional_line(line: &str) -> bool {
    let lower = line.trim().to_lowercase();
    lower.starts_with("aftermath:")
        || lower.starts_with("latent effect:")
        || lower.starts_with("additional effect:")
}

fn player_lines(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    for raw in text.lines() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }
        if let Some(marker) = MARKER_RE.find(line) {
            let keep = line[..marker.start()].trim();
            if !keep.is_empty() {
                out.push(keep.to_string());
            }
            break;
        }
        out.push(line.to_string());
    }
    out
}

/// Parse every stat in a single augment string. GearSwap lets augments pack two lines together with
/// a slash (`Mag. Acc+20 /Mag. Dmg.+20`) or with spaces (`Accuracy+20 Attack+20`); the same expression
/// finds each pair without splitting the string.
pub fn parse_augment(augment: &str) -> Vec<GearStat> {
    parse_stat_text(augment)
}

fn parse_stat_text(text: &str) -> Vec<GearStat> {
    let normalized = DOWN_RE.replace_all(text, "-$1");
    let mut out = Vec::new();
    for captures in COLON_RE.captures_iter(&normalized) {
        let Some(label) = captures.name("label").map(|value| value.as_str()) else {
            continue;
        };
        let Some(value) = captures
            .name("value")
            .and_then(|value| value.as_str().parse::<i64>().ok())
        else {
            continue;
        };
        let negative = captures
            .name("sign")
            .map(|sign| sign.as_str() == "-")
            .unwrap_or(false);
        let percent = captures.name("pct").is_some();
        if let Some(stat) = make_stat(label, if negative { -value } else { value }, percent) {
            out.push(stat);
        }
    }
    for captures in SIGNED_RE.captures_iter(&normalized) {
        let Some(label) = captures.name("label").map(|value| value.as_str()) else {
            continue;
        };
        let Some(value) = captures
            .name("value")
            .and_then(|value| value.as_str().parse::<i64>().ok())
        else {
            continue;
        };
        let negative = captures
            .name("sign")
            .map(|sign| sign.as_str() == "-")
            .unwrap_or(false);
        let percent = captures.name("pct").is_some();
        if let Some(stat) = make_stat(label, if negative { -value } else { value }, percent) {
            out.push(stat);
        }
    }
    out
}

fn make_stat(raw_label: &str, value: i64, source_percent: bool) -> Option<GearStat> {
    if value == 0 {
        return None;
    }
    let (key, label, order) = canonical_label(raw_label)?;
    let percent = source_percent || percent_default(&key);
    Some(GearStat {
        key,
        label,
        value,
        percent,
        order,
    })
}

fn canonical_label(raw: &str) -> Option<(String, String, i32)> {
    let cleaned = clean_label(raw);
    if cleaned.is_empty() {
        return None;
    }
    let lower = cleaned.to_lowercase();
    if let Some((_, key, label)) = ALIASES
        .iter()
        .find(|(alias, _, _)| *alias == lower.as_str())
    {
        return Some(((*key).to_string(), (*label).to_string(), order_for(key)));
    }
    let label = capitalize(&cleaned);
    Some((lower, label, 9000))
}

fn clean_label(raw: &str) -> String {
    let mut text = raw
        .trim()
        .trim_matches(|ch: char| matches!(ch, '"' | '\'' | '“' | '”'))
        .trim()
        .replace('"', "")
        .replace('“', "")
        .replace('”', "");
    text = text.split_whitespace().collect::<Vec<_>>().join(" ");
    while text.ends_with('.') {
        text.pop();
    }
    text.trim().to_string()
}

fn capitalize(value: &str) -> String {
    let mut chars = value.chars();
    match chars.next() {
        Some(first) => format!("{}{}", first.to_uppercase(), chars.as_str()),
        None => String::new(),
    }
}

fn percent_default(key: &str) -> bool {
    matches!(
        key,
        "haste"
            | "fast cast"
            | "quick magic"
            | "cure potency"
            | "cure potency ii"
            | "cure potency received"
            | "damage taken"
            | "physical damage taken"
            | "magic damage taken"
            | "physical damage taken ii"
            | "magic damage taken ii"
            | "breath damage taken"
            | "ranged damage taken"
            | "physical damage limit"
            | "weapon skill damage"
            | "magic burst damage"
            | "magic burst damage ii"
            | "double attack"
            | "triple attack"
            | "quadruple attack"
            | "dual wield"
            | "enhancing magic duration"
            | "enfeebling magic duration"
            | "magic critical hit rate"
            | "critical hit rate"
            | "critical hit damage"
            | "spell interruption rate"
            | "shield block rate"
            | "movement speed"
            | "song duration"
    )
}

fn order_for(key: &str) -> i32 {
    ORDER
        .iter()
        .position(|known| *known == key)
        .map(|index| index as i32 * 10)
        .unwrap_or(9000)
}

/// `order` is the preferred scan order for the Set totals: attributes, weapons, combat, magic,
/// skills, resistances, then everything the table does not name.
const ORDER: &[&str] = &[
    "def",
    "hp",
    "mp",
    "str",
    "dex",
    "vit",
    "agi",
    "int",
    "mnd",
    "chr",
    "attack",
    "accuracy",
    "ranged attack",
    "ranged accuracy",
    "magic atk. bonus",
    "magic accuracy",
    "magic accuracy skill",
    "magic damage",
    "evasion",
    "magic evasion",
    "magic def. bonus",
    "hand-to-hand skill",
    "dagger skill",
    "sword skill",
    "great sword skill",
    "axe skill",
    "great axe skill",
    "scythe skill",
    "polearm skill",
    "katana skill",
    "great katana skill",
    "club skill",
    "staff skill",
    "archery skill",
    "marksmanship skill",
    "throwing skill",
    "haste",
    "damage taken",
    "physical damage taken",
    "physical damage taken ii",
    "magic damage taken",
    "magic damage taken ii",
    "breath damage taken",
    "ranged damage taken",
    "physical damage limit",
    "cure potency",
    "cure potency ii",
    "cure potency received",
    "fast cast",
    "quick magic",
    "store tp",
    "dual wield",
    "double attack",
    "triple attack",
    "quadruple attack",
    "subtle blow",
    "subtle blow ii",
    "weapon skill damage",
    "weapon skill accuracy",
    "tp bonus",
    "magic burst damage",
    "magic burst damage ii",
    "skillchain bonus",
    "enmity",
    "refresh",
    "refresh potency",
    "regen",
    "regen potency",
    "regen duration",
    "enfeebling magic effect",
    "enfeebling magic duration",
    "enfeebling magic skill",
    "enhancing magic duration",
    "enhancing magic skill",
    "healing magic skill",
    "elemental magic skill",
    "divine magic skill",
    "dark magic skill",
    "singing skill",
    "string instrument skill",
    "wind instrument skill",
    "ninjutsu skill",
    "blue magic skill",
    "geomancy skill",
    "handbell skill",
    "shield skill",
    "parrying skill",
    "guard skill",
    "all magic skills",
    "all attributes",
    "fire resistance",
    "ice resistance",
    "wind resistance",
    "earth resistance",
    "thunder resistance",
    "water resistance",
    "light resistance",
    "dark resistance",
    "resistance to all status ailments",
    "spell interruption rate",
    "shield block rate",
    "magic critical hit rate",
    "critical hit rate",
    "critical hit damage",
    "song duration",
    "movement speed",
    "dmg",
    "delay",
];

/// Aliases are exact after `clean_label` (lowercase, no surrounding quotes, no trailing period).
/// Add a row here when the client or a GearSwap augment uses another spelling.
const ALIASES: &[(&str, &str, &str)] = &[
    // Attributes and vitals.
    ("def", "def", "DEF"),
    ("defense", "def", "DEF"),
    ("hp", "hp", "HP"),
    ("max hp", "hp", "HP"),
    ("mp", "mp", "MP"),
    ("max mp", "mp", "MP"),
    ("str", "str", "STR"),
    ("dex", "dex", "DEX"),
    ("vit", "vit", "VIT"),
    ("agi", "agi", "AGI"),
    ("int", "int", "INT"),
    ("mnd", "mnd", "MND"),
    ("chr", "chr", "CHR"),
    // Weapon fields.
    ("dmg", "dmg", "DMG"),
    ("delay", "delay", "Delay"),
    // Physical combat.
    ("attack", "attack", "Attack"),
    ("atk", "attack", "Attack"),
    ("accuracy", "accuracy", "Accuracy"),
    ("acc", "accuracy", "Accuracy"),
    ("ranged attack", "ranged attack", "Ranged Attack"),
    ("ranged atk", "ranged attack", "Ranged Attack"),
    ("rng. atk", "ranged attack", "Ranged Attack"),
    ("rng atk", "ranged attack", "Ranged Attack"),
    ("ranged accuracy", "ranged accuracy", "Ranged Accuracy"),
    ("ranged acc", "ranged accuracy", "Ranged Accuracy"),
    ("rng. acc", "ranged accuracy", "Ranged Accuracy"),
    ("rng acc", "ranged accuracy", "Ranged Accuracy"),
    (
        "weapon skill accuracy",
        "weapon skill accuracy",
        "Weapon skill accuracy",
    ),
    (
        "weaponskill accuracy",
        "weapon skill accuracy",
        "Weapon skill accuracy",
    ),
    (
        "ws accuracy",
        "weapon skill accuracy",
        "Weapon skill accuracy",
    ),
    ("ws acc", "weapon skill accuracy", "Weapon skill accuracy"),
    (
        "weapon skill damage",
        "weapon skill damage",
        "Weapon skill damage",
    ),
    (
        "weapon skill dmg",
        "weapon skill damage",
        "Weapon skill damage",
    ),
    (
        "weaponskill damage",
        "weapon skill damage",
        "Weapon skill damage",
    ),
    ("ws damage", "weapon skill damage", "Weapon skill damage"),
    ("ws dmg", "weapon skill damage", "Weapon skill damage"),
    (
        "magic burst damage",
        "magic burst damage",
        "Magic burst damage",
    ),
    (
        "magic burst dmg",
        "magic burst damage",
        "Magic burst damage",
    ),
    (
        "magic burst bonus",
        "magic burst damage",
        "Magic burst damage",
    ),
    (
        "magic burst damage ii",
        "magic burst damage ii",
        "Magic burst damage II",
    ),
    ("skillchain bonus", "skillchain bonus", "Skillchain Bonus"),
    ("skillchain damage", "skillchain bonus", "Skillchain Bonus"),
    ("skillchain dmg", "skillchain bonus", "Skillchain Bonus"),
    ("double attack", "double attack", "Double Attack"),
    ("triple attack", "triple attack", "Triple Attack"),
    ("quadruple attack", "quadruple attack", "Quadruple Attack"),
    ("subtle blow", "subtle blow", "Subtle Blow"),
    ("subtle blow ii", "subtle blow ii", "Subtle Blow II"),
    ("dual wield", "dual wield", "Dual Wield"),
    ("store tp", "store tp", "Store TP"),
    ("enmity", "enmity", "Enmity"),
    // Magic offence and defence.
    ("magic atk. bonus", "magic atk. bonus", "Magic Atk. Bonus"),
    ("magic atk bonus", "magic atk. bonus", "Magic Atk. Bonus"),
    ("magic attack", "magic atk. bonus", "Magic Atk. Bonus"),
    ("mag. atk. bns", "magic atk. bonus", "Magic Atk. Bonus"),
    ("mag.atk.bns", "magic atk. bonus", "Magic Atk. Bonus"),
    ("m. atk. b", "magic atk. bonus", "Magic Atk. Bonus"),
    ("m.atk.b", "magic atk. bonus", "Magic Atk. Bonus"),
    ("magic accuracy", "magic accuracy", "Magic Accuracy"),
    ("magic acc", "magic accuracy", "Magic Accuracy"),
    ("mag. acc", "magic accuracy", "Magic Accuracy"),
    ("mag acc", "magic accuracy", "Magic Accuracy"),
    ("m. acc", "magic accuracy", "Magic Accuracy"),
    (
        "magic accuracy skill",
        "magic accuracy skill",
        "Magic Accuracy skill",
    ),
    ("magic damage", "magic damage", "Magic Damage"),
    ("magic dmg", "magic damage", "Magic Damage"),
    ("mag. dmg", "magic damage", "Magic Damage"),
    ("mag dmg", "magic damage", "Magic Damage"),
    ("m. dmg", "magic damage", "Magic Damage"),
    ("magic evasion", "magic evasion", "Magic Evasion"),
    ("magic eva", "magic evasion", "Magic Evasion"),
    ("mag. eva", "magic evasion", "Magic Evasion"),
    ("mag eva", "magic evasion", "Magic Evasion"),
    ("m. eva", "magic evasion", "Magic Evasion"),
    ("evasion", "evasion", "Evasion"),
    ("eva", "evasion", "Evasion"),
    ("magic def. bonus", "magic def. bonus", "Magic Def. Bonus"),
    ("magic def bonus", "magic def. bonus", "Magic Def. Bonus"),
    ("magic defense", "magic def. bonus", "Magic Def. Bonus"),
    ("mag. def. bonus", "magic def. bonus", "Magic Def. Bonus"),
    ("mag.def.bonus", "magic def. bonus", "Magic Def. Bonus"),
    ("m. def. b", "magic def. bonus", "Magic Def. Bonus"),
    ("m.def.b", "magic def. bonus", "Magic Def. Bonus"),
    (
        "hand-to-hand skill",
        "hand-to-hand skill",
        "Hand-to-Hand skill",
    ),
    ("dagger skill", "dagger skill", "Dagger skill"),
    ("sword skill", "sword skill", "Sword skill"),
    (
        "great sword skill",
        "great sword skill",
        "Great Sword skill",
    ),
    ("axe skill", "axe skill", "Axe skill"),
    ("great axe skill", "great axe skill", "Great Axe skill"),
    ("scythe skill", "scythe skill", "Scythe skill"),
    ("polearm skill", "polearm skill", "Polearm skill"),
    ("katana skill", "katana skill", "Katana skill"),
    (
        "great katana skill",
        "great katana skill",
        "Great Katana skill",
    ),
    ("club skill", "club skill", "Club skill"),
    ("staff skill", "staff skill", "Staff skill"),
    ("archery skill", "archery skill", "Archery skill"),
    (
        "marksmanship skill",
        "marksmanship skill",
        "Marksmanship skill",
    ),
    ("throwing skill", "throwing skill", "Throwing skill"),
    // Damage taken and haste.
    ("haste", "haste", "Haste"),
    ("damage taken", "damage taken", "Damage taken"),
    ("dmg. taken", "damage taken", "Damage taken"),
    ("dmg taken", "damage taken", "Damage taken"),
    (
        "physical damage taken",
        "physical damage taken",
        "Physical damage taken",
    ),
    (
        "phys. dmg. taken",
        "physical damage taken",
        "Physical damage taken",
    ),
    (
        "phys. dmg taken",
        "physical damage taken",
        "Physical damage taken",
    ),
    (
        "physical dmg. taken",
        "physical damage taken",
        "Physical damage taken",
    ),
    (
        "physical dmg taken",
        "physical damage taken",
        "Physical damage taken",
    ),
    (
        "magic damage taken",
        "magic damage taken",
        "Magic damage taken",
    ),
    (
        "mag. dmg. taken",
        "magic damage taken",
        "Magic damage taken",
    ),
    ("mag. dmg taken", "magic damage taken", "Magic damage taken"),
    (
        "magic dmg. taken",
        "magic damage taken",
        "Magic damage taken",
    ),
    (
        "magic dmg taken",
        "magic damage taken",
        "Magic damage taken",
    ),
    (
        "breath damage taken",
        "breath damage taken",
        "Breath damage taken",
    ),
    (
        "breath dmg. taken",
        "breath damage taken",
        "Breath damage taken",
    ),
    (
        "breath dmg taken",
        "breath damage taken",
        "Breath damage taken",
    ),
    (
        "ranged damage taken",
        "ranged damage taken",
        "Ranged damage taken",
    ),
    (
        "ranged dmg. taken",
        "ranged damage taken",
        "Ranged damage taken",
    ),
    (
        "ranged dmg taken",
        "ranged damage taken",
        "Ranged damage taken",
    ),
    (
        "physical damage limit",
        "physical damage limit",
        "Physical damage limit",
    ),
    (
        "physical dmg. limit",
        "physical damage limit",
        "Physical damage limit",
    ),
    (
        "physical dmg limit",
        "physical damage limit",
        "Physical damage limit",
    ),
    // Cure, casting and refresh cycles.
    ("cure potency", "cure potency", "Cure potency"),
    ("cure potency ii", "cure potency ii", "Cure potency II"),
    (
        "cure potency received",
        "cure potency received",
        "Cure potency received",
    ),
    ("fast cast", "fast cast", "Fast Cast"),
    ("quick magic", "quick magic", "Quick Magic"),
    ("occ. quickens spellcasting", "quick magic", "Quick Magic"),
    ("refresh", "refresh", "Refresh"),
    ("refresh potency", "refresh potency", "Refresh potency"),
    ("regen", "regen", "Regen"),
    ("regen potency", "regen potency", "Regen potency"),
    ("regen duration", "regen duration", "Regen duration"),
    ("regen effect duration", "regen duration", "Regen duration"),
    // Magic skills and effect lines.
    (
        "enhancing magic duration",
        "enhancing magic duration",
        "Enhancing magic duration",
    ),
    (
        "enhancing magic effect duration",
        "enhancing magic duration",
        "Enhancing magic duration",
    ),
    (
        "enh. mag. eff. dur",
        "enhancing magic duration",
        "Enhancing magic duration",
    ),
    (
        "enhancing magic skill",
        "enhancing magic skill",
        "Enhancing magic skill",
    ),
    (
        "enh. magic skill",
        "enhancing magic skill",
        "Enhancing magic skill",
    ),
    (
        "enfeebling magic skill",
        "enfeebling magic skill",
        "Enfeebling magic skill",
    ),
    (
        "enfeeb. magic skill",
        "enfeebling magic skill",
        "Enfeebling magic skill",
    ),
    (
        "enfeebling magic effect",
        "enfeebling magic effect",
        "Enfeebling magic effect",
    ),
    (
        "enfeebling magic duration",
        "enfeebling magic duration",
        "Enfeebling magic duration",
    ),
    (
        "elemental magic skill",
        "elemental magic skill",
        "Elemental magic skill",
    ),
    (
        "elem. magic skill",
        "elemental magic skill",
        "Elemental magic skill",
    ),
    (
        "divine magic skill",
        "divine magic skill",
        "Divine magic skill",
    ),
    ("dark magic skill", "dark magic skill", "Dark magic skill"),
    (
        "healing magic skill",
        "healing magic skill",
        "Healing magic skill",
    ),
    ("singing skill", "singing skill", "Singing skill"),
    (
        "string instrument skill",
        "string instrument skill",
        "String instrument skill",
    ),
    (
        "wind instrument skill",
        "wind instrument skill",
        "Wind instrument skill",
    ),
    ("ninjutsu skill", "ninjutsu skill", "Ninjutsu skill"),
    ("blue magic skill", "blue magic skill", "Blue magic skill"),
    ("geomancy skill", "geomancy skill", "Geomancy skill"),
    ("handbell skill", "handbell skill", "Handbell skill"),
    ("shield skill", "shield skill", "Shield skill"),
    ("parrying skill", "parrying skill", "Parrying skill"),
    ("guard skill", "guard skill", "Guard skill"),
    ("all magic skills", "all magic skills", "All magic skills"),
    ("magic skills", "all magic skills", "All magic skills"),
    ("all attributes", "all attributes", "All attributes"),
    ("all attr", "all attributes", "All attributes"),
    // Other combat and resistances.
    ("movement speed", "movement speed", "Movement speed"),
    ("song duration", "song duration", "Song duration"),
    ("song duration bonus", "song duration", "Song duration"),
    (
        "magic critical hit rate",
        "magic critical hit rate",
        "Magic Critical hit rate",
    ),
    (
        "magic crit. hit rate",
        "magic critical hit rate",
        "Magic Critical hit rate",
    ),
    (
        "critical hit rate",
        "critical hit rate",
        "Critical hit rate",
    ),
    ("crit. hit rate", "critical hit rate", "Critical hit rate"),
    (
        "critical hit damage",
        "critical hit damage",
        "Critical hit damage",
    ),
    (
        "crit. hit damage",
        "critical hit damage",
        "Critical hit damage",
    ),
    (
        "spell interruption rate",
        "spell interruption rate",
        "Spell interruption rate",
    ),
    (
        "shield block rate",
        "shield block rate",
        "Shield block rate",
    ),
    (
        "resistance to all status ailments",
        "resistance to all status ailments",
        "Resistance to all status ailments",
    ),
    (
        "all status ailments resistance",
        "resistance to all status ailments",
        "Resistance to all status ailments",
    ),
    ("fire", "fire resistance", "Fire resistance"),
    ("fire resistance", "fire resistance", "Fire resistance"),
    ("ice", "ice resistance", "Ice resistance"),
    ("ice resistance", "ice resistance", "Ice resistance"),
    ("wind", "wind resistance", "Wind resistance"),
    ("wind resistance", "wind resistance", "Wind resistance"),
    ("earth", "earth resistance", "Earth resistance"),
    ("earth resistance", "earth resistance", "Earth resistance"),
    ("thunder", "thunder resistance", "Thunder resistance"),
    (
        "thunder resistance",
        "thunder resistance",
        "Thunder resistance",
    ),
    ("water", "water resistance", "Water resistance"),
    ("water resistance", "water resistance", "Water resistance"),
    ("light", "light resistance", "Light resistance"),
    ("light resistance", "light resistance", "Light resistance"),
    ("dark", "dark resistance", "Dark resistance"),
    ("dark resistance", "dark resistance", "Dark resistance"),
];

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn stat<'a>(stats: &'a [GearStat], label: &str) -> &'a GearStat {
        stats
            .iter()
            .find(|stat| stat.label == label)
            .unwrap_or_else(|| panic!("missing stat {label}: {stats:?}"))
    }

    #[test]
    fn reads_a_reforged_item_tooltip() {
        let description = "DEF:121 HP+74 MP+68 STR+29 DEX+32\nVIT+29 AGI+34 INT+37 MND+42 CHR+34\nAccuracy+64 Magic Accuracy+64\nEvasion+96 Magic Evasion+120\n\"Magic Def. Bonus\"+8\nElemental magic skill +18\nHaste+6%\nMagic burst damage +10\n\"Fast Cast\"+16%\nSet: Accuracy+ Ranged Accuracy+ Magic Accuracy+";
        let (lines, stats) = parse_description(description);
        assert_eq!(lines.len(), 9);
        assert!(!lines.iter().any(|line| line.starts_with("Set:")));
        assert_eq!(stat(&stats, "DEF").value, 121);
        assert_eq!(stat(&stats, "HP").value, 74);
        assert_eq!(stat(&stats, "STR").value, 29);
        assert_eq!(stat(&stats, "MND").value, 42);
        assert_eq!(stat(&stats, "Accuracy").value, 64);
        assert_eq!(stat(&stats, "Magic Accuracy").value, 64);
        assert_eq!(stat(&stats, "Evasion").value, 96);
        assert_eq!(stat(&stats, "Magic Evasion").value, 120);
        assert_eq!(stat(&stats, "Magic Def. Bonus").value, 8);
        assert_eq!(stat(&stats, "Elemental magic skill").value, 18);
        assert_eq!(stat(&stats, "Haste").value, 6);
        assert!(stat(&stats, "Haste").percent);
        assert_eq!(stat(&stats, "Magic burst damage").value, 10);
        assert!(stat(&stats, "Magic burst damage").percent);
        assert_eq!(stat(&stats, "Fast Cast").value, 16);
        assert!(stat(&stats, "Fast Cast").percent);
    }

    #[test]
    fn reads_augment_strings_without_losing_either_half() {
        let augments = [
            "MND+20",
            "Mag. Acc+20 /Mag. Dmg.+20",
            "MND+10",
            "\"Cure Potency\"+10%",
            "Phys. dmg. taken-10%",
        ];
        let stats: Vec<GearStat> = augments
            .iter()
            .flat_map(|augment| parse_augment(augment))
            .collect();
        assert_eq!(stat(&stats, "MND").value, 20);
        assert_eq!(stat(&stats, "Magic Accuracy").value, 20);
        assert_eq!(stat(&stats, "Magic Damage").value, 20);
        assert_eq!(stat(&stats, "Cure potency").value, 10);
        assert!(stat(&stats, "Cure potency").percent);
        assert_eq!(stat(&stats, "Physical damage taken").value, -10);
        assert!(stat(&stats, "Physical damage taken").percent);
        // The duplicate MND row stays separate; the totals add both.
        assert_eq!(stats.iter().filter(|stat| stat.label == "MND").count(), 2);
    }

    #[test]
    fn reads_the_abbreviated_augments_the_job_libraries_use() {
        let stats: Vec<GearStat> = [
            "DEX+20",
            "Accuracy+20 Attack+20",
            "\"Store TP\"+10",
            "\"Dual Wield\"+5",
            "Weapon skill damage +10%",
            "\"Mag.Atk.Bns.\"+10",
            "\"M. Def. B.\"+5",
            "Eva.+20 /Mag. Eva.+20",
            "Damage taken-5%",
            "\"Fast Cast\"+10",
        ]
        .iter()
        .flat_map(|augment| parse_augment(augment))
        .collect();
        assert_eq!(stat(&stats, "DEX").value, 20);
        assert_eq!(stat(&stats, "Accuracy").value, 20);
        assert_eq!(stat(&stats, "Attack").value, 20);
        assert_eq!(stat(&stats, "Store TP").value, 10);
        assert!(!stat(&stats, "Store TP").percent);
        assert_eq!(stat(&stats, "Dual Wield").value, 5);
        assert!(stat(&stats, "Dual Wield").percent);
        assert_eq!(stat(&stats, "Weapon skill damage").value, 10);
        assert!(stat(&stats, "Weapon skill damage").percent);
        assert_eq!(stat(&stats, "Magic Atk. Bonus").value, 10);
        assert_eq!(stat(&stats, "Magic Def. Bonus").value, 5);
        assert_eq!(stat(&stats, "Evasion").value, 20);
        assert_eq!(stat(&stats, "Magic Evasion").value, 20);
        assert_eq!(stat(&stats, "Damage taken").value, -5);
        assert_eq!(stat(&stats, "Fast Cast").value, 10);
        assert!(stat(&stats, "Fast Cast").percent);
    }

    #[test]
    fn keeps_flat_and_percent_apart() {
        let stats = parse_augment("HP+80 HP+10%");
        let hp: Vec<&GearStat> = stats.iter().filter(|stat| stat.key == "hp").collect();
        assert_eq!(hp.len(), 2);
        assert_eq!(hp[0].value, 80);
        assert!(!hp[0].percent);
        assert_eq!(hp[1].value, 10);
        assert!(hp[1].percent);
    }

    #[test]
    fn drops_set_pet_and_unity_blocks() {
        let description = "DEF:156 HP+91\nAccuracy+40\nDamage taken-7%\nPet: Accuracy+50\nRanged Accuracy+50\nMagic Accuracy+50";
        let (lines, stats) = parse_description(description);
        assert_eq!(
            lines,
            vec!["DEF:156 HP+91", "Accuracy+40", "Damage taken-7%"]
        );
        assert_eq!(stat(&stats, "Damage taken").value, -7);
        assert!(stats.iter().all(|stat| stat.label != "Magic Accuracy"));

        let (lines, stats) = parse_description("DEF:8\nUnity Ranking: HP+10～35\nHaste+3%");
        assert_eq!(lines, vec!["DEF:8"]);
        assert_eq!(stats.len(), 1);

        let (lines, stats) = parse_description("Enmity-10 Set: Accuracy+ Ranged Accuracy+");
        assert_eq!(lines, vec!["Enmity-10"]);
        assert_eq!(stat(&stats, "Enmity").value, -10);
    }

    #[test]
    fn conditional_lines_show_but_do_not_total() {
        let (lines, stats) = parse_description(
            "DEF:40\nLatent effect: Accuracy+10\nAftermath: Attack+10\nAdditional effect: Accuracy+5\nMagic accuracy skill +228",
        );
        assert_eq!(lines.len(), 5);
        assert_eq!(stat(&stats, "DEF").value, 40);
        assert_eq!(stat(&stats, "Magic Accuracy skill").value, 228);
        assert!(stats.iter().all(|stat| stat.label != "Accuracy"));
        assert!(stats.iter().all(|stat| stat.label != "Attack"));
    }

    #[test]
    fn pet_and_avatar_blocks_stay_out_of_the_player_totals() {
        let (lines, stats) = parse_description(
            "DEF:10 MP+20\nPet: Accuracy+50\nRanged Accuracy+50\nMagic Accuracy+50",
        );
        assert_eq!(lines, vec!["DEF:10 MP+20"]);
        assert_eq!(stat(&stats, "DEF").value, 10);
        assert!(stats.iter().all(|stat| stat.label != "Accuracy"));

        let (lines, stats) = parse_description("MP+15\nAvatar: Accuracy+30\nAttack+30");
        assert_eq!(lines, vec!["MP+15"]);
        assert_eq!(stat(&stats, "MP").value, 15);
        assert!(stats.iter().all(|stat| stat.label != "Accuracy"));
    }

    #[test]
    fn reads_all_magic_skills_as_one_line() {
        let (_, stats) = parse_description("Magic skills +10");
        assert_eq!(stat(&stats, "All magic skills").value, 10);
    }

    #[test]
    fn reads_weapon_skill_lines() {
        let (_, stats) = parse_description(
            "DMG:140 Delay:200 Magic Damage+155\nDagger skill +269 Parrying skill +269\n\"Store TP\"+10 \"TP Bonus\"+500",
        );
        assert_eq!(stat(&stats, "DMG").value, 140);
        assert_eq!(stat(&stats, "Delay").value, 200);
        assert_eq!(stat(&stats, "Magic Damage").value, 155);
        assert_eq!(stat(&stats, "Dagger skill").value, 269);
        assert_eq!(stat(&stats, "Parrying skill").value, 269);
        assert_eq!(stat(&stats, "Store TP").value, 10);
        assert_eq!(stat(&stats, "TP Bonus").value, 500);
    }

    #[test]
    fn turns_down_into_a_negative_stat() {
        let stats = parse_augment("Spell interruption rate down 5%");
        let rate = stat(&stats, "Spell interruption rate");
        assert_eq!(rate.value, -5);
        assert!(rate.percent);
    }

    #[test]
    fn deduplicates_same_name_in_two_slots() {
        let requests = vec![
            GearStatRequest {
                slot: "ear1".to_string(),
                name: "Tuisto Earring".to_string(),
                augments: vec![],
                id: 0,
            },
            GearStatRequest {
                slot: "ear2".to_string(),
                name: "Tuisto Earring".to_string(),
                augments: vec![],
                id: 0,
            },
        ];
        let resolved = vec![
            Some(ClientItem {
                id: 26112,
                name: "Tuisto Earring".to_string(),
                description: "DEF:20 VIT+10".to_string(),
                level: 99,
                item_level: 0,
            }),
            Some(ClientItem {
                id: 26112,
                name: "Tuisto Earring".to_string(),
                description: "DEF:20 VIT+10".to_string(),
                level: 99,
                item_level: 0,
            }),
        ];
        let stats = build_stats(&requests, &resolved);
        assert_eq!(stats.len(), 2);
        assert_eq!(stats[0].slot, "ear1");
        assert_eq!(stats[1].slot, "ear2");
        assert_eq!(stat(&stats[0].stats, "VIT").value, 10);
    }

    #[test]
    fn separates_base_and_augment_stats() {
        let requests = vec![GearStatRequest {
            slot: "back".to_string(),
            name: "Sucellos's Cape".to_string(),
            augments: vec!["DEX+20".to_string(), "Accuracy+20 Attack+20".to_string()],
            id: 0,
        }];
        let resolved = vec![Some(ClientItem {
            id: 26250,
            name: "Sucellos's Cape".to_string(),
            description: "DEF:15\nAccuracy+10\nEnhancing magic duration +20%".to_string(),
            level: 99,
            item_level: 0,
        })];
        let mut items = build_stats(&requests, &resolved);
        let item = items.remove(0);
        assert!(item.found);
        assert_eq!(item.base_stats.len(), 3);
        assert_eq!(item.augment_stats.len(), 3);
        assert_eq!(stat(&item.base_stats, "DEF").value, 15);
        assert_eq!(stat(&item.base_stats, "Accuracy").value, 10);
        assert_eq!(stat(&item.augment_stats, "DEX").value, 20);
        assert_eq!(stat(&item.augment_stats, "Accuracy").value, 20);
        let accuracy: i64 = item
            .stats
            .iter()
            .filter(|stat| stat.label == "Accuracy")
            .map(|stat| stat.value)
            .sum();
        assert_eq!(accuracy, 30);
        assert_eq!(
            item.stats.len(),
            item.base_stats.len() + item.augment_stats.len()
        );
    }

    #[test]
    fn asks_by_id_for_live_slots_and_by_name_for_library_sets() {
        let items = vec![
            GearStatRequest {
                slot: "main".to_string(),
                name: "Mpu Gandring".to_string(),
                augments: vec![],
                id: 20737,
            },
            GearStatRequest {
                slot: "back".to_string(),
                name: "A \"Cape\"".to_string(),
                augments: vec![],
                id: 0,
            },
        ];
        let code = item_query_code(&items);
        assert!(code.contains("local keys = {20737,\"A \\\"Cape\\\"\"}"));
        assert!(code.contains("if type(key) == 'number' then"));
        assert!(code.contains("pcall(res.item, key)"));
        assert!(code.contains("pcall(res.item_by_name, key, 2)"));
    }

    #[test]
    fn escapes_item_names_into_lua_strings() {
        let items = vec![GearStatRequest {
            slot: "back".to_string(),
            name: "A \"Cape\" \\ test".to_string(),
            augments: vec![],
            id: 0,
        }];
        let code = item_query_code(&items);
        assert!(code.contains(r#""A \"Cape\" \\ test""#));
    }

    #[test]
    fn reads_the_lua_reply_and_tolerates_missing_items() {
        let reply = json!([
            {
                "id": 26250,
                "name": "Sucellos's Cape",
                "description": "DEF:15\nEnfeebling magic effect +10\nEnhancing magic duration +20%",
                "level": 99,
                "item_level": 0
            },
            {"name": "Not an item"}
        ]);
        let items = parse_lua_reply(&reply);
        assert_eq!(items.len(), 2);
        assert_eq!(items[0].as_ref().unwrap().id, 26250);
        assert!(items[1].is_none());
    }

    #[test]
    fn every_known_stat_has_a_sort_order() {
        for (_, key, label) in ALIASES {
            assert!(
                ORDER.contains(key),
                "{label} ({key}) is missing from the Set totals order"
            );
            assert!(order_for(key) < 9000);
        }
    }

    #[test]
    fn keeps_unknown_stats_for_the_totals() {
        let stats = parse_augment("\"Daken\"+10");
        assert_eq!(stat(&stats, "Daken").value, 10);
        assert_eq!(stat(&stats, "Daken").order, 9000);
    }

    #[test]
    fn helper_names_are_not_stats() {
        // A malformed line must not turn a label into a phantom stat.
        let (_, stats) = parse_description("Enhances \"Fast Cast\" effect\nConverts 150 MP to HP");
        assert!(stats.is_empty());
    }

    #[test]
    fn no_stat_is_silently_dropped_for_unknown_labels() {
        let (_, stats) = parse_description("Waltz potency +15%");
        let waltz = stat(&stats, "Waltz potency");
        assert_eq!(waltz.value, 15);
        assert!(waltz.percent);
    }
}
