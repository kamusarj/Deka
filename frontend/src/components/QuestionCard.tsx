import { useState } from "react";
import QuestionEditor from "./QuestionEditor";
import RichContent, { MathText } from "./RichContent";
import type { QuestionEditPayload } from "./QuestionEditor";
import type { Answer, AnswerCitation, Question, ReviewStatus, RubricItem } from "../types";
import { formatDifficulty, formatQuestionType, formatReviewStatus } from "../utils/labels";

interface QuestionCardProps {
  examId?: number | null;
  version?: number;
  onEdit?: (questionId: string, payload: QuestionEditPayload) => Promise<unknown>;
  question: Question;
  audience?: "student" | "teacher";
  answer?: Answer;
  rubric?: RubricItem;
  reviewStatus?: ReviewStatus;
  isRegenerated?: boolean;
  isSelected?: boolean;
  onToggleSelect?: (questionId: string) => void;
  onReview?: (
    questionId: string,
    status: Exclude<ReviewStatus, "pending">,
  ) => void;
  onSaveToBank?: (questionId: string) => void;
  showControls?: boolean;
  defaultExpanded?: boolean;
  defaultSourceName?: string;
}

function normalizedSourceName(name: string, defaultSourceName?: string) {
  if (defaultSourceName && ["Local curriculum seed data", "Bộ dữ liệu MVP"].includes(name)) {
    return defaultSourceName;
  }
  return name;
}

function sourceEvidence(
  question: Question,
  answer?: Answer,
  defaultSourceName?: string,
): AnswerCitation | null {
  const citation = answer?.citations?.[0];
  if (citation) {
    return {
      ...citation,
      source_name: normalizedSourceName(citation.source_name, defaultSourceName),
    };
  }
  if (!question.source?.source_name) return null;
  return {
    source_type: question.source.source_type,
    source_name: normalizedSourceName(question.source.source_name, defaultSourceName),
    source_page: question.source.source_page,
    source_section: question.source.source_section
      ?? (question.metadata?.topic ? `Chủ đề: ${question.metadata.topic} · Yêu cầu cần đạt` : null),
    excerpt: question.source.source_excerpt ?? question.metadata?.achievement ?? null,
    doc_id: question.source.doc_id,
    retrieved_chunk_id: question.source.retrieved_chunk_id,
    verification_status: "unverified",
    verification_reason: "Bản ghi cũ không còn ngữ cảnh nguồn do hệ thống lưu để đối chiếu.",
  };
}

function SourceEvidence({
  question,
  answer,
  defaultSourceName,
}: {
  question: Question;
  answer?: Answer;
  defaultSourceName?: string;
}) {
  const citation = sourceEvidence(question, answer, defaultSourceName);
  if (!citation) {
    return (
      <aside className="question-evidence is-missing" aria-label="Tình trạng minh chứng nguồn">
        <div className="question-evidence-head">
          <h4>Minh chứng nguồn</h4>
          <span>Chưa có dữ liệu</span>
        </div>
        <p>Đề này chưa lưu nguồn và đoạn trích để đối chiếu. Không có trích dẫn nào được tự suy đoán.</p>
      </aside>
    );
  }

  const verificationStatus = citation.verification_status ?? "unverified";
  const statusLabel = verificationStatus === "verified"
    ? "Đã kiểm chứng"
    : verificationStatus === "rejected"
      ? "Không đạt kiểm chứng"
      : "Chưa kiểm chứng";

  return (
    <aside
      className={`question-evidence is-${verificationStatus}`}
      aria-label="Minh chứng nguồn"
    >
      <div className="question-evidence-head">
        <h4>Minh chứng nguồn</h4>
        <span>{statusLabel}</span>
      </div>
      <strong className="question-evidence-document">{citation.source_name}</strong>
      <div className="question-evidence-locators">
        {citation.source_page != null && <span>Trang {citation.source_page}</span>}
        {citation.source_section && <span>{citation.source_section}</span>}
        {citation.retrieved_chunk_id && (
          <span>Đoạn tham chiếu {citation.retrieved_chunk_id}</span>
        )}
      </div>
      {verificationStatus === "verified" && citation.excerpt ? (
        <blockquote>{citation.excerpt}</blockquote>
      ) : (
        <p className="question-evidence-warning">
          {citation.verification_reason
            ?? "Nguồn chưa có đủ dữ liệu để kiểm chứng; hệ thống không hiển thị nội dung như một trích dẫn đã xác thực."}
        </p>
      )}
    </aside>
  );
}

function MultipleChoiceQuestion({ question, answer, showAnswers }: { question: Question; answer?: Answer; showAnswers: boolean }) {
  if (!question.options) return null;
  const correctAnswer = (answer?.correct_answer ?? question.correct_answer ?? "")
    .trim()
    .replace(/[.)]/g, "")
    .toUpperCase();

  return (
    <div className="question-options" aria-label="Các phương án trả lời">
      {Object.entries(question.options).map(([key, value]) => {
        const isCorrect = showAnswers && Boolean(correctAnswer) && key.toUpperCase() === correctAnswer;
        return (
          <div className={`question-option ${isCorrect ? "is-correct" : ""}`} key={key}>
            <span className="question-option-key">{key}</span>
            <span><MathText text={value} /></span>
            {isCorrect && <span className="answer-state">Đáp án đúng</span>}
          </div>
        );
      })}
    </div>
  );
}

function TrueFalseQuestion({ question, answer, showAnswers }: { question: Question; answer?: Answer; showAnswers: boolean }) {
  if (!question.statements?.length) return null;

  return (
    <div className="question-statements" aria-label="Các phát biểu đúng sai">
      {question.statements.map((statement, index) => {
        const statementAnswer = answer?.answers?.find(
          (item) => item.statement_id === statement.id,
        );
        const isTrue = statementAnswer?.is_true ?? statement.is_true;
        return (
          <div className="question-statement" key={statement.id}>
            <div className="question-statement-row">
              <span className="question-statement-key">
                {String.fromCharCode(97 + index)}
              </span>
              <span className="question-statement-text"><MathText text={statement.content} /></span>
              {showAnswers && <span className={`truth-state ${isTrue ? "is-true" : "is-false"}`}>
                {isTrue ? "Đúng" : "Sai"}
              </span>}
            </div>
            {showAnswers && statementAnswer?.explanation && (
              <p className="statement-explanation"><MathText text={statementAnswer.explanation} /></p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ShortAnswerQuestion({ question, answer }: { question: Question; answer?: Answer }) {
  const expectedAnswer = answer?.correct_answer ?? question.correct_answer;
  return (
    <>
      {expectedAnswer && (
        <div className="question-answer-panel">
          <span className="question-answer-label">Đáp án</span>
          <strong><MathText text={expectedAnswer} /></strong>
        </div>
      )}
      {answer?.explanation && (
        <div className="question-solution">
          <h4>Lời giải chi tiết</h4>
          <p><MathText text={answer.explanation} /></p>
        </div>
      )}
    </>
  );
}

function EssayQuestion({
  question,
  answer,
  rubric,
}: {
  question: Question;
  answer?: Answer;
  rubric?: RubricItem;
}) {
  return (
    <>
      {question.sub_questions && question.sub_questions.length > 0 && (
        <div className="essay-subquestions">
          {question.sub_questions.map((subQuestion, index) => (
            <div className="essay-subquestion" key={subQuestion.id}>
              <span>{String.fromCharCode(97 + index)})</span>
              <p><MathText text={subQuestion.content} /></p>
              <strong>{subQuestion.score} điểm</strong>
            </div>
          ))}
        </div>
      )}
      {answer?.model_answer && (
        <div className="question-solution">
          <h4>Đáp án / Hướng dẫn trả lời</h4>
          <p><MathText text={answer.model_answer} /></p>
        </div>
      )}
      {answer?.key_points && answer.key_points.length > 0 && (
        <div className="essay-key-points">
          <h4>Ý chính cần có</h4>
          <ul>
            {answer.key_points.map((point, index) => <li key={index}>{point}</li>)}
          </ul>
        </div>
      )}
      {rubric && (
        <div className="question-rubric">
          <div className="question-rubric-head">
            <h4>Thang điểm</h4>
            <span>{rubric.total_score} điểm</span>
          </div>
          {rubric.criteria.map((criterion) => (
            <div className="question-rubric-criterion" key={criterion.id}>
              <strong>{criterion.name} · tối đa {criterion.max_score} điểm</strong>
              <ul>
                {criterion.levels.map((level, index) => (
                  <li key={index}>
                    <b>{level.score}đ</b> — <MathText text={level.description} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {rubric.grading_guide.length > 0 && (
            <div className="question-grading-guide">
              <strong>Hướng dẫn chấm</strong>
              <ul>
                {rubric.grading_guide.map((guide, index) => <li key={index}>{guide}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function QuestionContent({
  question,
  answer,
  rubric,
  defaultSourceName,
  showAnswers,
}: {
  question: Question;
  answer?: Answer;
  rubric?: RubricItem;
  defaultSourceName?: string;
  showAnswers: boolean;
}) {
  return (
    <>
      <p className="question-prompt"><MathText text={question.content} /></p>
      <RichContent blocks={question.rich_content} />
      {question.type === "multiple_choice" && (
        <MultipleChoiceQuestion question={question} answer={answer} showAnswers={showAnswers} />
      )}
      {question.type === "true_false" && (
        <TrueFalseQuestion question={question} answer={answer} showAnswers={showAnswers} />
      )}
      {showAnswers && question.type === "short_answer" && (
        <ShortAnswerQuestion question={question} answer={answer} />
      )}
      {question.type === "essay" && (
        <EssayQuestion question={question} answer={showAnswers ? answer : undefined} rubric={showAnswers ? rubric : undefined} />
      )}
      {showAnswers && question.type === "multiple_choice" && answer?.explanation && (
        <div className="question-solution">
          <h4>Lời giải chi tiết</h4>
          <p><MathText text={answer.explanation} /></p>
          {answer.option_explanations && (
            <div className="question-option-analysis">
              <h5>Phân tích từng phương án</h5>
              <ul>
                {Object.entries(answer.option_explanations).map(([label, explanation]) => (
                  <li key={label}>
                    <strong>{label}</strong>
                    <span><MathText text={explanation} /></span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {showAnswers && <SourceEvidence
        question={question}
        answer={answer}
        defaultSourceName={defaultSourceName}
      />}
    </>
  );
}

export default function QuestionCard({
  question,
  audience = "teacher",
  answer,
  rubric,
  reviewStatus,
  isRegenerated,
  isSelected,
  onToggleSelect,
  onReview,
  onSaveToBank,
  showControls = false,
  defaultExpanded = true,
  defaultSourceName,
  version = 1,
  examId,
  onEdit,
}: QuestionCardProps) {
  const [editing, setEditing] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);
  const showAnswers = audience === "teacher";
  const statusClass = showAnswers && reviewStatus ? `status-${reviewStatus.replace("needs_revision", "revision")}` : "";
  const cardId = question.original_id ?? question.id;

  return (
    <article
      id={`question-${cardId}`}
      className={`question-card ${statusClass} ${showAnswers && isRegenerated ? "new-question" : ""} ${expanded ? "is-expanded" : ""}`}
    >
      <div className="question-card-header">
        <button
          type="button"
          className="question-card-toggle"
          aria-expanded={expanded}
          aria-controls={`question-content-${question.id}`}
          onClick={() => setExpanded((current) => !current)}
        >
          <span className="question-card-heading">
            <strong className="question-number">Câu {question.number}</strong>
            <span className={`question-type-badge type-${question.type}`}>
              {formatQuestionType(question.type)}
            </span>
            {showAnswers && question.metadata?.is_calculation && (
              <span className="question-type-badge type-calculation">Có tính toán</span>
            )}
            {showAnswers && reviewStatus && (
              <span className={`review-status-badge review-${reviewStatus}`}>
                {formatReviewStatus(reviewStatus)}
              </span>
            )}
            {showAnswers && isRegenerated && <span className="regenerated-tag">Câu vừa tạo lại</span>}
          </span>
          <span className="question-preview">{question.content}</span>
          <svg className="question-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <div className="question-card-meta" aria-label="Thông tin câu hỏi">
          {showAnswers && <span>{formatDifficulty(question.difficulty)}</span>}
          {showAnswers && question.metadata?.topic && <span>{question.metadata.topic}</span>}
          <strong>{question.score} điểm</strong>
        </div>
      </div>

      <div
        id={`question-content-${question.id}`}
        className="question-card-panel"
        aria-hidden={!expanded}
      >
        <div className="question-card-panel-inner">
          <div className="question-body">
            {editing && onEdit ? <QuestionEditor examId={examId} question={question} answer={answer} rubric={rubric} version={version}
              onSave={(payload) => onEdit(question.id, payload)} onCancel={() => setEditing(false)} /> : <QuestionContent
              question={question}
              answer={answer}
              rubric={rubric}
              defaultSourceName={defaultSourceName}
              showAnswers={showAnswers}
            />}
          </div>
        </div>
      </div>

      {showAnswers && showControls && !editing && (onToggleSelect || onReview || onSaveToBank || onEdit) && (
        <div className="question-review-bar" aria-label={`Thao tác cho câu ${question.number}`}>
          {onToggleSelect && (
            <label className="question-select-action">
              <input
                type="checkbox"
                checked={isSelected ?? false}
                onChange={() => onToggleSelect(question.id)}
              />
              Chọn tạo lại
            </label>
          )}
          <div className="question-review-actions">
            {onEdit && <button type="button" className="secondary compact" onClick={() => { setExpanded(true); setEditing(true); }}>Chỉnh sửa</button>}
            {onReview && (
              <button
                type="button"
                className="secondary compact review-action-accept"
                onClick={() => onReview(question.id, "accepted")}
                disabled={reviewStatus === "accepted"}
                aria-pressed={reviewStatus === "accepted"}
              >
                {reviewStatus === "accepted" ? "✓ Đã duyệt" : "Chấp nhận"}
              </button>
            )}
            {onReview && (
              <button
                type="button"
                className="secondary compact"
                onClick={() => onReview(question.id, "needs_revision")}
                disabled={reviewStatus === "needs_revision"}
                aria-pressed={reviewStatus === "needs_revision"}
              >
                {reviewStatus === "needs_revision" ? "✓ Cần sửa" : "Yêu cầu sửa"}
              </button>
            )}
            {onReview && (
              <button
                type="button"
                className="secondary compact btn-danger"
                onClick={() => onReview(question.id, "rejected")}
                disabled={reviewStatus === "rejected"}
                aria-pressed={reviewStatus === "rejected"}
              >
                {reviewStatus === "rejected" ? "✓ Đã từ chối" : "Từ chối"}
              </button>
            )}
            {onSaveToBank && (
              <button
                type="button"
                className="ghost-btn compact"
                onClick={() => onSaveToBank(question.id)}
              >
                Lưu vào ngân hàng
              </button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
