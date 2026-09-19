"""Canonical hierarchical capabilities for stored application roles."""

SUPER_ADMIN_ROLE = "super_admin"
SCHOOL_ADMIN_ROLE = "school_admin"
TEACHER_ROLE = "teacher"
VIEWER_ROLE = "viewer"

ADMIN_ROLES = frozenset({SUPER_ADMIN_ROLE, SCHOOL_ADMIN_ROLE})
USER_ROLES = frozenset({TEACHER_ROLE, VIEWER_ROLE})
KNOWN_ROLES = ADMIN_ROLES | USER_ROLES
AI_METADATA_VIEWER_ROLES = frozenset({SUPER_ADMIN_ROLE})
CONTENT_WRITER_ROLES = frozenset(
    {SUPER_ADMIN_ROLE, SCHOOL_ADMIN_ROLE, TEACHER_ROLE}
)


def is_admin_role(role: str | None) -> bool:
    return role in ADMIN_ROLES


def is_user_role(role: str | None) -> bool:
    return role in USER_ROLES


def is_school_admin_role(role: str | None) -> bool:
    return role == SCHOOL_ADMIN_ROLE


def is_teacher_role(role: str | None) -> bool:
    return role == TEACHER_ROLE


def can_view_ai_provider_metadata(role: str | None) -> bool:
    return role in AI_METADATA_VIEWER_ROLES


def can_select_ai_provider(role: str | None) -> bool:
    return role == SUPER_ADMIN_ROLE


def can_write_content(role: str | None) -> bool:
    return role in CONTENT_WRITER_ROLES


def role_group(role: str | None) -> str | None:
    if is_admin_role(role):
        return "admin"
    if is_user_role(role):
        return "user"
    return None
