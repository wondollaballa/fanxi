#!/bin/sh
# Run the Fanxi server from this checkout.
set -e
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/server"
exec "${PYTHON:-python3}" -m fanxi_server run "$@"
