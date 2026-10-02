import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DemoApp from "./DemoApp";

function openDemo(path: string) {
  window.history.replaceState({}, "", `/#${path}`);
  return render(<DemoApp />);
}

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, "", "/");
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("public demo edge cases", () => {
  it("keeps the original and its clone independent when regenerating and approving questions", async () => {
    const user = userEvent.setup();
    const view = openDemo("/exams/de-minh-hoa-khtn-8");
    const originalText = within(screen.getAllByRole("article")[0]).getByRole("heading").textContent!;

    await user.click(screen.getAllByRole("button", { name: "Duyệt câu hỏi" })[0]);
    await user.click(screen.getByRole("button", { name: "Nhân bản đề" }));
    expect(await screen.findByRole("heading", { name: "Đề kiểm tra Giữa kỳ I · KHTN 8 (bản sao)" })).toBeInTheDocument();
    expect(screen.getByText("1/4 câu")).toBeInTheDocument();

    await user.click(within(screen.getAllByRole("article")[0]).getByRole("button", { name: "Tạo lại bản mẫu" }));
    const copiedText = within(screen.getAllByRole("article")[0]).getByRole("heading").textContent!;
    expect(copiedText).not.toBe(originalText);
    await user.click(within(screen.getAllByRole("article")[1]).getByRole("button", { name: "Duyệt câu hỏi" }));
    expect(screen.getByText("1/4 câu")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "← Đề đã tạo" }));
    await user.click(screen.getByRole("link", { name: (name) => name.includes("Đề kiểm tra Giữa kỳ I · KHTN 8") && !name.includes("bản sao") }));
    expect(await screen.findByRole("heading", { name: originalText })).toBeInTheDocument();
    expect(within(screen.getAllByRole("article")[0]).getByRole("button", { name: "✓ Đã duyệt" })).toBeInTheDocument();
    expect(within(screen.getAllByRole("article")[1]).getByRole("button", { name: "Duyệt câu hỏi" })).toBeInTheDocument();
    expect(screen.queryByText("Bản mẫu lần 2")).not.toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Ngân hàng câu hỏi" }));
    expect(await screen.findByText(originalText)).toBeInTheDocument();
    expect(screen.queryByText(copiedText)).not.toBeInTheDocument();
    expect(within(screen.getByRole("main")).getAllByRole("link")).toHaveLength(2);

    view.unmount();
    render(<DemoApp />);
    expect(screen.getByText(originalText)).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getAllByRole("link")).toHaveLength(2);
  });

  it.each([
    { grade: 6, levels: ["Nhận biết", "Thông hiểu", "Thông hiểu", "Vận dụng"], objectives: [/thể tích/, /nhiệt độ sôi/, /oxygen/, /hỗn hợp/], counts: [1, 2, 1] },
    { grade: 7, levels: ["Nhận biết", "Thông hiểu", "Thông hiểu", "Vận dụng"], objectives: [/nguyên tử/, /trung hoà/, /quang hợp/, /chăm sóc cây/], counts: [1, 2, 1] },
    { grade: 8, levels: ["Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng"], objectives: [/đơn vị áp suất/, /áp lực/, /p = F\/S/, /diện tích tiếp xúc/], counts: [1, 1, 2] },
    { grade: 9, levels: ["Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng"], objectives: [/điện trở/, /hiệu điện thế/, /định luật Ohm/, /an toàn điện/], counts: [1, 1, 2] },
  ])("keeps grade $grade questions, matrix, objectives and answers consistent after regenerating every question", async ({ grade, levels, objectives, counts }) => {
    const user = userEvent.setup();
    openDemo("/create");
    await user.selectOptions(screen.getByLabelText("Lớp"), String(grade));
    await user.click(screen.getByRole("button", { name: "Tạo bộ đề mẫu" }));
    expect(await screen.findByRole("heading", { name: `Đề kiểm tra Giữa kỳ I · KHTN ${grade}` })).toBeInTheDocument();

    const initialPrompts = screen.getAllByRole("article").map((article) => within(article).getByRole("heading").textContent);
    for (let index = 0; index < 4; index++) {
      await user.click(within(screen.getAllByRole("article")[index]).getByRole("button", { name: "Tạo lại bản mẫu" }));
    }
    const regeneratedQuestions = screen.getAllByRole("article");
    const types = ["Trắc nghiệm", "Đúng / Sai", "Trả lời ngắn", "Tự luận"];
    regeneratedQuestions.forEach((article, index) => {
      expect(within(article).getByRole("heading").textContent).not.toBe(initialPrompts[index]);
      expect(within(article).getByText(`Câu ${index + 1} · ${types[index]}`)).toBeInTheDocument();
      expect(within(article).getByText(`${levels[index]} · 2,5 điểm`)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Hiện đáp án" }));
    const inlineAnswers = regeneratedQuestions.map((article) => within(article).getByRole("paragraph").textContent!);
    const multipleChoiceOptions = within(regeneratedQuestions[0]).getAllByRole("listitem").map((option) => option.textContent);
    expect(inlineAnswers[0]).toBe(`A. ${multipleChoiceOptions[0]}`);
    expect(multipleChoiceOptions).toHaveLength(4);
    expect(inlineAnswers[1]).toBe("Đúng");

    await user.click(screen.getByRole("tab", { name: "Ma trận" }));
    const matrixRows = within(screen.getByRole("table")).getAllByRole("row");
    expect(within(matrixRows[1]).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([...counts.map((count) => `${count} câu`), "4 câu"]);
    expect(within(matrixRows[2]).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([...counts.map((count) => `${count * 25}%`), "100%"]);

    await user.click(screen.getByRole("tab", { name: "Bản đặc tả" }));
    const specificationRows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(specificationRows).toHaveLength(4);
    specificationRows.forEach((row, index) => {
      const cells = within(row).getAllByRole("cell");
      expect(cells[0]).toHaveTextContent(String(index + 1));
      expect(cells[1]).toHaveTextContent(types[index]);
      expect(cells[2]).toHaveTextContent(levels[index]);
      expect(cells[3]).toHaveTextContent(objectives[index]);
    });

    await user.click(screen.getByRole("tab", { name: "Đáp án & rubric" }));
    expect(screen.getByRole("heading", { name: "Đáp án và hướng dẫn chấm" })).toBeInTheDocument();
    inlineAnswers.forEach((answer) => expect(screen.getByText(answer)).toBeInTheDocument());
    expect(screen.getByText(/Chọn đúng đáp án: 2,5 điểm/)).toBeInTheDocument();
    expect(screen.getByText(/Xác định đúng: 1 điểm; giải thích đúng: 1,5 điểm/)).toBeInTheDocument();
  });

  it.each([
    { grade: 8, originalPrompt: /200 N.*0,5 m²/, alternatePrompt: /400 N.*1 m²/, originalAnswer: "p = F/S = 200/0,5 = 400 Pa.", alternateAnswer: "p = F/S = 400/1 = 400 Pa." },
    { grade: 9, originalPrompt: /6 Ω.*12 V/, alternatePrompt: /3 Ω.*6 V/, originalAnswer: "I = U/R = 12/6 = 2 A.", alternateAnswer: "I = U/R = 6/3 = 2 A." },
  ])("uses the correct numeric answer each time a grade $grade calculation question is regenerated", async ({ grade, originalPrompt, alternatePrompt, originalAnswer, alternateAnswer }) => {
    const user = userEvent.setup();
    const view = openDemo("/create");
    await user.selectOptions(screen.getByLabelText("Lớp"), String(grade));
    await user.click(screen.getByRole("button", { name: "Tạo bộ đề mẫu" }));
    await user.click(screen.getByRole("button", { name: "Hiện đáp án" }));

    for (let revision = 0; revision <= 4; revision++) {
      const calculation = within(screen.getAllByRole("article")[2]);
      expect(calculation.getByRole("heading")).toHaveTextContent(revision % 2 === 0 ? originalPrompt : alternatePrompt);
      expect(calculation.getByText(revision % 2 === 0 ? originalAnswer : alternateAnswer)).toBeInTheDocument();
      if (revision < 4) await user.click(calculation.getByRole("button", { name: "Tạo lại bản mẫu" }));
    }

    view.unmount();
    render(<DemoApp />);
    await user.click(screen.getByRole("button", { name: "Hiện đáp án" }));
    expect(within(screen.getAllByRole("article")[2]).getByText(originalAnswer)).toBeInTheDocument();
    expect(within(screen.getAllByRole("article")[2]).getByText("Bản mẫu lần 5")).toBeInTheDocument();
  });

  it("allows recovery from an unknown route through the dashboard navigation", async () => {
    const user = userEvent.setup();
    openDemo("/does-not-exist/nested");
    expect(screen.getByRole("heading", { name: "Chào mừng đến với Deka." })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Tạo đề mẫu" }));
    expect(await screen.findByRole("heading", { name: "Bắt đầu từ nội dung đã dạy." })).toBeInTheDocument();
  });

  it("allows recovery from an unknown exam without losing the saved exam list", async () => {
    const user = userEvent.setup();
    openDemo("/exams/missing-exam");
    expect(screen.getByRole("heading", { name: "Không tìm thấy đề mẫu" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Về danh sách đề" }));
    expect(await screen.findByRole("heading", { name: "Đề kiểm tra đã tạo" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Đề kiểm tra Giữa kỳ I · KHTN 8/ }));
    expect(await screen.findByRole("heading", { name: "Đề kiểm tra Giữa kỳ I · KHTN 8" })).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(4);
  });

  it.each([
    { method: "getItem" as const, error: "SecurityError" },
    { method: "setItem" as const, error: "QuotaExceededError" },
  ])("keeps creation and approvals usable when localStorage.$method throws", async ({ method, error }) => {
    vi.spyOn(Storage.prototype, method).mockImplementation(() => { throw new DOMException("Storage unavailable", error); });
    const user = userEvent.setup();
    openDemo("/create");
    await user.selectOptions(screen.getByLabelText("Lớp"), "7");
    await user.click(screen.getByRole("button", { name: "Tạo bộ đề mẫu" }));
    expect(await screen.findByRole("heading", { name: "Đề kiểm tra Giữa kỳ I · KHTN 7" })).toBeInTheDocument();

    const questionText = within(screen.getAllByRole("article")[0]).getByRole("heading").textContent!;
    await user.click(screen.getAllByRole("button", { name: "Duyệt câu hỏi" })[0]);
    await user.click(screen.getByRole("link", { name: "Ngân hàng câu hỏi" }));
    expect(await screen.findByText(questionText)).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: (name) => name.includes(questionText) }));
    expect(await screen.findByRole("button", { name: "✓ Đã duyệt" })).toBeInTheDocument();
  });
});
