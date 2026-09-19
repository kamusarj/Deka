"""Compatibility checks for the stored hierarchical role vocabulary."""

from app.services.role_policy import (
    can_select_ai_provider,
    can_view_ai_provider_metadata,
    can_write_content,
    is_admin_role,
    is_school_admin_role,
    is_teacher_role,
    is_user_role,
    role_group,
)


def test_stored_roles_remain_compatible_and_unknown_roles_fail_closed():
    assert is_admin_role("super_admin")
    assert is_admin_role("school_admin")
    assert is_school_admin_role("school_admin")
    assert is_teacher_role("teacher")
    assert is_user_role("teacher")
    assert is_user_role("viewer")
    assert can_view_ai_provider_metadata("super_admin")
    assert not can_view_ai_provider_metadata("school_admin")
    assert not can_view_ai_provider_metadata("teacher")
    assert not can_view_ai_provider_metadata("viewer")
    assert can_write_content("super_admin")
    assert can_write_content("school_admin")
    assert can_write_content("teacher")
    assert not can_write_content("viewer")
    assert can_select_ai_provider("super_admin")
    assert not can_select_ai_provider("school_admin")
    assert not can_select_ai_provider("teacher")
    assert not can_select_ai_provider("viewer")
    assert role_group("school_admin") == "admin"
    assert role_group("viewer") == "user"
    assert role_group("unexpected") is None
    assert not can_view_ai_provider_metadata("unexpected")
    assert not can_select_ai_provider("unexpected")
