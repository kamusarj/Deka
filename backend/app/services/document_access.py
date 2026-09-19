"""Document sharing access, shared by library, detail and RAG reads."""

from sqlalchemy import and_, false, or_, true, select
from app.models.document_cleanup import DocumentCleanup

from app.models.document import UploadedDocument as Document
from app.services.role_policy import KNOWN_ROLES, can_write_content


def _document_access_filter(actor):
    if actor is None:  # Internal maintenance; HTTP always supplies a user.
        return true()
    if actor.role not in KNOWN_ROLES:
        return false()
    if actor.role == "super_admin":
        return true()
    allowed = [
        Document.owner_user_id == actor.id,
        and_(Document.sharing_scope == "system", Document.sharing_status == "approved"),
    ]
    if actor.school_id is not None:
        school = Document.school_id == actor.school_id
        allowed.append(school if actor.role == "school_admin" else and_(school, Document.sharing_scope == "school"))
    return or_(*allowed)


def can_manage_document(document, actor):
    return actor is not None and can_write_content(actor.role) and (
        actor.role == "super_admin" or document.owner_user_id == actor.id
    )


def can_share_document_with_school(document, actor):
    return can_manage_document(document, actor) and document.school_id is not None and actor.school_id == document.school_id


def can_review_document(document, actor):
    return actor is not None and actor.role == "super_admin" and document.sharing_scope == "system" and document.sharing_status in {"pending", "approved"}


def document_access_filter(actor):
    return and_(_document_access_filter(actor), ~Document.id.in_(select(DocumentCleanup.document_id)))
