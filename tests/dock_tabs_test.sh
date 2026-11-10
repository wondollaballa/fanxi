#!/bin/sh
# Regression test for the tab-group behaviour the HUD relies on (tests/dock_tabs_test.cpp):
# fit the group to the selected tab, keep a manual resize, minimize/maximize from the tab bar.
# Needs build/third_party/imgui.a (tools/thirdparty.py imgui); no game files or display.
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$here")
archive="$root/build/third_party/imgui.a"
if [ ! -f "$archive" ]; then
    echo "dock_tabs_test: $archive is missing; run python3 tools/thirdparty.py imgui" >&2
    exit 2
fi
cxx=${CXX:-clang++}
"$cxx" -std=c++17 -O1 -I"$root/third_party/imgui" \
    '-DIMGUI_USER_CONFIG="../../host/addons/imconfig_xi.h"' \
    "$here/dock_tabs_test.cpp" "$archive" -o "$root/build/dock_tabs_test"
"$root/build/dock_tabs_test"
