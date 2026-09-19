import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./Login";

const { getOAuthConfigMock, loginMock, authState } = vi.hoisted(() => ({
  getOAuthConfigMock: vi.fn(),
  loginMock: vi.fn(),
  authState: { isAuthenticated: false, isLoading: false, sessionError: null as string | null },
}));

vi.mock("../services/api", () => ({
  getOAuthConfig: getOAuthConfigMock,
}));

vi.mock("../contexts/useAuth", () => ({
  useAuth: () => ({ login: loginMock, ...authState }),
}));

describe("Login OAuth providers", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_ENABLE_DEMO_LOGIN", "false");
    getOAuthConfigMock.mockReset();
    loginMock.mockReset();
    Object.assign(authState, { isAuthenticated: false, isLoading: false, sessionError: null });
  });

  afterEach(() => vi.unstubAllEnvs());

  it("hides demo credentials unless explicitly enabled", () => {
    getOAuthConfigMock.mockResolvedValue({ google: false, facebook: false });
    render(<MemoryRouter><Login /></MemoryRouter>);
    expect(screen.queryByRole("region", { name: "Đăng nhập nhanh để thử" })).not.toBeInTheDocument();
    expect(screen.queryByText("Demo@123456")).not.toBeInTheDocument();
  });

  it.each([
    ["Quản trị hệ thống", "superadmin@demo.smart-exam.test"],
    ["Quản trị trường", "schooladmin@demo.smart-exam.test"],
    ["Giáo viên", "teacher@demo.smart-exam.test"],
    ["Người xem", "viewer@demo.smart-exam.test"],
  ])("logs in as %s with ordinary credentials and preserves the destination", async (label, email) => {
    vi.stubEnv("VITE_ENABLE_DEMO_LOGIN", "true");
    getOAuthConfigMock.mockResolvedValue({ google: false, facebook: false });
    loginMock.mockResolvedValue(undefined);
    render(
      <MemoryRouter initialEntries={[{ pathname: "/login", state: { from: { pathname: "/community" } } }]}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/community" element={<p>cộng đồng</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(email)).toBeInTheDocument();
    expect(screen.getByText("Demo@123456")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Ghi nhớ đăng nhập" }));
    fireEvent.click(screen.getByRole("button", { name: `Đăng nhập thử: ${label}` }));
    await waitFor(() => expect(screen.getByText("cộng đồng")).toBeInTheDocument());
    expect(loginMock).toHaveBeenCalledWith(email, "Demo@123456", true);
  });

  it("prevents overlapping role logins and allows retry after an error", async () => {
    vi.stubEnv("VITE_ENABLE_DEMO_LOGIN", "true");
    getOAuthConfigMock.mockResolvedValue({ google: false, facebook: false });
    let rejectLogin!: (error: Error) => void;
    loginMock.mockImplementation(() => new Promise((_, reject) => { rejectLogin = reject; }));
    render(<MemoryRouter><Login /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập thử: Giáo viên" }));
    for (const button of screen.getAllByRole("button", { name: /^Đăng nhập thử:/ })) {
      expect(button).toBeDisabled();
    }
    expect(screen.getByRole("button", { name: "Đang đăng nhập…" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập thử: Người xem" }));
    expect(loginMock).toHaveBeenCalledTimes(1);
    rejectLogin(new Error("Không thể kết nối máy chủ"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Không thể kết nối máy chủ");
    expect(screen.getByRole("button", { name: "Đăng nhập thử: Người xem" })).toBeEnabled();
    expect(screen.getByLabelText("Email")).toHaveValue("teacher@demo.smart-exam.test");
  });

  it("returns an already authenticated visitor to the saved destination", () => {
    getOAuthConfigMock.mockResolvedValue({ google: false, facebook: false });
    authState.isAuthenticated = true;
    render(
      <MemoryRouter initialEntries={[{ pathname: "/login", state: { from: { pathname: "/exams/42" } } }]}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/exams/42" element={<p>chi tiết đề</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("chi tiết đề")).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it.each(["loading", "recovery"])("does not ask for credentials during session %s", (state) => {
    getOAuthConfigMock.mockResolvedValue({ google: false, facebook: false });
    authState.isLoading = state === "loading";
    authState.sessionError = state === "recovery" ? "Chưa thể kết nối" : null;
    render(<MemoryRouter><Login /></MemoryRouter>);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByLabelText("Mật khẩu")).not.toBeInTheDocument();
  });

  it("renders Google login when the backend enables it", async () => {
    getOAuthConfigMock.mockResolvedValue({ google: true, facebook: false });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Google" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Facebook" })).not.toBeInTheDocument();
  });

  it("returns to the protected deep link after login", async () => {
    getOAuthConfigMock.mockResolvedValue({ google: false, facebook: false });
    loginMock.mockResolvedValue(undefined);
    render(
      <MemoryRouter initialEntries={[{ pathname: "/login", state: { from: { pathname: "/exams/42", search: "?tab=matrix", hash: "" } } }]}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/exams/42" element={<p>chi tiết đề</p>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "teacher@example.test" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "password" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));

    await waitFor(() => expect(screen.getByText("chi tiết đề")).toBeInTheDocument());
    expect(loginMock).toHaveBeenCalledWith("teacher@example.test", "password", false);
  });

  it("passes the remember-login choice to authentication", async () => {
    getOAuthConfigMock.mockResolvedValue({ google: false, facebook: false });
    loginMock.mockResolvedValue(undefined);
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    const rememberLogin = screen.getByRole("checkbox", { name: "Ghi nhớ đăng nhập" });
    expect(rememberLogin).not.toBeChecked();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "teacher@example.test" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "password" } });
    fireEvent.click(rememberLogin);
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith("teacher@example.test", "password", true);
    });
  });

  it("declares browser autocomplete semantics for credentials", async () => {
    getOAuthConfigMock.mockResolvedValue({ google: false, facebook: false });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email");
    expect(screen.getByLabelText("Mật khẩu")).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
  });
});
