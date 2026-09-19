"""Current authorization at provider and commit checkpoints for long requests."""
from contextvars import ContextVar
from sqlalchemy import select, update
from app.models.user import User
from app.models.ai_account import AIUsage, UserSubscription
from app.models.document import UploadedDocument
from app.services.ai.errors import AIError
from app.services.ai.credits import utcnow
from app.services.document_access import document_access_filter

active_operation = ContextVar('active_operation', default=None)


def checkpoint():
    operation = active_operation.get()
    if operation is not None:
        operation.checkpoint()


def check_authority(db, operation, *, lock=False):
    # All locks are short and coordinated with writes to these same rows.
    if lock:
        db.execute(update(User).where(User.id == operation.user_id).values(token_version=User.token_version))
    actor = db.scalar(select(User).where(User.id == operation.user_id).execution_options(populate_existing=True))
    if actor is None or not actor.is_active or actor.deleted_at or not actor.email_verified:
        raise AIError('AI_AUTHORIZATION_CHANGED', 403)
    snapshot = (actor.role, actor.school_id, actor.token_version)
    if operation.actor_snapshot is not None and snapshot != operation.actor_snapshot:
        raise AIError('AI_AUTHORIZATION_CHANGED', 403)
    if lock:
        db.execute(update(UserSubscription).where(UserSubscription.user_id == actor.id)
                   .values(credit_balance=UserSubscription.credit_balance))
    subscription = db.scalar(select(UserSubscription).where(UserSubscription.user_id == actor.id)
                             .execution_options(populate_existing=True))
    if subscription is None or subscription.status != 'active':
        raise AIError('SUBSCRIPTION_INACTIVE', 403)
    for document_id in sorted(operation.document_ids):
        if lock:
            db.execute(update(UploadedDocument).where(UploadedDocument.id == document_id)
                       .values(version_id=UploadedDocument.version_id))
        document = db.scalar(select(UploadedDocument).where(UploadedDocument.id == document_id,
                              document_access_filter(actor)))
        if document is None:
            raise AIError('AI_AUTHORIZATION_CHANGED', 403)
    request = db.scalar(select(AIUsage).where(AIUsage.id == operation.request_id)
                        .execution_options(populate_existing=True))
    if request is None or request.status != 'reserved' or request.lease_owner != operation.lease_owner:
        raise AIError('AI_REQUEST_FENCED', 409)
    if request.lease_expires_at.replace(tzinfo=utcnow().tzinfo) <= utcnow():
        raise AIError('AI_REQUEST_FENCED', 409)
    return actor
