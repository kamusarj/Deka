import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { isSuperAdminRole } from "../auth/rolePolicy";
import { useAuth } from "../contexts/useAuth";
import { useExam } from "../hooks/useExam";
import DuplicateFindings from "../components/DuplicateFindings";
import { useExamFormAutosave } from "../hooks/useExamFormAutosave";
import { createDefaultExamPayload, readExamFormDraft, removeExamFormDraft } from "../utils/examFormDraft";
import { CurriculumForm, MatrixTable, QuestionCard, QuestionTypeTabs, QUESTION_TYPE_SECTIONS, QualityFindings, DifficultyRatioInput, PipelineProgress, SelectControl } from "../components";
import type { QuestionTypeFilter } from "../components";
import { getAiProviders, getAiModels, setAiModel, listDocuments } from "../services/api";
import { documentSharingLabel } from "../utils/documentSharing";
import type { AiProviderStatus, AiModelsResponse, CurriculumItem, Difficulty, DocumentResponse, ExamPayload, QuestionTypes } from "../types";
import { getApiErrorMessage } from "../utils/apiError";
import { curriculumAfterCollection } from "../utils/curriculumSuggestions";
import { isValidDifficultyRatio } from "../utils/difficultyRatio";

const QUESTION_TYPE_LABELS: Record<keyof QuestionTypes, string> = {
  multiple_choice: "Trắc nghiệm nhiều lựa chọn",
  true_false: "Đúng / Sai",
  short_answer: "Trả lời ngắn",
  essay: "Tự luận",
};

const CALCULATION_DIFFICULTY_OPTIONS: { value: Difficulty; label: string }[] = [
  { value: "nhan_biet", label: "Nhận biết" },
  { value: "thong_hieu", label: "Thông hiểu" },
  { value: "van_dung", label: "Vận dụng" },
];

const MINIMUM_SCORE_BY_TYPE: Record<keyof QuestionTypes, number> = {
  multiple_choice: 0.25,
  true_false: 1,
  short_answer: 0.25,
  essay: 0.5,
};

function resizeCalculationDifficulties(
  current: Difficulty[],
  count: number,
): Difficulty[] {
  const defaults: Difficulty[] = ["thong_hieu", "van_dung"];
  return Array.from(
    { length: count },
    (_, index) => current[index] ?? defaults[index % defaults.length],
  );
}

export default function CreateExam() {
  const { user } = useAuth();
  const [revision, setRevision] = useState(0);
  if (!user) return null;
  const scope = `${user.id}:${user.school_id ?? "platform"}`;
  return <CreateExamWorkspace key={`${scope}:${revision}`} scope={scope} onStartNew={() => setRevision((value) => value + 1)} />;
}

function CreateExamWorkspace({ scope, onStartNew }: { scope: string; onStartNew: () => void }) {
  const { user } = useAuth();
  const canConfigureModel = isSuperAdminRole(user?.role);
  const [initialDraft] = useState(() => readExamFormDraft(scope));
  const {
    loading,
    error,
    result,
    resourcePackage,
    pipelineStages,
    onCollectResources,
    onGenerateFullExam,
    onRegenerateQuestions,
    onReviewQuestion,
    onEditQuestion,
    onSaveQuestionsToBank,
    clearError,
  } = useExam();

  const [payload, setPayload] = useState<ExamPayload>(() => initialDraft.draft?.data.payload ?? createDefaultExamPayload());
  const [calculationCountInput, setCalculationCountInput] = useState(initialDraft.draft?.data.calculationCountInput ?? "2");
  const [selectedQuestions, setSelectedQuestions] = useState<string[]>([]);
  const [questionTypeFilter, setQuestionTypeFilter] = useState<QuestionTypeFilter>("all");
  const [regenerateReason, setRegenerateReason] = useState(
    "Câu cần rõ hơn và bám sát yêu cầu cần đạt",
  );
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<number[]>(initialDraft.draft?.data.selectedDocIds ?? []);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState("");
  const [documentsRefresh, setDocumentsRefresh] = useState(0);
  const [bankNotice, setBankNotice] = useState("");
  const [providers, setProviders] = useState<AiProviderStatus[]>([]);
  const [modelsInfo, setModelsInfo] = useState<AiModelsResponse>({});
  const [selectedModel, setSelectedModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [switchingModel, setSwitchingModel] = useState(false);
  const [configurationError, setConfigurationError] = useState("");
  const [formError, setFormError] = useState("");
  const [curriculumEdited, setCurriculumEdited] = useState(initialDraft.draft?.data.curriculumEdited ?? false);
  const [confirmStartNew, setConfirmStartNew] = useState(false);
  const [resetError, setResetError] = useState("");
  const draftData = useMemo(() => ({ payload, calculationCountInput, selectedDocIds, curriculumEdited }),
    [payload, calculationCountInput, selectedDocIds, curriculumEdited]);
  const { savedAt, saveError, retrySave } = useExamFormAutosave(scope, draftData, initialDraft.draft?.updatedAt ?? null);
  const documentSelectionPending = selectedDocIds.length > 0 && (documentsLoading || Boolean(documentsError));
  const missingRestoredDocuments = !documentsLoading && !documentsError && initialDraft.draft?.data.payload.grade === payload.grade
    ? initialDraft.draft.data.selectedDocIds.filter((id) => !documents.some((doc) => doc.id === id)).length : 0;

  function startNewExam() {
    try {
      removeExamFormDraft(scope);
      onStartNew();
    } catch {
      setResetError("Chưa thể xóa bản nháp trên trình duyệt. Các chỉnh sửa của bạn vẫn được giữ nguyên.");
    }
  }
  const isDraft = result?.publication_status === "draft";
  const failedQuestionIds = useMemo(
    () => Object.keys(result?.validation?.persistence?.question_failures ?? {}),
    [result?.validation?.persistence?.question_failures],
  );

  const difficultyIsValid = isValidDifficultyRatio(payload.difficulty_ratio);
  const durationIsValid = Number.isFinite(payload.duration_minutes) && payload.duration_minutes >= 15;
  const ordinaryQuestionScore = Object.values(payload.question_types).reduce(
    (total, config) => total + (config.enabled ? config.count * config.score_per_question : 0),
    0,
  );
  const shortAnswer = payload.question_types.short_answer;
  const effectiveQuestionScore = ordinaryQuestionScore + payload.calculation_requirement.count * (
    payload.calculation_requirement.score_per_question - shortAnswer.score_per_question
  );
  const effectiveScore = Math.round(effectiveQuestionScore * 100) / 100;
  const parsedCalculationCount = Number(calculationCountInput);
  const calculationCountInputIsValid =
    /^\d+$/.test(calculationCountInput) &&
    Number.isInteger(parsedCalculationCount) &&
    parsedCalculationCount >= 1 &&
    parsedCalculationCount <= 30 &&
    parsedCalculationCount === payload.calculation_requirement.count;
  const calculationIsValid =
    shortAnswer.enabled &&
    calculationCountInputIsValid &&
    payload.calculation_requirement.count >= 1 &&
    payload.calculation_requirement.count <= shortAnswer.count &&
    payload.calculation_requirement.score_per_question > 0 &&
    payload.calculation_requirement.difficulties.length ===
      payload.calculation_requirement.count;
  const questionScoreIsValid =
    payload.auto_distribute_scores ||
    Math.abs(effectiveScore - payload.total_score) < 0.001;
  const manualScoresHaveQuarterIncrement =
    payload.auto_distribute_scores || [
      ...(Object.keys(payload.question_types) as (keyof QuestionTypes)[])
        .filter((type) => payload.question_types[type].enabled && payload.question_types[type].count > 0)
        .map((type) => ({
          score: payload.question_types[type].score_per_question,
          minimum: MINIMUM_SCORE_BY_TYPE[type],
        })),
      { score: payload.calculation_requirement.score_per_question, minimum: 0.25 },
    ].every(({ score, minimum }) => score >= minimum && Math.abs(score * 4 - Math.round(score * 4)) < 0.001);
  const totalQuestionCount = Object.values(payload.question_types).reduce(
    (total, config) => total + (config.enabled ? config.count : 0),
    0,
  );
  const minimumScoreUnitsNeeded = (Object.keys(payload.question_types) as (keyof QuestionTypes)[]).reduce(
    (total, type) => total + (
      payload.question_types[type].enabled
        ? payload.question_types[type].count * MINIMUM_SCORE_BY_TYPE[type] * 4
        : 0
    ),
    0,
  );
  const scoreUnitCapacityIsValid =
    !payload.auto_distribute_scores || minimumScoreUnitsNeeded <= payload.total_score * 4;

  // Load uploaded documents for the selected grade (opt-in RAG source).
  useEffect(() => {
    let active = true;
    setDocuments([]);
    setDocumentsLoading(true);
    setDocumentsError("");
    listDocuments(payload.grade)
      .then((docs) => {
        if (!active) return;
        setDocuments(docs);
        setSelectedDocIds((current) => {
          const available = current.filter((id) => docs.some((doc) => doc.id === id));
          return available.length === current.length ? current : available;
        });
      })
      .catch((error) => {
        if (active) setDocumentsError(getApiErrorMessage(error, "Không tải được tài liệu cho khối đã chọn"));
      })
      .finally(() => { if (active) setDocumentsLoading(false); });
    return () => { active = false; };
  }, [payload.grade, documentsRefresh]);

  useEffect(() => {
    if (isDraft) setSelectedQuestions(failedQuestionIds);
  }, [failedQuestionIds, isDraft]);

  useEffect(() => {
    if (!canConfigureModel) {
      setProviders([]);
      setModelsInfo({});
      setSelectedModel("");
      return;
    }

    Promise.all([getAiProviders(), getAiModels()])
      .then(([providersData, modelsData]) => {
        setProviders(providersData.providers);
        setModelsInfo(modelsData);
        const current = modelsData.openai;
        if (current) setSelectedModel(current.current);
      })
      .catch(() => undefined);
  }, [canConfigureModel]);

  async function changeModel(model: string) {
    if (!model.trim()) return;
    setConfigurationError("");
    setSwitchingModel(true);
    try {
      await setAiModel("openai", model.trim());
      setSelectedModel(model.trim());
      setCustomModel("");
      // Refresh models info
      const data = await getAiModels();
      setModelsInfo(data);
    } catch (err: unknown) {
      setConfigurationError(getApiErrorMessage(err, "Không đổi được model AI"));
    } finally { setSwitchingModel(false); }
  }

  function toggleDocument(docId: number) {
    setSelectedDocIds((current) =>
      current.includes(docId)
        ? current.filter((id) => id !== docId)
        : [...current, docId],
    );
  }

  // Auto-populate curriculum when resource package is loaded
  useEffect(() => {
    if (resourcePackage?.curriculum_suggestions?.length) {
      const suggested = resourcePackage.curriculum_suggestions.map((item) => ({
        topic: item.topic,
        periods: item.periods,
        achievements: item.achievements,
      }));
      if (suggested.length > 0) {
        setPayload((prev) => ({
          ...prev,
          curriculum: curriculumAfterCollection(
            prev.curriculum,
            suggested,
            curriculumEdited,
          ),
        }));
      }
    }
  }, [curriculumEdited, resourcePackage]);

  // ── Form handlers ────────────────────────────────────
  function updateCurriculum(index: number, field: keyof CurriculumItem, value: string) {
    setCurriculumEdited(true);
    const next = [...payload.curriculum];
    next[index] = {
      ...next[index],
      [field]:
        field === "periods"
          ? Math.max(1, Number(value) || 1)
          : field === "achievements"
            ? [value]
            : value,
    };
    setPayload({ ...payload, curriculum: next });
  }

  function updateVariantCount(value: string) {
    const numericValue = Number(value) || 1;
    setPayload({
      ...payload,
      variant_count: Math.max(1, Math.min(30, numericValue)),
    });
  }

  function updateQuestionType(
    type: keyof QuestionTypes,
    field: "enabled" | "count" | "score_per_question",
    value: boolean | number,
  ) {
    setPayload((current) => {
      const nextTypes = {
        ...current.question_types,
        [type]: { ...current.question_types[type], [field]: value },
      };
      if (type === "short_answer" && field === "count") {
        nextTypes.short_answer.count = Math.max(
          current.calculation_requirement.count,
          Number(value),
        );
      }
      return {
        ...current,
        question_types: nextTypes,
      };
    });
  }

  function updateCalculationCount(value: string) {
    setCalculationCountInput(value);
    if (!/^\d+$/.test(value)) return;
    const count = Number(value);
    if (!Number.isInteger(count) || count < 1 || count > 30) return;
    setPayload((current) => ({
      ...current,
      question_types: {
        ...current.question_types,
        short_answer: {
          ...current.question_types.short_answer,
          count: Math.max(current.question_types.short_answer.count, count),
        },
      },
      calculation_requirement: {
        ...current.calculation_requirement,
        count,
        difficulties: resizeCalculationDifficulties(
          current.calculation_requirement.difficulties,
          count,
        ),
      },
    }));
  }

  function normalizeCalculationCountInput() {
    setCalculationCountInput(String(payload.calculation_requirement.count));
  }

  function updateCalculationDifficulty(index: number, difficulty: Difficulty) {
    setPayload((current) => {
      const difficulties = [...current.calculation_requirement.difficulties];
      difficulties[index] = difficulty;
      return {
        ...current,
        calculation_requirement: {
          ...current.calculation_requirement,
          difficulties,
        },
      };
    });
  }

  // ── Submit ───────────────────────────────────────────
  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    if (documentSelectionPending) {
      setFormError("Cần tải lại tài liệu đã chọn trước khi tạo đề.");
      return;
    }
    if (!difficultyIsValid || !durationIsValid || !calculationIsValid || !questionScoreIsValid || !manualScoresHaveQuarterIncrement || !scoreUnitCapacityIsValid) {
      setFormError(
        !durationIsValid
          ? "Thời gian làm bài phải từ 15 phút trở lên."
          : !difficultyIsValid
            ? "Mỗi tỷ lệ mức độ phải là số nguyên từ 0 đến 100, tổng bằng 100%."
            : !calculationIsValid
              ? "Đề phải có ít nhất một câu tính toán và số câu không được vượt phần trả lời ngắn."
              : !scoreUnitCapacityIsValid
                ? `Cấu trúc hiện tại vượt quỹ ${payload.total_score * 4} đơn vị 0,25 điểm của đề.`
              : !manualScoresHaveQuarterIncrement
                ? "Điểm mỗi câu/mỗi ý phải từ 0,25 và là bội số của 0,25."
              : `Tổng điểm theo cấu hình câu hỏi phải bằng ${payload.total_score} điểm.`,
      );
      return;
    }
    await onGenerateFullExam({ ...payload, use_uploaded_docs: selectedDocIds });
    setSelectedQuestions([]);
    setQuestionTypeFilter("all");
  }

  async function saveQuestionToBank(questionId: string) {
    if (!result?.id || isDraft) return;
    setBankNotice("");
    try {
      const saved = await onSaveQuestionsToBank(result.id, [questionId], ["from-create"]);
      setBankNotice(`Đã lưu câu vào ngân hàng. ${saved?.warning ?? ""}`);
    } catch {
      // error handled by hook
    }
  }

  // ── Review & Regenerate ──────────────────────────────
  async function markReview(
    questionId: string,
    status: "accepted" | "needs_revision" | "rejected",
  ) {
    if (!result?.id) return;
    await onReviewQuestion(result.id, questionId, status);
  }

  function toggleQuestion(questionId: string) {
    if (isDraft && !failedQuestionIds.includes(questionId)) return;
    setSelectedQuestions((current) =>
      current.includes(questionId)
        ? current.filter((id) => id !== questionId)
        : [...current, questionId],
    );
  }

  async function onRegenerateSelected() {
    if (!result?.id || selectedQuestions.length === 0) return;
    try {
      await onRegenerateQuestions({
        exam_id: result.id,
        question_ids: selectedQuestions,
        reason: regenerateReason,
        allow_provider_fallback: false,
      });
      setSelectedQuestions([]);
    } catch {
      // The hook displays the error. Keep the teacher's selection for retry.
    }
  }

  // ── Render ───────────────────────────────────────────
  return (
    <section className="layout exam-authoring-layout">
      {/* Left: Input Form */}
      <form className="panel" onSubmit={onSubmit}>
        <div className="panel-header">
          <h2>Tạo đề kiểm tra bằng AI</h2>
        </div>

        <div className="exam-draft-bar" aria-label="Bản nháp cấu hình đề">
          <div>
            <p role="status" aria-label="Trạng thái lưu bản nháp" aria-live="polite">
              {saveError ? "Chưa lưu được bản nháp" : savedAt ? "Đã lưu bản nháp" : "Đang lưu bản nháp…"}
              {!saveError && savedAt && <time dateTime={savedAt}>{new Date(savedAt).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</time>}
            </p>
            <small>{initialDraft.draft ? "Đã khôi phục lần chỉnh sửa trước. " : ""}Tự lưu riêng cho tài khoản này trên trình duyệt đang dùng.</small>
          </div>
          <button type="button" className="secondary compact" disabled={loading || switchingModel} onClick={() => setConfirmStartNew(true)}>Tạo đề mới</button>
        </div>
        {saveError && <div className="error-box" role="alert">
          <p>Trình duyệt đang chặn lưu trữ hoặc đã hết dung lượng. Các chỉnh sửa chưa được lưu; hãy thử lưu lại trước khi rời trang.</p>
          <button type="button" className="secondary compact" onClick={retrySave}>Thử lưu lại</button>
        </div>}
        {initialDraft.warning && <p className="muted">{initialDraft.warning}</p>}
        {confirmStartNew && <div className="exam-draft-confirm" role="group" aria-label="Bắt đầu đề mới">
          <p>Bắt đầu đề mới sẽ thay bản nháp đang sửa bằng mẫu mặc định. Các đề đã tạo vẫn được giữ lại.</p>
          <div>
            <button type="button" className="secondary compact" onClick={() => { setConfirmStartNew(false); setResetError(""); }}>Tiếp tục chỉnh sửa</button>
            <button type="button" className="compact" disabled={loading || switchingModel} onClick={startNewExam}>Bắt đầu đề mới</button>
          </div>
          {resetError && <p className="error" role="alert">{resetError}</p>}
        </div>}

        {canConfigureModel && providers.length > 0 && (
          <div className="ai-choice">
            <div className="ai-fixed-chain" aria-label="Thứ tự API AI">
              <span><strong>OpenAI</strong><small>API chính</small></span>
              <b aria-hidden="true">→</b>
              <span><strong>Gemini</strong><small>Dự phòng 1</small></span>
              <b aria-hidden="true">→</b>
              <span><strong>DeepSeek</strong><small>Dự phòng 2</small></span>
            </div>

            {/* Model selector */}
            {canConfigureModel && modelsInfo.openai && (
              <label className="ai-model-select">
                Model OpenAI chính
                <div className="ai-model-row">
                  <SelectControl
                    ariaLabel="Model AI"
                    value={selectedModel || modelsInfo.openai.current}
                    disabled={switchingModel}
                    onChange={(value) => {
                      if (value === "__custom") {
                        setSelectedModel("__custom");
                        setCustomModel("");
                      } else {
                        changeModel(value);
                      }
                    }}
                    options={[
                      ...modelsInfo.openai.suggested.map((model) => ({
                        value: model,
                        label: model,
                      })),
                      ...(!modelsInfo.openai.suggested.includes(modelsInfo.openai.current)
                        ? [{
                            value: modelsInfo.openai.current,
                            label: `${modelsInfo.openai.current} (hiện tại)`,
                          }]
                        : []),
                      { value: "__custom", label: "Nhập model khác..." },
                    ]}
                  />
                  {switchingModel && <span className="ai-model-loading">●</span>}
                </div>
                {/* Custom model input */}
                {selectedModel === "__custom" || customModel ? (
                  <div className="ai-model-custom">
                    <input
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      placeholder="Nhập tên model, ví dụ: gpt-4o-mini"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          changeModel(customModel);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="secondary compact"
                      onClick={() => changeModel(customModel)}
                      disabled={!customModel.trim() || switchingModel}
                    >
                      Áp dụng
                    </button>
                  </div>
                ) : null}
              </label>
            )}
          </div>
        )}

        {configurationError && <p className="error">{configurationError}</p>}

        {/* School info */}
        <div className="grid two">
          <label>
            Trường
            <input
              value={payload.school}
              onChange={(e) => setPayload({ ...payload, school: e.target.value })}
              required
            />
          </label>
          <label>
            Năm học
            <input
              value={payload.school_year}
              onChange={(e) => setPayload({ ...payload, school_year: e.target.value })}
              required
            />
          </label>
          <label>
            Khối
            <SelectControl
              ariaLabel="Khối"
              value={payload.grade}
              onChange={(value) => {
                setSelectedDocIds([]);
                setPayload({ ...payload, grade: Number(value) });
              }}
              options={[6, 7, 8, 9].map((grade) => ({ value: grade, label: `Lớp ${grade}` }))}
            />
          </label>
          <label>
            Loại kiểm tra
            <SelectControl
              ariaLabel="Loại kiểm tra"
              value={payload.exam_type}
              onChange={(value) => setPayload({ ...payload, exam_type: value })}
              options={[
                "Giữa học kì I",
                "Cuối học kì I",
                "Giữa học kì II",
                "Cuối học kì II",
              ].map((examType) => ({ value: examType, label: examType }))}
            />
          </label>
          <label>
            Thời gian (phút)
            <input
              type="number"
              min={15}
              required
              value={payload.duration_minutes}
              onChange={(e) =>
                setPayload({ ...payload, duration_minutes: Number(e.target.value) })
              }
            />
          </label>
          <label>
            Số mã đề
            <input
              type="number"
              min={1}
              max={30}
              value={payload.variant_count}
              onChange={(e) => updateVariantCount(e.target.value)}
            />
          </label>
        </div>

        {/* Collect resources */}
        <button
          type="button"
          className="secondary wide"
          disabled={loading}
          onClick={() =>
            onCollectResources({
              grade: payload.grade,
              subject: payload.subject,
              exam_type: payload.exam_type,
            })
          }
        >
          {loading ? "Đang thu thập..." : "Thu thập tài liệu tham khảo"}
        </button>

        {resourcePackage && (
          <p className="pass">
            Đã thu thập {resourcePackage.curriculum_suggestions?.length ?? 0} chủ đề gợi ý.
          </p>
        )}

        {/* Opt-in RAG: dùng tài liệu đã upload làm nguồn câu hỏi */}
        {(documentsLoading || documentsError || documents.length > 0) && (
          <div className="resource-section">
            <strong>Dùng tài liệu cá nhân và được chia sẻ</strong>
            <p className="muted">Chọn tài liệu làm nguồn cho câu hỏi.</p>
            {documentsLoading && <p className="muted" role="status">Đang tải tài liệu…</p>}
            {documentsError && <div role="alert" className="error-box">
              <p>{documentsError}</p>
              <button type="button" className="secondary compact" onClick={() => setDocumentsRefresh(value => value + 1)}>Tải lại tài liệu</button>
            </div>}
            <div className="doc-checklist">
              {documents.map((doc) => (
                <label key={doc.id} className="checkline">
                  <input
                    type="checkbox"
                    checked={selectedDocIds.includes(doc.id)}
                    onChange={() => toggleDocument(doc.id)}
                  />
                  {doc.filename}{" "}
                  <span className="badge badge-accent">{doc.file_type.toUpperCase()}</span>
                  <span className="badge">{documentSharingLabel(doc)}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {missingRestoredDocuments > 0 && <p className="muted">{missingRestoredDocuments} tài liệu đã chọn không còn khả dụng. Hãy kiểm tra lại nguồn tài liệu trước khi tạo đề.</p>}

        {/* Curriculum form */}
        <div className="panel-section">
          <CurriculumForm
            curriculum={payload.curriculum}
            onChange={updateCurriculum}
            onAdd={() =>
              {
                setCurriculumEdited(true);
                setPayload({
                  ...payload,
                  curriculum: [
                    ...payload.curriculum,
                    { topic: "Chủ đề mới", periods: 1, achievements: ["Nêu được kiến thức trọng tâm"] },
                  ],
                });
              }
            }
          />
        </div>

        <div className="panel-section question-structure-section">
          <div className="question-structure-heading">
            <div>
              <h3 className="subsection-title">Cấu trúc và điểm câu hỏi</h3>
              <p className="muted">
                Tổng {totalQuestionCount} câu. Câu tính toán nằm trong phần trả lời ngắn;
                tăng số câu tính toán có thể làm tổng số câu tăng theo.
              </p>
            </div>
            <strong className={questionScoreIsValid ? "score-total is-valid" : "score-total is-invalid"}>
              {payload.auto_distribute_scores
                ? `Tự cân về ${payload.total_score} điểm`
                : `${effectiveScore}/${payload.total_score} điểm`}
            </strong>
          </div>
          <label className="checkline auto-score-toggle">
            <input
              type="checkbox"
              checked={payload.auto_distribute_scores}
              onChange={(event) => setPayload({
                ...payload,
                auto_distribute_scores: event.target.checked,
              })}
            />
            Tự động phân bổ điểm theo tỷ lệ mức độ
          </label>
          {payload.auto_distribute_scores && (
            <p className="muted auto-score-note">
              Mỗi câu/mỗi ý tối thiểu 0,25; câu nhiều ý nhận tổng điểm là bội số của 0,25. Tổng đề giữ đúng {payload.total_score} điểm;
              tỷ lệ mức độ được làm tròn về phương án gần nhất có thể chấm theo nấc 0,25.
            </p>
          )}
          <div className="question-type-config" aria-label="Cấu trúc câu hỏi">
            {(Object.keys(QUESTION_TYPE_LABELS) as (keyof QuestionTypes)[]).map((type) => {
              const config = payload.question_types[type];
              return (
                <div className="question-type-config-row" key={type}>
                  <label className="checkline question-type-toggle">
                    <input
                      type="checkbox"
                      checked={config.enabled}
                      disabled={type === "short_answer"}
                      onChange={(event) => updateQuestionType(type, "enabled", event.target.checked)}
                    />
                    {QUESTION_TYPE_LABELS[type]}
                  </label>
                  <label>
                    Số câu
                    <input
                      aria-label={`Số câu ${QUESTION_TYPE_LABELS[type]}`}
                      type="number"
                      min={type === "short_answer" ? 1 : 0}
                      value={config.count}
                      onChange={(event) => updateQuestionType(type, "count", Math.max(0, Number(event.target.value)))}
                    />
                  </label>
                  <label>
                    Điểm/câu
                    <input
                      aria-label={`Điểm mỗi câu ${QUESTION_TYPE_LABELS[type]}`}
                      type="number"
                      min={MINIMUM_SCORE_BY_TYPE[type]}
                      step={0.25}
                      disabled={payload.auto_distribute_scores}
                      value={config.score_per_question}
                      onChange={(event) => updateQuestionType(type, "score_per_question", Math.max(MINIMUM_SCORE_BY_TYPE[type], Number(event.target.value)))}
                    />
                  </label>
                </div>
              );
            })}
          </div>
          <fieldset className="calculation-config">
            <legend>Câu tính toán bắt buộc</legend>
            <label>
              Số câu tính toán
              <input
                aria-label="Số câu tính toán bắt buộc"
                type="number"
                min={1}
                max={30}
                required
                value={calculationCountInput}
                onChange={(event) => updateCalculationCount(event.target.value)}
                onBlur={normalizeCalculationCountInput}
              />
            </label>
            <label>
              Điểm mỗi câu tính toán
              <input
                aria-label="Điểm mỗi câu tính toán"
                type="number"
                min={0.25}
                step={0.25}
                required
                disabled={payload.auto_distribute_scores}
                value={payload.calculation_requirement.score_per_question}
                onChange={(event) => setPayload({
                  ...payload,
                  calculation_requirement: {
                    ...payload.calculation_requirement,
                    score_per_question: Math.max(0.25, Number(event.target.value)),
                  },
                })}
              />
            </label>
            <div className="calculation-difficulty-config">
              <p>Chọn mức độ cho từng câu tính toán</p>
              <div className="calculation-difficulty-list">
                {payload.calculation_requirement.difficulties.map((difficulty, index) => (
                  <label key={index}>
                    Câu tính toán {index + 1}
                    <SelectControl
                      ariaLabel={`Mức độ câu tính toán ${index + 1}`}
                      value={difficulty}
                      options={CALCULATION_DIFFICULTY_OPTIONS}
                      onChange={(next) => updateCalculationDifficulty(index, next)}
                    />
                  </label>
                ))}
              </div>
            </div>
          </fieldset>
          {!calculationIsValid && (
            <p className="error">Số câu tính toán phải là số nguyên từ 1 đến 30.</p>
          )}
          {!payload.auto_distribute_scores && !questionScoreIsValid && (
            <p className="error">Hãy điều chỉnh số câu hoặc điểm/câu để tổng đúng {payload.total_score} điểm.</p>
          )}
          {!manualScoresHaveQuarterIncrement && (
            <p className="error">Điểm mỗi câu/mỗi ý phải từ 0,25 và là bội số của 0,25.</p>
          )}
          {!scoreUnitCapacityIsValid && (
            <p className="error">
              Cấu trúc hiện tại cần {minimumScoreUnitsNeeded} đơn vị 0,25 điểm nhưng đề chỉ có {payload.total_score * 4} đơn vị.
            </p>
          )}
        </div>

        {/* Difficulty ratio */}
        <div className="panel-section">
          <h3 className="subsection-title">Tỷ lệ mức độ</h3>
          <DifficultyRatioInput
            value={payload.difficulty_ratio}
            onChange={(next) => setPayload({ ...payload, difficulty_ratio: next })}
          />
        </div>

        {error && (
          <div className="error-box">
            <p className="error">{error}</p>
            <button type="button" className="secondary compact" onClick={clearError}>
              Đóng
            </button>
          </div>
        )}
        {formError && <p className="error">{formError}</p>}
        <button type="submit" disabled={loading || documentSelectionPending || !difficultyIsValid || !durationIsValid || !calculationIsValid || !questionScoreIsValid || !manualScoresHaveQuarterIncrement || !scoreUnitCapacityIsValid} className="wide">
          {loading ? "Đang tạo..." : "Tạo đề kiểm tra"}
        </button>
      </form>

      {/* Right: Results */}
      <section className="panel result">
        {loading && (
          <PipelineProgress stages={pipelineStages} />
        )}

        {!loading && !result && (
          <div className="empty-state">
            <h3>Kết quả sẽ hiển thị tại đây</h3>
          </div>
        )}

        {!loading && result && (
          <>
            <div className="result-head">
              <h2>{isDraft ? "Bản nháp" : "Đề"}{result.exam_number != null ? ` #${result.exam_number}` : ""}</h2>
              <Link className="button-link secondary compact" to={`/exams/${result.id}`}>
                Xem chi tiết →
              </Link>
            </div>

            {isDraft && (
              <div className="error-box" role="status">
                <strong>Bản nháp chưa qua kiểm định bắt buộc</strong>
                <p>
                  Nội dung AI thật đã được giữ lại. Bản này chưa thể xuất hoặc
                  lưu vào ngân hàng; chỉ tạo lại các câu được đánh dấu lỗi.
                </p>
              </div>
            )}

            <QualityFindings report={result.validation.verification_report} />
            <DuplicateFindings report={result.validation.duplicate_report} />

            {/* Matrix */}
            <h3 className="subsection-title">Ma trận đề</h3>
            <MatrixTable matrix={result.matrix} summary={result.summary} />

            {/* Review tools */}
            <div className="generated-review-head">
              <div>
                <span className="exam-review-eyebrow">Nội dung đề</span>
                <h3 className="subsection-title">Duyệt câu hỏi</h3>
                <p>Mở từng câu để xem đáp án; chọn các câu cần tạo lại.</p>
              </div>
              <strong>{result.questions.length} câu</strong>
            </div>
            <div className="regeneration-toolbar">
              <input
                value={regenerateReason}
                onChange={(e) => setRegenerateReason(e.target.value)}
                placeholder="Lý do tạo lại..."
              />
              <button
                type="button"
                onClick={onRegenerateSelected}
                disabled={loading || selectedQuestions.length === 0}
              >
                Tạo lại {selectedQuestions.length} {isDraft ? "câu lỗi" : "câu đã chọn"}
              </button>
            </div>

            {bankNotice && <p className="pass" style={{ margin: "0.5rem 0" }}>{bankNotice}</p>}

            <QuestionTypeTabs
              questions={result.questions}
              value={questionTypeFilter}
              onChange={setQuestionTypeFilter}
            />

            <div id="exam-question-list" className="exam-question-list generated-question-list">
              {QUESTION_TYPE_SECTIONS
                .filter((section) => questionTypeFilter === "all" || section.type === questionTypeFilter)
                .map((section) => ({
                  ...section,
                  questions: result.questions.filter((question) => question.type === section.type),
                }))
                .filter((section) => section.questions.length > 0)
                .map((section) => (
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
                          key={question.id}
                          question={question}
                          examId={result.id} version={result.version_id ?? 1}
                          onEdit={(questionId, edit) => onEditQuestion(result.id!, questionId, edit)}
                          answer={result.answer_key.find((answer) => answer.question_id === question.id)}
                          rubric={result.rubric.find((rubric) => rubric.question_id === question.id)}
                          reviewStatus={result.review_status?.[question.id]?.status ?? "pending"}
                          isRegenerated={result.review_status?.[question.id]?.regenerated}
                          isSelected={selectedQuestions.includes(question.id)}
                          onToggleSelect={
                            !isDraft || failedQuestionIds.includes(question.id)
                              ? toggleQuestion
                              : undefined
                          }
                          onReview={markReview}
                          onSaveToBank={isDraft ? undefined : saveQuestionToBank}
                          showControls
                          defaultExpanded={index === 0}
                          defaultSourceName={result.resource_package?.raw_data?.curriculum_file}
                        />
                      ))}
                    </div>
                  </section>
                ))}
            </div>
          </>
        )}
      </section>
    </section>
  );
}
