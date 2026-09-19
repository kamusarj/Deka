#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/../.."
environment=${1:?deployment environment}
destination=${2:?restricted journal directory}
if [[ ${3:-} != --apply ]]; then
  echo 'Dry run: export current signed authority and deletion journal to a new restricted snapshot; atomically replace current symlink.'; exit 0
fi
mkdir -p "$destination"
[[ ! -L "$destination" ]] || { echo 'Journal destination must not be a symlink'; exit 1; }
chmod 700 "$destination"
destination=$(realpath "$destination")
exec 9>"$destination/.export.lock"
flock -n 9 || { echo 'A journal export is already running'; exit 1; }
snapshot=$(mktemp -d "$destination/snapshot.XXXXXXXX")
compose=(docker compose --env-file "$environment" -f docker-compose.production.yml)
complete=false
cleanup() { if [[ $complete == false ]]; then rm -rf -- "$snapshot";fi; }
trap cleanup EXIT
"${compose[@]}" run --rm --no-deps --entrypoint python backend -m app.services.restore_authority export > "$snapshot/authority.json"
"${compose[@]}" run --rm --no-deps --entrypoint python backend -m app.services.deletion_journal export > "$snapshot/deletions.json"
python3 - "$snapshot" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
a=json.loads((root/'authority.json').read_text());d=json.loads((root/'deletions.json').read_text())
assert a['signature'] and a['data']['users'] and isinstance(d,list)
PY
(cd "$snapshot" && sha256sum authority.json deletions.json > SHA256SUMS)
ln -s "${snapshot##*/}" "$destination/.current-${snapshot##*/}"
mv -Tf "$destination/.current-${snapshot##*/}" "$destination/current"
complete=true
echo 'Journal snapshot exported; copy the restricted snapshot off host and verify its checksums. No retention deletion performed.'
