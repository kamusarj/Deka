"""Export current deletion evidence separately from backups; import before restore opens."""
import argparse
import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select, text, func
from app.core.database import get_session_factory
from app.models.document import UploadedDocument
from app.models.document_cleanup import DocumentCleanup
from app.models.user import User
from app.services.audit_service import record_audit


class Entry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_id: int = Field(ge=1)
    owner_user_id: int | None
    stored_filename: str = Field(min_length=1, max_length=500)


def reconcile(sessions, entries, *, actor_id, apply=False):
    entries = TypeAdapter(list[Entry]).validate_python(entries)
    for item in entries:
        if Path(item.stored_filename).name != item.stored_filename or '\\' in item.stored_filename:
            raise ValueError('Invalid journal filename')
    with sessions.begin() as db:
        actor = db.get(User, actor_id)
        if actor is None or not actor.is_active or actor.deleted_at or actor.role != 'super_admin':
            raise ValueError('Active Super Admin required')
        for item in entries:
            document = db.get(UploadedDocument, item.document_id)
            if document and (document.stored_filename != item.stored_filename or document.owner_user_id != item.owner_user_id):
                raise ValueError('Journal ownership differs from restored data; refusing automatic reconciliation')
            existing = db.scalar(select(DocumentCleanup).where(DocumentCleanup.document_id == item.document_id))
            if existing and (existing.stored_filename != item.stored_filename or existing.owner_user_id != item.owner_user_id):
                raise ValueError('Conflicting deletion evidence')
            if apply:
                if not existing:
                    db.add(DocumentCleanup(**item.model_dump()))
                if document:
                    db.delete(document)
        if apply and db.get_bind().dialect.name == 'postgresql':
            db.flush()
            next_id = max(db.scalar(select(func.max(UploadedDocument.id))) or 0,
                          db.scalar(select(func.max(DocumentCleanup.document_id))) or 0) + 1
            db.execute(text("SELECT setval(pg_get_serial_sequence('uploaded_documents', 'id'), :next_id, false)"), {'next_id': next_id})
        if apply:
            record_audit(db, actor=actor, action='documents.restore_reconciled', target_type='document_cleanup',
                         details={'count': len(entries)})
    return {'dry_run': not apply, 'count': len(entries)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['export', 'reconcile'])
    parser.add_argument('--journal')
    parser.add_argument('--actor-id', type=int)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    sessions = get_session_factory()
    if args.command == 'export':
        with sessions() as db:
            result = [dict(row) for row in db.execute(select(DocumentCleanup.document_id,
                DocumentCleanup.owner_user_id, DocumentCleanup.stored_filename)).mappings()]
    else:
        if not args.journal or not args.actor_id:
            parser.error('reconcile requires --journal and --actor-id')
        result = reconcile(sessions, json.loads(Path(args.journal).read_text()), actor_id=args.actor_id, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
