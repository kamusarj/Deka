"""Tenant scope helpers for persisted teacher resources."""

from fastapi import HTTPException
from sqlalchemy import false


def scope_query(query, model, actor):
    """Restrict a SQLAlchemy query to the actor's permitted tenant scope.

    ``actor=None`` preserves direct service use for local maintenance and the
    pre-auth unit tests. HTTP routes always supply an authenticated actor.
    """
    if actor is None or actor.role == "super_admin":
        return query
    if actor.role == "school_admin":
        if actor.school_id is None:
            return query.filter(false())
        return query.filter(model.school_id == actor.school_id)
    return query.filter(model.owner_user_id == actor.id)


def require_resource_access(resource, actor):
    """Return 404 for resources outside the actor scope, avoiding ID probing."""
    if actor is None or actor.role == "super_admin":
        return resource
    allowed = (
        actor.school_id is not None and resource.school_id == actor.school_id
        if actor.role == "school_admin"
        else resource.owner_user_id == actor.id
    )
    if not allowed:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài nguyên")
    return resource


def require_resource_mutation(resource, actor):
    """Allow global Super Admin mutation; every other actor may mutate only owned rows."""
    if actor is None or actor.role == "super_admin":
        return resource
    if resource.owner_user_id != actor.id:
        # Match read-scope behavior so callers cannot probe resource ownership.
        raise HTTPException(status_code=404, detail="Không tìm thấy tài nguyên")
    return resource


def ownership_values(actor) -> dict:
    if actor is None:
        return {}
    return {"owner_user_id": actor.id, "school_id": actor.school_id}
