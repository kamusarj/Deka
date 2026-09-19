#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
authoring_test_dir="$(mktemp -d)"
trap 'rm -rf "$authoring_test_dir"' EXIT
(
  cd "$repo_root/backend"
  ENV=test USE_POSTGRES=false DATABASE_URL="sqlite:///$authoring_test_dir/tests.db" .venv/bin/python -m pytest tests -q
  .venv/bin/python -m compileall -q app
)
(
  cd "$repo_root/frontend"
  npm run lint
  npx tsc -b
  npm run test:run
  npm run build
)
