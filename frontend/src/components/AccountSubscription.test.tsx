import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import AccountSubscription from "./AccountSubscription";
import { setToken } from "../contexts/authStorage";

const mocks = vi.hoisted(() => ({ subscription: vi.fn(), credits: vi.fn(), usage: vi.fn() }));
vi.mock("../services/aiAccount", () => ({ getSubscription: mocks.subscription, getCredits: mocks.credits, getUsage: mocks.usage }));
const subscription = { plan: "BASIC", status: "active", credit_allowance: 500, credit_balance: 640,
  current_period_start: "2026-09-01T00:00:00Z", current_period_end: "2026-10-01T00:00:00Z" };

describe("Subscription account panel", () => {
  beforeEach(() => {
    setToken("current-user-token", false);
    vi.resetAllMocks();
    mocks.subscription.mockResolvedValue(subscription);
    mocks.credits.mockResolvedValue({ balance: 640, transactions: [
      { id: 1, type: "refund", amount: 10, created_at: "2026-09-12T09:00:00Z" },
    ] });
    mocks.usage.mockResolvedValue({ items: [
      { id: "1", operation: "exam_generation", status: "success", credits_charged: 10, reserved_credits: 0, created_at: "2026-09-12T09:00:00Z" },
      { id: "2", operation: "question_regeneration", status: "failed", credits_charged: 0, reserved_credits: 0, created_at: "2026-09-12T09:00:00Z" },
      { id: "3", operation: "exam_generation", status: "reserved", credits_charged: 0, reserved_credits: 10, created_at: "2026-09-12T09:00:00Z" },
    ] });
  });

  it("shows allowance and balance without treating carry-over as a percentage", async () => {
    render(<MemoryRouter><AccountSubscription /></MemoryRouter>);
    expect(screen.getByRole("status")).toHaveTextContent("Đang tải gói sử dụng");
    expect(await screen.findByText("BASIC")).toBeInTheDocument();
    expect(screen.getByText("640")).toBeInTheDocument();
    expect(screen.getByText("500 credit mỗi kỳ; gia hạn khi sử dụng AI, không truy lĩnh tháng bỏ lỡ.")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Xem thống kê sử dụng" })).toHaveAttribute("href", "/usage");
    expect(screen.getByText("Lịch sử credit").closest("details")).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Lịch sử credit"));
    expect(screen.getByText("Hoàn credit")).toBeInTheDocument();
    expect(screen.getByText("+10")).toBeInTheDocument();
  });

  it("retries a failure without fabricating a plan or balance", async () => {
    mocks.subscription.mockRejectedValueOnce(new Error("network"));
    render(<MemoryRouter><AccountSubscription /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Chưa tải được gói sử dụng");
    expect(screen.queryByText("BASIC")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tải lại số dư" }));
    expect(await screen.findByText("BASIC")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows zero credit and an honest empty history", async () => {
    mocks.credits.mockResolvedValue({ balance: 0, transactions: [] });
    mocks.usage.mockResolvedValue({ items: [] });
    render(<MemoryRouter><AccountSubscription /></MemoryRouter>);
    await screen.findByText("BASIC");
    expect(screen.getByRole("status")).toHaveTextContent("Bạn đã dùng hết credit");
    fireEvent.click(screen.getByText("Lịch sử credit"));
    expect(screen.getByText("Chưa có biến động credit")).toBeInTheDocument();
  });

  it("ignores old-session responses and cancels on unmount", async () => {
    let finish!: (value: typeof subscription) => void;
    mocks.subscription.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const view = render(<MemoryRouter><AccountSubscription /></MemoryRouter>);
    const signal = mocks.subscription.mock.calls[0][0] as AbortSignal;
    setToken("new-user-token", false);
    await act(async () => { finish(subscription); });
    expect(screen.queryByText("BASIC")).not.toBeInTheDocument();
    view.unmount();
    expect(signal.aborted).toBe(true);
  });

  it("refreshes the server balance", async () => {
    render(<MemoryRouter><AccountSubscription /></MemoryRouter>);
    await screen.findByText("640");
    mocks.credits.mockResolvedValue({ balance: 630, transactions: [] });
    fireEvent.click(screen.getByRole("button", { name: "Tải lại số dư" }));
    await waitFor(() => expect(screen.getByText("630")).toBeInTheDocument());
    expect(mocks.credits).toHaveBeenCalledTimes(2);
  });
});
