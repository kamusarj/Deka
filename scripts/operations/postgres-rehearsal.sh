#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if [[ ${1:-} != --apply ]]; then
  echo 'Dry run: disposable loopback PostgreSQL, concurrency/migration/SIGKILL tests, cleanup.';exit 0
fi
name=audit-184-pg-$RANDOM-$RANDOM
cleanup() { docker rm -fv "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run -d --name "$name" -e POSTGRES_PASSWORD=synthetic-postgres-184 -e POSTGRES_DB=audit_test -p 127.0.0.1::5432 smart-exam-postgres:ready-184 >/dev/null
for i in {1..30}; do
  if docker exec "$name" pg_isready -U postgres -d audit_test >/dev/null; then break;fi
  sleep 1
done
port=$(docker port "$name" 5432/tcp);port=${port##*:}
cd backend
ENV=test DATABASE_URL="postgresql://postgres:synthetic-postgres-184@127.0.0.1:$port/audit_test" USE_POSTGRES=true AI_TEST_POSTGRES=1 \
  uv run --frozen python -m pytest tests/test_ai_postgres.py tests/test_release_postgres.py -q
