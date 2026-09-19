import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DocumentResponse, FullExamResponse } from "../types";
import CreateExam from "./CreateExam";
import { createDefaultExamPayload, examFormDraftKey, readExamFormDraft, writeExamFormDraft } from "../utils/examFormDraft";

const {
  authState,
  getAiModelsMock,
  getAiProvidersMock,
  listDocumentsMock,
  onGenerateFullExamMock,
  onRegenerateQuestionsMock,
  resultState,
} = vi.hoisted(() => ({
  authState: { id: 1, school_id: 5, role: "school_admin" },
  getAiModelsMock: vi.fn(),
  getAiProvidersMock: vi.fn(),
  listDocumentsMock: vi.fn(),
  onGenerateFullExamMock: vi.fn(),
  onRegenerateQuestionsMock: vi.fn(),
  resultState: { value: null as FullExamResponse | null },
}));

vi.mock("../contexts/useAuth", () => ({
  useAuth: () => ({ user: { ...authState } }),
}));

vi.mock("../hooks/useExam", () => ({
  useExam: () => ({
    loading: false,
    error: "",
    result: resultState.value,
    resourcePackage: null,
    pipelineStages: [],
    onCollectResources: vi.fn(),
    onGenerateFullExam: onGenerateFullExamMock,
    onRegenerateQuestions: onRegenerateQuestionsMock,
    onReviewQuestion: vi.fn(),
    onSaveQuestionsToBank: vi.fn(),
    clearError: vi.fn(),
  }),
}));

vi.mock("../services/api", () => ({
  getAiModels: getAiModelsMock,
  getAiProviders: getAiProvidersMock,
  listDocuments: listDocumentsMock,
  setAiModel: vi.fn(),
}));

describe("CreateExam provider visibility", () => {
  const sourceDoc = (id: number, grade: number): DocumentResponse => ({
    id, grade, filename: `nguon-lop-${grade}.pdf`, file_type: "pdf", size: 100,
    status: "ready", text_preview: "Tài liệu kiểm thử", text_length: 100,
  });

  it("ignores a previous grade's document response arriving after the selected grade", async () => {
    let finish!: (docs: DocumentResponse[]) => void;
    listDocumentsMock.mockReturnValueOnce(new Promise<DocumentResponse[]>(resolve => { finish = resolve; }))
      .mockResolvedValueOnce([sourceDoc(9, 9)]);
    render(<CreateExam />);
    fireEvent.click(screen.getByRole("combobox", { name: "Khối" }));
    fireEvent.click(screen.getByRole("option", { name: "Lớp 9" }));
    expect(await screen.findByLabelText(/nguon-lop-9.pdf/)).toBeInTheDocument();
    await act(async () => { finish([sourceDoc(6, 6)]); });
    expect(screen.getByLabelText(/nguon-lop-9.pdf/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/nguon-lop-6.pdf/)).not.toBeInTheDocument();
  });

  it("clears previous grade sources immediately while the next grade is loading", async () => {
    listDocumentsMock.mockResolvedValueOnce([sourceDoc(6, 6)]).mockReturnValueOnce(new Promise(() => {}));
    render(<CreateExam />);
    const source = await screen.findByLabelText(/nguon-lop-6.pdf/);
    fireEvent.click(source);
    fireEvent.click(screen.getByRole("combobox", { name: "Khối" }));
    fireEvent.click(screen.getByRole("option", { name: "Lớp 9" }));
    expect(screen.queryByLabelText(/nguon-lop-6.pdf/)).not.toBeInTheDocument();
    expect(screen.getByText("Đang tải tài liệu…")).toBeInTheDocument();
  });

  it("shows a document-load error and allows retry without calling AI", async () => {
    listDocumentsMock.mockRejectedValueOnce(new Error("Tạm thời không tải được nguồn tài liệu"))
      .mockResolvedValueOnce([sourceDoc(6, 6)]);
    render(<CreateExam />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Tạm thời không tải được nguồn tài liệu");
    fireEvent.click(screen.getByRole("button", { name: "Tải lại tài liệu" }));
    expect(await screen.findByLabelText(/nguon-lop-6.pdf/)).toBeInTheDocument();
    expect(onGenerateFullExamMock).not.toHaveBeenCalled();
  });

  beforeEach(() => {
    authState.id = 1;
    authState.school_id = 5;
    authState.role = "school_admin";
    getAiModelsMock.mockReset();
    getAiProvidersMock.mockReset();
    listDocumentsMock.mockReset();
    onGenerateFullExamMock.mockReset();
    onRegenerateQuestionsMock.mockReset();
    onGenerateFullExamMock.mockResolvedValue(undefined);
    onRegenerateQuestionsMock.mockResolvedValue(undefined);
    resultState.value = null;
    listDocumentsMock.mockResolvedValue([]);
    getAiProvidersMock.mockResolvedValue({
      active_provider: "openai",
      providers: [
        {
          provider: "openai",
          model: "gpt-4.1",
          verify_model: "gpt-4.1",
          configured: true,
          key_exposed: false,
          priority: 1,
          role: "primary",
        },
      ],
    });
    getAiModelsMock.mockResolvedValue({
      openai: {
        current: "gpt-4.1",
        current_verify: "gpt-4.1",
        suggested: ["gpt-4.1"],
      },
    });
  });

  it("does not show or request provider configuration for a school admin", async () => {
    render(
      <MemoryRouter>
        <CreateExam />
      </MemoryRouter>,
    );

    await waitFor(() => expect(listDocumentsMock).toHaveBeenCalled());
    expect(getAiProvidersMock).not.toHaveBeenCalled();
    expect(getAiModelsMock).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Thứ tự API AI")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Trường")).toBeInTheDocument();
  });

  it("saves edits immediately and restores the full form on remount without generating", async () => {
    const first = render(<CreateExam />);
    await waitFor(() => expect(listDocumentsMock).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("Trường"), { target: { value: "THCS Bản nháp riêng" } });
    fireEvent.change(screen.getByLabelText("Năm học"), { target: { value: "2026-2027" } });
    fireEvent.change(screen.getByLabelText("Thời gian (phút)"), { target: { value: "60" } });
    fireEvent.change(screen.getAllByLabelText("Chủ đề hoặc bài học")[0], { target: { value: "Bài học đang sửa" } });
    fireEvent.change(screen.getAllByLabelText("Yêu cầu cần đạt")[0], { target: { value: "Giải thích hiện tượng" } });
    fireEvent.click(screen.getByRole("button", { name: "+ Thêm bài học" }));
    fireEvent.click(screen.getByRole("button", { name: "Nặng vận dụng 20/40/40" }));
    fireEvent.change(screen.getByLabelText("Số câu Trắc nghiệm nhiều lựa chọn"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Số câu tính toán bắt buộc"), { target: { value: "" } });
    expect(readExamFormDraft("1:5").draft?.data).toMatchObject({
      payload: { school: "THCS Bản nháp riêng", school_year: "2026-2027", duration_minutes: 60,
        question_types: { multiple_choice: { count: 10 } }, difficulty_ratio: { nhan_biet: 20, thong_hieu: 40, van_dung: 40 } },
      calculationCountInput: "", curriculumEdited: true,
    });
    first.unmount();
    render(<CreateExam />);
    expect(screen.getByLabelText("Trường")).toHaveValue("THCS Bản nháp riêng");
    expect(screen.getByLabelText("Năm học")).toHaveValue("2026-2027");
    expect(screen.getByLabelText("Thời gian (phút)")).toHaveValue(60);
    expect(screen.getAllByLabelText("Chủ đề hoặc bài học")).toHaveLength(4);
    expect(screen.getAllByLabelText("Chủ đề hoặc bài học")[0]).toHaveValue("Bài học đang sửa");
    expect(screen.getAllByLabelText("Yêu cầu cần đạt")[0]).toHaveValue("Giải thích hiện tượng");
    expect(screen.getByLabelText("Tỷ lệ Vận dụng (phần trăm)")).toHaveValue(40);
    expect(screen.getByLabelText("Số câu Trắc nghiệm nhiều lựa chọn")).toHaveValue(10);
    expect(screen.getByLabelText("Số câu tính toán bắt buộc")).toHaveValue(null);
    expect(screen.getByText(/Đã khôi phục lần chỉnh sửa trước/)).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Trạng thái lưu bản nháp" })).toHaveTextContent("Đã lưu bản nháp");
    expect(onGenerateFullExamMock).not.toHaveBeenCalled();
  });

  it("persists sequential slider changes and restores them without changing the first level", async () => {
    const view = render(<CreateExam />);
    await waitFor(() => expect(listDocumentsMock).toHaveBeenCalled());
    fireEvent.change(screen.getByRole("slider", { name: "Tỷ lệ Nhận biết" }), { target: { value: "35" } });
    fireEvent.change(screen.getByRole("slider", { name: "Tỷ lệ Thông hiểu" }), { target: { value: "50" } });
    expect(readExamFormDraft("1:5").draft?.data.payload.difficulty_ratio).toEqual({
      nhan_biet: 35, thong_hieu: 50, van_dung: 15,
    });
    view.unmount();
    render(<CreateExam />);
    expect(screen.getByLabelText("Tỷ lệ Nhận biết (phần trăm)")).toHaveValue(35);
    expect(screen.getByLabelText("Tỷ lệ Thông hiểu (phần trăm)")).toHaveValue(50);
    expect(screen.getByLabelText("Tỷ lệ Vận dụng (phần trăm)")).toHaveValue(15);
    expect(onGenerateFullExamMock).not.toHaveBeenCalled();
  });

  it("isolates live account/school switches and restores each account's latest edits", () => {
    const view = render(<CreateExam />);
    fireEvent.change(screen.getByLabelText("Trường"), { target: { value: "Tài khoản A" } });
    authState.id = 2;
    view.rerender(<CreateExam />);
    expect(screen.getByLabelText("Trường")).toHaveValue("THCS Nguyễn Du");
    fireEvent.change(screen.getByLabelText("Trường"), { target: { value: "Tài khoản B" } });
    authState.id = 1;
    view.rerender(<CreateExam />);
    expect(screen.getByLabelText("Trường")).toHaveValue("Tài khoản A");
    authState.school_id = 6;
    view.rerender(<CreateExam />);
    expect(screen.getByLabelText("Trường")).toHaveValue("THCS Nguyễn Du");
    expect(readExamFormDraft("2:5").draft?.data.payload.school).toBe("Tài khoản B");
  });

  it("requires confirmation to reset and leaves another account's draft intact", () => {
    writeExamFormDraft("2:5", { payload: { ...createDefaultExamPayload(), school: "Tài khoản B" }, calculationCountInput: "2", curriculumEdited: false, selectedDocIds: [] });
    const view = render(<CreateExam />);
    fireEvent.change(screen.getByLabelText("Trường"), { target: { value: "Đang chỉnh sửa" } });
    fireEvent.click(screen.getByRole("button", { name: "Tạo đề mới" }));
    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục chỉnh sửa" }));
    expect(screen.getByLabelText("Trường")).toHaveValue("Đang chỉnh sửa");
    fireEvent.click(screen.getByRole("button", { name: "Tạo đề mới" }));
    fireEvent.click(screen.getByRole("button", { name: "Bắt đầu đề mới" }));
    expect(screen.getByLabelText("Trường")).toHaveValue("THCS Nguyễn Du");
    expect(readExamFormDraft("2:5").draft?.data.payload.school).toBe("Tài khoản B");
    view.unmount();
    render(<CreateExam />);
    expect(screen.getByLabelText("Trường")).toHaveValue("THCS Nguyễn Du");
  });

  it("shows storage failures without losing edits and retries persistence", () => {
    render(<CreateExam />);
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Quota"); });
    fireEvent.change(screen.getByLabelText("Trường"), { target: { value: "Chưa lưu" } });
    expect(screen.getByRole("status", { name: "Trạng thái lưu bản nháp" })).toHaveTextContent("Chưa lưu được bản nháp");
    expect(screen.getByLabelText("Trường")).toHaveValue("Chưa lưu");
    write.mockRestore();
    fireEvent.click(screen.getByRole("button", { name: "Thử lưu lại" }));
    expect(screen.getByRole("status", { name: "Trạng thái lưu bản nháp" })).toHaveTextContent("Đã lưu bản nháp");
    expect(readExamFormDraft("1:5").draft?.data.payload.school).toBe("Chưa lưu");
  });

  it("keeps current edits if removing the draft fails", () => {
    render(<CreateExam />);
    fireEvent.change(screen.getByLabelText("Trường"), { target: { value: "Giữ lại" } });
    const remove = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("Blocked"); });
    fireEvent.click(screen.getByRole("button", { name: "Tạo đề mới" }));
    fireEvent.click(screen.getByRole("button", { name: "Bắt đầu đề mới" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Chưa thể xóa bản nháp");
    expect(screen.getByLabelText("Trường")).toHaveValue("Giữ lại");
    remove.mockRestore();
  });

  it("opens a usable default form with feedback when stored data is corrupt", () => {
    localStorage.setItem(examFormDraftKey("1:5"), "{bad json");
    render(<CreateExam />);
    expect(screen.getByLabelText("Trường")).toHaveValue("THCS Nguyễn Du");
    expect(screen.getByText(/Không khôi phục được bản nháp cũ/)).toBeInTheDocument();
  });

  it("retains restored document choices through load failure and reconciles on retry", async () => {
    writeExamFormDraft("1:5", { payload: createDefaultExamPayload(), calculationCountInput: "2", curriculumEdited: true, selectedDocIds: [8, 99] });
    listDocumentsMock.mockRejectedValueOnce(new Error("Mất kết nối")).mockResolvedValueOnce([sourceDoc(8, 8)]);
    render(<CreateExam />);
    expect(screen.getByRole("button", { name: "Tạo đề kiểm tra" })).toBeDisabled();
    expect(readExamFormDraft("1:5").draft?.data.selectedDocIds).toEqual([8, 99]);
    await screen.findByText("Mất kết nối");
    expect(readExamFormDraft("1:5").draft?.data.selectedDocIds).toEqual([8, 99]);
    fireEvent.click(screen.getByRole("button", { name: "Tải lại tài liệu" }));
    expect(await screen.findByLabelText(/nguon-lop-8.pdf/)).toBeChecked();
    expect(readExamFormDraft("1:5").draft?.data.selectedDocIds).toEqual([8]);
    expect(screen.getByText(/1 tài liệu đã chọn không còn khả dụng/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tạo đề kiểm tra" }));
    await waitFor(() => expect(onGenerateFullExamMock).toHaveBeenCalledWith(expect.objectContaining({ use_uploaded_docs: [8] })));
  });

  it("keeps the form draft after generation and on subsequent reopen", async () => {
    const view = render(<CreateExam />);
    fireEvent.change(screen.getByLabelText("Trường"), { target: { value: "Đề đang tạo" } });
    fireEvent.click(screen.getByRole("button", { name: "Tạo đề kiểm tra" }));
    await waitFor(() => expect(onGenerateFullExamMock).toHaveBeenCalledTimes(1));
    expect(readExamFormDraft("1:5").draft?.data.payload.school).toBe("Đề đang tạo");
    view.unmount();
    render(<CreateExam />);
    expect(screen.getByLabelText("Trường")).toHaveValue("Đề đang tạo");
    expect(onGenerateFullExamMock).toHaveBeenCalledTimes(1);
  });

  it("shows and requests provider configuration for a super admin", async () => {
    authState.role = "super_admin";
    render(<CreateExam />);

    expect(await screen.findByLabelText("Thứ tự API AI")).toBeInTheDocument();
    expect(getAiProvidersMock).toHaveBeenCalledTimes(1);
    expect(getAiModelsMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText("API chính")).toBeInTheDocument();
  });

  it("requires calculation count and points and sends them with the exam", async () => {
    render(<CreateExam />);

    expect(screen.getByLabelText("Số câu tính toán bắt buộc")).toHaveValue(2);
    expect(screen.getByLabelText("Điểm mỗi câu tính toán")).toHaveValue(0.5);
    expect(screen.getByLabelText("Điểm mỗi câu tính toán")).toBeDisabled();
    expect(screen.getByLabelText("Tự động phân bổ điểm theo tỷ lệ mức độ")).toBeChecked();
    expect(screen.getByLabelText("Mức độ câu tính toán 1")).toHaveTextContent("Thông hiểu");
    expect(screen.getByLabelText("Mức độ câu tính toán 2")).toHaveTextContent("Vận dụng");
    expect(screen.getByText("Tự cân về 10 điểm")).toBeInTheDocument();
    expect(screen.getByText(/Tổng 16 câu/)).toBeInTheDocument();
    expect(screen.getByText(/tối thiểu 0,25/)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Mức độ câu tính toán 1"));
    fireEvent.click(screen.getByRole("option", { name: "Nhận biết" }));

    fireEvent.click(screen.getByRole("button", { name: "Tạo đề kiểm tra" }));

    await waitFor(() => expect(onGenerateFullExamMock).toHaveBeenCalledTimes(1));
    expect(onGenerateFullExamMock.mock.calls[0][0]).toMatchObject({
      auto_distribute_scores: true,
      allow_provider_fallback: false,
      calculation_requirement: {
        count: 2,
        score_per_question: 0.5,
        difficulties: ["nhan_biet", "van_dung"],
      },
      question_types: {
        short_answer: { enabled: true, count: 2, score_per_question: 0.5 },
      },
    });
  });

  it("lets calculation count expand short answers and keeps intermediate input editable", async () => {
    render(<CreateExam />);

    const calculationCount = screen.getByLabelText("Số câu tính toán bắt buộc");
    fireEvent.change(calculationCount, { target: { value: "" } });

    expect(calculationCount).toHaveValue(null);
    expect(screen.getByRole("button", { name: "Tạo đề kiểm tra" })).toBeDisabled();

    fireEvent.change(calculationCount, { target: { value: "4" } });

    expect(calculationCount).toHaveValue(4);
    expect(screen.getByLabelText("Số câu Trả lời ngắn")).toHaveValue(4);
    expect(screen.getByText(/Tổng 18 câu/)).toBeInTheDocument();
    expect(screen.getByLabelText("Mức độ câu tính toán 3")).toBeInTheDocument();
    expect(screen.getByLabelText("Mức độ câu tính toán 4")).toBeInTheDocument();
    expect(screen.getByText("Tự cân về 10 điểm")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tạo đề kiểm tra" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Tạo đề kiểm tra" }));
    await waitFor(() => expect(onGenerateFullExamMock).toHaveBeenCalledTimes(1));
    expect(onGenerateFullExamMock.mock.calls[0][0]).toMatchObject({
      auto_distribute_scores: true,
      question_types: {
        short_answer: { enabled: true, count: 4 },
      },
      calculation_requirement: {
        count: 4,
        difficulties: ["thong_hieu", "van_dung", "thong_hieu", "van_dung"],
      },
    });
  });

  it("keeps fixed-score validation when automatic distribution is disabled", () => {
    render(<CreateExam />);

    fireEvent.click(screen.getByLabelText("Tự động phân bổ điểm theo tỷ lệ mức độ"));

    fireEvent.change(screen.getByLabelText("Điểm mỗi câu tính toán"), {
      target: { value: "1" },
    });

    expect(screen.getByText("11/10 điểm")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tạo đề kiểm tra" })).toBeDisabled();
    expect(onGenerateFullExamMock).not.toHaveBeenCalled();
  });

  it("rejects manual scores that are not quarter-point increments", () => {
    render(<CreateExam />);

    fireEvent.click(screen.getByLabelText("Tự động phân bổ điểm theo tỷ lệ mức độ"));
    fireEvent.change(screen.getByLabelText("Điểm mỗi câu Trắc nghiệm nhiều lựa chọn"), {
      target: { value: "0.3" },
    });

    expect(screen.getByText("Điểm mỗi câu/mỗi ý phải từ 0,25 và là bội số của 0,25.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tạo đề kiểm tra" })).toBeDisabled();
  });

  it.each([false, true])("labels a saved draft and retries only stored failures without fallback (failure=%s)", async (fails) => {
    if (fails) onRegenerateQuestionsMock.mockRejectedValueOnce(new Error("Reviewer unavailable"));
    resultState.value = {
      id: 55,
      exam_number: 4,
      publication_status: "draft",
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
      validation: {
        passed: false,
        score: 100,
        checks: [],
        warnings: [],
        errors: [],
        persistence: {
          status: "draft",
          publishable: false,
          question_failures: { q_4: ["learning_objective_copy"] },
        },
      },
      review_status: {},
      variants: [],
    };

    render(
      <MemoryRouter>
        <CreateExam />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Bản nháp chưa qua kiểm định bắt buộc")).toBeInTheDocument();
    expect(screen.getByText("Bản nháp #4")).toBeInTheDocument();
    expect(screen.queryByText("Bản nháp #55")).not.toBeInTheDocument();
    const retry = await screen.findByRole("button", { name: "Tạo lại 1 câu lỗi" });
    fireEvent.click(retry);

    await waitFor(() => {
      expect(onRegenerateQuestionsMock).toHaveBeenCalledWith({
        exam_id: 55,
        question_ids: ["q_4"],
        reason: "Câu cần rõ hơn và bám sát yêu cầu cần đạt",
        allow_provider_fallback: false,
      });
    });
    if (fails) expect(screen.getByRole("button", { name: "Tạo lại 1 câu lỗi" })).toBeEnabled();
  });
});
