import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import QuestionBank from "./QuestionBank";

const { listBankQuestionsMock, deleteBankQuestionMock } = vi.hoisted(() => ({
  listBankQuestionsMock: vi.fn(),
  deleteBankQuestionMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  listBankQuestions: listBankQuestionsMock,
  deleteBankQuestion: deleteBankQuestionMock,
}));

describe("QuestionBank search", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    listBankQuestionsMock.mockReset().mockResolvedValue([]);
    deleteBankQuestionMock.mockReset();
  });

  afterEach(() => vi.useRealTimers());

  it("debounces typing and aborts the superseded request", async () => {
    render(<QuestionBank />);
    await act(() => vi.advanceTimersByTimeAsync(300));
    expect(listBankQuestionsMock).toHaveBeenCalledTimes(1);
    const initialSignal = listBankQuestionsMock.mock.calls[0][1] as AbortSignal;

    fireEvent.change(screen.getByPlaceholderText("Tìm theo nội dung..."), {
      target: { value: "phản" },
    });
    fireEvent.change(screen.getByPlaceholderText("Tìm theo nội dung..."), {
      target: { value: "phản ứng" },
    });

    expect(initialSignal.aborted).toBe(true);
    await act(() => vi.advanceTimersByTimeAsync(299));
    expect(listBankQuestionsMock).toHaveBeenCalledTimes(1);
    await act(() => vi.advanceTimersByTimeAsync(1));
    expect(listBankQuestionsMock).toHaveBeenCalledTimes(2);
    expect(listBankQuestionsMock.mock.calls[1][0].search).toBe("phản ứng");
  });

  it("shows the complete saved question and its direct answer", async () => {
    listBankQuestionsMock.mockResolvedValueOnce([
      {
        id: 21,
        content: "Tim người có bao nhiêu ngăn?",
        type: "multiple_choice",
        difficulty: "nhan_biet",
        subject: "Khoa học tự nhiên",
        tags: [],
        options: { A: "2", B: "3", C: "4", D: "5" },
        answer: { correct_answer: "C" },
        usage_count: 0,
      },
      {
        id: 23,
        content: "Nêu tên cơ quan bơm máu.",
        type: "short_answer",
        difficulty: "nhan_biet",
        subject: "Khoa học tự nhiên",
        tags: [],
        answer: { correct_answer: "Tim" },
        usage_count: 0,
      },
      {
        id: 24,
        content: "Trình bày vai trò của tim.",
        type: "essay",
        difficulty: "van_dung",
        subject: "Khoa học tự nhiên",
        tags: [],
        sub_questions: [{ id: "q24a", content: "Nêu chức năng chính.", score: 1 }],
        answer: { model_answer: "Tim co bóp để đưa máu đi khắp cơ thể." },
        usage_count: 0,
      },
    ]);

    render(<QuestionBank />);
    await act(() => vi.advanceTimersByTimeAsync(300));

    expect(screen.getByText("Tim người có bao nhiêu ngăn?")).toBeInTheDocument();
    expect(screen.getByText("4", { selector: ".option-item" })).toBeInTheDocument();
    expect(screen.getByText("C. 4")).toBeInTheDocument();
    expect(screen.getByText("Tim", { selector: ".bank-answer span" })).toBeInTheDocument();
    expect(screen.getByText("a) Nêu chức năng chính.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Tim co bóp để đưa máu đi khắp cơ thể.")).toBeInTheDocument();
  });

  it("keeps legacy nested answers readable", async () => {
    listBankQuestionsMock.mockResolvedValueOnce([
      {
        id: 22,
        content: "Xác định đúng hoặc sai.",
        type: "true_false",
        difficulty: "thong_hieu",
        subject: "Khoa học tự nhiên",
        tags: [],
        statements: [
          { id: "s1", content: "Nước sôi ở 100°C." },
          { id: "s2", content: "Nước là kim loại." },
        ],
        answer: {
          answer: {
            answers: [
              { statement_id: "s1", is_true: true },
              { statement_id: "s2", is_true: false },
            ],
          },
          rubric: null,
        },
        usage_count: 0,
      },
    ]);

    render(<QuestionBank />);
    await act(() => vi.advanceTimersByTimeAsync(300));

    expect(screen.getByText("a) Nước sôi ở 100°C.")).toBeInTheDocument();
    expect(screen.getByText("a) Đúng; b) Sai")).toBeInTheDocument();
  });
});
