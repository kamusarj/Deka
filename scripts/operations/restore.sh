#!/usr/bin/env bash
# Restore only to an empty database and uploads volume, with current deletion evidence.
set -euo pipefail
umask 077
if [[ $# -lt 4 || $# -gt 5 ]]; then
  echo 'Usage: restore.sh ENV_FILE BACKUP_DIRECTORY CURRENT_DELETION_JOURNAL ACTOR_ID [--apply]' >&2
  exit 2
fi
environment=$1
backup_directory=$(realpath "$2")
journal=$(realpath "$3")
actor_id=$4
[[ "$actor_id" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid actor ID' >&2; exit 2; }
[[ "$journal" != "$backup_directory"/* ]] || { echo 'Supply current deletion evidence kept independently of the old backup' >&2; exit 2; }
compose=(docker compose --env-file "$environment" -f docker-compose.production.yml)
"${compose[@]}" config --quiet
python3 - "$backup_directory" <<'PY'
import hashlib, json, sys, tarfile
from pathlib import Path, PurePosixPath
root = Path(sys.argv[1])
manifest = json.loads((root/'manifest.json').read_text())
assert manifest['consistent_writers_stopped']
for name, digest in manifest['files'].items():
    assert Path(name).name == name
    with (root/name).open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == digest, 'Backup checksum mismatch'
with tarfile.open(root/'uploads.tar.gz') as archive:
    for item in archive:
        path = PurePosixPath(item.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert item.isfile() or item.isdir(), 'Links/devices are not allowed in restored uploads'
PY
if [[ ${5:-} != --apply ]]; then
  echo 'Dry run: verify checksums; require empty target database/uploads; restore; apply current deletion journal; leave backend stopped for validation.'
  exit 0
fi
authority=$(realpath "${CURRENT_AUTHORITY_JOURNAL:?Supply a current signed authority journal outside the backup}")
[[ "$authority" != "$backup_directory"/* ]] || { echo 'Authority evidence must be independent of the old backup' >&2; exit 2; }
if [[ -n $("${compose[@]}" ps --status running --quiet backend) ]]; then
  echo 'Backend must be stopped before restore' >&2; exit 2
fi
"${compose[@]}" up -d --wait postgres
count=$("${compose[@]}" exec -T postgres psql -U smart_exam -d smart_exam_db -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
[[ "$count" == 0 ]] || { echo 'Refusing to overwrite a nonempty database' >&2; exit 2; }
"${compose[@]}" run --rm --no-deps --entrypoint python backend -c 'from pathlib import Path; assert not any(Path("/app/app/data/uploads").iterdir()), "Uploads must be empty"'
"${compose[@]}" exec -T postgres pg_restore -U smart_exam -d smart_exam_db --no-owner --no-acl --exit-on-error < "$backup_directory/postgres.dump"
"${compose[@]}" run --rm -T --no-deps --entrypoint tar backend -C /app/app/data/uploads -xzf - < "$backup_directory/uploads.tar.gz"
"${compose[@]}" run --rm --no-deps --entrypoint python backend -m app.core.migrations
"${compose[@]}" run --rm --no-deps -v "$journal:/tmp/current-deletions.json:ro" --entrypoint python backend -m app.services.deletion_journal reconcile --journal /tmp/current-deletions.json --actor-id "$actor_id" --apply
"${compose[@]}" run --rm --no-deps --entrypoint python backend -m app.services.document_cleanup --apply
"${compose[@]}" run --rm --no-deps -v "$authority:/tmp/current-authority.json:ro" --entrypoint python backend -m app.services.restore_authority reconcile --journal /tmp/current-authority.json --actor-id "$actor_id" --apply
printf '%s\n' 'Restored; backend remains stopped. Verify roles, ledger, documents, RAG and current deletion evidence before opening access.'
