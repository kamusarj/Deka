from app.models.audit_log import AuditLog


def record_audit(
    db,
    *,
    actor,
    action: str,
    target_type: str,
    target_id: int | None = None,
    school_id: int | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Append a sanitized audit event to the caller's transaction."""
    event = AuditLog(
        actor_user_id=getattr(actor, "id", None),
        action=action,
        target_type=target_type,
        target_id=target_id,
        school_id=school_id if school_id is not None else getattr(actor, "school_id", None),
        details=details or {},
    )
    db.add(event)
    return event
