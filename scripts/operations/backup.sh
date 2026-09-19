#!/usr/bin/env bash
# Consistent pilot backup by pausing writers. Default is a reviewable dry run.
set -euo pipefail
umask 077
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo 'Usage: backup.sh ENV_FILE NEW_BACKUP_DIRECTORY [--apply]' >&2
  exit 2
fi
environment=$1
backup_directory=$2
apply=${3:-}
[[ -f "$environment" ]] || { echo 'Environment file does not exist' >&2; exit 2; }
[[ ! -e "$backup_directory" ]] || { echo 'Choose a new backup directory' >&2; exit 2; }
compose=(docker compose --env-file "$environment" -f docker-compose.production.yml)
"${compose[@]}" config --quiet
if [[ "$apply" != --apply ]]; then
  echo 'Dry run: stop backend writers; export deletion journal, PostgreSQL and uploads; checksum artifacts; restart backend.'
  exit 0
fi
mkdir -p "$backup_directory"
mapfile -t running_backends < <("${compose[@]}" ps --status running --quiet backend)
"${compose[@]}" stop backend
restore_writers() {
  if (( ${#running_backends[@]} )); then
    docker start "${running_backends[@]}" >/dev/null
  fi
}
trap restore_writers EXIT
"${compose[@]}" exec -T postgres pg_dump -U smart_exam -d smart_exam_db -Fc > "$backup_directory/postgres.dump"
"${compose[@]}" run --rm --no-deps --entrypoint tar backend -C /app/app/data/uploads -czf - . > "$backup_directory/uploads.tar.gz"
"${compose[@]}" run --rm --no-deps --entrypoint python backend -m app.services.deletion_journal export > "$backup_directory/deletions.json"
"${compose[@]}" images --format json > "$backup_directory/images.json"
python3 - "$backup_directory" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
root = Path(sys.argv[1])
manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'consistent_writers_stopped': True,
            'files': {path.name: hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() for path in root.iterdir() if path.is_file()}}
(root/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
PY
echo 'Backup created. Copy encrypted artifacts and the latest deletion journal to separate restricted off-host storage; verify restore before accepting the backup.'
