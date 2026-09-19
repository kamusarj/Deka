import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import ProtectedRoute from "./ProtectedRoute";
import type { RoleCapability } from "../auth/rolePolicy";
import { AuthContext } from "../contexts/authContextValue";
import type { AuthContextType, AuthUser } from "../contexts/authContextValue";

const teacher: AuthUser = {
  id: 1,
  email: "co.lan@example.com",
  name: "Cô Lan",
  role: "teacher",
  is_active: true,
  school_id: null,
  created_at: null,
  can_change_password: true,
};

function renderGuard(
  auth: Partial<AuthContextType>,
  roles?: readonly string[],
  requiredCapability?: RoleCapability,
) {
  const value: AuthContextType = {
    user: null,
    isLoading: false,
    sessionError: null,
    isAuthenticated: false,
    login: async () => {},
    register: async () => {},
    logout: async () => {},
    refreshUser: async () => {},
    ...auth,
  };

  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={["/private"]}>
        <Routes>
          <Route
            path="/private"
            element={
              <ProtectedRoute roles={roles} requiredCapability={requiredCapability}>
                <p>nội dung riêng tư</p>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<p>trang đăng nhập</p>} />
          <Route path="/dashboard" element={<p>trang tổng quan</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("ProtectedRoute", () => {
  it("shows the loading state while auth resolves", () => {
    renderGuard({ isLoading: true });
    expect(screen.getByText("Đang tải…")).toBeInTheDocument();
  });

  it("redirects anonymous visitors to /login", () => {
    renderGuard({ isAuthenticated: false });
    expect(screen.getByText("trang đăng nhập")).toBeInTheDocument();
    expect(screen.queryByText("nội dung riêng tư")).not.toBeInTheDocument();
  });

  it("renders the page for an authenticated user", () => {
    renderGuard({ isAuthenticated: true, user: teacher });
    expect(screen.getByText("nội dung riêng tư")).toBeInTheDocument();
  });

  it("sends a user without the required role back to the dashboard", () => {
    renderGuard({ isAuthenticated: true, user: teacher }, ["school_admin"]);
    expect(screen.getByText("trang tổng quan")).toBeInTheDocument();
    expect(screen.queryByText("nội dung riêng tư")).not.toBeInTheDocument();
  });

  it("allows a user whose role is listed", () => {
    renderGuard(
      { isAuthenticated: true, user: { ...teacher, role: "school_admin" } },
      ["school_admin"],
    );
    expect(screen.getByText("nội dung riêng tư")).toBeInTheDocument();
  });

  it("denies platform administration to a teacher", () => {
    renderGuard({ isAuthenticated: true, user: teacher }, undefined, "platform_admin");
    expect(screen.getByText("trang tổng quan")).toBeInTheDocument();
  });

  it("allows only super admin into platform administration", () => {
    renderGuard(
      { isAuthenticated: true, user: { ...teacher, role: "super_admin" } },
      undefined,
      "platform_admin",
    );
    expect(screen.getByText("nội dung riêng tư")).toBeInTheDocument();
  });

  it.each(["super_admin", "school_admin"])("allows %s to manage school teachers", (role) => {
    renderGuard({ isAuthenticated: true, user: { ...teacher, role } }, undefined, "school_teacher_admin");
    expect(screen.getByText("nội dung riêng tư")).toBeInTheDocument();
  });

  it("allows super_admin to select an AI provider", () => {
    const role = "super_admin";
    renderGuard(
      { isAuthenticated: true, user: { ...teacher, role } },
      undefined,
      "ai_provider_mutation",
    );
    expect(screen.getByText("nội dung riêng tư")).toBeInTheDocument();
  });

  it.each(["school_admin", "teacher", "viewer"])("denies AI provider selection to %s", (role) => {
    renderGuard(
      { isAuthenticated: true, user: { ...teacher, role } },
      undefined,
      "ai_provider_mutation",
    );
    expect(screen.getByText("trang tổng quan")).toBeInTheDocument();
  });
});
