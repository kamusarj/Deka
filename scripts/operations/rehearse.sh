#!/usr/bin/env bash
set -euo pipefail
# Creates and removes only randomly named synthetic Compose projects; no public ports.
if [[ ${1:-} != --apply ]]; then
  echo 'Dry run: create isolated PostgreSQL/uploads projects, seed synthetic data, backup/restore, verify and remove test volumes. Use --apply to rehearse.'
  exit 0
fi
cd "$(dirname "$0")/../.."
root=$(mktemp -d /tmp/smart-exam-audit-184.XXXXXX)
chmod 700 "$root"
suffix=${root##*.}
suffix=${suffix,,}
cp deploy/backend.staging.env.example "$root/backend.env"
for target in source restore; do
  subnet=185
  [[ "$target" == restore ]] && subnet=186
  cat > "$root/$target.env" <<EOF
COMPOSE_PROJECT_NAME=audit-184-$target-$suffix
PUBLIC_DOMAIN=audit-184.example.com
ACME_EMAIL=operator@example.com
POSTGRES_PASSWORD=audit-only-password
SECRET_KEY=audit-only-secret-at-least-32-characters-184
MFA_ENCRYPTION_KEY=audit-only-independent-mfa-secret-184-32-characters
BACKEND_IMAGE=${AUDIT_BACKEND_IMAGE:-smart-exam-backend:ready-184}
FRONTEND_IMAGE=${AUDIT_FRONTEND_IMAGE:-smart-exam-frontend:ready-184}
BACKEND_ENV_FILE=$root/backend.env
INTERNAL_SUBNET=172.30.$subnet.0/24
PROXY_INTERNAL_IP=172.30.$subnet.10
EOF
done
source_compose=(docker compose --env-file "$root/source.env" -f docker-compose.production.yml)
restore_compose=(docker compose --env-file "$root/restore.env" -f docker-compose.production.yml)
cleanup() {
  "${source_compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  "${restore_compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
"${source_compose[@]}" up -d --wait postgres
"${source_compose[@]}" run --rm --no-deps migrate
cat > "$root/seed.py" <<'PY'
from pathlib import Path
from app.core.database import get_session_factory
from app.models.user import User
from app.models.document import UploadedDocument
from app.models.exam import Exam
from app.models.admin_mfa import AdminMFA
from app.services.admin_mfa import cipher
from app.services.ai.credits import CreditService
sessions = get_session_factory()
with sessions.begin() as db:
    db.add_all([User(id=1,email='admin@example.com',name='Synthetic admin',role='super_admin'),User(id=2,email='teacher@example.com',name='Synthetic teacher',role='teacher')])
with sessions.begin() as db:
    db.add(UploadedDocument(id=1,owner_user_id=2,filename='synthetic.txt',stored_filename='synthetic.txt',file_type='txt',size=9,extracted_text='synthetic'))
with sessions.begin() as db:
    db.add(UploadedDocument(id=2,owner_user_id=2,filename='retained.txt',stored_filename='retained.txt',file_type='txt',size=8,extracted_text='retained',sharing_scope='system',sharing_status='approved'))
    db.add(Exam(id=1,owner_user_id=2,school='Synthetic',grade=8,subject='KHTN',exam_type='test',duration_minutes=45,school_year='2026',matrix=[],summary={},specification=[],questions=[],answer_key=[],rubric=[],validation={},resource_package={'document_ids':[2]}))
    db.add(AdminMFA(user_id=1,enabled=True,encrypted_secret=cipher().encrypt(b'JBSWY3DPEHPK3PXP').decode(),last_counter=10,recovery_hashes=[]))
Path('/app/app/data/uploads/synthetic.txt').write_text('synthetic')
Path('/app/app/data/uploads/retained.txt').write_text('retained')
assert CreditService().account(2)['credit_balance'] == 50
print('Seeded synthetic owner, operator, file and credit ledger')
PY
chmod 755 "$root"
chmod 644 "$root/seed.py"
"${source_compose[@]}" run --rm --no-deps -v "$root/seed.py:/tmp/seed.py:ro" --entrypoint python backend -c 'exec(open("/tmp/seed.py").read())'
scripts/operations/backup.sh "$root/source.env" "$root/backup" --apply
printf '%s\n' '[{"document_id":1,"owner_user_id":2,"stored_filename":"synthetic.txt"}]' > "$root/current.json"
chmod 644 "$root/current.json"
scripts/operations/restore.sh "$root/restore.env" "$root/backup" "$root/current.json" 1
"${source_compose[@]}" run --rm --no-deps --entrypoint python backend -c 'from app.core.database import get_session_factory; from app.models.user import User; from app.models.ai_account import UserSubscription; from sqlalchemy import select
with get_session_factory().begin() as db:
 user=db.get(User,2);user.role="viewer";user.token_version=7
 db.scalar(select(UserSubscription).where(UserSubscription.user_id==2)).status="paused"'
"${source_compose[@]}" run --rm --no-deps --entrypoint python backend -m app.services.restore_authority export > "$root/authority.json"
chmod 644 "$root/authority.json"
export CURRENT_AUTHORITY_JOURNAL="$root/authority.json"
start=$(date +%s)
scripts/operations/restore.sh "$root/restore.env" "$root/backup" "$root/current.json" 1 --apply
cat > "$root/check.py" <<'PY'
from pathlib import Path
from sqlalchemy import select, func
from app.core.database import get_session_factory
from app.models.document import UploadedDocument
from app.models.document_cleanup import DocumentCleanup
from app.models.ai_account import CreditTransaction
from app.services.ai.credits import CreditService
with get_session_factory()() as db:
    from app.models.user import User
    from app.models.exam import Exam
    from app.models.ai_account import UserSubscription
    assert db.get(User,2).role == 'viewer' and db.get(User,2).token_version == 8
    assert db.scalar(select(UserSubscription).where(UserSubscription.user_id==2)).status == 'paused'
    assert db.get(UploadedDocument,2).sharing_scope == 'private'
    assert db.get(Exam,1).owner_user_id == 2 and db.get(Exam,1).resource_package['document_ids'] == [2]
    assert Path('/app/app/data/uploads/retained.txt').read_text() == 'retained'
    assert db.get(UploadedDocument,1) is None
    assert db.scalar(select(DocumentCleanup).where(DocumentCleanup.document_id==1)).status == 'complete'
    assert db.scalar(select(func.sum(CreditTransaction.amount))) == 50
assert CreditService().read_account(2)['credit_balance'] == 50
assert not Path('/app/app/data/uploads/synthetic.txt').exists()
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    assert client.get('/ready',headers={'host':'localhost'}).status_code == 200
print('PASS: restored ledger=50; deleted file denied; retained file/exam/source link preserved; current role/token/subscription applied; sharing revoked; readiness succeeds')
PY
chmod 644 "$root/check.py"
"${restore_compose[@]}" run --rm --no-deps -v "$root/check.py:/tmp/check.py:ro" --entrypoint python backend -c 'exec(open("/tmp/check.py").read())'
printf 'Synthetic restore validation elapsed_seconds=%s\n' "$(( $(date +%s) - start ))"
printf 'Synthetic artifacts retained at %s\n' "$root"

if [[ -n ${AUDIT_ROLLBACK_IMAGE:-} ]]; then
  # Compatibility includes the old image's MFA contract: reverse key conversion first.
  "${restore_compose[@]}" run --rm --no-deps --entrypoint python backend -c 'from app.core.database import get_session_factory; from app.core.config import settings; from app.services.mfa_rotation import rotate; print(rotate(get_session_factory(),actor_id=1,old_key=settings.MFA_ENCRYPTION_KEY,new_key=settings.SECRET_KEY,apply=True))'
  BACKEND_IMAGE="$AUDIT_ROLLBACK_IMAGE" "${restore_compose[@]}" run --rm --no-deps --entrypoint python backend -c 'from app.core.database import get_session_factory; from app.models.admin_mfa import AdminMFA; from app.services.admin_mfa import cipher; from fastapi.testclient import TestClient; from app.main import app
with get_session_factory()() as db:
 assert cipher().decrypt(db.get(AdminMFA,1).encrypted_secret.encode()) == b"JBSWY3DPEHPK3PXP"
with TestClient(app) as client:
 assert client.get("/ready",headers={"host":"localhost"}).status_code == 200
print("PASS: prior image readiness and MFA decryption after explicit reverse key conversion")'
fi
