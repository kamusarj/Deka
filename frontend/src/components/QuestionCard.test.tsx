import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import QuestionCard from "./QuestionCard";
import type { Answer, Question, RubricItem } from "../types";

const metadata = {
  topic: "Hệ tuần hoàn",
  lesson: "Tim và mạch máu",
  knowledge_unit: "Tim",
  achievement: "Mô tả cấu tạo tim",
  bloom_level: "remember",
};

const multipleChoiceQuestion: Question = {
  id: "q_1",
  number: 1,
  type: "multiple_choice",
  difficulty: "nhan_biet",
  score: 1,
  content: "Tim người có bao nhiêu ngăn?",
  options: { A: "2", B: "3", C: "4", D: "5" },
  metadata,
};

describe("QuestionCard teacher review presentation", () => {
  it.each<Question["type"]>(["multiple_choice", "true_false", "short_answer", "essay"])(
    "keeps %s student content without rendering teacher answers or hints",
    (type) => {
      const question: Question = {
        ...multipleChoiceQuestion,
        type,
        correct_answer: type === "multiple_choice" ? "C" : "SECRET embedded answer",
        statements: [{ id: "s_1_1", content: "Phát biểu cần đánh giá", is_true: true }],
        sub_questions: [{ id: "sub_1", content: "Yêu cầu của ý a", score: 1 }],
        metadata: { ...metadata, is_calculation: true },
        source: {
          source_type: "local_json",
          source_name: "SECRET source",
          confidence_score: 1,
        },
      };
      const answer: Answer = {
        question_id: question.id,
        question_number: question.number,
        type,
        correct_answer: type === "multiple_choice" ? "C" : "SECRET answer key",
        explanation: "SECRET explanation",
        option_explanations: { C: "SECRET option explanation" },
        answers: [{ statement_id: "s_1_1", is_true: true, explanation: "SECRET statement explanation" }],
        model_answer: "SECRET model answer",
        key_points: ["SECRET key point"],
      };
      const rubric: RubricItem = {
        question_id: question.id,
        question_number: question.number,
        type,
        total_score: 1,
        criteria: [],
        grading_guide: ["SECRET grading guide"],
      };
      const props = {
        question, answer, rubric, audience: "student" as const,
        reviewStatus: "accepted" as const, isRegenerated: true, showControls: true,
        onReview: vi.fn(), onToggleSelect: vi.fn(), onSaveToBank: vi.fn(),
      };
      const { container, rerender } = render(<QuestionCard {...props} />);

      function expectStudentContent() {
        expect(screen.getAllByText(question.content).length).toBeGreaterThan(0);
        expect(screen.getAllByText("1 điểm").length).toBeGreaterThan(0);
        expect(container.textContent).not.toMatch(/SECRET|Đáp án đúng|Lời giải|Hướng dẫn|Thang điểm|Ý chính|Minh chứng|Nhận biết|Hệ tuần hoàn|Có tính toán|Đã duyệt|Câu vừa tạo lại/);
        expect(container.querySelector(".is-correct, .truth-state, .question-review-bar, .status-accepted")).toBeNull();
        if (type === "multiple_choice") {
          for (const option of Object.values(question.options!)) {
            expect(screen.getByText(option)).toBeInTheDocument();
          }
        }
        if (type === "true_false") expect(screen.getByText("Phát biểu cần đánh giá")).toBeInTheDocument();
        if (type === "essay") expect(screen.getByText("Yêu cầu của ý a")).toBeInTheDocument();
      }
      expectStudentContent();
      // Removing the separate key must not expose answers embedded in the question.
      rerender(<QuestionCard {...props} answer={undefined} />);
      expectStudentContent();
    },
  );

  it("provides an informative collapsed summary and accessible expansion", () => {
    render(<QuestionCard question={multipleChoiceQuestion} defaultExpanded={false} />);

    const toggle = screen.getByRole("button", { name: /Câu 1.*Trắc nghiệm.*Tim người/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Nhận biết")).toBeInTheDocument();
    expect(screen.getByText("Hệ tuần hoàn")).toBeInTheDocument();
    expect(screen.getByText("1 điểm")).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("highlights the multiple-choice answer and explanation", () => {
    const answer: Answer = {
      question_id: "q_1",
      question_number: 1,
      type: "multiple_choice",
      correct_answer: "C",
      explanation: "Tim người có bốn ngăn.",
    };
    render(<QuestionCard question={multipleChoiceQuestion} answer={answer} />);

    expect(screen.getByText("Đáp án đúng")).toBeInTheDocument();
    expect(screen.getByText("4").closest(".question-option")).toHaveClass("is-correct");
    expect(screen.getByText("Lời giải chi tiết")).toBeInTheDocument();
    expect(screen.getByText("Tim người có bốn ngăn.")).toBeInTheDocument();
  });

  it("shows option analysis and exact document evidence without flattening it into prose", () => {
    const question: Question = {
      ...multipleChoiceQuestion,
      source: {
        source_type: "rag_retrieval",
        source_name: "SGK Sinh học 10.pdf",
        source_page: 12,
        source_section: "Bài 3 · Tế bào",
        source_excerpt: "Tế bào là đơn vị cấu trúc cơ bản của cơ thể sống.",
        confidence_score: 0.91,
      },
    };
    const answer: Answer = {
      question_id: "q_1",
      question_number: 1,
      type: "multiple_choice",
      correct_answer: "C",
      explanation: "Kết luận: chọn C vì tim người có bốn ngăn.",
      option_explanations: {
        A: "Không chọn vì thiếu hai ngăn.",
        B: "Không chọn vì thiếu một ngăn.",
        C: "Đúng theo cấu tạo tim người.",
        D: "Không chọn vì thừa một ngăn.",
      },
      citations: [{
        source_type: "rag_retrieval",
        source_name: "SGK Sinh học 10.pdf",
        source_page: 12,
        source_section: "Bài 3 · Tế bào",
        excerpt: "Tế bào là đơn vị cấu trúc cơ bản của cơ thể sống.",
        retrieved_chunk_id: "doc_7_4",
        verification_status: "verified",
        verification_reason: "Đoạn trích khớp chunk đã truy xuất.",
        verified_against: "retrieved_chunk",
      }],
    };

    render(<QuestionCard question={question} answer={answer} />);

    expect(screen.getByText("Phân tích từng phương án")).toBeInTheDocument();
    expect(screen.getByText("SGK Sinh học 10.pdf")).toBeInTheDocument();
    expect(screen.getByText("Trang 12")).toBeInTheDocument();
    expect(screen.getByText("Bài 3 · Tế bào")).toBeInTheDocument();
    expect(screen.getByText("Đoạn tham chiếu doc_7_4")).toBeInTheDocument();
    expect(screen.getByText("Tế bào là đơn vị cấu trúc cơ bản của cơ thể sống.")).toBeInTheDocument();
    expect(screen.getByText("Đã kiểm chứng")).toBeInTheDocument();
  });

  it("does not present an unverified historical excerpt as a quotation", () => {
    const question: Question = {
      ...multipleChoiceQuestion,
      source: {
        source_type: "local_json",
        source_name: "Dữ liệu đề cũ",
        source_excerpt: "Nội dung chưa thể đối chiếu.",
        confidence_score: 1,
      },
    };

    render(<QuestionCard question={question} />);

    expect(screen.getByText("Chưa kiểm chứng")).toBeInTheDocument();
    expect(screen.queryByText("Nội dung chưa thể đối chiếu.")).not.toBeInTheDocument();
    expect(screen.getByText(/không còn ngữ cảnh nguồn/)).toBeInTheDocument();
  });

  it("clearly warns when server-side citation verification rejects evidence", () => {
    const answer: Answer = {
      question_id: "q_1",
      question_number: 1,
      type: "multiple_choice",
      citations: [{
        source_type: "rag_retrieval",
        source_name: "SGK Sinh học 10.pdf",
        excerpt: "Nội dung sai khác.",
        verification_status: "rejected",
        verification_reason: "Đoạn trích không khớp chunk tài liệu đã truy xuất.",
      }],
    };

    render(<QuestionCard question={multipleChoiceQuestion} answer={answer} />);

    expect(screen.getByText("Không đạt kiểm chứng")).toBeInTheDocument();
    expect(screen.queryByText("Nội dung sai khác.")).not.toBeInTheDocument();
    expect(screen.getByText(/không khớp chunk tài liệu/)).toBeInTheDocument();
  });

  it("labels missing historical provenance instead of inventing a citation", () => {
    render(<QuestionCard question={multipleChoiceQuestion} />);

    expect(screen.getByText("Chưa có dữ liệu")).toBeInTheDocument();
    expect(screen.getByText(/Không có trích dẫn nào được tự suy đoán/)).toBeInTheDocument();
  });

  it("keeps all true-false statements inside one parent question", () => {
    const question: Question = {
      ...multipleChoiceQuestion,
      id: "q_2",
      number: 2,
      type: "true_false",
      content: "Đọc thông tin và xác định tính đúng sai của các phát biểu.",
      options: undefined,
      statements: [
        { id: "s_a", content: "Máu vận chuyển oxygen.", is_true: true },
        { id: "s_b", content: "Tim người có hai ngăn.", is_true: false },
        { id: "s_c", content: "Động mạch đưa máu rời tim.", is_true: true },
        { id: "s_d", content: "Tĩnh mạch luôn mang máu giàu oxygen.", is_true: false },
      ],
    };
    const answer: Answer = {
      question_id: "q_2",
      question_number: 2,
      type: "true_false",
      answers: question.statements?.map((statement) => ({
        statement_id: statement.id,
        is_true: statement.is_true,
        explanation: `Giải thích ${statement.id}`,
      })),
    };
    const { container } = render(<QuestionCard question={question} answer={answer} />);

    expect(container.querySelectorAll("article.question-card")).toHaveLength(1);
    expect(container.querySelectorAll(".question-statement")).toHaveLength(4);
    expect(screen.getAllByText("Đúng")).toHaveLength(2);
    expect(screen.getAllByText("Sai")).toHaveLength(2);
    expect(screen.getByText("Giải thích s_a")).toBeInTheDocument();
  });

  it("renders a short answer without fake choices", () => {
    const question: Question = {
      ...multipleChoiceQuestion,
      id: "q_3",
      number: 3,
      type: "short_answer",
      content: "Tính giá trị của biểu thức.",
      options: undefined,
    };
    const answer: Answer = {
      question_id: "q_3",
      question_number: 3,
      type: "short_answer",
      correct_answer: "12,5",
      explanation: "Thay số và rút gọn biểu thức.",
    };
    const { container } = render(<QuestionCard question={question} answer={answer} />);

    expect(screen.getByText("Đáp án")).toBeInTheDocument();
    expect(screen.getByText("12,5")).toBeInTheDocument();
    expect(container.querySelector(".question-options")).not.toBeInTheDocument();
  });

  it("renders essay guidance, key points, and rubric when present", () => {
    const question: Question = {
      ...multipleChoiceQuestion,
      id: "q_4",
      number: 4,
      type: "essay",
      content: "Phân tích vai trò của hệ tuần hoàn.",
      options: undefined,
      sub_questions: [{ id: "q_4_a", content: "Nêu hai vai trò.", score: 1 }],
    };
    const answer: Answer = {
      question_id: "q_4",
      question_number: 4,
      type: "essay",
      model_answer: "Hệ tuần hoàn vận chuyển các chất.",
      key_points: ["Vận chuyển oxygen", "Vận chuyển chất dinh dưỡng"],
    };
    const rubric: RubricItem = {
      question_id: "q_4",
      question_number: 4,
      type: "essay",
      total_score: 2,
      criteria: [{
        id: "c_1",
        name: "Nội dung",
        max_score: 2,
        levels: [{ score: 2, description: "Đầy đủ", criteria: "Đủ ý" }],
      }],
      grading_guide: ["Chấm theo ý đúng."],
    };
    render(<QuestionCard question={question} answer={answer} rubric={rubric} />);

    expect(screen.getByText("Nêu hai vai trò.")).toBeInTheDocument();
    expect(screen.getByText("Đáp án / Hướng dẫn trả lời")).toBeInTheDocument();
    expect(screen.getByText("Ý chính cần có")).toBeInTheDocument();
    expect(screen.getByText("Thang điểm")).toBeInTheDocument();
    expect(screen.getByText("Chấm theo ý đúng.")).toBeInTheDocument();
  });

  it("preserves stable finding targets and every backend review decision", () => {
    const onReview = vi.fn();
    const { container } = render(
      <QuestionCard question={multipleChoiceQuestion} onReview={onReview} showControls />,
    );

    expect(container.querySelector("#question-q_1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Chấp nhận" }));
    fireEvent.click(screen.getByRole("button", { name: "Yêu cầu sửa" }));
    fireEvent.click(screen.getByRole("button", { name: "Từ chối" }));

    expect(onReview.mock.calls).toEqual([
      ["q_1", "accepted"],
      ["q_1", "needs_revision"],
      ["q_1", "rejected"],
    ]);
  });

  it("preserves regeneration selection and question-bank actions", () => {
    const onToggleSelect = vi.fn();
    const onSaveToBank = vi.fn();
    render(
      <QuestionCard
        question={multipleChoiceQuestion}
        isSelected={false}
        onToggleSelect={onToggleSelect}
        onSaveToBank={onSaveToBank}
        showControls
      />,
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "Chọn tạo lại" }));
    fireEvent.click(screen.getByRole("button", { name: "Lưu vào ngân hàng" }));

    expect(onToggleSelect).toHaveBeenCalledWith("q_1");
    expect(onSaveToBank).toHaveBeenCalledWith("q_1");
  });
});
