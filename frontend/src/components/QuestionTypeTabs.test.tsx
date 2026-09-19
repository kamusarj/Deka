import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import QuestionTypeTabs from "./QuestionTypeTabs";
import type { Question } from "../types";

const metadata = {
  topic: "Hàm số",
  lesson: "Khảo sát hàm số",
  knowledge_unit: "Đạo hàm",
  achievement: "Vận dụng đạo hàm",
  bloom_level: "apply",
};

const questions: Question[] = [
  {
    id: "q_1",
    number: 1,
    type: "multiple_choice",
    difficulty: "nhan_biet",
    score: 0.25,
    content: "Câu trắc nghiệm",
    options: { A: "A", B: "B" },
    metadata,
  },
  {
    id: "q_2",
    number: 2,
    type: "essay",
    difficulty: "van_dung",
    score: 2,
    content: "Câu tự luận",
    metadata,
  },
];

describe("QuestionTypeTabs", () => {
  it("shows only question types present in the exam", () => {
    render(<QuestionTypeTabs questions={questions} value="all" onChange={() => {}} />);

    expect(screen.getByRole("tab", { name: "Tất cả · 2 câu" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Phần I. Nhiều lựa chọn · 1 câu" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Tự luận · 1 câu" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Đúng\/Sai/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Trả lời ngắn/ })).not.toBeInTheDocument();
  });

  it("reports the selected data-driven filter", () => {
    const onChange = vi.fn();
    render(<QuestionTypeTabs questions={questions} value="all" onChange={onChange} />);

    fireEvent.click(screen.getByRole("tab", { name: "Tự luận · 1 câu" }));
    expect(onChange).toHaveBeenCalledWith("essay");
  });
});
