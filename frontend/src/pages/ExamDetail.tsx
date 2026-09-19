import { useContext, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { useExam } from "../hooks/useExam";
import DuplicateFindings from "../components/DuplicateFindings";
import {
  LoadingSpinner,
  MatrixTable,
  QualityFindings,
  QuestionCard,
  QUESTION_TYPE_SECTIONS,
  QuestionTypeTabs,
  SelectControl,
} from "../components";
import type { QuestionTypeFilter } from "../components";
import { useToast } from "../contexts/useToast";
import { formatDifficulty, formatQuestionType } from "../utils/labels";
import type { ExportDocument, FullExamResponse } from "../types";
import { AuthContext } from "../contexts/authContextValue";
import { canWriteContent, isSuperAdminRole } from "../auth/rolePolicy";

export default function ExamDetail() {
  const { id } = useParams<{ id: string }>();
  return <ExamWorkspace key={id} id={id} />;
}

function ExamWorkspace({ id }: { id: string | undefined }) {
  const user = useContext(AuthContext)?.user ?? { id: -1, role: "teacher" };
  const navigate = useNavigate();
  const {
    loading,
    error,
    onLoadExam,
    onExportDocx,
    onExportPdf,
    onDeleteExam,
    onDuplicateExam,
    onRegenerateQuestions,
    onReviewQuestion,
    onEditQuestion,
    onSaveQuestionsToBank,
  } = useExam();
  const [exam, setExam] = useState<FullExamResponse | null>(null);
  const [exporting, setExporting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [selectedVariantCode, setSelectedVariantCode] = useState("");
  const [questionTypeFilter, setQuestionTypeFilter] = useState<QuestionTypeFilter>("all");
  const [audience, setAudience] = useState<"student" | "teacher">("teacher");
  const isTeacherView = audience === "teacher";
  const [previewDocument, setPreviewDocument] = useState<"exam" | "matrix" | "specification">("exam");
  const visibleDocument = isTeacherView ? previewDocument : "exam";
  const [exportDocument, setExportDocument] = useState<ExportDocument>("exam");
  const { notify } = useToast();

  const variants = useMemo(() => exam?.variants ?? [], [exam?.variants]);
  const selectedVariant = useMemo(
    () => variants.find((variant) => variant.code === selectedVariantCode),
    [selectedVariantCode, variants],
  );
  const displayedQuestions = useMemo(
    () => selectedVariant?.questions ?? exam?.questions ?? [],
    [exam?.questions, selectedVariant],
  );
  const displayedSpecification = useMemo(() => {
    const specification = exam?.specification ?? [];
    if (!selectedVariant) return specification;
    const numbers = new Map(selectedVariant.questions.map((question) => [question.original_id, question.number]));
    return specification.map((item) => ({
      ...item,
      question_number: numbers.get(item.question_id) ?? item.question_number,
    })).sort((left, right) => left.question_number - right.question_number);
  }, [exam?.specification, selectedVariant]);
  const displayedAnswers = useMemo(
    () => selectedVariant?.answer_key ?? exam?.answer_key ?? [],
    [exam?.answer_key, selectedVariant],
  );
  const answerByQuestionId = useMemo(
    () => new Map(displayedAnswers.map((answer) => [answer.question_id, answer])),
    [displayedAnswers],
  );
  const rubricByQuestionId = useMemo(
    () => new Map((exam?.rubric ?? []).map((rubric) => [rubric.question_id, rubric])),
    [exam?.rubric],
  );
  const visibleSections = useMemo(
    () => QUESTION_TYPE_SECTIONS
      .filter((section) => questionTypeFilter === "all" || section.type === questionTypeFilter)
      .map((section) => ({
        ...section,
        questions: displayedQuestions.filter((question) => question.type === section.type),
      }))
      .filter((section) => section.questions.length > 0),
    [displayedQuestions, questionTypeFilter],
  );
  const acceptedCount = useMemo(
    () => Object.values(exam?.review_status ?? {}).filter((review) => review.status === "accepted").length,
    [exam?.review_status],
  );
  const defaultSourceName = exam?.resource_package?.raw_data?.curriculum_file;
  const isDraft = exam?.publication_status === "draft";
  const failedQuestionIds = useMemo(
    () => Object.keys(exam?.validation?.persistence?.question_failures ?? {}),
    [exam?.validation?.persistence?.question_failures],
  );

  useEffect(() => {
    if (!id) return;
    let active = true;
    onLoadExam(Number(id)).then(data => { if (active) setExam(data); }).catch(() => {});
    return () => { active = false; };
  }, [id, onLoadExam]);

  // ExamWorkspace is keyed by the route id, so its initial state already resets
  // for another exam. A post-load reset can erase a tab the user just selected.
  useEffect(() => {
    if (
      questionTypeFilter !== "all" &&
      !displayedQuestions.some((question) => question.type === questionTypeFilter)
    ) {
      setQuestionTypeFilter("all");
    }
  }, [displayedQuestions, questionTypeFilter]);

  function downloadBlob(blob: Blob, filename: string) {
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(url);
  }

  async function handleExport(format: "docx" | "pdf") {
    if (!exam?.id) return;
    setExporting(true);
    try {
      const document = isTeacherView ? exportDocument : "exam";
      const options = { document, variant_code: selectedVariantCode || undefined };
      const blob = format === "pdf"
        ? await onExportPdf(exam.id, audience, options)
        : await onExportDocx(exam.id, audience, options);
      downloadBlob(blob, `smart-exam-${exam.id}-${document}-${selectedVariantCode || "original"}.${format}`);
      notify(`Đã xuất file ${format.toUpperCase()}`, "success");
    } catch {
      notify(`Không xuất được file ${format.toUpperCase()}`, "error");
    } finally {
      setExporting(false);
    }
  }

  async function handleDuplicate() {
    if (!exam?.id) return;
    setBusy(true);
    try {
      const duplicated = await onDuplicateExam(exam.id);
      if (duplicated?.id) {
        notify(`Đã nhân bản thành đề #${duplicated.id}`, "success");
        navigate(`/exams/${duplicated.id}`);
      }
    } catch {
      notify("Không nhân bản được đề", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!exam?.id) return;
    if (!window.confirm("Xóa đề kiểm tra này? Hành động không thể hoàn tác.")) return;
    setBusy(true);
    try {
      await onDeleteExam(exam.id);
      notify("Đã xóa đề kiểm tra", "success");
      navigate("/exams");
    } catch {
      notify("Không xóa được đề", "error");
      setBusy(false);
    }
  }

  async function handleSaveAccepted() {
    if (!exam?.id || isDraft) return;
    setBusy(true);
    setNotice("");
    try {
      const saved = await onSaveQuestionsToBank(exam.id, []);
      const count = saved.count;
      setNotice(`Đã lưu ${count} câu đã duyệt vào ngân hàng. ${saved.warning}`);
      notify(`Đã lưu ${count} câu vào ngân hàng`, "success");
    } catch {
      notify("Không lưu được câu hỏi vào ngân hàng", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleRepairDraft() {
    if (!exam?.id || !isDraft || failedQuestionIds.length === 0) return;
    setBusy(true);
    try {
      await onRegenerateQuestions({
        exam_id: exam.id,
        question_ids: failedQuestionIds,
        reason: "Sửa các lỗi kiểm định đã lưu trong bản nháp",
        allow_provider_fallback: false,
      });
      const updated = await onLoadExam(exam.id);
      setExam(updated);
      notify(
        updated.publication_status === "verified"
          ? "Bản nháp đã qua kiểm định"
          : "Đã lưu lần sửa; bản nháp vẫn còn câu lỗi",
        updated.publication_status === "verified" ? "success" : "info",
      );
    } catch {
      notify("Không tạo lại được các câu lỗi", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleReviewQuestion(
    questionId: string,
    status: "accepted" | "needs_revision" | "rejected",
  ) {
    if (!exam?.id) return;
    try {
      const updated = await onReviewQuestion(exam.id, questionId, status);
      setExam(updated);
      notify("Đã cập nhật trạng thái câu hỏi", "success");
    } catch {
      notify("Không cập nhật được trạng thái câu hỏi", "error");
    }
  }

  if (loading) return <LoadingSpinner message="Đang tải đề..." />;
  if (error && !exam) return <p className="error">{error}</p>;
  if (!exam) {
    return (
      <div className="empty-state">
        <h3>Không tìm thấy đề kiểm tra</h3>
      </div>
    );
  }

  const canWrite = canWriteContent(user?.role);
  const canMutateExam = isSuperAdminRole(user?.role) || (canWrite && exam.owner_user_id === user?.id);

  return (
    <section className="content-page detail exam-review-page">
      {error && (
        <div className="error-box" role="alert">
          <p className="error">{error}</p>
        </div>
      )}

      <header className="exam-review-header">
        <div className="exam-review-title">
          <span className="exam-review-eyebrow">
            {isDraft ? "Bản nháp" : "Đề kiểm tra"}{exam.exam_number != null ? ` #${exam.exam_number}` : ""}
          </span>
          <h1>{exam.exam_info.exam_type}</h1>
          <p>{exam.exam_info.school}</p>
          <div className="exam-review-meta" aria-label="Thông tin đề kiểm tra">
            <span><b>Môn</b> {exam.exam_info.subject}</span>
            <span><b>Khối</b> {exam.exam_info.grade}</span>
            <span><b>Thời gian</b> {exam.exam_info.duration_minutes} phút</span>
            <span><b>Số câu</b> {displayedQuestions.length}</span>
            <span><b>Tổng điểm</b> {exam.summary.total_score ?? exam.exam_info.total_score}</span>
            <span><b>Năm học</b> {exam.exam_info.school_year}</span>
            {isTeacherView && !selectedVariant && displayedQuestions.length > 0 && (
              <span className="exam-review-progress"><b>Đã duyệt</b> {acceptedCount}/{displayedQuestions.length}</span>
            )}
          </div>
        </div>

        <div className="exam-review-actions">
          <label className="exam-export-select">
            Chế độ xem và xuất
            <SelectControl
              ariaLabel="Chọn chế độ xem và xuất"
              value={audience}
              onChange={(value) => setAudience(value as "student" | "teacher")}
              options={[
                { value: "student", label: "Học sinh · không đáp án" },
                { value: "teacher", label: "Giáo viên · đủ đáp án" },
              ]}
            />
          </label>
          {isTeacherView && <label className="exam-export-select">
            Tài liệu tải xuống
            <SelectControl
              ariaLabel="Chọn tài liệu tải xuống"
              value={exportDocument}
              onChange={(value) => setExportDocument(value as ExportDocument)}
              options={[
                { value: "exam", label: "Đề kiểm tra · chỉ câu hỏi" },
                { value: "answers", label: "Đáp án và hướng dẫn chấm" },
                { value: "matrix", label: "Ma trận đề" },
                { value: "specification", label: "Bản đặc tả" },
              ]}
            />
          </label>}
          <small>Bản tải: {selectedVariantCode ? `Mã đề ${selectedVariantCode}` : "Bản gốc"}</small>
          <div className="exam-action-row">
            <button type="button" onClick={() => handleExport("docx")} disabled={exporting || isDraft}>
              {exporting ? "Đang xuất..." : "Tải Word"}
            </button>
            <button type="button" className="secondary" onClick={() => handleExport("pdf")} disabled={exporting || isDraft}>
              Tải PDF
            </button>
            {isTeacherView && canWrite && (
              <button type="button" className="secondary" onClick={handleSaveAccepted} disabled={busy || isDraft}>
                Lưu câu đã duyệt
              </button>
            )}
            {isTeacherView && canMutateExam && isDraft && failedQuestionIds.length > 0 && (
              <button type="button" onClick={handleRepairDraft} disabled={busy}>
                Tạo lại {failedQuestionIds.length} câu lỗi
              </button>
            )}
            {isTeacherView && canWrite && (
              <button type="button" className="ghost-btn" onClick={handleDuplicate} disabled={busy}>
                Nhân bản
              </button>
            )}
            {isTeacherView && canMutateExam && (
              <button type="button" className="ghost-btn danger-text" onClick={handleDelete} disabled={busy}>
                Xóa đề
              </button>
            )}
          </div>
        </div>
      </header>

      {isDraft && (
        <div className="error-box" role="status">
          <strong>Bản nháp chưa qua kiểm định bắt buộc</strong>
          <p>
            Nội dung AI thật đã được lưu để không mất kết quả. Bản này chưa thể
            xuất hoặc đưa câu hỏi vào ngân hàng.
          </p>
        </div>
      )}

      {isTeacherView && notice && <p className="exam-review-notice pass">{notice}</p>}
      {isTeacherView && visibleDocument === "exam" && <QualityFindings report={exam.validation?.verification_report} />}
      {isTeacherView && visibleDocument === "exam" && <DuplicateFindings report={exam.validation?.duplicate_report} />}

      {variants.length > 0 && (
        <div className="variant-toolbar">
          <div>
            <strong>Phiên bản đề</strong>
            <span>{isTeacherView ? "Chọn bản gốc để duyệt nội dung" : "Chọn mã đề để xem câu hỏi"}</span>
          </div>
          <div className="variant-tabs" role="tablist" aria-label="Chọn mã đề">
            <button
              type="button"
              className={`variant-tab ${selectedVariantCode === "" ? "variant-tab-active" : ""}`}
              onClick={() => setSelectedVariantCode("")}
            >
              Bản gốc
            </button>
            {variants.map((variant) => (
              <button
                key={variant.code}
                type="button"
                className={`variant-tab ${selectedVariantCode === variant.code ? "variant-tab-active" : ""}`}
                onClick={() => setSelectedVariantCode(variant.code)}
              >
                Mã {variant.code}
              </button>
            ))}
          </div>
        </div>
      )}

      {isTeacherView && <div className="variant-toolbar">
        <label className="exam-export-select">
          Nội dung hiển thị
          <SelectControl
            ariaLabel="Chọn nội dung hiển thị"
            value={previewDocument}
            onChange={(value) => setPreviewDocument(value as typeof previewDocument)}
            options={[
              { value: "exam", label: "Đề kiểm tra" },
              { value: "matrix", label: "Ma trận đề" },
              { value: "specification", label: "Bản đặc tả" },
            ]}
          />
        </label>
      </div>}

      {visibleDocument === "exam" && <section className="exam-question-workspace" aria-labelledby="exam-questions-title">
        <div className="exam-question-workspace-head">
          <div>
            <span className="exam-review-eyebrow">Nội dung đề</span>
            <h2 id="exam-questions-title">
              Đề kiểm tra{selectedVariant ? ` · Mã ${selectedVariant.code}` : ""}
            </h2>
            <p>{isTeacherView
              ? "Chọn từng phần để rà soát nhanh; mở câu hỏi để xem đáp án và hướng dẫn chấm."
              : "Chọn từng phần và mở câu hỏi để xem đề bài cùng các phương án trả lời."}</p>
          </div>
          <strong>{displayedQuestions.length} câu</strong>
        </div>

        <QuestionTypeTabs
          questions={displayedQuestions}
          value={questionTypeFilter}
          onChange={setQuestionTypeFilter}
        />

        <div id="exam-question-list" className="exam-question-list">
          {visibleSections.map((section) => (
            <section className="exam-question-section" key={section.type}>
              <div className="exam-question-section-head">
                <div>
                  <span>{section.part ?? "Phần tự luận"}</span>
                  <h3>{section.heading}</h3>
                </div>
                <span>{section.questions.length} câu</span>
              </div>
              <div className="exam-question-cards">
                {section.questions.map((question, index) => (
                  <QuestionCard
                    examId={exam.id} version={exam.version_id ?? 1}
                    onEdit={!selectedVariant && canMutateExam ? async (questionId, payload) => {
                      const updated = await onEditQuestion(exam.id!, questionId, payload);
                      setExam(updated);
                    } : undefined}
                    key={question.id}
                    question={question}
                    audience={audience}
                    answer={answerByQuestionId.get(question.id)}
                    rubric={rubricByQuestionId.get(question.original_id ?? question.id)}
                    reviewStatus={selectedVariant ? undefined : exam.review_status?.[question.id]?.status ?? "pending"}
                    isRegenerated={selectedVariant ? undefined : exam.review_status?.[question.id]?.regenerated}
                    onReview={!selectedVariant && canMutateExam ? handleReviewQuestion : undefined}
                    showControls={!selectedVariant && canMutateExam}
                    defaultExpanded={index === 0}
                    defaultSourceName={defaultSourceName}
                  />
                ))}
              </div>
            </section>
          ))}
          {displayedQuestions.length === 0 && (
            <div className="empty-state">
              <h3>Đề chưa có câu hỏi</h3>
            </div>
          )}
        </div>
      </section>}

      {visibleDocument !== "exam" && <section className="exam-question-workspace" aria-label="Tài liệu đề kiểm tra">
        <div className="exam-support-content">
          {visibleDocument === "matrix" && <section>
            <h2 className="section-title">Ma trận đề kiểm tra</h2>
            <MatrixTable matrix={exam.matrix} summary={exam.summary} />
          </section>}

          {visibleDocument === "specification" && (
            <section>
              <h2 className="section-title">Bản đặc tả</h2>
              {displayedSpecification.length === 0 ? <p className="empty-state">Chưa có bản đặc tả</p> : <div className="spec-table-wrapper">
                <table className="spec-table">
                  <colgroup>
                    <col className="spec-col-num" />
                    <col className="spec-col-topic" />
                    <col className="spec-col-knowledge" />
                    <col className="spec-col-achievement" />
                    <col className="spec-col-difficulty" />
                    <col className="spec-col-type" />
                    <col className="spec-col-score" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Chủ đề</th>
                      <th>Nội dung kiến thức</th>
                      <th>Yêu cầu cần đạt</th>
                      <th>Mức độ</th>
                      <th>Dạng</th>
                      <th>Điểm</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedSpecification.map((specification) => (
                      <tr key={specification.question_id}>
                        <td>{specification.question_number}</td>
                        <td>{specification.topic}</td>
                        <td>{specification.knowledge_unit}</td>
                        <td>{specification.achievement}</td>
                        <td>
                          <span className={`tag-difficulty diff-${specification.difficulty}`}>
                            {formatDifficulty(specification.difficulty)}
                          </span>
                        </td>
                        <td><span className="badge badge-accent">{formatQuestionType(specification.question_type)}</span></td>
                        <td><span className="badge">{specification.score}đ</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>}
            </section>
          )}
        </div>
      </section>}
    </section>
  );
}
