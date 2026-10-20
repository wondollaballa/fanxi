#!/bin/sh
# Start the launcher from this checkout.
exec "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/launcher/fanxi-launcher" "$@"
