#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} != --apply ]]; then
  echo 'Dry run: create synthetic SQL/SMTP/HTTPS services on loopback 58443/58080, run browser account/MFA tests, remove test project.'
  exit 0
fi
cd "$(dirname "$0")/../.."
root=$(mktemp -d /tmp/audit-184-browser.XXXXXX)
suffix=${root##*.}; suffix=${suffix,,}
chmod 700 "$root"
cp deploy/backend.staging.env.example "$root/backend.env"
mkdir "$root/mailbox";chmod 777 "$root/mailbox"
cat > "$root/env" <<EOF
COMPOSE_PROJECT_NAME=audit-184-browser-$suffix
PUBLIC_DOMAIN=audit-184.example.com
ACME_EMAIL=operator@example.com
POSTGRES_PASSWORD=audit-only-password
SECRET_KEY=audit-only-signing-key-at-least-32-characters
MFA_ENCRYPTION_KEY=audit-only-independent-mfa-key-at-least-32-characters
BACKEND_IMAGE=${AUDIT_BACKEND_IMAGE:-smart-exam-backend:ready-184}
FRONTEND_IMAGE=${AUDIT_FRONTEND_IMAGE:-smart-exam-frontend:ready-184}
BACKEND_ENV_FILE=$root/backend.env
INTERNAL_SUBNET=172.30.187.0/24
PROXY_INTERNAL_IP=172.30.187.10
EOF
python3 - "$root" <<'PY'
import json, subprocess, sys
from pathlib import Path
root=Path(sys.argv[1])
config=json.loads(subprocess.check_output(['docker','compose','--env-file',str(root/'env'),'-f','docker-compose.production.yml','config','--format','json']))
for name in ['backend','migrate']:
    config['services'][name]['environment'].update(PUBLIC_REGISTRATION_ENABLED='true',SMTP_HOST='smtp-sink',SMTP_PORT='1025',SMTP_USE_TLS='false',
       SMTP_FROM_EMAIL='synthetic@example.com',TRUSTED_HOSTS='["localhost","backend"]',CORS_ORIGINS='["https://localhost:58443"]')
    config['services'][name].pop('env_file',None)
config['services']['backend']['healthcheck']={'test':['CMD','curl','-fsS','http://localhost:8000/ready'],'interval':'2s','timeout':'3s','start_period':'1s','retries':30}
config['services']['proxy']['ports']=[{'target':443,'published':'58443','host_ip':'127.0.0.1','protocol':'tcp'},
                                    {'target':80,'published':'58080','host_ip':'127.0.0.1','protocol':'tcp'}]
caddy=Path('deploy/Caddyfile').read_text().replace('email {$ACME_EMAIL}', 'auto_https disable_redirects').replace('{$PUBLIC_DOMAIN} {','https://localhost {\n    tls internal')
caddy+='\n:80 {\n redir https://localhost:58443{uri} permanent\n}\n'
(root/'Caddyfile').write_text(caddy)
for mount in config['services']['proxy']['volumes']:
    if mount.get('target')=='/etc/caddy/Caddyfile':mount['source']=str(root/'Caddyfile')
config['services']['smtp-sink']={'healthcheck': {
    'test': ['CMD', 'python', '-c', 'import smtplib; s=smtplib.SMTP("127.0.0.1", 1025, timeout=2); s.quit()'],
    'interval': '2s', 'timeout': '3s', 'retries': 30,
    }, 'image':config['services']['backend']['image'],'entrypoint':['python','-c','exec(open("/tmp/smtp.py").read())'],
    'networks':{'internal':None},'volumes':[{'type':'bind','source':str(Path('scripts/operations/smtp-fixture.py').resolve()),'target':'/tmp/smtp.py','read_only':True},
                                          {'type':'bind','source':str(root/'mailbox'),'target':'/mailbox'}]}
(root/'compose.json').write_text(json.dumps(config))
PY
compose=(docker compose -f "$root/compose.json")
mkdir -p docs/validation/production-audit
cleanup() { "${compose[@]}" logs --no-color frontend proxy > docs/validation/production-audit/browser-runtime.log 2>&1 || true; "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
"${compose[@]}" up -d --wait postgres smtp-sink
"${compose[@]}" run --rm --no-deps migrate
"${compose[@]}" run --rm --no-deps -e BOOTSTRAP_ADMIN_PASSWORD=Synthetic-audit-password-184! --entrypoint python backend -m app.services.bootstrap_admin --email operator@example.com --apply
"${compose[@]}" up -d --wait backend frontend proxy
for attempt in {1..40}; do
  if curl --silent --fail --insecure https://localhost:58443/ready >/dev/null;then break;fi
  sleep 1
done
curl --silent --fail --insecure https://localhost:58443/ready >/dev/null
redirect=$(curl --silent --output /dev/null --write-out '%{http_code}' http://localhost:58080/ready)
[[ "$redirect" == 301 ]] || { echo 'Expected HTTP to HTTPS redirect';exit 1; }
NODE_PATH=${NODE_PATH:-/tmp/audit-184-browser/node_modules} AUDIT_BROWSER_URL=https://localhost:58443 AUDIT_MAILBOX="$root/mailbox" node scripts/operations/browser-rehearsal.cjs
