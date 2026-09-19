import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Account from "./Account";
import { getToken, removeToken, setToken } from "../contexts/authStorage";

vi.mock("../components/AccountSubscription", () => ({ default: () => <section>Gói sử dụng & credit</section> }));
const notify = vi.fn();
vi.mock("../contexts/useToast", () => ({ useToast: () => ({ notify }) }));

const {
  authChangePasswordMock,
  authUpdateProfileMock,
  getMySchoolMock,
  refreshUserMock,
  state,
} = vi.hoisted(() => ({
  authChangePasswordMock: vi.fn(),
  authUpdateProfileMock: vi.fn(),
  getMySchoolMock: vi.fn(),
  refreshUserMock: vi.fn(),
  state: {
    user: {
      id: 7,
      email: "teacher@example.test",
      name: "Nguyễn Văn A",
      role: "teacher",
      is_active: true,
      school_id: 3 as number | null,
      avatar_url: null,
      created_at: "2026-08-01T08:00:00+00:00",
      can_change_password: true,
      must_change_password: false,
    },
  },
}));

vi.mock("../contexts/useAuth", () => ({
  useAuth: () => ({ user: state.user, refreshUser: refreshUserMock }),
}));

vi.mock("../services/api", () => ({
  authChangePassword: authChangePasswordMock,
  authUpdateProfile: authUpdateProfileMock,
  getMySchool: getMySchoolMock,
}));

describe("Account self-service", () => {
  beforeEach(() => {
    setToken("account-token", false);
    authChangePasswordMock.mockReset();
    notify.mockReset();
    authUpdateProfileMock.mockReset();
    getMySchoolMock.mockReset();
    refreshUserMock.mockReset();
    authUpdateProfileMock.mockResolvedValue({});
    authChangePasswordMock.mockResolvedValue({
      message: "Đổi mật khẩu thành công",
      access_token: "rotated-token",
      token_type: "bearer",
    });
    refreshUserMock.mockResolvedValue(undefined);
    getMySchoolMock.mockResolvedValue({
      id: 3,
      name: "THPT Nguyễn Du",
      address: "12 Nguyễn Du, Hà Nội",
      phone: "024-1234-5678",
      created_at: null,
    });
    state.user = { ...state.user, can_change_password: true, school_id: 3, must_change_password: false };
  });

  afterEach(() => removeToken());

  it.each(["logout", "new login"])("ignores a password rotation response after %s", async (action) => {
    let finish!: (response: { access_token: string }) => void;
    authChangePasswordMock.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const view = render(<Account />);
    await screen.findAllByText("THPT Nguyễn Du");
    fireEvent.click(screen.getByText("Bảo mật tài khoản"));
    fireEvent.change(screen.getByLabelText("Mật khẩu hiện tại"), { target: { value: "old-password" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu mới"), { target: { value: "new-password" } });
    fireEvent.change(screen.getByLabelText("Xác nhận mật khẩu mới"), { target: { value: "new-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));
    view.unmount();
    if (action === "logout") removeToken();
    else setToken("other-account-token", true);
    await act(async () => { finish({ access_token: "rotated-old-account-token" }); });
    expect(getToken()).toBe(action === "logout" ? null : "other-account-token");
    expect(refreshUserMock).not.toHaveBeenCalled();
  });

  it("renders school details and saves profile and password changes", async () => {
    render(<Account />);

    expect(await screen.findByText("THPT Nguyễn Du")).toBeInTheDocument();
    expect(screen.getByText("12 Nguyễn Du, Hà Nội")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Họ và tên"), { target: { value: "Nguyễn Văn B" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu thông tin" }));
    await waitFor(() => expect(authUpdateProfileMock).toHaveBeenCalledWith("Nguyễn Văn B"));
    expect(refreshUserMock).toHaveBeenCalled();
    await waitFor(() => expect(notify).toHaveBeenCalledWith("Đã cập nhật thông tin cá nhân", "success"));

    fireEvent.click(screen.getByText("Bảo mật tài khoản"));
    fireEvent.change(screen.getByLabelText("Mật khẩu hiện tại"), { target: { value: "old-password" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu mới"), { target: { value: "new-password" } });
    fireEvent.change(screen.getByLabelText("Xác nhận mật khẩu mới"), { target: { value: "new-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));

    await waitFor(() => expect(authChangePasswordMock).toHaveBeenCalledWith("old-password", "new-password"));
    expect(await screen.findByText("✓ Đổi mật khẩu thành công")).toBeInTheDocument();
  });

  it("shows provider guidance instead of a password form for OAuth-only accounts", async () => {
    state.user = { ...state.user, can_change_password: false, school_id: null };
    getMySchoolMock.mockResolvedValue(null);

    render(<Account />);

    expect(await screen.findByText("Tài khoản đăng nhập qua nhà cung cấp")).toBeInTheDocument();
    expect(screen.queryByLabelText("Mật khẩu hiện tại")).not.toBeInTheDocument();
    expect(await screen.findByText("Chưa được phân trường")).toBeInTheDocument();
  });

  it("shows a school request failure instead of the unassigned state", async () => {
    getMySchoolMock.mockRejectedValue({
      response: { data: { detail: "Không thể đọc thông tin trường" } },
    });

    render(<Account />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Không thể đọc thông tin trường",
    );
    expect(screen.queryByText("Liên hệ quản trị viên để được thêm vào đúng trường đang giảng dạy."))
      .not.toBeInTheDocument();
  });

  it("keeps the page compact and opens security for temporary-password accounts", async () => {
    state.user.must_change_password = true;
    render(<Account />);
    await screen.findByText("THPT Nguyễn Du");
    expect(screen.getByText("Bảo mật tài khoản").closest("details")).toHaveAttribute("open");
    expect(screen.getByRole("alert")).toHaveTextContent("mật khẩu tạm");
    expect(screen.queryByText("Gói sử dụng & credit")).not.toBeInTheDocument();
    expect(screen.getAllByText("teacher@example.test")).toHaveLength(1);
  });

  it("keeps security collapsed normally and prevents unchanged profile saves", async () => {
    render(<Account />);
    await screen.findByText("THPT Nguyễn Du");
    expect(screen.getByText("Bảo mật tài khoản").closest("details")).not.toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Lưu thông tin" })).toBeDisabled();
    expect(screen.queryByLabelText("Thông tin nhanh")).not.toBeInTheDocument();
  });

  it("rejects reusing the current password before calling the API", async () => {
    render(<Account />);
    await screen.findAllByText("THPT Nguyễn Du");

    fireEvent.click(screen.getByText("Bảo mật tài khoản"));
    fireEvent.change(screen.getByLabelText("Mật khẩu hiện tại"), {
      target: { value: "same-password" },
    });
    fireEvent.change(screen.getByLabelText("Mật khẩu mới"), {
      target: { value: "same-password" },
    });
    fireEvent.change(screen.getByLabelText("Xác nhận mật khẩu mới"), {
      target: { value: "same-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Mật khẩu mới phải khác mật khẩu hiện tại",
    );
    expect(authChangePasswordMock).not.toHaveBeenCalled();
  });
});


it("keeps MFA enrollment usable when a protected school request requires step-up", async () => {
  const previous = state.user.role;
  state.user.role = "super_admin";
  getMySchoolMock.mockRejectedValue({ response: { data: { detail: {
    code: "ADMIN_MFA_REQUIRED", message: "Cần xác thực MFA để tiếp tục.",
  } } } });
  try {
    render(<Account />);
    expect(await screen.findByText("Cần xác thực MFA để tiếp tục.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Xác thực MFA quản trị" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thiết lập lần đầu" })).toBeInTheDocument();
  } finally { state.user.role = previous; }
});
