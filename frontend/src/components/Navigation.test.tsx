import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HashRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AppFooter from "./AppFooter";
import Layout from "./Layout";
import Landing from "../pages/Landing";
import RouteScroll from "./RouteScroll";

vi.mock("../contexts/useAuth", () => ({ useAuth: () => ({ user: { role: "teacher" }, isAuthenticated: true, logout: vi.fn() }) }));
vi.mock("./SubscriptionPlans", () => ({ default: () => null }));
vi.mock("./ThemeToggle", () => ({ default: () => null }));

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="route">{location.pathname}{location.hash}</output>;
}
function renderNavigation() {
  return render(<HashRouter><RouteScroll /><LocationProbe /><Routes>
    <Route path="/dashboard" element={<Layout><h1>Dashboard content</h1></Layout>} />
    <Route path="/" element={<><Landing /><AppFooter /></>} />
    <Route path="*" element={<p>Unknown route</p>} />
  </Routes></HashRouter>);
}

beforeEach(() => {
  window.history.replaceState(null, "", "/#/dashboard");
  vi.stubGlobal("IntersectionObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); window.history.replaceState(null, "", "/"); });

describe("HashRouter section links", () => {
  it.each([["true", "/login"], ["false", "/"]])("returns logout to %s demo-mode destination", async (enabled, destination) => {
    vi.stubEnv("VITE_ENABLE_DEMO_LOGIN", enabled);
    renderNavigation();
    fireEvent.click(screen.getByRole("button", { name: "Tài khoản" }));
    fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));
    await waitFor(() => expect(screen.getByLabelText("route").textContent).toBe(destination));
  });

  it("keeps the dashboard route when skipping navigation and focuses main content", async () => {
    renderNavigation();
    fireEvent.click(screen.getByText("Bỏ qua điều hướng"));
    await waitFor(() => expect(screen.getByLabelText("route").textContent).toMatch(/^\/dashboard/));
    expect(screen.getByRole("heading", { name: "Dashboard content" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveFocus();
  });

  it("shows only the compact copyright footer in the workspace", () => {
    renderNavigation();
    const footer = screen.getByRole("contentinfo");
    expect(footer).toHaveTextContent("© 2026 Deka.");
    expect(within(footer).queryByRole("link")).not.toBeInTheDocument();
  });

  it.each([['Tính năng', 'tinh-nang'], ['Quy trình', 'quy-trinh']])("opens the landing %s section from the public footer", async (label, id) => {
    window.history.replaceState(null, "", "/#/");
    renderNavigation();
    fireEvent.click(within(screen.getByRole("contentinfo")).getByRole("link", { name: label }));
    await waitFor(() => expect(screen.getByLabelText("route")).toHaveTextContent(`/#${id}`));
    expect(document.getElementById(id)).toBeInTheDocument();
  });
});
