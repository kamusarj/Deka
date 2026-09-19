import { StrictMode } from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthContext";
import { getToken, removeToken, setToken } from "./authStorage";
import { useAuth } from "./useAuth";
import ProtectedRoute from "../components/ProtectedRoute";
import OAuthCallback from "../pages/OAuthCallback";
import type { AuthUser } from "./authContextValue";

const { getMe, login, logout } = vi.hoisted(() => ({
  getMe: vi.fn(), login: vi.fn(), logout: vi.fn(),
}));
vi.mock("../services/api", () => ({
  authGetMe: getMe, authLogin: login, authLogout: logout, authRegister: vi.fn(),
}));
const teacher: AuthUser = {
  id: 1, email: "teacher@example.test", name: "Teacher", role: "teacher",
  is_active: true, school_id: null, created_at: null, can_change_password: true,
};

function Controls() {
  const auth = useAuth();
  return <>
    <output>{auth.user?.name ?? "anonymous"}</output>
    <button onClick={() => void auth.logout()}>logout</button>
    <button onClick={() => void auth.login("new@example.test", "password", true).catch(() => {})}>new login</button>
  </>;
}
function renderSession(initialEntry = "/private") {
  return render(<StrictMode><AuthProvider><Controls />
    <MemoryRouter initialEntries={[initialEntry]}><Routes>
      <Route path="/private" element={<ProtectedRoute><p>private content</p></ProtectedRoute>} />
      <Route path="/auth/callback" element={<OAuthCallback />} />
      <Route path="/login" element={<><p>login form</p><Link to="/auth/callback?token=oauth-token">OAuth callback</Link></>} />
    </Routes></MemoryRouter>
  </AuthProvider></StrictMode>);
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => {
  vi.resetAllMocks();
  removeToken();
  logout.mockResolvedValue(undefined);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  removeToken();
});

describe("session restoration", () => {
  it("clears local identity while a captured remote logout is still pending", async () => {
    setToken("old-token", true);
    getMe.mockResolvedValue(teacher);
    const pending = deferred<void>();
    logout.mockReturnValue(pending.promise);
    renderSession();
    await screen.findByText("Teacher");
    fireEvent.click(screen.getByRole("button", { name: "logout" }));
    expect(getToken()).toBeNull();
    expect(screen.getByText("anonymous")).toBeInTheDocument();
    await act(async () => { pending.resolve(); });
  });

  it("does not let delayed logout clear a newer login", async () => {
    setToken("old-token", true);
    getMe.mockResolvedValue(teacher);
    const pending = deferred<void>();
    logout.mockReturnValue(pending.promise);
    login.mockResolvedValue({ access_token: "new-token", user: { ...teacher, name: "New teacher" } });
    renderSession();
    await screen.findByText("Teacher");
    fireEvent.click(screen.getByRole("button", { name: "logout" }));
    fireEvent.click(screen.getByRole("button", { name: "new login" }));
    await screen.findByText("New teacher");
    await act(async () => { pending.resolve(); });
    expect(getToken()).toBe("new-token");
    expect(screen.getByText("New teacher")).toBeInTheDocument();
  });

  it("does not resurrect a session from a login that finishes after logout", async () => {
    const pending = deferred<{ access_token: string; user: AuthUser }>();
    login.mockReturnValue(pending.promise);
    renderSession();
    fireEvent.click(screen.getByRole("button", { name: "new login" }));
    fireEvent.click(screen.getByRole("button", { name: "logout" }));
    await act(async () => {});
    await act(async () => { pending.resolve({ access_token: "late-token", user: teacher }); });
    expect(getToken()).toBeNull();
    expect(screen.getByText("anonymous")).toBeInTheDocument();
  });

  it("keeps the most recently started login when replies arrive out of order", async () => {
    const pending = deferred<{ access_token: string; user: AuthUser }>();
    login.mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce({ access_token: "new-token", user: { ...teacher, name: "New teacher" } });
    renderSession();
    fireEvent.click(screen.getByRole("button", { name: "new login" }));
    fireEvent.click(screen.getByRole("button", { name: "new login" }));
    await screen.findByText("New teacher");
    await act(async () => { pending.resolve({ access_token: "late-token", user: teacher }); });
    expect(getToken()).toBe("new-token");
    expect(screen.getByText("New teacher")).toBeInTheDocument();
  });

  it.each(["smart-exam-token", null])("clears identity when another tab removes storage (key=%s)", async (key) => {
    setToken("old-token", true);
    getMe.mockResolvedValue(teacher);
    renderSession();
    await screen.findByText("Teacher");
    localStorage.clear();
    fireEvent(window, new StorageEvent("storage", { key, storageArea: localStorage }));
    expect(await screen.findByText("login form")).toBeInTheDocument();
    expect(screen.getByText("anonymous")).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });

  it("hides the previous identity until another tab's replacement token is verified", async () => {
    setToken("old-token", true);
    getMe.mockResolvedValue(teacher);
    renderSession();
    await screen.findByText("Teacher");
    const pending = deferred<AuthUser>();
    getMe.mockReturnValue(pending.promise);
    localStorage.setItem("smart-exam-token", "new-token");
    fireEvent(window, new StorageEvent("storage", { key: "smart-exam-token", storageArea: localStorage }));
    expect(screen.queryByText("Teacher")).not.toBeInTheDocument();
    expect(screen.queryByText("private content")).not.toBeInTheDocument();
    await act(async () => { pending.resolve({ ...teacher, id: 2, name: "New teacher" }); });
    expect(await screen.findByText("New teacher")).toBeInTheDocument();
    expect(screen.getByText("private content")).toBeInTheDocument();
  });

  it("retains a session-scoped identity when another tab changes local storage", async () => {
    setToken("session-token", false);
    getMe.mockResolvedValue(teacher);
    renderSession();
    await screen.findByText("Teacher");
    getMe.mockClear();
    localStorage.setItem("smart-exam-token", "other-tab-token");
    fireEvent(window, new StorageEvent("storage", { key: "smart-exam-token", storageArea: localStorage }));
    expect(getMe).not.toHaveBeenCalled();
    expect(getToken()).toBe("session-token");
    expect(screen.getByText("Teacher")).toBeInTheDocument();
  });

  it("ignores verification of the previous token after an external account change", async () => {
    setToken("old-token", true);
    const old = deferred<AuthUser>();
    getMe.mockReturnValue(old.promise);
    renderSession();
    getMe.mockResolvedValue({ ...teacher, id: 2, name: "New teacher" });
    localStorage.setItem("smart-exam-token", "new-token");
    fireEvent(window, new StorageEvent("storage", { key: "smart-exam-token", storageArea: localStorage }));
    await screen.findByText("New teacher");
    await act(async () => { old.resolve(teacher); });
    expect(screen.getByText("New teacher")).toBeInTheDocument();
    expect(getToken()).toBe("new-token");
  });

  it("restores OAuth identity before entering its private destination", async () => {
    const pending = deferred<AuthUser>();
    getMe.mockReturnValue(pending.promise);
    sessionStorage.setItem("smart-exam-auth-return", "/private");
    renderSession("/login");
    await screen.findByText("login form");
    fireEvent.click(screen.getByRole("link", { name: "OAuth callback" }));
    expect(screen.queryByText("login form")).not.toBeInTheDocument();
    await act(async () => { pending.resolve(teacher); });
    expect(await screen.findByText("private content")).toBeInTheDocument();
    expect(screen.getByText("Teacher")).toBeInTheDocument();
    expect(getToken()).toBe("oauth-token");
  });

  it("restores a saved local token without submitting credentials", async () => {
    localStorage.setItem("smart-exam-token", "remembered-token");
    getMe.mockResolvedValue(teacher);
    renderSession();
    expect(await screen.findByText("private content")).toBeInTheDocument();
    expect(screen.getByText("Teacher")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it.each([
    new Error("network unavailable"),
    { isAxiosError: true, response: { status: 503 } },
    { isAxiosError: true, code: "ECONNABORTED" },
  ])("retains saved tokens on a temporary error and recovers by retry", async (error) => {
    setToken("remembered-token", true);
    getMe.mockRejectedValue(error);
    renderSession();
    const retry = await screen.findByRole("button", { name: "Thử lại" });
    expect(getToken()).toBe("remembered-token");
    expect(screen.queryByText("private content")).not.toBeInTheDocument();
    expect(screen.queryByText("login form")).not.toBeInTheDocument();
    getMe.mockResolvedValue(teacher);
    fireEvent.click(retry);
    expect(await screen.findByText("private content")).toBeInTheDocument();
    expect(localStorage.getItem("smart-exam-token")).toBe("remembered-token");
  });

  it("retries automatically when connectivity returns", async () => {
    setToken("remembered-token", true);
    getMe.mockRejectedValue(new Error("offline"));
    renderSession();
    await screen.findByRole("button", { name: "Thử lại" });
    getMe.mockResolvedValue(teacher);
    fireEvent(window, new Event("online"));
    expect(await screen.findByText("private content")).toBeInTheDocument();
  });

  it("retries a startup server failure automatically after five seconds", async () => {
    vi.useFakeTimers();
    setToken("remembered-token", true);
    getMe.mockRejectedValue(new Error("server starting"));
    renderSession();
    await act(async () => {});
    expect(screen.getByRole("button", { name: "Thử lại" })).toBeInTheDocument();
    getMe.mockResolvedValue(teacher);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(screen.getByText("private content")).toBeInTheDocument();
  });

  it("invalidates expired or revoked tokens on a 401", async () => {
    setToken("expired-token", true);
    getMe.mockRejectedValue({ isAxiosError: true, response: { status: 401 } });
    renderSession();
    expect(await screen.findByText("login form")).toBeInTheDocument();
    expect(getToken()).toBeNull();
    expect(localStorage.getItem("smart-exam-token")).toBeNull();
    expect(sessionStorage.getItem("smart-exam-token")).toBeNull();
  });

  it("does not resurrect a logged-out user from a delayed verification", async () => {
    setToken("remembered-token", true);
    const pending = deferred<AuthUser>();
    getMe.mockReturnValue(pending.promise);
    renderSession();
    fireEvent.click(screen.getByRole("button", { name: "logout" }));
    await screen.findByText("login form");
    await act(async () => { pending.resolve(teacher); });
    expect(screen.getByText("anonymous")).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });

  it("does not overwrite a new login with an older verification result", async () => {
    setToken("old-token", true);
    const pending = deferred<AuthUser>();
    getMe.mockReturnValue(pending.promise);
    login.mockResolvedValue({ access_token: "new-token", user: { ...teacher, name: "New teacher" } });
    renderSession();
    fireEvent.click(screen.getByRole("button", { name: "new login" }));
    await screen.findByText("New teacher");
    await act(async () => { pending.resolve(teacher); });
    expect(screen.getByText("New teacher")).toBeInTheDocument();
    expect(getToken()).toBe("new-token");
  });

  it("clears local state when remote logout fails", async () => {
    setToken("remembered-token", true);
    getMe.mockResolvedValue(teacher);
    logout.mockRejectedValue(new Error("offline"));
    renderSession();
    await screen.findByText("private content");
    fireEvent.click(screen.getByRole("button", { name: "logout" }));
    expect(await screen.findByText("login form")).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });
});
