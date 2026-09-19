export const ROLE_TIERS = ["super_admin", "school_admin", "teacher", "viewer"] as const;

export type RoleCapability =
  | "workspace_read"
  | "platform_admin"
  | "school_teacher_admin"
  | "content_write"
  | "ai_provider_metadata"
  | "ai_provider_mutation";

export function isSuperAdminRole(role: string | null | undefined): boolean {
  return role === "super_admin";
}

export function isSchoolAdminRole(role: string | null | undefined): boolean {
  return role === "school_admin";
}

export function isTeacherRole(role: string | null | undefined): boolean {
  return role === "teacher";
}

export function isViewerRole(role: string | null | undefined): boolean {
  return role === "viewer";
}

export function isAdminRole(role: string | null | undefined): boolean {
  return isSuperAdminRole(role) || isSchoolAdminRole(role);
}

export function isUserRole(role: string | null | undefined): boolean {
  return isTeacherRole(role) || isViewerRole(role);
}

export function canUseAuthenticatedWorkspace(role: string | null | undefined): boolean {
  return role != null && (ROLE_TIERS as readonly string[]).includes(role);
}

export function canManagePlatform(role: string | null | undefined): boolean {
  return isSuperAdminRole(role);
}

export function canManageSchoolTeachers(role: string | null | undefined): boolean {
  return isSuperAdminRole(role) || isSchoolAdminRole(role);
}

export function canViewAiProviderMetadata(role: string | null | undefined): boolean {
  return isSuperAdminRole(role);
}

export function canSelectAiProvider(role: string | null | undefined): boolean {
  return canManagePlatform(role);
}

export function canWriteContent(role: string | null | undefined): boolean {
  return !isViewerRole(role) && (
    isSuperAdminRole(role) || isSchoolAdminRole(role) || isTeacherRole(role)
  );
}

export function hasRoleCapability(
  role: string | null | undefined,
  capability: RoleCapability,
): boolean {
  if (capability === "workspace_read") return canUseAuthenticatedWorkspace(role);
  if (capability === "platform_admin") return canManagePlatform(role);
  if (capability === "school_teacher_admin") return canManageSchoolTeachers(role);
  if (capability === "ai_provider_metadata") return canViewAiProviderMetadata(role);
  if (capability === "content_write") return canWriteContent(role);
  return canSelectAiProvider(role);
}

export function getStoredRoleLabel(role: string | null | undefined): string {
  const labels: Record<string, string> = {
    super_admin: "Super Admin",
    school_admin: "School Admin",
    teacher: "Teacher",
    viewer: "Viewer",
  };
  return role ? labels[role] ?? "Vai trò không xác định" : "Chưa xác định";
}

export function getRoleBadgeClass(role: string | null | undefined): string {
  if (isSuperAdminRole(role)) return "is-super-admin";
  if (isSchoolAdminRole(role)) return "is-school-admin";
  if (isTeacherRole(role)) return "is-teacher";
  return "is-viewer";
}
