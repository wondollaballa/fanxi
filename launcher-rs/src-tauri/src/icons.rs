//! Item icons for the launcher's EquipViewer.
//!
//! The game's own resource layer decodes an item's 32x32 icon from the DATs (`res.item_icon_rgba`
//! in `host/addons/res_lua.c`), and the control addon returns it as top-down RGBA hex. This module
//! turns that into a PNG data URL and keeps a copy in `<data dir>/icons/<id>.png`, so the launcher
//! does not ask the game again for the same item. The slot order, ammo count and encumbrance
//! overlay mirror Windower's EquipViewer addon; the icon decode itself is Fanxi's resource reader.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};

use base64::Engine as _;
use png::{BitDepth, ColorType, Encoder};

use crate::config;
use crate::error::{AppError, AppResult};

fn memory() -> &'static Mutex<HashMap<u32, String>> {
    static CACHE: OnceLock<Mutex<HashMap<u32, String>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

pub fn cache_dir() -> PathBuf {
    config::data_dir().join("icons")
}

/// The PNG data URL for an item, if a previous session already cached it.
pub fn cached(id: u32) -> Option<String> {
    if let Some(url) = memory().lock().ok()?.get(&id) {
        return Some(url.clone());
    }
    let bytes = std::fs::read(cache_dir().join(format!("{id}.png"))).ok()?;
    let url = data_url(&bytes);
    if let Ok(mut cache) = memory().lock() {
        cache.insert(id, url.clone());
    }
    Some(url)
}

/// Encode RGBA bytes as a PNG, write the per-item cache file, and return the data URL.
pub fn store(id: u32, width: u32, height: u32, rgba: &[u8]) -> AppResult<String> {
    let png = encode_png(width, height, rgba)?;
    let url = data_url(&png);
    let folder = cache_dir();
    if std::fs::create_dir_all(&folder).is_ok() {
        // A failed cache write is not fatal: the icon still works for this session.
        let _ = std::fs::write(folder.join(format!("{id}.png")), &png);
    }
    if let Ok(mut cache) = memory().lock() {
        cache.insert(id, url.clone());
    }
    Ok(url)
}

pub fn data_url(png: &[u8]) -> String {
    format!(
        "data:image/png;base64,{}",
        base64::engine::general_purpose::STANDARD.encode(png)
    )
}

pub fn encode_png(width: u32, height: u32, rgba: &[u8]) -> AppResult<Vec<u8>> {
    if width == 0 || height == 0 || rgba.len() != (width as usize) * (height as usize) * 4 {
        return Err(AppError::Validation(
            "the icon is not a width x height RGBA image".to_string(),
        ));
    }
    let mut bytes = Vec::new();
    {
        let mut encoder = Encoder::new(&mut bytes, width, height);
        encoder.set_color(ColorType::Rgba);
        encoder.set_depth(BitDepth::Eight);
        let mut writer = encoder
            .write_header()
            .map_err(|error| AppError::Io(format!("cannot write icon PNG: {error}")))?;
        writer
            .write_image_data(rgba)
            .map_err(|error| AppError::Io(format!("cannot write icon PNG: {error}")))?;
    }
    Ok(bytes)
}

pub fn decode_hex(hex: &str) -> Option<Vec<u8>> {
    let text = hex.trim();
    if text.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(text.len() / 2);
    let bytes = text.as_bytes();
    for pair in bytes.chunks_exact(2) {
        let high = (pair[0] as char).to_digit(16)?;
        let low = (pair[1] as char).to_digit(16)?;
        out.push((high * 16 + low) as u8);
    }
    Some(out)
}

/// Parse one `icons` reply item and cache it. Empty icons (id 0 / no resource) are skipped.
pub fn from_reply(item: &serde_json::Value) -> Option<(u32, String)> {
    let id = item.get("id")?.as_u64()? as u32;
    let width = item.get("width")?.as_u64()? as u32;
    let height = item.get("height")?.as_u64()? as u32;
    let hex = item.get("rgba")?.as_str()?;
    if width == 0 || height == 0 || hex.is_empty() {
        return None;
    }
    let rgba = decode_hex(hex)?;
    let url = store(id, width, height, &rgba).ok()?;
    Some((id, url))
}

pub fn clear_cache() -> AppResult<usize> {
    if let Ok(mut cache) = memory().lock() {
        cache.clear();
    }
    let folder = cache_dir();
    let mut removed = 0;
    let Ok(entries) = std::fs::read_dir(&folder) else {
        return Ok(0);
    };
    for entry in entries.flatten() {
        if entry.path().extension().and_then(|ext| ext.to_str()) == Some("png")
            && std::fs::remove_file(entry.path()).is_ok()
        {
            removed += 1;
        }
    }
    Ok(removed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hex_round_trip() {
        assert_eq!(decode_hex("00ff10ab"), Some(vec![0, 255, 16, 171]));
        assert_eq!(decode_hex("abc"), None);
        assert_eq!(decode_hex("zz"), None);
    }

    #[test]
    fn png_encode_has_the_png_signature() {
        let rgba = vec![255u8; 2 * 2 * 4];
        let png = encode_png(2, 2, &rgba).expect("png");
        assert_eq!(&png[..8], b"\x89PNG\r\n\x1a\n");
        assert!(data_url(&png).starts_with("data:image/png;base64,"));
    }

    #[test]
    fn png_rejects_the_wrong_pixel_count() {
        assert!(encode_png(2, 2, &[0u8; 3]).is_err());
        assert!(encode_png(0, 0, &[]).is_err());
    }
}
