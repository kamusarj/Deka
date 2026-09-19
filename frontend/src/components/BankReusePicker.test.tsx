import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BankReusePicker from "./BankReusePicker";
import type { Question } from "../types";
const { search, template } = vi.hoisted(() => ({ search: vi.fn(), template: vi.fn() }));
vi.mock("../services/api", () => ({ searchBankQuestions: search, bankEditTemplate: template }));
const question = { id: "q1", number: 1, type: "short_answer", difficulty: "nhan_biet", content: "Cơ quan nào quang hợp?" } as Question;

describe("bank reuse", () => {
  it("searches matching type and level then loads a versioned edit template", async () => {
    search.mockResolvedValue([{ id: 12, content: "Bộ phận nào quang hợp?", type: "short_answer", difficulty: "nhan_biet", answer: { correct_answer: "Lá" }, tags: [] }]);
    const payload = { content: "Bộ phận nào quang hợp?", correct_answer: "Lá", version_id: 4, bank_question_id: 12 };
    template.mockResolvedValue(payload);
    const choose = vi.fn();
    render(<BankReusePicker examId={2} question={question} version={4} onChoose={choose} />);
    fireEvent.click(screen.getByText("Lấy nội dung từ ngân hàng"));
    fireEvent.click(screen.getByRole("button", { name: "Tìm câu tương tự" }));
    fireEvent.click(await screen.findByRole("button", { name: "Thay nội dung bằng câu này" }));
    await waitFor(() => expect(choose).toHaveBeenCalledWith(payload));
    expect(search).toHaveBeenCalledWith(question.content, { type: "short_answer", difficulty: "nhan_biet" });
    expect(template).toHaveBeenCalledWith(2, "q1", 12, 4);
  });
});
