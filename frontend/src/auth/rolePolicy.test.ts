import { describe, expect, it } from "vitest";

import {
  canManagePlatform,
  canManageSchoolTeachers,
  canSelectAiProvider,
  canUseAuthenticatedWorkspace,
  canViewAiProviderMetadata,
  getStoredRoleLabel,
  hasRoleCapability,
} from "./rolePolicy";

describe("hierarchical rolePolicy", () => {
  it("shows authenticated workspace navigation to every recognized role", () => {
    expect(canUseAuthenticatedWorkspace("super_admin")).toBe(true);
    expect(canUseAuthenticatedWorkspace("school_admin")).toBe(true);
    expect(canUseAuthenticatedWorkspace("teacher")).toBe(true);
    expect(canUseAuthenticatedWorkspace("viewer")).toBe(true);
    expect(canUseAuthenticatedWorkspace("owner")).toBe(false);
    expect(canUseAuthenticatedWorkspace("")).toBe(false);
    expect(canUseAuthenticatedWorkspace(null)).toBe(false);
    expect(canUseAuthenticatedWorkspace(undefined)).toBe(false);
  });

  it("grants platform management only to super admins", () => {
    expect(canManagePlatform("super_admin")).toBe(true);
    expect(canManagePlatform("school_admin")).toBe(false);
    expect(canManagePlatform("teacher")).toBe(false);
  });

  it("grants school teacher management to both admin tiers", () => {
    expect(canManageSchoolTeachers("super_admin")).toBe(true);
    expect(canManageSchoolTeachers("school_admin")).toBe(true);
    expect(canManageSchoolTeachers("teacher")).toBe(false);
  });

  it("reserves global AI-provider mutation for super admins", () => {
    expect(canSelectAiProvider("super_admin")).toBe(true);
    expect(canSelectAiProvider("school_admin")).toBe(false);
    expect(canSelectAiProvider("teacher")).toBe(false);
    expect(canSelectAiProvider("viewer")).toBe(false);
  });

  it("reserves AI-provider metadata for super admins", () => {
    expect(canViewAiProviderMetadata("super_admin")).toBe(true);
    expect(canViewAiProviderMetadata("school_admin")).toBe(false);
    expect(canViewAiProviderMetadata("teacher")).toBe(false);
    expect(canViewAiProviderMetadata("viewer")).toBe(false);
  });

  it("fails closed for unknown roles and displays exact tier labels", () => {
    expect(hasRoleCapability("owner", "platform_admin")).toBe(false);
    expect(hasRoleCapability("owner", "school_teacher_admin")).toBe(false);
    expect(hasRoleCapability("owner", "ai_provider_metadata")).toBe(false);
    expect(hasRoleCapability("owner", "ai_provider_mutation")).toBe(false);
    expect(getStoredRoleLabel("super_admin")).toBe("Super Admin");
    expect(getStoredRoleLabel("school_admin")).toBe("School Admin");
    expect(getStoredRoleLabel("teacher")).toBe("Teacher");
  });
});
