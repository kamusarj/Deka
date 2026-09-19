import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Home from "./Home";

const { summary, recent } = vi.hoisted(() => ({ summary: vi.fn(), recent: vi.fn() }));
vi.mock("../services/api", () => ({ getDashboardSummary: summary, searchExams: recent }));
vi.mock("../contexts/useAuth", () => ({ useAuth: () => ({ user: { id: 1, role: "teacher" } }) }));

beforeEach(() => {
  summary.mockReset().mockResolvedValue({ scope_label: "Cá nhân", exams: 7, questions: 42, bank_questions: 9, documents: 3 });
  recent.mockReset().mockResolvedValue({ items: [], total: 0 });
});

describe("dashboard request failures", () => {
  it("shows the account number while linking with the permanent ID", async () => {
    recent.mockResolvedValue({ items: [{ id: 21, exam_number: 8, school: "Đề số tám", grade: 8, subject: "KHTN", exam_type: "Giữa kỳ" }] });
    render(<MemoryRouter><Home /></MemoryRouter>);
    expect(await screen.findByText("#8")).toBeInTheDocument();
    expect(screen.queryByText("#21")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Đề số tám/ })).toHaveAttribute("href", "/exams/21");
  });

  it("keeps successful statistics and offers retry instead of a false empty exam list", async () => {
    recent.mockRejectedValueOnce(new Error("Không tải được đề gần đây"));
    render(<MemoryRouter><Home /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được đề gần đây");
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.queryByText("Chưa có đề nào trong phạm vi này")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByText("Chưa có đề nào trong phạm vi này")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps recent exams when summary fails without inventing zero counts", async () => {
    summary.mockRejectedValueOnce(new Error("Không tải được thống kê"));
    recent.mockResolvedValue({ items: [{ id: 7, school: "Đề mới nhất", grade: 8, subject: "KHTN", exam_type: "Giữa kỳ" }] });
    const view = render(<MemoryRouter><Home /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được thống kê");
    expect(screen.getByText("Đề mới nhất")).toBeInTheDocument();
    expect(screen.queryByText("#7")).not.toBeInTheDocument();
    expect([...view.container.querySelectorAll(".stat-value")].map(node => node.textContent)).toEqual(["—", "—", "—", "—"]);
    await waitFor(() => expect(screen.queryByText("Đang tải…")).not.toBeInTheDocument());
  });
});
