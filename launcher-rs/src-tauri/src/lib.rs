mod api;
mod commands;
mod config;
mod control;
mod error;
mod game;
mod gear;
mod icons;

use commands::AppState;
use tracing_subscriber::EnvFilter;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("fanxi_launcher=info,warn"));
    let _ = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(false)
        .try_init();

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            commands::bootstrap,
            commands::refresh_public,
            commands::get_config,
            commands::login,
            commands::register,
            commands::logout,
            commands::switch_account,
            commands::forget_account,
            commands::create_character,
            commands::save_character_design,
            commands::select_character,
            commands::set_last_page,
            commands::save_settings,
            commands::detect_game_dir,
            commands::find_host64,
            commands::defaults_dir,
            commands::build_game,
            commands::build_log,
            commands::open_data_dir,
            commands::launch,
            commands::launch_all,
            commands::team,
            commands::create_sub,
            commands::activate_sub,
            commands::create_sub_character,
            commands::launch_sub,
            commands::launch_team,
            commands::delete_sub,
            commands::list_instances,
            commands::stop_instance,
            commands::stop_all,
            commands::send_command,
            commands::send_chat,
            commands::control_state,
            commands::control_metrics,
            commands::set_follow,
            commands::follow_status,
            commands::follow_events,
            commands::gear_slots,
            commands::equip_icons,
            commands::gear_item_ids,
            commands::clear_icon_cache,
            commands::gear_job,
            commands::gear_load_default,
            commands::gear_load_file,
            commands::gear_equip,
            commands::gear_wear_set,
            commands::gear_phase,
            commands::gear_phase_status,
            commands::gear_phase_lock,
            commands::gear_phase_kiting,
            commands::gear_phase_resting,
            commands::gear_phase_focus,
            commands::gear_phase_lock_slots,
            commands::gear_job_spells,
            commands::gear_job_abilities,
            commands::gear_weapons,
            commands::gear_apply_set,
            commands::gear_save_library,
            commands::gear_save,
            commands::gear_versions,
            commands::gear_defaults,
            commands::game_log
        ])
        .run(tauri::generate_context!())
        .expect("error while running Fanxi Launcher");
}
