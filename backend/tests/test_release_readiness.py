"""Deployment controls use synthetic state and no provider credentials."""
import json
from io import BytesIO
from zipfile import ZipFile
from types import SimpleNamespace
import pytest
from sqlalchemy import select, create_engine, text
from app.core.config import settings
from app.models.user import User
from app.models.admin_mfa import AdminMFA
from app.models.document import UploadedDocument
from app.services.admin_mfa import cipher
from tests.test_ai_credits import accounts


def test_mfa_key_survives_jwt_rotation_and_reencryption_is_atomic(accounts, monkeypatch):
    from app.services.mfa_rotation import rotate
    from cryptography.fernet import InvalidToken
    old, new = 'synthetic-old-independent-mfa-key-184', 'synthetic-new-independent-mfa-key-184'
    monkeypatch.setattr(settings, 'MFA_ENCRYPTION_KEY', old)
    encrypted = cipher().encrypt(b'synthetic-secret').decode()
    monkeypatch.setattr(settings, 'SECRET_KEY', ''.join(['rota', 'ted-', 'synt', 'heti', 'c-si', 'gnin', 'g-ke', 'y-at', '-lea', 'st-3', '2']))
    assert cipher().decrypt(encrypted.encode()) == b'synthetic-secret'
    with accounts.sessions.begin() as db:
        db.add(User(id=9, email='operator@example.com', name='Operator', role='super_admin'))
        db.add(AdminMFA(user_id=1, encrypted_secret=encrypted, enabled=True))
    assert rotate(accounts.sessions, actor_id=9, old_key=old, new_key=new)['dry_run']
    with accounts.sessions() as db:
        assert db.get(AdminMFA, 1).encrypted_secret == encrypted
    with pytest.raises(InvalidToken):
        rotate(accounts.sessions, actor_id=9, old_key=''.join(['inco', 'rrec', 't-sy', 'nthe', 'tic-', 'key-', 'at-l', 'east', '-32']), new_key=new, apply=True)
    rotate(accounts.sessions, actor_id=9, old_key=old, new_key=new, apply=True)
    with accounts.sessions() as db:
        assert cipher(new).decrypt(db.get(AdminMFA, 1).encrypted_secret.encode()) == b'synthetic-secret'


def test_restore_authority_rejects_tampering_and_revokes_stale_grants(accounts, monkeypatch):
    from app.services.restore_authority import snapshot, reconcile
    monkeypatch.setattr(settings, 'MFA_ENCRYPTION_KEY', ''.join(['synt', 'heti', 'c-jo', 'urna', 'l-ke', 'y-at', '-lea', 'st-3', '2-ch', 'arac', 'ters']))
    with accounts.sessions.begin() as db:
        db.add(User(id=9, email='operator@example.com', name='Operator', role='super_admin'))
        user = db.get(User, 1)
        user.role, user.token_version, user.password_hash = 'viewer', 4, 'new-password-hash'
        db.add(UploadedDocument(id=4, owner_user_id=1, filename='shared.txt', stored_filename='shared.txt',
                               file_type='txt', sharing_scope='system', sharing_status='approved'))
    current = snapshot(accounts.sessions)
    assert 'new-password-hash' not in json.dumps(current)
    corrupt = json.loads(json.dumps(current))
    corrupt['data']['users'][0]['role'] = 'super_admin'
    with pytest.raises(ValueError, match='signature'):
        reconcile(accounts.sessions, corrupt, actor_id=9, apply=True)
    # Simulate restoring old authority and credentials from a valid DB backup.
    with accounts.sessions.begin() as db:
        user = db.get(User, 1)
        user.role, user.token_version, user.password_hash = 'super_admin', 0, 'old-password-hash'
    assert reconcile(accounts.sessions, current, actor_id=9)['dry_run']
    result = reconcile(accounts.sessions, current, actor_id=9, apply=True)
    assert result['password_resets'] == [1] and result['shares_revoked'] == 1
    with accounts.sessions() as db:
        user = db.get(User, 1)
        assert user.role == 'viewer' and user.token_version == 5
        assert user.password_hash is None and user.must_change_password
        assert db.get(UploadedDocument, 4).sharing_scope == 'private'


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16'])
def test_office_xml_entities_are_rejected_before_parser(encoding):
    from app.extractors.document_extractors import validate_container, InvalidDocumentError
    data = BytesIO()
    payload = '<?xml version="1.0" encoding="' + encoding + '"?><!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x>&secret;</x>'
    with ZipFile(data, 'w') as archive:
        archive.writestr('word/document.xml', payload.encode(encoding))
    with pytest.raises(InvalidDocumentError, match='DTD/entity'):
        validate_container('docx', data.getvalue())


def test_ocr_does_not_inherit_keys_or_accept_custom_models(monkeypatch):
    from app.extractors import ocr
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-provider-sentinel')
    monkeypatch.setattr(settings, 'OCR_LANGUAGES', 'vie+eng')
    monkeypatch.setattr(settings, 'ENV', 'production')
    def child(command, **kwargs):
        assert command[1:] == ['stdin', 'stdout', '-l', 'vie+eng']
        assert kwargs['env'] == {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'OMP_THREAD_LIMIT': '1',
                                 'TESSDATA_PREFIX': '/usr/share/tesseract-ocr/5/tessdata'}
        return SimpleNamespace(stdout=b'synthetic')
    monkeypatch.setattr(ocr.subprocess, 'run', child)
    assert ocr.TesseractOCRProvider().recognize(b'fixture').text == 'synthetic'
    monkeypatch.setattr(settings, 'OCR_LANGUAGES', '../../uploads/evil')
    with pytest.raises(ValueError, match='installed'):
        ocr.TesseractOCRProvider().recognize(b'fixture')


def test_schema_checks_uniqueness_not_just_revision(tmp_path):
    from app.core.migrations import upgrade_ai_schema, check_schema
    engine = create_engine(f'sqlite:///{tmp_path}/schema.sqlite')
    upgrade_ai_schema(engine)
    check_schema(engine)
    with engine.begin() as db:
        db.execute(text('DROP INDEX uq_ai_idempotency'))
    with pytest.raises(RuntimeError, match='uniqueness incompatible'):
        check_schema(engine)
    engine.dispose()


def test_orphan_inventory_never_deletes_unknown_or_symlink(accounts, tmp_path):
    from app.services.document_orphans import inventory
    tmp_path = tmp_path / 'uploads'
    tmp_path.mkdir()
    (tmp_path / 'unowned.pdf').write_bytes(b'fixture')
    (tmp_path / 'link').symlink_to(tmp_path / 'unowned.pdf')
    result = inventory(accounts.sessions, tmp_path, limit=1)
    assert result['next_after'] == 'link'
    assert result['items'][0]['status'] == 'unsafe_symlink'
    result = inventory(accounts.sessions, tmp_path, after='link')
    assert result['items'][0]['status'] == 'unowned_review_required'
    assert (tmp_path / 'unowned.pdf').exists()


def test_first_operator_bootstrap_is_one_time_and_requires_strong_password(accounts):
    from app.services.bootstrap_admin import create
    with pytest.raises(ValueError, match='12 to 72'):
        create(accounts.sessions, email='operator@example.com', password='weak123')
    assert create(accounts.sessions, email='operator@example.com', password='synthetic-strong-password')['dry_run']
    assert create(accounts.sessions, email='operator@example.com', password='synthetic-strong-password', apply=True)['created']
    with pytest.raises(ValueError, match='already exists'):
        create(accounts.sessions, email='another@example.com', password='synthetic-strong-password', apply=True)
