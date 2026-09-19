import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SchoolAdmin from "./SchoolAdmin";

const api = vi.hoisted(() => ({ listSchools: vi.fn(), listAdminUsers: vi.fn(), listAuditLogs: vi.fn(), updateManagedUser: vi.fn(), transferTeacher: vi.fn() }));
vi.mock("../services/api", async (original) => ({ ...await original<typeof import("../services/api")>(), ...api }));
vi.mock("../contexts/useAuth", () => ({ useAuth: () => ({ user: { id: 1, role: "super_admin" } }) }));

const teacher = { id: 2, name: "Teacher", email: "teacher@example.test", role: "teacher", school_id: null, is_active: true };
beforeEach(() => {
  vi.clearAllMocks();
  api.listSchools.mockResolvedValue([{ id: 3, name: "Trường mới", address: null, phone: null }]);
  api.listAdminUsers.mockResolvedValue([teacher]);
  api.listAuditLogs.mockResolvedValue({ items: [], total: 0 });
  api.updateManagedUser.mockImplementation(async (_id, data) => ({ ...teacher, ...data }));
  api.transferTeacher.mockResolvedValue({ ...teacher, school_id: 3 });
});

describe("account editor role and school submission", () => {
  it.each([["School Admin", "school_admin"], ["Viewer", "viewer"]])("includes the selected school when a teacher becomes %s", async (label, role) => {
    render(<SchoolAdmin />);
    const card = (await screen.findByText("teacher@example.test")).closest("article")!;
    fireEvent.click(within(card).getByRole("combobox", { name: "Quyền của teacher@example.test" }));
    fireEvent.click(screen.getByRole("option", { name: label }));
    fireEvent.click(within(card).getByRole("combobox", { name: "Trường của teacher@example.test" }));
    fireEvent.click(screen.getByRole("option", { name: "Trường mới" }));
    fireEvent.click(within(card).getByRole("button", { name: "Lưu tài khoản" }));
    await waitFor(() => expect(api.updateManagedUser).toHaveBeenCalledWith(2, expect.objectContaining({ role, school_id: 3 })));
    expect(api.transferTeacher).not.toHaveBeenCalled();
  });

  it("retains the teacher transfer endpoint when the role stays teacher", async () => {
    render(<SchoolAdmin />);
    const card = (await screen.findByText("teacher@example.test")).closest("article")!;
    fireEvent.click(within(card).getByRole("combobox", { name: "Trường của teacher@example.test" }));
    fireEvent.click(screen.getByRole("option", { name: "Trường mới" }));
    fireEvent.click(within(card).getByRole("button", { name: "Lưu tài khoản" }));
    await waitFor(() => expect(api.transferTeacher).toHaveBeenCalledWith(2, 3));
  });
});
