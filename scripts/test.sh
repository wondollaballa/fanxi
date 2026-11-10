#!/bin/sh
# Run the server, launcher and tool tests.
set -e
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
echo "== server"
python3 -m unittest discover -s server/tests -v
echo "== launcher"
(cd launcher-rs && npm run check)
cargo test --manifest-path launcher-rs/src-tauri/Cargo.toml
echo "== tools"
python3 tools/gen_oboro.py --check
python3 tools/gen_limbus_weapons.py --check
python3 tests/verify_install_test.py
python3 tests/chat_complete_test.py
echo "== admin dashboard"
python3 tests/fanxi_tui_test.py
echo "== hud labels"
python3 tests/spell_names_test.py
echo "== hud spell sections"
python3 tests/spell_sections_test.py
echo "== spell mode groups"
python3 tests/spell_groups_test.py
echo "== hud cooldowns"
python3 tests/hud_cool_test.py
echo "== magic bag"
python3 tests/magic_bag_test.py
echo "== hud docking"
python3 tests/hud_dock_test.py
if [ -f build/third_party/imgui.a ]; then
    echo "== hud dock tabs"
    tests/dock_tabs_test.sh
fi
echo "== equip view"
python3 tests/equipview_hud_test.py
echo "== item name aliases"
python3 tests/reforged_items_test.py
echo "== corsair pickers"
python3 tests/cor_hud_test.py
echo "== trust actions"
python3 tests/trust_hud_test.py
echo "== battle waltzes"
python3 tests/dancer_waltz_test.py
echo "== syntax"
python3 -m compileall -q server/fanxi_server tools/make_brand_assets.py
echo "OK"
