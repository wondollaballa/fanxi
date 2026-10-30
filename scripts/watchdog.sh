#!/bin/sh
# Run the client watchdog detached from this shell.
#   ./scripts/watchdog.sh           start (idempotent: the script's lock refuses a second copy)
#   ./scripts/watchdog.sh --status  show whether it is running
#   ./scripts/watchdog.sh --stop    stop it
set -e
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
case "$1" in
  --status)
    pgrep -fl "scripts/watchdog.py" || echo "watchdog is not running"
    ;;
  --stop)
    pkill -f "scripts/watchdog.py" && echo "watchdog stopped" || echo "watchdog was not running"
    ;;
  *)
    if ! pgrep -f "scripts/watchdog.py" >/dev/null 2>&1; then
      nohup python3 scripts/watchdog.py >> data/watchdog.out 2>&1 &
      echo "watchdog started (pid $!)"
    else
      echo "watchdog already running"
    fi
    ;;
esac
