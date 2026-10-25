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
python3 tests/verify_install_test.py
python3 tests/chat_complete_test.py
echo "== syntax"
python3 -m compileall -q server/fanxi_server tools/make_brand_assets.py
echo "OK"
