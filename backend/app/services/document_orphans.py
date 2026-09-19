"""Bounded read-only orphan inventory. Unknown ownership is never grounds for deletion."""
import argparse
import json
from pathlib import Path
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_session_factory
from app.models.document import UploadedDocument
from app.models.document_cleanup import DocumentCleanup


def inventory(sessions, root, *, after='', limit=100):
    if not 1 <= limit <= 1000:
        raise ValueError('Limit must be between 1 and 1000')
    # Directory listing is read-only; results and database queries are bounded.
    import heapq
    paths = heapq.nsmallest(limit + 1, (p for p in Path(root).iterdir() if p.name > after), key=lambda p:p.name)
    batch = paths[:limit]
    names = [p.name for p in batch]
    with sessions() as db:
        live = set(db.scalars(select(UploadedDocument.stored_filename).where(UploadedDocument.stored_filename.in_(names))))
        jobs = set(db.scalars(select(DocumentCleanup.stored_filename).where(DocumentCleanup.stored_filename.in_(names))))
    return {'dry_run': True, 'items': [{'filename': p.name, 'status': 'unsafe_symlink' if p.is_symlink() else
                'referenced' if p.name in live else 'cleanup_recorded' if p.name in jobs else 'unowned_review_required'} for p in batch],
            'next_after': batch[-1].name if len(paths) > limit else None}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after', default='')
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(inventory(get_session_factory(), settings.UPLOAD_DIR, after=args.after, limit=args.limit)))
