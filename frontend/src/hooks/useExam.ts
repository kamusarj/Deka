import { useState, useCallback, useEffect, useRef } from "react";
import type {
  ExamPayload,
  ExamExportOptions,
  ExamResponse,
  FullExamResponse,
  CollectResourcesRequest,
  ResourcePackage,
  RegenerateQuestionsRequest,
  PipelineStageEvent,
  PipelineStageInfo,
  PipelineStageId,
  ReviewStatus,
} from "../types";
import { PIPELINE_STAGES } from "../types";
import {
  collectResources,
  generateFullExamStream,
  regenerateQuestions,
  reviewQuestions,
  editQuestion,
  listExams,
  getExam,
  exportDocx,
  exportPdf,
  deleteExam,
  duplicateExam,
  saveQuestionsFromExam,
} from "../services/api";
import { generationRequest, completeGenerationRequest } from "../utils/generationRequest";
import { getApiErrorMessage } from "../utils/apiError";

export function buildReviewRequest(
  questionId: string,
  status: Exclude<ReviewStatus, "pending">,
) {
  return {
    accepted_question_ids: status === "accepted" ? [questionId] : [],
    needs_revision_question_ids: status === "needs_revision" ? [questionId] : [],
    rejected_question_ids: status === "rejected" ? [questionId] : [],
  };
}

interface UseExamReturn {
  onEditQuestion: (examId: number, questionId: string, payload: import("../components/QuestionEditor").QuestionEditPayload) => Promise<FullExamResponse>;
  loading: boolean;
  error: string;
  result: FullExamResponse | null;
  resourcePackage: ResourcePackage | null;
  exams: ExamResponse[];
  pipelineStages: PipelineStageInfo[];
  currentStage: PipelineStageId | null;

  // Actions
  onCollectResources: (req: CollectResourcesRequest) => Promise<void>;
  onGenerateFullExam: (payload: ExamPayload) => Promise<void>;
  onRegenerateQuestions: (req: RegenerateQuestionsRequest) => Promise<void>;
  onReviewQuestion: (
    examId: number,
    questionId: string,
    status: Exclude<ReviewStatus, "pending">,
  ) => Promise<FullExamResponse>;
  onLoadExams: () => Promise<void>;
  onLoadExam: (examId: number) => Promise<FullExamResponse>;
  onExportDocx: (examId: number, audience?: "student" | "teacher", options?: ExamExportOptions) => Promise<Blob>;
  onExportPdf: (examId: number, audience?: "student" | "teacher", options?: ExamExportOptions) => Promise<Blob>;
  onDeleteExam: (examId: number) => Promise<void>;
  onDuplicateExam: (examId: number) => Promise<FullExamResponse>;
  onSaveQuestionsToBank: (
    examId: number,
    questionIds: string[],
    tags?: string[],
  ) => Promise<{ count: number; warning: string }>;
  clearError: () => void;
  setResult: (result: FullExamResponse | null) => void;
}

export function useExam(): UseExamReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<FullExamResponse | null>(null);
  const [resourcePackage, setResourcePackage] = useState<ResourcePackage | null>(null);
  const [exams, setExams] = useState<ExamResponse[]>([]);
  const [pipelineStages, setPipelineStages] = useState<PipelineStageInfo[]>([]);
  const [currentStage, setCurrentStage] = useState<PipelineStageId | null>(null);
  const generationControllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => generationControllerRef.current?.abort(), []);

  const clearError = useCallback(() => setError(""), []);

  const resetPipeline = useCallback(() => {
    setPipelineStages(
      PIPELINE_STAGES.map((s) => ({ ...s, status: "pending" as const, message: "" })),
    );
    setCurrentStage(null);
  }, []);

  const handleStageEvent = useCallback((event: PipelineStageEvent) => {
    setCurrentStage(event.stage as PipelineStageId);
    setPipelineStages((prev) =>
      prev.map((s) =>
        s.id === event.stage
          ? { ...s, status: event.status, message: event.message }
          : s,
      ),
    );
  }, []);

  const onCollectResources = useCallback(
    async (req: CollectResourcesRequest) => {
      setLoading(true);
      setError("");
      try {
        const data = await collectResources(req);
        setResourcePackage(data.resource_package);
      } catch (err: unknown) {
        setError(getApiErrorMessage(err, "Không thu thập được tài liệu tham khảo"));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const onGenerateFullExam = useCallback(async (payload: ExamPayload) => {
    generationControllerRef.current?.abort();
    const controller = new AbortController();
    generationControllerRef.current = controller;
    setLoading(true);
    setError("");
    setResult(null);
    resetPipeline();
    try {
      const key = await generationRequest(payload);
      const data = await generateFullExamStream(payload, handleStageEvent, controller.signal, key);
      completeGenerationRequest(key);
      setResult(data);
    } catch (err: unknown) {
      if (!controller.signal.aborted) {
        setError(getApiErrorMessage(err, "Không tạo được đề kiểm tra"));
      }
    } finally {
      if (generationControllerRef.current === controller) {
        generationControllerRef.current = null;
        setLoading(false);
      }
    }
  }, [resetPipeline, handleStageEvent]);

  const onRegenerateQuestions = useCallback(
    async (req: RegenerateQuestionsRequest) => {
      setLoading(true);
      setError("");
      try {
        const data = await regenerateQuestions(req);
        setResult(data);
      } catch (err: unknown) {
        setError(getApiErrorMessage(err, "Không tạo lại được câu hỏi"));
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const onEditQuestion = useCallback(async (examId: number, questionId: string, payload: import("../components/QuestionEditor").QuestionEditPayload) => {
    const updated = await editQuestion(examId, questionId, payload);
    setResult((current) => current?.id === examId ? updated : current);
    return updated;
  }, []);

  const onReviewQuestion = useCallback(
    async (
      examId: number,
      questionId: string,
      status: Exclude<ReviewStatus, "pending">,
    ) => {
      setError("");
      try {
        const updated = await reviewQuestions(examId, buildReviewRequest(questionId, status));
        setResult(updated);
        return updated;
      } catch (err: unknown) {
        setError(getApiErrorMessage(err, "Không cập nhật được trạng thái duyệt"));
        throw err;
      }
    },
    [],
  );

  const onLoadExams = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listExams();
      setExams(data);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Không tải được danh sách đề"));
    } finally {
      setLoading(false);
    }
  }, []);

  const onLoadExam = useCallback(async (examId: number) => {
    setLoading(true);
    setError("");
    try {
      const data = await getExam(examId);
      return data;
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Không tải được chi tiết đề"));
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const onExportDocx = useCallback(async (examId: number, audience: "student" | "teacher" = "teacher", options: ExamExportOptions = {}) => {
    setError("");
    try {
      return await exportDocx(examId, audience, options);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Không xuất được file Word"));
      throw err;
    }
  }, []);

  const onExportPdf = useCallback(async (examId: number, audience: "student" | "teacher" = "teacher", options: ExamExportOptions = {}) => {
    setError("");
    try {
      return await exportPdf(examId, audience, options);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Không xuất được file PDF"));
      throw err;
    }
  }, []);

  const onDeleteExam = useCallback(async (examId: number) => {
    setError("");
    try {
      await deleteExam(examId);
      setExams((current) => current.filter((exam) => exam.id !== examId));
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Không xóa được đề kiểm tra"));
      throw err;
    }
  }, []);

  const onDuplicateExam = useCallback(async (examId: number) => {
    setError("");
    try {
      return await duplicateExam(examId);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Không nhân bản được đề kiểm tra"));
      throw err;
    }
  }, []);

  const onSaveQuestionsToBank = useCallback(
    async (examId: number, questionIds: string[], tags: string[] = []) => {
      setError("");
      try {
        const result = await saveQuestionsFromExam(examId, questionIds, tags);
        return { count: result.count, warning: result.duplicate_findings?.map(item => `Câu ngân hàng ${item.matched_question_id}: ${item.reason}`).join(" ") ?? "" };
      } catch (err: unknown) {
        setError(getApiErrorMessage(err, "Không lưu được câu hỏi vào ngân hàng"));
        throw err;
      }
    },
    [],
  );

  return {
    loading,
    error,
    result,
    resourcePackage,
    exams,
    pipelineStages,
    currentStage,
    onCollectResources,
    onGenerateFullExam,
    onRegenerateQuestions,
    onReviewQuestion,
    onEditQuestion,
    onLoadExams,
    onLoadExam,
    onExportDocx,
    onExportPdf,
    onDeleteExam,
    onDuplicateExam,
    onSaveQuestionsToBank,
    clearError,
    setResult,
  };
}
