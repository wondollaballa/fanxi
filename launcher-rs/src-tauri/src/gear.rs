//! GearSwap helpers: job detection, flattening, Lua output and timestamped versions.
//!
//! The live client parses GearSwap files itself (the control port's `gearswap` command), so this
//! module only deals with the JSON it returns and the files the launcher writes back.

use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Local};
use serde::Serialize;
use serde_json::Value;

use crate::error::{AppError, AppResult};

pub const SLOT_KEYS: [&str; 16] = [
    "main", "sub", "range", "ammo", "head", "body", "hands", "legs", "feet", "neck", "waist",
    "ear1", "ear2", "ring1", "ring2", "back",
];

pub fn normalize_slot(value: &str) -> String {
    match value.trim().to_lowercase().as_str() {
        "left_ear" | "left ear" => "ear1".to_string(),
        "right_ear" | "right ear" => "ear2".to_string(),
        "left_ring" | "left ring" => "ring1".to_string(),
        "right_ring" | "right ring" => "ring2".to_string(),
        other => other.to_string(),
    }
}

pub fn is_slot(value: &str) -> bool {
    SLOT_KEYS.contains(&normalize_slot(value).as_str())
}

pub const JOB_NAMES: [&str; 22] = [
    "Warrior",
    "Monk",
    "White Mage",
    "Black Mage",
    "Red Mage",
    "Thief",
    "Paladin",
    "Dark Knight",
    "Beastmaster",
    "Bard",
    "Ranger",
    "Samurai",
    "Ninja",
    "Dragoon",
    "Summoner",
    "Blue Mage",
    "Corsair",
    "Puppetmaster",
    "Dancer",
    "Scholar",
    "Geomancer",
    "Rune Fencer",
];

pub const JOB_ABBRS: [&str; 22] = [
    "WAR", "MNK", "WHM", "BLM", "RDM", "THF", "PLD", "DRK", "BST", "BRD", "RNG", "SAM", "NIN",
    "DRG", "SMN", "BLU", "COR", "PUP", "DNC", "SCH", "GEO", "RUN",
];

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct JobInfo {
    pub job_id: i64,
    pub name: String,
    pub abbr: String,
    pub level: i64,
    pub character: String,
}

pub fn job_from_state(state: Option<&Value>) -> Option<JobInfo> {
    let player = state?.get("player")?;
    let job_id = player.get("job").and_then(value_i64)?;
    if !(1..=22).contains(&job_id) {
        return None;
    }
    let level = player.get("level").and_then(value_i64).unwrap_or(0);
    let character = player
        .get("name")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    Some(job_info(job_id, level, character))
}

pub fn job_from_character(character: Option<&Value>) -> Option<JobInfo> {
    let character = character?;
    let job_id = character.get("main_job").and_then(value_i64)?;
    if !(1..=22).contains(&job_id) {
        return None;
    }
    let level = character.get("main_level").and_then(value_i64).unwrap_or(0);
    let name = character
        .get("name")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    Some(job_info(job_id, level, name))
}

pub fn job_abbr(value: &Value) -> String {
    let number = value
        .as_i64()
        .or_else(|| value.as_str().and_then(|text| text.parse().ok()))
        .unwrap_or(0);
    if (1..=22).contains(&number) {
        return JOB_ABBRS[(number - 1) as usize].to_string();
    }
    if let Some(text) = value.as_str() {
        let upper = text.trim().to_uppercase();
        if JOB_ABBRS.contains(&upper.as_str()) {
            return upper;
        }
    }
    String::new()
}

pub fn job_name(value: i64) -> String {
    if (1..=22).contains(&value) {
        JOB_NAMES[(value - 1) as usize].to_string()
    } else {
        "Adventurer".to_string()
    }
}

fn job_info(job_id: i64, level: i64, character: String) -> JobInfo {
    JobInfo {
        job_id,
        name: job_name(job_id),
        abbr: JOB_ABBRS[(job_id - 1) as usize].to_string(),
        level,
        character,
    }
}

pub fn ordered_items(items: BTreeMap<String, String>) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    for slot in SLOT_KEYS {
        if let Some(item) = items.get(slot) {
            if !item.is_empty() {
                out.insert(slot.to_string(), item.clone());
            }
        }
    }
    for (key, value) in items {
        if !out.contains_key(&key) && !value.is_empty() {
            out.insert(key, value);
        }
    }
    out
}

pub fn clean_named_items(items: &BTreeMap<String, String>) -> AppResult<BTreeMap<String, String>> {
    let mut out = BTreeMap::new();
    for (key, value) in items {
        let slot = normalize_slot(key);
        if !SLOT_KEYS.contains(&slot.as_str()) {
            return Err(AppError::Validation(format!(
                "unknown equipment slot: {key}"
            )));
        }
        let name = value.trim().to_string();
        if name.is_empty() {
            continue;
        }
        if name.contains('\n') || name.contains('\r') {
            return Err(AppError::Validation(
                "an item name cannot contain a line break".to_string(),
            ));
        }
        if name.chars().count() > 64 {
            return Err(AppError::Validation(
                "item names must be 64 characters or fewer".to_string(),
            ));
        }
        out.insert(slot, name);
    }
    Ok(ordered_items(out))
}

fn item_name(value: &Value) -> Option<String> {
    match value {
        Value::String(text) => Some(text.clone()),
        Value::Object(map) => map
            .get("name")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned),
        _ => None,
    }
}

fn item_augments(value: &Value) -> Vec<String> {
    let Some(raw) = value.get("augments") else {
        return Vec::new();
    };
    let mut out = Vec::new();
    match raw {
        Value::String(text) => out.push(text.clone()),
        Value::Array(items) => {
            for item in items {
                if let Some(text) = scalar_text(item) {
                    out.push(text);
                }
            }
        }
        Value::Object(map) => {
            let mut numeric: Vec<(i64, String)> = map
                .iter()
                .filter_map(|(key, item)| {
                    let index = key.parse::<i64>().ok()?;
                    Some((index, scalar_text(item)?))
                })
                .collect();
            numeric.sort_by_key(|(index, _)| *index);
            out.extend(numeric.into_iter().map(|(_, text)| text));
        }
        _ => {}
    }
    out
}

fn scalar_text(value: &Value) -> Option<String> {
    match value {
        Value::String(text) => Some(text.clone()),
        Value::Number(number) => Some(number.to_string()),
        _ => None,
    }
}

pub fn flatten_sets(tree: &Value) -> BTreeMap<String, BTreeMap<String, String>> {
    let mut out = BTreeMap::new();
    walk_flat(tree, "sets", &mut out);
    out
}

fn walk_flat(value: &Value, path: &str, out: &mut BTreeMap<String, BTreeMap<String, String>>) {
    let Some(map) = value.as_object() else {
        return;
    };
    let slot_bearing = map.keys().any(|key| is_slot(key));
    if slot_bearing {
        let mut items = BTreeMap::new();
        for slot in SLOT_KEYS {
            if let Some(raw) = map
                .iter()
                .find(|(key, _)| normalize_slot(key) == slot)
                .map(|(_, value)| value)
            {
                if let Some(name) = item_name(raw) {
                    let name = name.trim().to_string();
                    if !name.is_empty() {
                        items.insert(slot.to_string(), name);
                    }
                }
            }
        }
        if !items.is_empty() {
            out.insert(path.to_string(), ordered_items(items));
        }
        return;
    }
    for (key, child) in map {
        walk_flat(child, &format!("{path}.{key}"), out);
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct GearItem {
    pub name: String,
    pub augments: Vec<String>,
}

pub fn flatten_sets_detailed(tree: &Value) -> BTreeMap<String, BTreeMap<String, GearItem>> {
    let mut out = BTreeMap::new();
    walk_detailed(tree, "sets", &mut out);
    out
}

fn walk_detailed(
    value: &Value,
    path: &str,
    out: &mut BTreeMap<String, BTreeMap<String, GearItem>>,
) {
    let Some(map) = value.as_object() else {
        return;
    };
    let slot_bearing = map.keys().any(|key| is_slot(key));
    if slot_bearing {
        let mut items: BTreeMap<String, GearItem> = BTreeMap::new();
        for slot in SLOT_KEYS {
            if let Some(raw) = map
                .iter()
                .find(|(key, _)| normalize_slot(key) == slot)
                .map(|(_, value)| value)
            {
                if let Some(name) = item_name(raw) {
                    let name = name.trim().to_string();
                    if !name.is_empty() {
                        items.insert(
                            slot.to_string(),
                            GearItem {
                                name,
                                augments: item_augments(raw),
                            },
                        );
                    }
                }
            }
        }
        if !items.is_empty() {
            out.insert(path.to_string(), items);
        }
        return;
    }
    for (key, child) in map {
        walk_detailed(child, &format!("{path}.{key}"), out);
    }
}

pub fn normalize_set_path(text: &str) -> AppResult<String> {
    let raw = text.trim();
    if raw.is_empty() {
        return Err(AppError::Validation("the set path is empty".to_string()));
    }
    if raw == "sets" {
        return Err(AppError::Validation(
            "use a path like sets.idle.pdt (no empty levels)".to_string(),
        ));
    }
    let body = raw.strip_prefix("sets.").unwrap_or(raw);
    let segments: Vec<&str> = body.split('.').map(str::trim).collect();
    if segments.is_empty() || segments.iter().any(|segment| segment.is_empty()) {
        return Err(AppError::Validation(
            "use a path like sets.idle.pdt (no empty levels)".to_string(),
        ));
    }
    for segment in &segments {
        if segment.chars().count() > 64 {
            return Err(AppError::Validation(
                "each set name level must be 64 characters or fewer".to_string(),
            ));
        }
        if segment
            .chars()
            .any(|ch| matches!(ch, '[' | ']' | '"' | '\n' | '\r'))
        {
            return Err(AppError::Validation(
                "set names cannot contain [ ] \" or line breaks".to_string(),
            ));
        }
    }
    Ok(format!("sets.{}", segments.join(".")))
}

pub fn path_conflict(path: &str, existing: impl IntoIterator<Item = String>) -> Option<String> {
    let path = normalize_set_path(path).ok()?;
    for raw in existing {
        let Ok(other) = normalize_set_path(&raw) else {
            continue;
        };
        if other == path {
            continue;
        }
        if other.starts_with(&(path.clone() + ".")) || path.starts_with(&(other.clone() + ".")) {
            return Some(other);
        }
    }
    None
}

const LUA_KEYWORDS: [&str; 22] = [
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function", "goto", "if", "in",
    "local", "nil", "not", "or", "repeat", "return", "then", "true", "until", "while",
];

pub fn lua_string(value: &str) -> String {
    let escaped = value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "");
    format!("\"{escaped}\"")
}

pub fn lua_path(path: &str) -> AppResult<String> {
    let path = normalize_set_path(path)?;
    let mut expression = "sets".to_string();
    for segment in path.split('.').skip(1) {
        let identifier = is_identifier(segment) && !LUA_KEYWORDS.contains(&segment);
        if identifier {
            expression.push('.');
            expression.push_str(segment);
        } else {
            expression.push('[');
            expression.push_str(&lua_string(segment));
            expression.push(']');
        }
    }
    Ok(expression)
}

fn is_identifier(value: &str) -> bool {
    let mut chars = value.chars();
    match chars.next() {
        Some(first) if first.is_ascii_alphabetic() || first == '_' => {}
        _ => return false,
    }
    chars.all(|ch| ch.is_ascii_alphanumeric() || ch == '_')
}

pub fn normalized_library(
    sets: &BTreeMap<String, BTreeMap<String, String>>,
) -> AppResult<BTreeMap<String, BTreeMap<String, String>>> {
    let mut out = BTreeMap::new();
    for (raw, items) in sets {
        let path = normalize_set_path(raw)?;
        out.insert(path, items.clone());
    }
    let paths: Vec<String> = out.keys().cloned().collect();
    for path in &paths {
        if let Some(other) = path_conflict(path, paths.iter().filter(|item| *item != path).cloned())
        {
            return Err(AppError::Validation(format!(
                "{path} collides with {other}"
            )));
        }
    }
    Ok(out)
}

pub fn serialize_library(
    sets: &BTreeMap<String, BTreeMap<String, String>>,
    character: &str,
    job: &str,
    source: &str,
    when: DateTime<Local>,
) -> AppResult<String> {
    serialize_library_with(sets, character, job, source, when, false)
}

/// `in_place` writes the file the Gear page loaded, so the header says the launcher edits it
/// instead of telling the reader to re-import a timestamped copy.
fn serialize_library_with(
    sets: &BTreeMap<String, BTreeMap<String, String>>,
    character: &str,
    job: &str,
    source: &str,
    when: DateTime<Local>,
    in_place: bool,
) -> AppResult<String> {
    let sets = normalized_library(sets)?;
    let mut out = String::new();
    let title = format!("{} {}", character.trim(), job.trim())
        .trim()
        .to_string();
    let title = if title.is_empty() {
        "GearSwap".to_string()
    } else {
        title
    };
    writeln!(out, "--[[").ok();
    if in_place {
        writeln!(out, "    Fanxi GearSwap library — {title}").ok();
        writeln!(out, "    Updated {}", when.format("%Y-%m-%d %H:%M:%S")).ok();
        writeln!(
            out,
            "    The launcher writes sets back to this file; the first copy is kept as a .bak."
        )
        .ok();
    } else {
        writeln!(out, "    Fanxi GearSwap version — {title}").ok();
        writeln!(out, "    Created {}", when.format("%Y-%m-%d %H:%M:%S")).ok();
    }
    if !source.trim().is_empty() {
        writeln!(
            out,
            "    Source: {}",
            source
                .replace("]]", "] ]")
                .replace(|ch| ch == '\n' || ch == '\r', " ")
        )
        .ok();
    }
    writeln!(out).ok();
    if !in_place {
        writeln!(
            out,
            "    Re-import this file with Gear -> Import your own .lua…"
        )
        .ok();
    }
    writeln!(
        out,
        "    Each set holds only slot = \"Item\" pairs so Fanxi lists every one;"
    )
    .ok();
    writeln!(
        out,
        "    to add a variant, copy an existing set and give it a new path."
    )
    .ok();
    writeln!(out, "]]").ok();
    writeln!(out).ok();
    writeln!(out, "function get_sets()").ok();
    writeln!(out, "    sets = {{}}").ok();

    let mut containers = BTreeSet::new();
    for path in sets.keys() {
        let parts: Vec<&str> = path.split('.').collect();
        for index in 2..parts.len() {
            containers.insert(parts[..index].join("."));
        }
    }
    let mut containers: Vec<String> = containers.into_iter().collect();
    containers.sort_by_key(|value| (value.matches('.').count(), value.to_lowercase()));
    for container in containers {
        writeln!(out, "    {} = {{}}", lua_path(&container)?).ok();
    }

    let mut group: Option<String> = None;
    for path in sets.keys() {
        let items = &sets[path];
        if items.is_empty() {
            continue;
        }
        let top = path.split('.').nth(1).unwrap_or(path).to_string();
        if group.as_deref() != Some(&top) {
            writeln!(out).ok();
            writeln!(out, "    -- ===== {top} =====").ok();
            group = Some(top);
        }
        writeln!(out, "    {} = {{", lua_path(path)?).ok();
        for slot in SLOT_KEYS {
            if let Some(item) = items.get(slot) {
                writeln!(out, "        {slot} = {},", lua_string(item)).ok();
            }
        }
        writeln!(out, "    }}").ok();
    }
    writeln!(out, "end").ok();
    writeln!(out).ok();
    if in_place {
        writeln!(
            out,
            "-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak."
        )
        .ok();
    } else {
        writeln!(
            out,
            "-- Fanxi saves a new timestamped copy; this file was never the source."
        )
        .ok();
    }
    writeln!(out).ok();
    Ok(out)
}

/// Write the edited sets back to the library the Gear page loaded. The first copy of the file is
/// kept as `<name>.lua.bak`, so the launcher does not destroy a library it was told to edit.
pub fn write_library(
    path: &Path,
    sets: &BTreeMap<String, BTreeMap<String, String>>,
    character: &str,
    job: &str,
    source: &str,
    when: DateTime<Local>,
) -> AppResult<(PathBuf, Option<PathBuf>)> {
    if path.extension().and_then(|ext| ext.to_str()) != Some("lua") {
        return Err(AppError::Validation(format!(
            "{} is not a .lua library",
            path.display()
        )));
    }
    let text = serialize_library_with(sets, character, job, source, when, true)?;
    let mut backup = None;
    if path.is_file() {
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("library.lua");
        let candidate = path.with_file_name(format!("{name}.bak"));
        if !candidate.exists() {
            std::fs::copy(path, &candidate)?;
        }
        backup = Some(candidate);
    }
    std::fs::write(path, text)?;
    Ok((path.to_path_buf(), backup))
}

pub fn sanitize_name(value: &str) -> String {
    let mut text = String::new();
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.') {
            text.push(ch);
        } else {
            text.push('-');
        }
    }
    let text = text.trim_matches(|ch| ch == '-' || ch == '.').to_string();
    let text = collapse_hyphens(&text);
    if text.is_empty() {
        "gearswap".to_string()
    } else {
        text
    }
}

fn collapse_hyphens(value: &str) -> String {
    let mut out = String::new();
    let mut last_hyphen = false;
    for ch in value.chars() {
        if ch == '-' {
            if !last_hyphen {
                out.push(ch);
            }
            last_hyphen = true;
        } else {
            out.push(ch);
            last_hyphen = false;
        }
    }
    out
}

pub fn timestamp(when: DateTime<Local>) -> String {
    when.format("%Y%m%d-%H%M%S").to_string()
}

#[cfg(test)]
pub fn versioned_name(base: &str, when: DateTime<Local>) -> String {
    format!("{}-{}.lua", sanitize_name(base), timestamp(when))
}

pub fn unique_version_path(folder: &Path, base: &str, when: DateTime<Local>) -> AppResult<PathBuf> {
    std::fs::create_dir_all(folder)?;
    let stem = sanitize_name(base);
    let stamp = timestamp(when);
    let mut candidate = folder.join(format!("{stem}-{stamp}.lua"));
    let mut number = 2;
    while candidate.exists() {
        candidate = folder.join(format!("{stem}-{stamp}-{number}.lua"));
        number += 1;
    }
    Ok(candidate)
}

pub fn save_version(
    folder: &Path,
    sets: &BTreeMap<String, BTreeMap<String, String>>,
    base: &str,
    character: &str,
    job: &str,
    source: &str,
    when: DateTime<Local>,
) -> AppResult<PathBuf> {
    let target = unique_version_path(folder, base, when)?;
    let text = serialize_library(sets, character, job, source, when)?;
    std::fs::write(&target, text)?;
    Ok(target)
}

pub fn write_profile_snapshot(
    folder: &Path,
    sets: &BTreeMap<String, BTreeMap<String, String>>,
    character: &str,
    job: &str,
    source: &str,
    version_path: &Path,
    when: DateTime<Local>,
) -> AppResult<PathBuf> {
    std::fs::create_dir_all(folder)?;
    let name = version_path
        .with_extension("json")
        .file_name()
        .map(|name| name.to_os_string())
        .unwrap_or_default();
    let target = folder.join(name);
    let payload = serde_json::json!({
        "character": character,
        "job": job,
        "source": source,
        "saved_at": when.format("%Y-%m-%dT%H:%M:%S").to_string(),
        "version": version_path.file_name().and_then(|name| name.to_str()).unwrap_or_default(),
        "sets": sets,
    });
    std::fs::write(&target, serde_json::to_string_pretty(&payload)? + "\n")?;
    Ok(target)
}

pub fn defaults_dir(repo_root: Option<&Path>, resource_dir: Option<&Path>) -> Option<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(override_dir) = std::env::var("FANXI_GEARSWAP_DIR") {
        if !override_dir.trim().is_empty() {
            candidates.push(crate::config::expand_home(override_dir.trim()));
        }
    }
    if let Some(root) = repo_root {
        candidates.push(root.join("gearswap"));
    }
    if let Some(resources) = resource_dir {
        candidates.push(resources.join("gearswap"));
    }
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join("gearswap"));
        candidates.push(cwd.join("..").join("gearswap"));
    }
    for candidate in candidates {
        if candidate.is_dir() && has_lua(&candidate) {
            return Some(candidate);
        }
    }
    None
}

fn has_lua(folder: &Path) -> bool {
    std::fs::read_dir(folder)
        .map(|entries| {
            entries.flatten().any(|entry| {
                entry
                    .path()
                    .extension()
                    .and_then(|ext| ext.to_str())
                    .map(|ext| ext.eq_ignore_ascii_case("lua"))
                    .unwrap_or(false)
            })
        })
        .unwrap_or(false)
}

/// Whether a loaded library came from the bundled job defaults folder. Those are the libraries
/// the launcher owns and may write back; an imported file is never modified in place.
pub fn is_default_library(path: &Path, folder: &Path) -> bool {
    let canon = |value: &Path| std::fs::canonicalize(value).unwrap_or_else(|_| value.to_path_buf());
    canon(path).starts_with(canon(folder))
}

pub fn default_file(folder: &Path, job: &str) -> Option<PathBuf> {
    let abbr = job_abbr(&Value::String(job.to_string()));
    if abbr.is_empty() {
        return None;
    }
    let candidate = folder.join(format!("{abbr}.lua"));
    candidate.is_file().then_some(candidate)
}

pub fn apply_set(
    sets: &mut BTreeMap<String, BTreeMap<String, String>>,
    path: &str,
    items: BTreeMap<String, String>,
    original_path: Option<&str>,
    keep_original: bool,
) -> AppResult<String> {
    let path = normalize_set_path(path)?;
    let items = clean_named_items(&items)?;
    if items.is_empty() {
        return Err(AppError::Validation(
            "a set needs at least one item".to_string(),
        ));
    }
    let original = original_path.map(normalize_set_path).transpose()?;
    if keep_original && original.as_deref() == Some(path.as_str()) {
        return Err(AppError::Validation(
            "choose a new path for the copy".to_string(),
        ));
    }
    let ignored = if keep_original {
        None
    } else {
        original.clone()
    };
    let candidates = sets
        .keys()
        .filter(|other| Some(other.as_str()) != ignored.as_deref())
        .cloned();
    if let Some(conflict) = path_conflict(&path, candidates) {
        return Err(AppError::Validation(format!(
            "{path} collides with {conflict}"
        )));
    }
    if let Some(original) = original {
        if !keep_original && original != path {
            sets.remove(&original);
        }
    }
    sets.insert(path.clone(), items);
    Ok(path)
}

fn value_i64(value: &Value) -> Option<i64> {
    value
        .as_i64()
        .or_else(|| value.as_u64().and_then(|number| i64::try_from(number).ok()))
        .or_else(|| value.as_str().and_then(|text| text.parse().ok()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn when() -> DateTime<Local> {
        Local.with_ymd_and_hms(2026, 10, 21, 9, 23, 19).unwrap()
    }

    use chrono::TimeZone;

    #[test]
    fn jobs_and_slots() {
        let state = serde_json::json!({"player": {"job": 13, "level": 99, "name": "Onedough"}});
        let job = job_from_state(Some(&state)).unwrap();
        assert_eq!((job.abbr.as_str(), job.level), ("NIN", 99));
        assert_eq!(normalize_slot("left_ear"), "ear1");
    }

    #[test]
    fn flattens_sets_and_augments() {
        let tree = serde_json::json!({
            "idle": {"pdt": {"head": "Nyame Helm", "left_ear": "Tuisto Earring"}},
            "midcast": {"Enfeebling Magic": {"body": {"name": "Nyame Mail"},
                                             "ring2": "Dingir Ring"}}
        });
        let sets = flatten_sets(&tree);
        assert_eq!(sets["sets.idle.pdt"]["head"], "Nyame Helm");
        assert_eq!(sets["sets.idle.pdt"]["ear1"], "Tuisto Earring");
        assert_eq!(sets["sets.midcast.Enfeebling Magic"]["body"], "Nyame Mail");
        assert!(!sets.contains_key("sets.idle"));

        let detailed = flatten_sets_detailed(&serde_json::json!({
            "idle": {"dt": {"head": {"name": "Nyame Helm", "augments": ["HP+60", "DEF+30"]}}}
        }));
        assert_eq!(detailed["sets.idle.dt"]["head"].augments.len(), 2);
    }

    #[test]
    fn paths_round_trip() {
        assert_eq!(normalize_set_path("idle.pdt").unwrap(), "sets.idle.pdt");
        assert_eq!(
            lua_path("sets.midcast.Enfeebling Magic").unwrap(),
            "sets.midcast[\"Enfeebling Magic\"]"
        );
        assert!(normalize_set_path("sets..pdt").is_err());
        assert_eq!(
            path_conflict("sets.idle", ["sets.idle.pdt".to_string()]),
            Some("sets.idle.pdt".to_string())
        );
    }

    #[test]
    fn only_bundled_libraries_are_written() {
        let folder = std::env::temp_dir().join(format!(
            "fanxi-gear-defaults-{}-{}",
            std::process::id(),
            when().timestamp()
        ));
        std::fs::create_dir_all(&folder).unwrap();
        let inside = folder.join("NIN.lua");
        std::fs::write(&inside, "-- sets\n").unwrap();
        assert!(is_default_library(&inside, &folder));
        let outside = std::env::temp_dir().join("SomebodyElses.lua");
        assert!(!is_default_library(&outside, &folder));
        std::fs::remove_dir_all(&folder).ok();
    }

    #[test]
    fn writes_a_library_back_with_one_backup() {
        let folder = std::env::temp_dir().join(format!(
            "fanxi-gear-write-{}-{}",
            std::process::id(),
            when().timestamp()
        ));
        std::fs::create_dir_all(&folder).unwrap();
        let file = folder.join("NIN.lua");
        std::fs::write(&file, "-- original\n").unwrap();
        let mut sets = BTreeMap::new();
        sets.insert(
            "sets.weaponset.katana".to_string(),
            BTreeMap::from([
                ("main".to_string(), "Dokoku".to_string()),
                ("sub".to_string(), "Kikoku".to_string()),
            ]),
        );
        let (target, backup) = write_library(&file, &sets, "Onedough", "NIN", "", when()).unwrap();
        assert_eq!(target, file);
        let backup = backup.expect("the first write keeps the original");
        assert!(backup.exists());
        assert_eq!(std::fs::read_to_string(&backup).unwrap(), "-- original\n");
        let text = std::fs::read_to_string(&file).unwrap();
        assert!(text.contains("sets.weaponset.katana = {"));
        assert!(text.contains("sub = \"Kikoku\""));
        assert!(text.contains("kept as a .bak"));
        // A second write reuses the first backup instead of replacing it.
        let (_, second) = write_library(&file, &sets, "Onedough", "NIN", "", when()).unwrap();
        assert_eq!(second.as_deref(), Some(backup.as_path()));
        assert_eq!(std::fs::read_to_string(&backup).unwrap(), "-- original\n");
        std::fs::remove_dir_all(&folder).ok();
    }

    #[test]
    fn serializes_a_reimportable_file() {
        let mut sets = BTreeMap::new();
        sets.insert(
            "sets.idle".to_string(),
            BTreeMap::from([("head".to_string(), "Nyame Helm".to_string())]),
        );
        let text = serialize_library(&sets, "Aria", "WAR", "", when()).unwrap();
        assert!(text.contains("function get_sets()"));
        assert!(text.contains("sets.idle = {"));
        assert!(text.contains("head = \"Nyame Helm\""));
        assert!(text.contains("2026-10-21 09:23:19"));
        assert_eq!(versioned_name("WAR", when()), "WAR-20261021-092319.lua");
    }

    #[test]
    fn applies_and_renames_a_set() {
        let mut sets = BTreeMap::new();
        sets.insert(
            "sets.idle".to_string(),
            BTreeMap::from([("head".to_string(), "A".to_string())]),
        );
        let path = apply_set(
            &mut sets,
            "idle.pdt",
            BTreeMap::from([("head".to_string(), "B".to_string())]),
            Some("sets.idle"),
            false,
        )
        .unwrap();
        assert_eq!(path, "sets.idle.pdt");
        assert!(!sets.contains_key("sets.idle"));
        assert_eq!(sets["sets.idle.pdt"]["head"], "B");
    }
}
