import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FullExamResponse } from "../types";
import ExamDetail from "./ExamDetail";

const { loadExamMock, regenerateQuestionsMock, reviewQuestionMock, exportDocxMock, exportPdfMock, state } = vi.hoisted(() => ({
  loadExamMock: vi.fn(),
  regenerateQuestionsMock: vi.fn(),
  reviewQuestionMock: vi.fn(),
  exportDocxMock: vi.fn(),
  exportPdfMock: vi.fn(),
  state: { loading: false, error: "" },
}));

const exam = {
  id: 42,
  exam_number: 3,
  exam_info: {
    school: "THCS Nguyễn Du",
    grade: 8,
    subject: "Khoa học tự nhiên",
    exam_type: "Giữa học kì I",
    duration_minutes: 45,
    school_year: "2026-2027",
    total_score: 10,
  },
  matrix: [],
  summary: {
    nhan_biet: { total_count: 0, total_score: 0, percentage: 0 },
    thong_hieu: { total_count: 0, total_score: 0, percentage: 0 },
    van_dung: { total_count: 0, total_score: 0, percentage: 0 },
    total_score: 10,
  },
  specification: [],
  questions: [],
  answer_key: [],
  rubric: [],
  validation: { passed: true, score: 100, checks: [], warnings: [], errors: [] },
  review_status: {},
  variants: [],
} satisfies FullExamResponse;

vi.mock("../hooks/useExam", () => ({
  useExam: () => ({
    loading: state.loading,
    error: state.error,
    onLoadExam: loadExamMock,
    onExportDocx: exportDocxMock,
    onExportPdf: exportPdfMock,
    onDeleteExam: vi.fn(),
    onDuplicateExam: vi.fn(),
    onRegenerateQuestions: regenerateQuestionsMock,
    onReviewQuestion: reviewQuestionMock,
    onSaveQuestionsToBank: vi.fn(),
  }),
}));

vi.mock("../contexts/useToast", () => ({
  useToast: () => ({ notify: vi.fn() }),
}));

function detailRoute() {
  return (
    <MemoryRouter initialEntries={["/exams/42"]}>
      <Link to="/exams/43">Mở đề tiếp theo</Link>
      <Routes>
        <Route path="/exams/:id" element={<ExamDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ExamDetail error boundary", () => {
  beforeEach(() => {
    state.loading = false;
    state.error = "";
    loadExamMock.mockReset();
    exportDocxMock.mockReset();
    exportPdfMock.mockReset();
    reviewQuestionMock.mockReset();
    regenerateQuestionsMock.mockReset();
    regenerateQuestionsMock.mockResolvedValue(undefined);
    loadExamMock.mockResolvedValue(exam);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("uses the account number in the heading and the permanent ID for loading", async () => {
    render(detailRoute());
    expect(await screen.findByText("Đề kiểm tra #3")).toBeInTheDocument();
    expect(loadExamMock).toHaveBeenCalledWith(42);
    expect(screen.queryByText("Đề kiểm tra #42")).not.toBeInTheDocument();
  });

  it("renders legacy exam responses without a global-ID heading", async () => {
    loadExamMock.mockResolvedValue({ ...exam, exam_number: null });
    render(detailRoute());
    expect(await screen.findByText("Đề kiểm tra", { selector: ".exam-review-title .exam-review-eyebrow" })).toBeInTheDocument();
  });

  it("ignores a previous exam load that finishes after navigating to another exam", async () => {
    let finishOld!: (value: FullExamResponse) => void;
    loadExamMock.mockReturnValueOnce(new Promise<FullExamResponse>(resolve => { finishOld = resolve; }))
      .mockResolvedValueOnce({ ...exam, id: 43, exam_info: { ...exam.exam_info, school: "Trường của đề mới" } });
    render(detailRoute());
    fireEvent.click(screen.getByRole("link", { name: "Mở đề tiếp theo" }));
    await screen.findByText("Trường của đề mới");
    await act(async () => finishOld(exam));
    expect(screen.getByText("Trường của đề mới")).toBeInTheDocument();
    expect(screen.queryByText("THCS Nguyễn Du")).not.toBeInTheDocument();
  });

  it("clears the previous exam and its action controls when the next exam fails to load", async () => {
    loadExamMock.mockResolvedValueOnce(exam).mockRejectedValueOnce(new Error("Exam no longer accessible"));
    render(detailRoute());
    await screen.findByText("THCS Nguyễn Du");
    fireEvent.click(screen.getByRole("link", { name: "Mở đề tiếp theo" }));
    await waitFor(() => expect(loadExamMock).toHaveBeenLastCalledWith(43));
    expect(screen.queryByText("THCS Nguyễn Du")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tải Word" })).not.toBeInTheDocument();
  });

  it("does not restore the previous exam when its review finishes after navigation", async () => {
    const oldExam: FullExamResponse = { ...exam, owner_user_id: -1, questions: [{
      id: "q_1", number: 1, type: "multiple_choice", difficulty: "nhan_biet", score: 1,
      content: "Câu hỏi đề trước", options: { A: "Đúng", B: "Sai" },
      metadata: { topic: "Tim", lesson: "Tim", knowledge_unit: "Tim", achievement: "Mô tả tim", bloom_level: "remember" },
    }] };
    let finishReview!: (value: FullExamResponse) => void;
    loadExamMock.mockResolvedValueOnce(oldExam).mockResolvedValueOnce({ ...exam, id: 43, exam_info: { ...exam.exam_info, school: "Trường của đề mới" } });
    reviewQuestionMock.mockReturnValueOnce(new Promise<FullExamResponse>(resolve => { finishReview = resolve; }));
    render(detailRoute());
    fireEvent.click(await screen.findByRole("button", { name: "Chấp nhận" }));
    fireEvent.click(screen.getByRole("link", { name: "Mở đề tiếp theo" }));
    await screen.findByText("Trường của đề mới");
    await act(async () => finishReview({ ...oldExam, review_status: { q_1: { status: "accepted" } } }));
    expect(screen.getByText("Trường của đề mới")).toBeInTheDocument();
    expect(screen.queryByText("THCS Nguyễn Du")).not.toBeInTheDocument();
  });

  it("keeps a failed draft repair on the same draft without reloading it as success", async () => {
    loadExamMock.mockResolvedValueOnce({ ...exam, owner_user_id: -1, publication_status: "draft", validation: {
      ...exam.validation, passed: false, persistence: { status: "draft", publishable: false, question_failures: { q_1: ["answer_mismatch"] } },
    } });
    regenerateQuestionsMock.mockRejectedValueOnce(new Error("Reviewer unavailable"));
    render(detailRoute());
    fireEvent.click(await screen.findByRole("button", { name: "Tạo lại 1 câu lỗi" }));
    await waitFor(() => expect(regenerateQuestionsMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Tạo lại 1 câu lỗi" })).toBeEnabled());
    expect(loadExamMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Tải Word" })).toBeDisabled();
  });

  it("switches original and variant previews with the export audience and restores teacher details", async () => {
    const question = {
      id: "q_1", number: 1, type: "multiple_choice" as const,
      difficulty: "nhan_biet" as const, score: 1,
      content: "Chọn số ngăn của tim người.",
      options: { A: "Hai ngăn", B: "Bốn ngăn" },
      correct_answer: "B",
      metadata: { topic: "Hệ tuần hoàn", lesson: "Tim", knowledge_unit: "Tim", achievement: "Nêu cấu tạo", bloom_level: "remember" },
    };
    const answer = {
      question_id: "q_1", question_number: 1, type: "multiple_choice" as const,
      correct_answer: "B", explanation: "Lời giải chỉ dành cho giáo viên.",
    };
    loadExamMock.mockResolvedValue({
      ...exam,
      owner_user_id: -1,
      questions: [question], answer_key: [answer],
      review_status: { q_1: { status: "pending" } },
      validation: {
        ...exam.validation,
        verification_report: {
          overall_score: 90, overall_status: "passed_with_warnings",
          summary: { total_questions: 1, auto_approved: 0, needs_review: 1, auto_rejected: 0 },
          question_reports: [],
          action_required: [{ priority: "medium", question_id: "q_1", message: "Gợi ý chỉ dành cho giáo viên.", fix: "" }],
        },
      },
      variants: [{
        code: "101",
        questions: [{ ...question, id: "101_q_1", original_id: "q_1", options: { A: "Bốn ngăn", B: "Hai ngăn" }, correct_answer: "A" }],
        answer_key: [{ ...answer, question_id: "101_q_1", correct_answer: "A" }],
      }],
    } satisfies FullExamResponse);
    vi.stubGlobal("URL", class extends URL {
      static createObjectURL = vi.fn(() => "blob:exam");
      static revokeObjectURL = vi.fn();
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    exportDocxMock.mockResolvedValue(new Blob());
    exportPdfMock.mockResolvedValue(new Blob());
    const { container } = render(detailRoute());
    expect(await screen.findByText("Đáp án đúng")).toBeInTheDocument();
    expect(screen.getByText("Gợi ý chỉ dành cho giáo viên.")).toBeInTheDocument();

    function chooseAudience(label: string) {
      fireEvent.click(screen.getByRole("combobox", { name: "Chọn chế độ xem và xuất" }));
      fireEvent.click(screen.getByRole("option", { name: label }));
    }
    function expectStudentPreview() {
      expect(screen.getByText("Hai ngăn")).toBeInTheDocument();
      expect(screen.getByText("Bốn ngăn")).toBeInTheDocument();
      expect(container.textContent).not.toMatch(/chỉ dành cho giáo viên|Đáp án đúng|Minh chứng nguồn|Hệ tuần hoàn|Nhận biết|Cấu trúc và bản đặc tả|Chấp nhận|Lưu câu đã duyệt/);
      expect(container.querySelector(".is-correct, .quality-findings, .question-review-bar, .exam-support-panel")).toBeNull();
    }
    chooseAudience("Học sinh · không đáp án");
    expectStudentPreview();
    fireEvent.click(screen.getByRole("button", { name: "Mã 101" }));
    expectStudentPreview();

    fireEvent.click(screen.getByRole("button", { name: "Tải PDF" }));
    await waitFor(() => expect(exportPdfMock).toHaveBeenCalledWith(42, "student", { document: "exam", variant_code: "101" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Tải PDF" })).toBeEnabled());

    chooseAudience("Giáo viên · đủ đáp án");
    expect(screen.getByText("Bốn ngăn").closest(".question-option")).toHaveClass("is-correct");
    expect(screen.getByText("Lời giải chỉ dành cho giáo viên.")).toBeInTheDocument();
    expect(screen.getByText("Gợi ý chỉ dành cho giáo viên.")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Chọn nội dung hiển thị" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Bản gốc" }));
    expect(screen.getByRole("button", { name: "Chấp nhận" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tải Word" }));
    await waitFor(() => expect(exportDocxMock).toHaveBeenCalledWith(42, "teacher", { document: "exam", variant_code: undefined }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Tải Word" })).toBeEnabled());

    fireEvent.click(screen.getByRole("button", { name: "Mã 101" }));
    for (const [label, document] of [
      ["Đáp án và hướng dẫn chấm", "answers"],
      ["Ma trận đề", "matrix"],
      ["Bản đặc tả", "specification"],
    ]) {
      fireEvent.click(screen.getByRole("combobox", { name: "Chọn tài liệu tải xuống" }));
      fireEvent.click(screen.getByRole("option", { name: label }));
      fireEvent.click(screen.getByRole("button", { name: "Tải Word" }));
      await waitFor(() => expect(exportDocxMock).toHaveBeenLastCalledWith(42, "teacher", { document, variant_code: "101" }));
      await waitFor(() => expect(screen.getByRole("button", { name: "Tải Word" })).toBeEnabled());
    }
    chooseAudience("Học sinh · không đáp án");
    expect(screen.queryByRole("combobox", { name: "Chọn tài liệu tải xuống" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tải Word" }));
    await waitFor(() => expect(exportDocxMock).toHaveBeenLastCalledWith(42, "student", { document: "exam", variant_code: "101" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Tải Word" })).toBeEnabled());
  });

  it("opens matrix and specification directly while keeping student preview and exports separate", async () => {
    const question = {
      id: "q_1", number: 1, type: "multiple_choice" as const,
      difficulty: "nhan_biet" as const, score: 1, content: "Câu hỏi xem trước",
      options: { A: "Phương án A", B: "Phương án B" },
      metadata: { topic: "Chủ đề", lesson: "Bài học", knowledge_unit: "Kiến thức", achievement: "Yêu cầu", bloom_level: "remember" },
    };
    loadExamMock.mockResolvedValue({
      ...exam,
      questions: [question],
      matrix: [{
        id: "m1", topic_id: "t1", topic_name: "Chủ đề", lesson_id: "l1", lesson_name: "Dữ liệu ma trận",
        nhan_biet: { count: 1, score: 1, question_type: "multiple_choice" },
        thong_hieu: { count: 0, score: 0, question_type: "multiple_choice" },
        van_dung: { count: 0, score: 0, question_type: "multiple_choice" }, total_score: 1,
      }],
      specification: [{
        question_id: "q_1", question_number: 1, question_type: "multiple_choice", difficulty: "nhan_biet", score: 1,
        topic: "Chủ đề", lesson: "Bài học", knowledge_unit: "Kiến thức", achievement: "Yêu cầu đặc tả", bloom_level: "remember",
      }],
      variants: [{ code: "101", questions: [{ ...question, id: "101_q_1", original_id: "q_1", number: 2 }], answer_key: [] }],
    } satisfies FullExamResponse);
    render(detailRoute());
    expect(await screen.findByRole("combobox", { name: "Chọn nội dung hiển thị" })).toHaveTextContent("Đề kiểm tra");
    function select(label: string, option: string) {
      fireEvent.click(screen.getByRole("combobox", { name: label }));
      fireEvent.click(screen.getByRole("option", { name: option }));
    }
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    select("Chọn nội dung hiển thị", "Ma trận đề");
    expect(screen.getByRole("heading", { name: "Ma trận đề kiểm tra" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Dữ liệu ma trận" })).toBeInTheDocument();
    expect(screen.queryByText("Câu hỏi xem trước")).not.toBeInTheDocument();
    select("Chọn nội dung hiển thị", "Bản đặc tả");
    expect(screen.getByRole("heading", { name: "Bản đặc tả" })).toBeInTheDocument();
    expect(screen.queryByText("Dữ liệu ma trận")).not.toBeInTheDocument();
    const row = screen.getByRole("cell", { name: "Yêu cầu đặc tả" }).closest("tr")!;
    expect(within(row).getAllByRole("cell")[0]).toHaveTextContent(/^1$/);
    fireEvent.click(screen.getByRole("button", { name: "Mã 101" }));
    expect(within(row).getAllByRole("cell")[0]).toHaveTextContent(/^2$/);
    expect(screen.getByRole("combobox", { name: "Chọn tài liệu tải xuống" })).toHaveTextContent("Đề kiểm tra · chỉ câu hỏi");
    select("Chọn chế độ xem và xuất", "Học sinh · không đáp án");
    expect(screen.queryByRole("combobox", { name: "Chọn nội dung hiển thị" })).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Yêu cầu đặc tả")).not.toBeInTheDocument();
    expect(screen.getByText("Phương án A")).toBeInTheDocument();
    select("Chọn chế độ xem và xuất", "Giáo viên · đủ đáp án");
    expect(screen.getByRole("heading", { name: "Bản đặc tả" })).toBeInTheDocument();
    select("Chọn nội dung hiển thị", "Đề kiểm tra");
    expect(screen.getByText("Phương án A")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it.each([
    ["Ma trận đề", "Chưa có ma trận đề"],
    ["Bản đặc tả", "Chưa có bản đặc tả"],
  ])("shows an empty state for missing %s", async (label, message) => {
    render(detailRoute());
    fireEvent.click(await screen.findByRole("combobox", { name: "Chọn nội dung hiển thị" }));
    fireEvent.click(screen.getByRole("option", { name: label }));
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("keeps the loaded exam visible when a later action reports an error", async () => {
    const view = render(detailRoute());
    expect(await screen.findByText(/THCS Nguyễn Du/)).toBeInTheDocument();

    state.error = "Không xuất được file Word";
    view.rerender(detailRoute());

    await waitFor(() => {
      expect(screen.getByText(/THCS Nguyễn Du/)).toBeInTheDocument();
      expect(screen.getByRole("alert")).toHaveTextContent("Không xuất được file Word");
    });
  });

  it("shows only actionable feedback with the correct display number", async () => {
    loadExamMock.mockResolvedValue({
      ...exam,
      validation: {
        ...exam.validation,
        verification_report: {
          overall_score: 92,
          overall_status: "passed",
          summary: { total_questions: 1, auto_approved: 1, needs_review: 0, auto_rejected: 0 },
          action_required: [{
            priority: "medium",
            question_id: "q_1",
            message: "Câu hỏi còn mơ hồ.",
            fix: "Nêu rõ điều kiện trong câu hỏi.",
          }],
          question_reports: [{
            question_id: "q_1",
            question_number: 1,
            verification_score: 92,
            status: "needs_review",
            issues: [{
              severity: "medium",
              type: "ambiguous",
              description: "Câu hỏi còn mơ hồ.",
              suggestion: "Nêu rõ điều kiện trong câu hỏi.",
            }],
          }],
        },
      },
      variants: [{
        code: "101",
        questions: [{
          id: "101_q_1",
          original_id: "q_1",
          number: 1,
          type: "multiple_choice",
          difficulty: "nhan_biet",
          score: 1,
          content: "Câu hỏi mã đề",
          options: { A: "A", B: "B", C: "C", D: "D" },
          metadata: {
            topic: "Tế bào",
            lesson: "Cấu tạo tế bào",
            knowledge_unit: "Cấu tạo",
            achievement: "Mô tả",
            bloom_level: "remember",
          },
        }],
        answer_key: [],
      }],
    } satisfies FullExamResponse);

    render(detailRoute());

    expect(await screen.findByRole("link", { name: "Câu 1" })).toHaveAttribute(
      "href",
      "#question-q_1",
    );
    expect(screen.getByText("Nêu rõ điều kiện trong câu hỏi.", { exact: false })).toBeInTheDocument();
    expect(screen.queryByText(/Validation|Kiểm tra đề|Điểm chất lượng|q_1|AI/i)).not.toBeInTheDocument();
  });

  it("opens the original exam and allows review after reopening", async () => {
    const originalQuestion = {
      id: "q_1",
      number: 1,
      type: "multiple_choice" as const,
      difficulty: "nhan_biet" as const,
      score: 1,
      content: "Câu hỏi bản gốc",
      options: { A: "Đúng", B: "Sai 1", C: "Sai 2", D: "Sai 3" },
      metadata: {
        topic: "Tế bào",
        lesson: "Tế bào",
        knowledge_unit: "Khái niệm",
        achievement: "Nêu khái niệm tế bào",
        bloom_level: "remember",
      },
    };
    const reopenedExam = {
      ...exam,
      owner_user_id: -1,
      questions: [originalQuestion],
      review_status: { q_1: { status: "pending" as const } },
      variants: [{
        code: "101",
        questions: [{ ...originalQuestion, id: "101_q_1", original_id: "q_1", content: "Câu hỏi mã đề 101" }],
        answer_key: [],
      }],
    } satisfies FullExamResponse;
    loadExamMock.mockResolvedValue(reopenedExam);
    reviewQuestionMock.mockResolvedValue({
      ...reopenedExam,
      review_status: { q_1: { status: "accepted" as const } },
    });

    render(detailRoute());

    expect((await screen.findAllByText("Câu hỏi bản gốc")).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Bản gốc" })).toHaveClass("variant-tab-active");
    expect(screen.queryByText("Câu hỏi mã đề 101")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Chấp nhận" }));

    await waitFor(() => {
      expect(reviewQuestionMock).toHaveBeenCalledWith(42, "q_1", "accepted");
      expect(screen.getByRole("button", { name: "✓ Đã duyệt" })).toBeDisabled();
    });
  });

  it("filters the persisted exam by only the question types that exist", async () => {
    const sharedMetadata = {
      topic: "Tế bào",
      lesson: "Cấu tạo tế bào",
      knowledge_unit: "Cấu tạo",
      achievement: "Mô tả",
      bloom_level: "remember",
    };
    loadExamMock.mockResolvedValue({
      ...exam,
      owner_user_id: -1,
      questions: [
        {
          id: "q_mc",
          number: 1,
          type: "multiple_choice",
          difficulty: "nhan_biet",
          score: 1,
          content: "Câu hỏi nhiều lựa chọn",
          options: { A: "Đúng", B: "Sai" },
          metadata: sharedMetadata,
        },
        {
          id: "q_tf",
          number: 2,
          type: "true_false",
          difficulty: "thong_hieu",
          score: 1,
          content: "Ngữ cảnh chung đúng sai",
          statements: [
            { id: "q_tf_a", content: "Phát biểu a", is_true: true },
            { id: "q_tf_b", content: "Phát biểu b", is_true: false },
          ],
          metadata: sharedMetadata,
        },
      ],
      review_status: {
        q_mc: { status: "pending" },
        q_tf: { status: "pending" },
      },
    } satisfies FullExamResponse);

    render(detailRoute());

    expect(await screen.findByRole("tab", { name: "Tất cả · 2 câu" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Phần I. Nhiều lựa chọn · 1 câu" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Phần II. Đúng/Sai · 1 câu" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Trả lời ngắn/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Tự luận/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Phần II. Đúng/Sai · 1 câu" }));

    expect(screen.queryByText("Câu hỏi nhiều lựa chọn")).not.toBeInTheDocument();
    expect(screen.getAllByText("Ngữ cảnh chung đúng sai").length).toBeGreaterThan(0);
    expect(screen.getByText("Phát biểu a")).toBeInTheDocument();
    expect(screen.getByText("Phát biểu b")).toBeInTheDocument();
  });

  it("labels drafts, blocks publication actions, and repairs only failed ids", async () => {
    const draft = {
      ...exam,
      owner_user_id: -1,
      publication_status: "draft" as const,
      validation: {
        ...exam.validation,
        passed: false,
        persistence: {
          status: "draft" as const,
          publishable: false,
          question_failures: { q_2: ["learning_objective_copy"] },
        },
      },
    } satisfies FullExamResponse;
    loadExamMock.mockResolvedValue(draft);

    render(detailRoute());

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Bản nháp chưa qua kiểm định bắt buộc",
    );
    expect(screen.getByRole("button", { name: "Tải Word" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Tải PDF" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Lưu câu đã duyệt" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Tạo lại 1 câu lỗi" }));

    await waitFor(() => {
      expect(regenerateQuestionsMock).toHaveBeenCalledWith({
        exam_id: 42,
        question_ids: ["q_2"],
        reason: "Sửa các lỗi kiểm định đã lưu trong bản nháp",
        allow_provider_fallback: false,
      });
    });
  });
});
