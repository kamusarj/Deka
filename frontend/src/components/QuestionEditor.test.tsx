import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import QuestionCard from "./QuestionCard";
import type { Answer, Question, RichBlock, RubricItem } from "../types";

const question: Question = { id: "q1", number: 1, type: "multiple_choice", difficulty: "nhan_biet", score: 1, content: "Lá có chức năng gì?", options: { A: "Quang hợp", B: "Hút nước", C: "Vận chuyển", D: "Sinh sản" }, metadata: { topic: "Cây", lesson: "Lá", knowledge_unit: "Lá", achievement: "Nêu vai trò lá", bloom_level: "remember" } };
const answer: Answer = { question_id: "q1", question_number: 1, type: "multiple_choice", correct_answer: "A", explanation: "Lá chứa diệp lục để quang hợp.", option_explanations: { A: "Lá thực hiện quang hợp.", B: "Rễ hấp thụ nước.", C: "Thân vận chuyển.", D: "Hoa tham gia sinh sản." } };
const richBlocks: RichBlock[] = [
  { type: "latex", content: "F=ma", display: "block" },
  { type: "diagram", alt: "Hình thí nghiệm", spec: { type: "drawing", width: 640, height: 360, objects: [{ type: "line", x: 40, y: 40, x2: 120, y2: 40 }] } },
];

function select(name: string, option: string) {
  fireEvent.click(screen.getByRole("combobox", { name }));
  fireEvent.click(screen.getByRole("option", { name: option }));
}

describe("teacher editor", () => {
  it("saves MCQ stem, options and answer with original version then keeps regeneration available", async () => {
    const onEdit = vi.fn().mockResolvedValue({});
    const onToggleSelect = vi.fn();
    render(<QuestionCard question={question} answer={answer} version={7} onEdit={onEdit} onToggleSelect={onToggleSelect} showControls />);
    fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa" }));
    fireEvent.change(screen.getByLabelText("Nội dung câu hỏi"), { target: { value: "Chức năng chính của lá là gì?" } });
    fireEvent.change(screen.getByLabelText("Phương án B"), { target: { value: "Thoát hơi nước" } });
    select("Đáp án đúng", "B");
    fireEvent.click(screen.getByRole("button", { name: "Lưu và kiểm định" }));
    await waitFor(() => expect(onEdit).toHaveBeenCalledWith("q1", expect.objectContaining({ version_id: 7, correct_answer: "B", options: expect.objectContaining({ B: "Thoát hơi nước" }) })));
    fireEvent.click(await screen.findByLabelText("Chọn tạo lại"));
    expect(onToggleSelect).toHaveBeenCalledWith("q1");
  });

  it("cancel restores original content and save failure retains the edited form", async () => {
    const onEdit = vi.fn().mockRejectedValue(new Error("Phiên bản đã thay đổi"));
    render(<QuestionCard question={question} answer={answer} onEdit={onEdit} showControls />);
    fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa" }));
    fireEvent.change(screen.getByLabelText("Nội dung câu hỏi"), { target: { value: "Bản sửa" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu và kiểm định" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Phiên bản đã thay đổi");
    expect(screen.getByLabelText("Nội dung câu hỏi")).toHaveValue("Bản sửa");
    fireEvent.click(screen.getByRole("button", { name: "Hủy" }));
    fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa" }));
    expect(screen.getByLabelText("Nội dung câu hỏi")).toHaveValue(question.content);
  });

  it("saves formula display and diagram object choices without losing rich content", async () => {
    const onEdit = vi.fn().mockResolvedValue({});
    render(<QuestionCard question={{ ...question, rich_content: richBlocks }} answer={answer} version={7} onEdit={onEdit} showControls />);
    fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa" }));
    select("Kiểu công thức khối 1", "Trong dòng");
    select("Loại đối tượng 1, khối 2", "Đường tròn");
    fireEvent.change(screen.getByLabelText("radius"), { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu và kiểm định" }));
    await waitFor(() => expect(onEdit).toHaveBeenCalledWith("q1", expect.objectContaining({
      version_id: 7,
      rich_content: [
        { ...richBlocks[0], display: "inline" },
        expect.objectContaining({
          type: "diagram", alt: "Hình thí nghiệm",
          spec: expect.objectContaining({ objects: [expect.objectContaining({ type: "circle", x: 40, y: 40, radius: 25 })] }),
        }),
      ],
    })));
  });

  it.each(["Đáp án đúng", "Kiểu công thức khối 1", "Loại đối tượng 1, khối 2"])("locks the open %s menu while saving and restores it after failure", async (name) => {
    let reject!: (reason: Error) => void;
    const pending = new Promise((_resolve, no) => { reject = no; });
    const onEdit = vi.fn().mockReturnValue(pending);
    render(<QuestionCard question={{ ...question, rich_content: richBlocks }} answer={answer} onEdit={onEdit} showControls />);
    fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa" }));
    fireEvent.click(screen.getByRole("combobox", { name }));
    expect(screen.getByRole("listbox", { name })).toBeInTheDocument();
    fireEvent.submit(screen.getByRole("form", { name: "Sửa câu 1" }));
    expect(screen.queryByRole("listbox", { name })).not.toBeInTheDocument();
    for (const combo of screen.getAllByRole("combobox")) expect(combo).toBeDisabled();
    await act(async () => reject(new Error("Thử lưu lại")));
    expect(await screen.findByRole("alert")).toHaveTextContent("Thử lưu lại");
    expect(screen.getByRole("combobox", { name })).toBeEnabled();
    expect(screen.getByRole("combobox", { name: "Đáp án đúng" })).toHaveTextContent("A");
    expect(screen.getByRole("combobox", { name: "Kiểu công thức khối 1" })).toHaveTextContent("Riêng một dòng");
    expect(screen.getByRole("combobox", { name: "Loại đối tượng 1, khối 2" })).toHaveTextContent("Đoạn thẳng");
  });

  it("edits true/false truth and explanation together", async () => {
    const onEdit = vi.fn().mockResolvedValue({});
    const q: Question = { ...question, type: "true_false", options: undefined, statements: Array.from({ length: 4 }, (_, i) => ({ id: `s${i}`, content: `Phát biểu khoa học ${i + 1}`, is_true: true })) };
    render(<QuestionCard question={q} answer={{ ...answer, type: "true_false", answers: q.statements!.map(s => ({ statement_id: s.id, is_true: true, explanation: "Lời giải" })) }} onEdit={onEdit} showControls />);
    fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa" }));
    fireEvent.click(screen.getByLabelText("Phát biểu 1 đúng"));
    fireEvent.change(screen.getByLabelText("Giải thích phát biểu 1"), { target: { value: "Sai vì…" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu và kiểm định" }));
    await waitFor(() => expect(onEdit).toHaveBeenCalledWith("q1", expect.objectContaining({ statements: expect.arrayContaining([expect.objectContaining({ id: "s0", is_true: false, explanation: "Sai vì…" })]) })));
  });

  it("edits essay expected answer and scoring breakdown", async () => {
    const onEdit = vi.fn().mockResolvedValue({});
    const q: Question = { ...question, type: "essay", options: undefined, sub_questions: [{ id: "part1", content: "Giải thích vai trò lá.", score: 1 }] };
    const rubric: RubricItem = { question_id: "q1", question_number: 1, type: "essay", total_score: 1, grading_guide: ["Chấm theo ý"], criteria: [{ id: "c1", name: "Vai trò của lá", max_score: 1, levels: [{ score: 1, description: "Nêu quang hợp", criteria: "Đúng" }] }] };
    render(<QuestionCard question={q} answer={{ ...answer, type: "essay", model_answer: "Đáp án ban đầu" }} rubric={rubric} onEdit={onEdit} showControls />);
    fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa" }));
    fireEvent.change(screen.getByLabelText("Đáp án mẫu"), { target: { value: "Lá thực hiện quang hợp nhờ diệp lục." } });
    fireEvent.change(screen.getByLabelText("Tên tiêu chí 1"), { target: { value: "Cơ chế quang hợp" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu và kiểm định" }));
    await waitFor(() => expect(onEdit).toHaveBeenCalledWith("q1", expect.objectContaining({ model_answer: "Lá thực hiện quang hợp nhờ diệp lục.", rubric_criteria: expect.arrayContaining([expect.objectContaining({ name: "Cơ chế quang hợp" })]) })));
  });
});

it("edits a short answer without changing the question type", async () => {
  const onEdit = vi.fn().mockResolvedValue({});
  render(<QuestionCard question={{ ...question, type: "short_answer", options: undefined }} answer={{ ...answer, type: "short_answer", correct_answer: "Lá" }} version={2} onEdit={onEdit} showControls />);
  fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa" }));
  fireEvent.change(screen.getByLabelText("Đáp án dự kiến"), { target: { value: "Lục lạp" } });
  fireEvent.click(screen.getByRole("button", { name: "Lưu và kiểm định" }));
  await waitFor(() => expect(onEdit).toHaveBeenCalledWith("q1", expect.objectContaining({ correct_answer: "Lục lạp", version_id: 2 })));
});
