//! The window the launcher asks the game to open.
//!
//! `host64` already accepts `--reg-final`, a registry file loaded after the host's `saved.reg`.
//! Five of the game's own display keys live there: `0001` x `0002` are the window size, `0034` is
//! the window mode (0 full screen, 1 windowed, 2 borderless, 3 borderless full screen), and `0037`
//! x `0038` are the menu resolution, which is the window size over the UI scale. Writing them as a
//! launcher-owned overlay means Settings can choose the size the game opens at without touching the
//! player's game folder or their saved registry.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, Monitor};

use crate::config;
use crate::error::{AppError, AppResult};

pub const MIN_WIDTH: u32 = 640;
pub const MIN_HEIGHT: u32 = 480;
pub const MAX_DIMENSION: u32 = 16_384;
pub const MIN_UI_SCALE: f64 = 0.5;
pub const MAX_UI_SCALE: f64 = 3.0;
const MIN_MENU_WIDTH: u32 = 320;
const MIN_MENU_HEIGHT: u32 = 240;
const DEFAULT_UI_SCALE: f64 = 2.0;

/// The game's own window modes, in the order the registry numbers them.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum WindowMode {
    /// A normal window with a frame.
    #[default]
    Windowed,
    /// A frameless window at the chosen size.
    Borderless,
    /// The display's own mode, in place.
    Fullscreen,
    /// Frameless over the whole desktop, at the display's size.
    BorderlessFullscreen,
}

impl WindowMode {
    /// The value the game reads from `settings.reg` key 0034.
    pub fn registry_value(self) -> u32 {
        match self {
            Self::Fullscreen => 0,
            Self::Windowed => 1,
            Self::Borderless => 2,
            Self::BorderlessFullscreen => 3,
        }
    }
}

/// The game window settings the launcher writes for `host64`.
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct GameDisplay {
    pub mode: WindowMode,
    pub width: u32,
    pub height: u32,
    /// The window size divided by this is the menu resolution. 2 renders the menus at half the
    /// window's resolution, which makes them appear larger (the sign-in screen's default).
    pub ui_scale: f64,
}

impl Default for GameDisplay {
    fn default() -> Self {
        Self {
            mode: WindowMode::Windowed,
            width: 1280,
            height: 720,
            ui_scale: DEFAULT_UI_SCALE,
        }
    }
}

impl GameDisplay {
    /// The menu resolution the game's interface is laid out at.
    pub fn menu_size(&self) -> (u32, u32) {
        let display = self.sanitized();
        let width = (display.width as f64 / display.ui_scale).round() as u32;
        let height = (display.height as f64 / display.ui_scale).round() as u32;
        (
            even(width).max(MIN_MENU_WIDTH).min(display.width),
            even(height).max(MIN_MENU_HEIGHT).min(display.height),
        )
    }

    /// Reject sizes and scales the game cannot use, before they reach a launch.
    pub fn validate(&self) -> AppResult<()> {
        if !(MIN_WIDTH..=MAX_DIMENSION).contains(&self.width) {
            return Err(AppError::Validation(format!(
                "the game window width must be between {MIN_WIDTH} and {MAX_DIMENSION} pixels"
            )));
        }
        if !(MIN_HEIGHT..=MAX_DIMENSION).contains(&self.height) {
            return Err(AppError::Validation(format!(
                "the game window height must be between {MIN_HEIGHT} and {MAX_DIMENSION} pixels"
            )));
        }
        if !self.ui_scale.is_finite() || !(MIN_UI_SCALE..=MAX_UI_SCALE).contains(&self.ui_scale) {
            return Err(AppError::Validation(format!(
                "the interface scale must be between {MIN_UI_SCALE}x and {MAX_UI_SCALE}x"
            )));
        }
        Ok(())
    }

    /// Valid, rounded values. Even dimensions keep the game's render targets and menus even; a
    /// stale or hand-edited configuration is clamped rather than refused at launch.
    pub fn sanitized(self) -> Self {
        let ui_scale = if self.ui_scale.is_finite() {
            self.ui_scale.clamp(MIN_UI_SCALE, MAX_UI_SCALE)
        } else {
            DEFAULT_UI_SCALE
        };
        Self {
            mode: self.mode,
            width: even(self.width).clamp(MIN_WIDTH, MAX_DIMENSION),
            height: even(self.height).clamp(MIN_HEIGHT, MAX_DIMENSION),
            ui_scale,
        }
    }

    /// The overlay `host64` loads after `saved.reg`.
    pub fn registry_text(&self) -> String {
        let display = self.sanitized();
        let (menu_width, menu_height) = display.menu_size();
        format!(
            "REGEDIT4\r\n\r\n[HKEY_LOCAL_MACHINE\\SOFTWARE\\PlayOnlineUS\\SquareEnix\\FinalFantasyXI]\r\n\
             \"0001\"=dword:{:08x}\r\n\
             \"0002\"=dword:{:08x}\r\n\
             \"0034\"=dword:{:08x}\r\n\
             \"0037\"=dword:{:08x}\r\n\
             \"0038\"=dword:{:08x}\r\n",
            display.width,
            display.height,
            display.mode.registry_value(),
            menu_width,
            menu_height
        )
    }
}

fn even(value: u32) -> u32 {
    value / 2 * 2
}

/// Where the launcher keeps the overlay it hands to every visible client.
pub fn overlay_path() -> PathBuf {
    config::data_dir().join("display.reg")
}

/// Write the overlay for the next launch. The file is replaced atomically so a launch that starts
/// while the previous one is still writing never reads a half-written registry.
pub fn write_overlay(display: &GameDisplay) -> AppResult<PathBuf> {
    display.validate()?;
    let path = overlay_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    write_reg_file(&path, display)?;
    Ok(path)
}

fn write_reg_file(path: &Path, display: &GameDisplay) -> AppResult<()> {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("display.reg");
    let tmp = path.with_file_name(format!("{name}.{}.tmp", std::process::id()));
    fs::write(&tmp, display.registry_text().as_bytes())?;
    #[cfg(windows)]
    {
        // rename() does not replace an existing file on every Windows filesystem.
        let _ = fs::remove_file(path);
    }
    if let Err(error) = fs::rename(&tmp, path) {
        let _ = fs::remove_file(&tmp);
        return Err(error.into());
    }
    Ok(())
}

/// The last display the game saved in the host's `saved.reg`.
///
/// `launcher.json` files written before the Game window card existed have no display settings;
/// reading the game's own saved values once keeps an existing player's window exactly as it was
/// until they choose something in Settings.
pub fn read_saved_display() -> Option<GameDisplay> {
    let dir = config::data_dir();
    let mut candidates = vec![dir.join("saved.reg")];
    // host64 spells the Linux folder "Fanxi" while launcher.json lives in "fanxi".
    if let Some(parent) = dir.parent() {
        candidates.push(parent.join("Fanxi").join("saved.reg"));
    }
    candidates
        .into_iter()
        .find_map(|path| read_saved_display_at(&path))
}

fn read_saved_display_at(path: &Path) -> Option<GameDisplay> {
    let raw = fs::read(path).ok()?;
    let text = decode_reg_text(&raw);
    let mut width = None;
    let mut height = None;
    let mut mode = None;
    let mut menu_width = None;
    for line in text.lines() {
        let line = line.trim();
        if let Some(value) = reg_dword(line, "0001") {
            width = Some(value);
        } else if let Some(value) = reg_dword(line, "0002") {
            height = Some(value);
        } else if let Some(value) = reg_dword(line, "0034") {
            mode = Some(value);
        } else if let Some(value) = reg_dword(line, "0037") {
            menu_width = Some(value);
        }
    }
    let width = width?;
    let height = height?;
    if !(MIN_WIDTH..=MAX_DIMENSION).contains(&width)
        || !(MIN_HEIGHT..=MAX_DIMENSION).contains(&height)
    {
        return None;
    }
    let mode = match mode.unwrap_or(1) {
        0 => WindowMode::Fullscreen,
        2 => WindowMode::Borderless,
        3 => WindowMode::BorderlessFullscreen,
        _ => WindowMode::Windowed,
    };
    let ui_scale = match menu_width {
        Some(menu_width) if menu_width >= 64 && width > menu_width => {
            (width as f64 / menu_width as f64).clamp(MIN_UI_SCALE, MAX_UI_SCALE)
        }
        // 0 is the game's "use the window size" setting. A present but unusable value keeps the
        // old 1:1 interface rather than silently enlarging it.
        Some(_) => 1.0,
        // No menu keys at all: the launcher's recommended scale is the best guess.
        None => DEFAULT_UI_SCALE,
    };
    Some(
        GameDisplay {
            mode,
            width,
            height,
            ui_scale,
        }
        .sanitized(),
    )
}

fn reg_dword(line: &str, key: &str) -> Option<u32> {
    let prefix = format!("\"{key}\"=dword:");
    let value = line.strip_prefix(&prefix)?;
    u32::from_str_radix(value.trim(), 16).ok()
}

fn decode_reg_text(raw: &[u8]) -> String {
    if raw.starts_with(&[0xFF, 0xFE]) {
        let units: Vec<u16> = raw[2..]
            .chunks_exact(2)
            .map(|pair| u16::from_le_bytes([pair[0], pair[1]]))
            .collect();
        return String::from_utf16_lossy(&units);
    }
    String::from_utf8_lossy(raw).into_owned()
}

/// One display, in the units the game's window API uses (screen coordinates on macOS, pixels
/// elsewhere), so "fit this display" produces a window that actually fits.
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DisplayMonitor {
    /// What `launcher.json` remembers for this display: the OS's name, or its size and position
    /// when the OS has no name for it. A choice that no longer matches falls back to the main
    /// display.
    pub id: String,
    pub name: Option<String>,
    pub width: u32,
    pub height: u32,
    pub work_width: u32,
    pub work_height: u32,
    pub physical_width: u32,
    pub physical_height: u32,
    pub scale_factor: f64,
    pub primary: bool,
}

#[derive(Clone, Debug, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DisplayInfo {
    pub monitors: Vec<DisplayMonitor>,
}

/// The displays attached right now, for the resolution presets in Settings.
pub fn info(app: &AppHandle) -> DisplayInfo {
    let primary = app.primary_monitor().ok().flatten();
    let mut monitors: Vec<DisplayMonitor> = app
        .available_monitors()
        .unwrap_or_default()
        .into_iter()
        .filter(|monitor| monitor.size().width > 0 && monitor.size().height > 0)
        .map(|monitor| {
            let scale = if monitor.scale_factor() > 0.0 {
                monitor.scale_factor()
            } else {
                1.0
            };
            let physical_width = monitor.size().width;
            let physical_height = monitor.size().height;
            let width = game_units(physical_width, scale);
            let height = game_units(physical_height, scale);
            let work = monitor.work_area().size;
            let (work_width, work_height) = if work.width > 0 && work.height > 0 {
                (
                    game_units(work.width, scale),
                    game_units(work.height, scale),
                )
            } else {
                (width, height)
            };
            let is_primary = primary.as_ref().is_some_and(|candidate| {
                candidate.position() == monitor.position() && candidate.size() == monitor.size()
            });
            DisplayMonitor {
                id: monitor_id(&monitor),
                name: monitor.name().cloned(),
                width,
                height,
                work_width,
                work_height,
                physical_width,
                physical_height,
                scale_factor: scale,
                primary: is_primary,
            }
        })
        .collect();
    if !monitors.iter().any(|monitor| monitor.primary) {
        if let Some(first) = monitors.first_mut() {
            first.primary = true;
        }
    }
    DisplayInfo { monitors }
}

#[cfg(target_os = "macos")]
fn game_units(physical: u32, scale: f64) -> u32 {
    ((physical as f64) / scale).round().max(1.0) as u32
}

#[cfg(not(target_os = "macos"))]
fn game_units(physical: u32, _scale: f64) -> u32 {
    physical
}

#[cfg(target_os = "macos")]
fn game_units_i32(physical: i32, scale: f64) -> i32 {
    ((physical as f64) / scale).round() as i32
}

#[cfg(not(target_os = "macos"))]
fn game_units_i32(physical: i32, _scale: f64) -> i32 {
    physical
}

/// The app handle, kept from startup so a launch can read the attached displays without
/// threading it through the process table. `None` in unit tests, where there is no app.
static APP: OnceLock<AppHandle> = OnceLock::new();

pub fn remember_app(app: &AppHandle) {
    let _ = APP.set(app.clone());
}

/// What `launcher.json` stores for a display. The OS name identifies a display across launches;
/// on macOS that is the model number ("Monitor #29451"), so two displays of the same model share
/// an id and the first one wins.
pub fn monitor_id(monitor: &Monitor) -> String {
    match monitor.name() {
        Some(name) if !name.trim().is_empty() => name.trim().to_string(),
        _ => format!(
            "{}x{}@{},{}",
            monitor.size().width,
            monitor.size().height,
            monitor.position().x,
            monitor.position().y
        ),
    }
}

/// The display a saved choice names. An empty choice is the main display; a display that is no
/// longer attached is `None` (the caller leaves the windows where they are rather than moving
/// them somewhere the player did not ask for).
pub fn choose_monitor(app: &AppHandle, id: &str) -> Option<Monitor> {
    let id = id.trim();
    if id.is_empty() {
        return app.primary_monitor().ok().flatten();
    }
    app.available_monitors()
        .ok()?
        .into_iter()
        .find(|monitor| monitor_id(monitor) == id)
}

/// A display's place and size in the units the game's window API uses: screen points on macOS,
/// pixels elsewhere. `FANXI_DISPLAY` carries these to `host64`, which puts its windows here.
pub fn game_rect(monitor: &Monitor) -> (i32, i32, u32, u32) {
    let scale = if monitor.scale_factor() > 0.0 {
        monitor.scale_factor()
    } else {
        1.0
    };
    let position = monitor.position();
    (
        game_units_i32(position.x, scale),
        game_units_i32(position.y, scale),
        game_units(monitor.size().width, scale),
        game_units(monitor.size().height, scale),
    )
}

/// `FANXI_DISPLAY=x,y,w,h` for the chosen display, or `None` for the main display (whose windows
/// keep the placement they have always had) or a display that is not attached.
pub fn game_window_spec(monitor: &str) -> Option<String> {
    if monitor.trim().is_empty() {
        return None;
    }
    let app = APP.get()?;
    let target = choose_monitor(app, monitor)?;
    Some(display_spec(game_rect(&target)))
}

fn display_spec((x, y, width, height): (i32, i32, u32, u32)) -> String {
    format!("{x},{y},{width},{height}")
}

/// Puts the launcher's own window in the middle of the chosen display's usable area. An empty
/// choice is the main display, where the window's configured center already is; moving there too
/// makes "Main display" take effect after the choice changed.
pub fn place_launcher_window(app: &AppHandle, monitor: &str) -> AppResult<()> {
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| AppError::Config("the launcher window is not open".to_string()))?;
    let Some(target) = choose_monitor(app, monitor) else {
        return Ok(());
    };
    let scale = if target.scale_factor() > 0.0 {
        target.scale_factor()
    } else {
        1.0
    };
    let area = target.work_area();
    // Tauri positions the window from its logical (point) coordinates; the monitor's work area is
    // physical. The outer size is physical at the window's current scale factor.
    let window_scale = window
        .scale_factor()
        .ok()
        .filter(|scale| *scale > 0.0)
        .unwrap_or(1.0);
    let outer = window.outer_size().map_err(|error| {
        AppError::Config(format!("cannot read the launcher window's size: {error}"))
    })?;
    let (x, y) = centered_in(
        (
            area.position.x as f64 / scale,
            area.position.y as f64 / scale,
            area.size.width as f64 / scale,
            area.size.height as f64 / scale,
        ),
        (
            outer.width as f64 / window_scale,
            outer.height as f64 / window_scale,
        ),
    );
    window
        .set_position(tauri::LogicalPosition::new(x, y))
        .map_err(|error| AppError::Config(format!("cannot move the launcher window: {error}")))?;
    Ok(())
}

fn centered_in(area: (f64, f64, f64, f64), size: (f64, f64)) -> (f64, f64) {
    let (area_x, area_y, area_width, area_height) = area;
    let (width, height) = size;
    (
        area_x + (area_width - width) / 2.0,
        area_y + (area_height - height) / 2.0,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_every_window_mode_to_its_registry_value() {
        assert_eq!(WindowMode::Fullscreen.registry_value(), 0);
        assert_eq!(WindowMode::Windowed.registry_value(), 1);
        assert_eq!(WindowMode::Borderless.registry_value(), 2);
        assert_eq!(WindowMode::BorderlessFullscreen.registry_value(), 3);
        assert_eq!(
            serde_json::to_string(&WindowMode::BorderlessFullscreen).unwrap(),
            "\"borderless-fullscreen\""
        );
    }

    #[test]
    fn writes_the_game_display_keys_and_menu_resolution() {
        let display = GameDisplay {
            mode: WindowMode::BorderlessFullscreen,
            width: 1920,
            height: 1080,
            ui_scale: 2.0,
        };
        let text = display.registry_text();
        assert!(text.starts_with("REGEDIT4\r\n"));
        assert!(
            text.contains(
                "[HKEY_LOCAL_MACHINE\\SOFTWARE\\PlayOnlineUS\\SquareEnix\\FinalFantasyXI]"
            )
        );
        assert!(text.contains("\"0001\"=dword:00000780\r\n"));
        assert!(text.contains("\"0002\"=dword:00000438\r\n"));
        assert!(text.contains("\"0034\"=dword:00000003\r\n"));
        assert!(text.contains("\"0037\"=dword:000003c0\r\n"));
        assert!(text.contains("\"0038\"=dword:0000021c\r\n"));
    }

    #[test]
    fn rounds_odd_sizes_and_keeps_the_menu_supported() {
        let display = GameDisplay {
            mode: WindowMode::Windowed,
            width: 1367,
            height: 769,
            ui_scale: 3.0,
        }
        .sanitized();
        assert_eq!((display.width, display.height), (1366, 768));
        assert_eq!(display.menu_size(), (454, 256));

        let tiny = GameDisplay {
            mode: WindowMode::Windowed,
            width: 640,
            height: 480,
            ui_scale: 3.0,
        };
        assert_eq!(tiny.menu_size(), (MIN_MENU_WIDTH, MIN_MENU_HEIGHT));
    }

    #[test]
    fn rejects_a_window_the_game_cannot_open() {
        let error = GameDisplay {
            width: 320,
            ..GameDisplay::default()
        }
        .validate()
        .unwrap_err();
        assert!(error.to_string().contains("width"));

        let error = GameDisplay {
            ui_scale: 4.0,
            ..GameDisplay::default()
        }
        .validate()
        .unwrap_err();
        assert!(error.to_string().contains("interface scale"));
    }

    #[test]
    fn default_display_is_a_fitting_window() {
        let display = GameDisplay::default();
        assert_eq!(display.mode, WindowMode::Windowed);
        assert_eq!((display.width, display.height), (1280, 720));
        assert_eq!(display.menu_size(), (640, 360));
    }

    #[test]
    fn a_partial_game_display_keeps_the_other_defaults() {
        let display: GameDisplay = serde_json::from_str(r#"{"mode":"borderless"}"#).unwrap();
        assert_eq!(display.mode, WindowMode::Borderless);
        assert_eq!((display.width, display.height), (1280, 720));
        assert_eq!(display.ui_scale, 2.0);
    }

    fn temp_dir(label: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "fanxi-display-{label}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn reads_the_games_saved_display() {
        let dir = temp_dir("read");
        let path = dir.join("saved.reg");
        fs::write(
            &path,
            "REGEDIT4\r\n\r\n\
             [HKEY_LOCAL_MACHINE\\SOFTWARE\\PlayOnlineUS\\SquareEnix\\FinalFantasyXI]\r\n\
             \"0001\"=dword:00000a00\r\n\
             \"0002\"=dword:000005a0\r\n\
             \"0034\"=dword:00000002\r\n\
             \"0037\"=dword:00000500\r\n\
             \"0038\"=dword:000002d0\r\n",
        )
        .unwrap();
        let display = read_saved_display_at(&path).unwrap();
        assert_eq!(display.mode, WindowMode::Borderless);
        assert_eq!((display.width, display.height), (2560, 1440));
        assert_eq!(display.ui_scale, 2.0);
        assert_eq!(display.menu_size(), (1280, 720));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_zero_menu_resolution_keeps_the_games_one_to_one_ui() {
        let dir = temp_dir("read-auto-menu");
        let path = dir.join("saved.reg");
        fs::write(
            &path,
            "REGEDIT4\r\n\r\n\"0001\"=dword:00000500\r\n\"0002\"=dword:000002d0\r\n\
             \"0034\"=dword:00000001\r\n\"0037\"=dword:00000000\r\n\
             \"0038\"=dword:00000000\r\n",
        )
        .unwrap();
        let display = read_saved_display_at(&path).unwrap();
        assert_eq!(display.ui_scale, 1.0);
        assert_eq!(display.menu_size(), (1280, 720));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn replaces_the_overlay_file_in_one_step() {
        let dir = temp_dir("write");
        let path = dir.join("display.reg");
        let first = GameDisplay {
            width: 1600,
            height: 900,
            ..GameDisplay::default()
        };
        write_reg_file(&path, &first).unwrap();
        assert!(
            fs::read_to_string(&path)
                .unwrap()
                .contains("\"0001\"=dword:00000640")
        );
        let second = GameDisplay {
            mode: WindowMode::Borderless,
            width: 1920,
            height: 1080,
            ..GameDisplay::default()
        };
        write_reg_file(&path, &second).unwrap();
        let text = fs::read_to_string(&path).unwrap();
        assert!(text.contains("\"0001\"=dword:00000780"));
        assert!(text.contains("\"0034\"=dword:00000002"));
        assert_eq!(
            fs::read_dir(&dir).unwrap().filter_map(Result::ok).count(),
            1,
            "only the final overlay is left behind"
        );
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn the_games_display_spec_is_its_window_units() {
        assert_eq!(
            display_spec((-3440, -458, 3440, 1440)),
            "-3440,-458,3440,1440"
        );
        assert_eq!(display_spec((0, 0, 1512, 982)), "0,0,1512,982");
    }

    #[test]
    fn the_launcher_window_is_centered_in_the_display() {
        // The S34CG50's usable area, and a window that is 1180 x 788 points.
        assert_eq!(
            centered_in((-3440.0, -458.0, 3440.0, 1440.0), (1180.0, 788.0)),
            (-2310.0, -132.0)
        );
        assert_eq!(
            centered_in((0.0, 38.0, 1512.0, 944.0), (1180.0, 788.0)),
            (166.0, 116.0)
        );
    }

    #[test]
    fn an_unattached_display_sends_no_placement() {
        // `game_window_spec` has no app handle in tests, so a choice cannot be resolved; the game
        // then keeps the placement it always had rather than being sent somewhere arbitrary.
        assert_eq!(game_window_spec("Monitor #29451"), None);
    }
}
