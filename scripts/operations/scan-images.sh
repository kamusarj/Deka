#!/usr/bin/env bash
set -euo pipefail
# Read-only scans of supplied images, without provider credentials.
cd "$(dirname "$0")/../.."
backend=${1:?backend image}
frontend=${2:?frontend image}
output=${3:?evidence directory}
mkdir -p "$output"
output=$(realpath "$output")
cache=${AUDIT_TRIVY_CACHE:-/tmp/audit-184-trivy-cache}
mkdir -p "$cache"
for name in backend frontend proxy postgres; do
  case $name in
    backend) candidate=$backend;;
    frontend) candidate=$frontend;;
    proxy) candidate=${PROXY_IMAGE:-deka-proxy:ready-184};;
    postgres) candidate=${POSTGRES_IMAGE:-deka-postgres:ready-184};;
  esac
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock:ro -v "$cache:/root/.cache" \
    aquasec/trivy:0.65.0 image --scanners vuln --severity HIGH,CRITICAL --format json "$candidate" > "$output/$name-vulnerabilities.json"
  image_id=$(docker image inspect --format '{{.Id}}' "$candidate")
  if [[ $name == backend ]]; then
    docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
      --tmpfs /tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777 -e ENV=test -e PYTHONPATH=/app -e DATABASE_URL=sqlite:////tmp/facts.sqlite \
      -v "$PWD/scripts/operations/image-security-facts.py:/tmp/facts.py:ro" "$candidate" python /tmp/facts.py > "$output/$name-profile.json"
  else
    printf '{"facts":{}}\n' > "$output/$name-profile.json"
  fi
  python3 - "$output/$name-profile.json" "$image_id" <<'PY'
import json, sys
from pathlib import Path
path=Path(sys.argv[1]); data=json.loads(path.read_text()); data['image_id']=sys.argv[2]; path.write_text(json.dumps(data,indent=2)+'\n')
PY
done
status=0
for name in backend frontend proxy postgres; do
  python3 scripts/operations/security-gate.py --scan "$output/$name-vulnerabilities.json" \
    --profile "$output/$name-profile.json" > "$output/$name-gate.json" || status=1
done
exit "$status"
