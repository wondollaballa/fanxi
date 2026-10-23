#!/bin/sh
# Pull a patched FINAL FANTASY XI folder from another machine, then check it.
#
#   scripts/fetch-retail.sh user@desktop:"/path/…/FINAL FANTASY XI" [dest] [verify options]
#
# PlayOnline's Check Files is what patches the data and it needs a graphics adapter, so the patch
# itself runs on a desktop. This copies the result here: rsync resumes a cut transfer, and then
# tools/verify_install.py says whether the tree is complete, which build its programs are, and —
# with --baseline — exactly which files the patch touched.
#
#   scripts/fetch-retail.sh me@pc:"C:/…/FINAL FANTASY XI" ~/ffxi-2026-10 \
#       --baseline ~/ffxi-2019
set -e
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

if [ -z "$1" ]; then
    echo 'usage: fetch-retail.sh user@host:"/path/to/FINAL FANTASY XI" [dest] [verify options]' >&2
    exit 2
fi
src=$1
shift
if [ -n "$1" ] && [ "${1#-}" = "$1" ]; then
    dest=$1
    shift
else
    dest=${FANXI_GAME_DIR:-$HOME/.local/share/fanxi/FINAL FANTASY XI}
fi

echo "from  $src"
echo "to    $dest"
mkdir -p "$dest"

# -a keeps the tree's timestamps, --partial keeps a half-copied DAT for the next run, and the
# trailing slashes copy the folder's contents rather than the folder itself. --progress rather
# than --info=progress2: macOS still ships rsync 2.6.9, which has no --info.
rsync -a --partial --human-readable --progress "$src/" "$dest/"

exec python3 tools/verify_install.py "$dest" "$@"
