"""Repeatable targeted cleanup; errors leave durable work pending."""
import argparse
import json
from pathlib import Path
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_session_factory
from app.models.document_cleanup import DocumentCleanup
from app.rag.vector_store import delete_document_vectors


def cleanup_one(sessions, cleanup_id, *, upload_dir=None):
    root = Path(upload_dir or settings.UPLOAD_DIR)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    with sessions() as db:
        job = db.get(DocumentCleanup, cleanup_id)
        if job is None:
            return False
        filename, document_id, owner_id = job.stored_filename, job.document_id, job.owner_user_id
    error_type = None
    try:
        target = (root / filename).resolve()
        if Path(filename).name != filename or target.parent != root.resolve():
            raise ValueError('Unsafe stored path')
        target.unlink(missing_ok=True)
        delete_document_vectors(document_id, owner_id)
    except Exception as error:
        error_type = type(error).__name__
    with sessions.begin() as db:
        job = db.get(DocumentCleanup, cleanup_id)
        job.attempts += 1
        job.status = 'pending' if error_type else 'complete'
        job.error_type = error_type
    return error_type is None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--after-id', type=int, default=0)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error('limit must be between 1 and 1000')
    sessions = get_session_factory()
    with sessions() as db:
        jobs = db.scalars(select(DocumentCleanup.id).where(DocumentCleanup.id > args.after_id)
                          .order_by(DocumentCleanup.id).limit(args.limit)).all()
    # Recheck completed jobs as well: late cache writes and restored cache copies
    # must not invalidate deletion evidence. Cursor makes batches bounded.
    result = {str(job): cleanup_one(sessions, job) if args.apply else 'dry_run' for job in jobs}
    print(json.dumps({'results': result, 'next_after_id': jobs[-1] if jobs else None}))


if __name__ == '__main__':
    main()
