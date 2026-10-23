#!/bin/sh
# Run every dependency-free test in the repository.
set -e
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
echo "== server"
python3 -m unittest discover -s server/tests -v
echo "== launcher"
python3 -m unittest discover -s launcher/tests -v
echo "== tools"
python3 tests/verify_install_test.py
echo "== syntax"
python3 -m compileall -q server/fanxi_server launcher/fanxi_launcher tools/make_brand_assets.py
echo "OK"
