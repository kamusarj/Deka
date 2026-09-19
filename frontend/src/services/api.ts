import { rememberGenerationRequest, completeGenerationRequest } from "../utils/generationRequest";
import axios from "axios";
import { getToken, removeToken } from "../contexts/authStorage";
import { getApiErrorMessage } from "../utils/apiError";
import type {
  BankQuestion,
  CommunityTopic, CommunityTopicDetail, CommunityQuestion, CommunityComment, CommunityPage,
  AiProviderStatus,
  AiProvider,
  AiProvidersResponse,
  BankQuestionFilters,
  CollectResourcesRequest,
  CollectResourcesResponse,
  DocumentDetailResponse,
  DocumentResponse,
  DocumentScope,
  DocumentLibrary,
  ExamPayload,
  ExamExportOptions,
  ExamResponse,
  ExamSearchResponse,
  DashboardSummary,
  FullExamResponse,
  PipelineStageEvent,
  RagQueryResponse,
  RegenerateQuestionsRequest,
  RegenerateQuestionsResponse,
  ReviewQuestionsRequest,
  SaveFromExamResponse,
} from "../types";

// Same-origin is the safe default in both supported environments: Vite proxies
// /api to localhost:8000 in development and nginx proxies it in Docker. An
// explicit URL remains available for deployments with a separate API origin.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "",
});

export async function collectResources(
  data: CollectResourcesRequest,
): Promise<CollectResourcesResponse> {
  const res = await api.post("/api/resources/collect", data);
  return res.data;
}

export async function testLlm(prompt: string): Promise<{ provider?: string; model: string; text: string }> {
  const res = await api.post("/api/ai/test-llm", { prompt });
  return res.data;
}

export async function getAiProviderStatus(): Promise<AiProviderStatus> {
  const res = await api.get("/api/ai/status");
  return res.data;
}

export async function getAiProviders(): Promise<AiProvidersResponse> {
  const res = await api.get("/api/ai/providers");
  return res.data;
}

export async function getAiModels(): Promise<Record<string, {
  suggested: string[];
  current: string;
  current_verify: string;
}>> {
  const res = await api.get("/api/ai/models");
  return res.data;
}

export async function setAiModel(
  provider: AiProvider,
  model: string,
  verifyModel?: string,
): Promise<{ provider: string; model: string; verify_model: string; message: string }> {
  const res = await api.post("/api/ai/model", {
    provider,
    model,
    verify_model: verifyModel ?? null,
  });
  return res.data;
}

/** @deprecated Dùng testLlm() cho provider hiện tại, hoặc gọi testGemini để luôn dùng Gemini. */
export async function testGemini(prompt: string): Promise<{ model: string; text: string }> {
  const res = await api.post("/api/ai/test-gemini", { prompt });
  return res.data;
}

export async function analyzeCurriculum(data: {
  grade: number;
  subject: string;
  exam_type: string;
  teaching_plan: string;
}) {
  const res = await api.post("/api/curriculum/analyze", data);
  return res.data;
}

export async function generateMatrix(data: ExamPayload) {
  const res = await api.post("/api/exams/generate-matrix", data);
  return res.data;
}

export async function generateSpecification(data: ExamPayload) {
  const res = await api.post("/api/exams/generate-specification", data);
  return res.data;
}

export async function generateFullExam(data: ExamPayload, idempotencyKey: string = crypto.randomUUID()): Promise<FullExamResponse> {
  const res = await api.post("/api/exams/generate-full-exam", data, { headers: { "Idempotency-Key": idempotencyKey } });
  return res.data;
}

/**
 * SSE streaming version of generateFullExam.
 * Calls onStage for each pipeline stage event, returns final result.
 */
export async function generateFullExamStream(
  data: ExamPayload,
  onStage: (event: PipelineStageEvent) => void,
  signal?: AbortSignal,
  idempotencyKey: string = crypto.randomUUID(),
): Promise<FullExamResponse> {
  const baseURL = import.meta.env.VITE_API_BASE_URL ?? "";
  const token = getToken();
  const response = await fetch(`${baseURL}/api/exams/generate-full-exam/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
    signal,
  });

  if (!response.ok || !response.body) {
    if (response.status === 401) invalidateMatchingSession(token ? `Bearer ${token}` : undefined);
    let errorMsg = `Lỗi server (${response.status})`;
    try {
      const errorText = await response.text();
      if (errorText) {
        try {
          const parsed = JSON.parse(errorText);
          errorMsg = getApiErrorMessage({ response: { data: parsed } }, errorMsg);
        } catch {
          errorMsg = errorText;
        }
      }
    } catch {
      // ignore read errors
    }
    throw new Error(errorMsg);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: FullExamResponse | null = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        let parsed: PipelineStageEvent | { type: "result"; payload: FullExamResponse };
        try {
          parsed = JSON.parse(jsonStr);
        } catch {
          // Ignore a malformed event without abandoning an otherwise valid stream.
          continue;
        }

        const request = parsed as { request_id?: string; request_status?: string };
        if (request.request_id) rememberGenerationRequest(idempotencyKey, request.request_id);
        if (request.request_status === "failed") completeGenerationRequest(idempotencyKey);
        if ("type" in parsed) {
          result = parsed.payload;
          continue;
        }

        if (parsed.status === "error" || parsed.stage === "error") {
          throw new Error(parsed.message || "Không thể tạo đề kiểm tra");
        } else {
          onStage(parsed);
        }
      }
    }
  } catch (error) {
    try {
      await reader.cancel();
    } catch {
      // Preserve the original stream/parsing error if cancellation also fails.
    }
    throw error;
  } finally {
    reader.releaseLock();
  }

  if (!result) throw new Error("Không nhận được kết quả từ server");
  return result;
}

export async function editQuestion(examId: number, questionId: string, payload: import("../components/QuestionEditor").QuestionEditPayload): Promise<FullExamResponse> {
  const { data } = await api.patch<FullExamResponse>(`/api/exams/${examId}/questions/${encodeURIComponent(questionId)}`, payload);
  return data;
}

export async function reviewQuestions(
  id: number,
  data: ReviewQuestionsRequest,
): Promise<FullExamResponse> {
  const res = await api.post(`/api/exams/${id}/review`, data);
  return res.data;
}

export async function regenerateQuestions(
  data: RegenerateQuestionsRequest,
): Promise<RegenerateQuestionsResponse> {
  const res = await api.post("/api/questions/regenerate", data);
  return res.data;
}

export async function listExams(): Promise<ExamResponse[]> {
  const res = await api.get("/api/exams");
  return res.data;
}

export async function searchExams(params: {
  subject?: string;
  grade?: number;
  exam_type?: string;
  owner_user_id?: number;
  page?: number;
  page_size?: number;
}): Promise<ExamSearchResponse> {
  const res = await api.get("/api/exams/search", { params });
  return res.data;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const res = await api.get("/api/dashboard/summary");
  return res.data;
}

export async function getExam(id: number): Promise<FullExamResponse> {
  const res = await api.get(`/api/exams/${id}`);
  return res.data;
}

export async function exportDocx(id: number, audience: "student" | "teacher" = "teacher", options: ExamExportOptions = {}): Promise<Blob> {
  const res = await api.post(`/api/exams/${id}/export-docx`, null, {
    params: { audience, ...options },
    responseType: "blob",
  });
  return res.data;
}

export async function exportPdf(id: number, audience: "student" | "teacher" = "teacher", options: ExamExportOptions = {}): Promise<Blob> {
  const res = await api.post(`/api/exams/${id}/export-pdf`, null, {
    params: { audience, ...options },
    responseType: "blob",
  });
  return res.data;
}

export async function deleteExam(id: number): Promise<{ id: number; deleted: boolean }> {
  const res = await api.delete(`/api/exams/${id}`);
  return res.data;
}

export async function duplicateExam(id: number): Promise<FullExamResponse> {
  const res = await api.post(`/api/exams/${id}/duplicate`);
  return res.data;
}

// ── Documents (Phase 2) ─────────────────────────────
export async function listDocuments(grade?: number, library?: DocumentLibrary): Promise<DocumentResponse[]> {
  const res = await api.get("/api/documents", {
    params: grade != null || library ? { grade, library } : undefined,
  });
  return res.data;
}

export async function uploadDocument(
  file: File,
  grade?: number,
  ocrMode: "auto" | "native" | "ocr" = "auto",
): Promise<DocumentDetailResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("ocr_mode", ocrMode);
  if (grade != null) form.append("grade", String(grade));
  const res = await api.post("/api/documents/upload", form);
  return res.data;
}

export async function getDocument(id: number): Promise<DocumentDetailResponse> {
  const res = await api.get(`/api/documents/${id}`);
  return res.data;
}

export async function deleteDocument(id: number): Promise<{ id: number; deleted: boolean }> {
  const res = await api.delete(`/api/documents/${id}`);
  return res.data;
}

export async function updateDocumentSharing(id: number, scope: DocumentScope, version_id: number): Promise<DocumentDetailResponse> {
  const res = await api.patch(`/api/documents/${id}/sharing`, { scope, version_id });
  return res.data;
}

export async function reviewDocumentSharing(id: number, decision: "approve" | "reject", version_id: number, note = ""): Promise<DocumentDetailResponse> {
  const res = await api.post(`/api/documents/${id}/review`, { decision, version_id, note });
  return res.data;
}

// ── Question Bank (Phase 2) ─────────────────────────
export async function listBankQuestions(
  filters: BankQuestionFilters = {},
  signal?: AbortSignal,
): Promise<BankQuestion[]> {
  const res = await api.get("/api/question-bank", { params: filters, signal });
  return res.data;
}

export async function saveQuestionsFromExam(
  examId: number,
  questionIds: string[],
  tags: string[] = [],
): Promise<SaveFromExamResponse> {
  const res = await api.post("/api/question-bank/save-from-exam", {
    exam_id: examId,
    question_ids: questionIds,
    tags,
  });
  return res.data;
}

export async function deleteBankQuestion(
  id: number,
): Promise<{ id: number; deleted: boolean }> {
  const res = await api.delete(`/api/question-bank/${id}`);
  return res.data;
}

// ── RAG (Phase 2) ───────────────────────────────────
export async function queryRag(
  query: string,
  options: { grade?: number; document_ids?: number[]; k?: number } = {},
): Promise<RagQueryResponse> {
  const res = await api.post("/api/rag/query", { query, ...options });
  return res.data;
}

// ── Auth ────────────────────────────────────────────
export interface AuthUser {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  school_id: number | null;
  avatar_url?: string | null;
  created_at: string | null;
  can_change_password: boolean;
  email_verified?: boolean;
  must_change_password?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export async function authLogin(email: string, password: string): Promise<TokenResponse> {
  const res = await api.post("/api/auth/login", { email, password });
  return res.data;
}

export interface RegistrationResponse {
  message: string;
  requires_email_verification: boolean;
}

export async function authRegister(email: string, password: string, name: string): Promise<RegistrationResponse> {
  const res = await api.post("/api/auth/register", { email, password, name });
  return res.data;
}

export async function authVerifyEmail(token: string): Promise<{ message: string }> {
  const res = await api.post("/api/auth/verify-email", { token });
  return res.data;
}

export async function authResendVerification(email: string): Promise<{ message: string }> {
  const res = await api.post("/api/auth/resend-verification", { email });
  return res.data;
}

export async function authForgotPassword(email: string): Promise<{ message: string }> {
  const res = await api.post("/api/auth/forgot-password", { email });
  return res.data;
}

export async function authResetPassword(token: string, newPassword: string): Promise<{ message: string }> {
  const res = await api.post("/api/auth/reset-password", { token, new_password: newPassword });
  return res.data;
}

export async function authGetMe(): Promise<AuthUser> {
  const res = await api.get("/api/auth/me", { timeout: 10000 });
  return res.data;
}

export async function authUpdateProfile(name: string): Promise<AuthUser> {
  const res = await api.put("/api/auth/profile", { name });
  return res.data;
}

export async function authChangePassword(currentPassword: string, newPassword: string): Promise<{
  message: string;
  access_token: string;
  token_type: string;
}> {
  const token = getToken();
  const res = await api.post("/api/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  }, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  return res.data;
}

export async function authLogout(): Promise<void> {
  const token = getToken();
  if (!token) return;
  await api.post("/api/auth/logout", undefined, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: 10000,
  });
}

export async function getOAuthConfig(): Promise<{ google: boolean; facebook: boolean }> {
  const res = await api.get("/api/auth/oauth-config");
  return res.data;
}

// ── School Admin ─────────────────────────────────────
export interface SchoolInfo {
  id: number;
  name: string;
  address: string | null;
  phone: string | null;
  created_at: string | null;
}

export async function createSchool(name: string, address?: string, phone?: string): Promise<SchoolInfo> {
  const res = await api.post("/api/admin/schools", { name, address, phone });
  return res.data;
}

export async function listSchools(): Promise<SchoolInfo[]> {
  const res = await api.get("/api/admin/schools");
  return res.data;
}

export async function updateSchool(
  id: number,
  data: { name?: string; address?: string | null; phone?: string | null },
): Promise<SchoolInfo> {
  const res = await api.put(`/api/admin/schools/${id}`, data);
  return res.data;
}

export async function getMySchool(): Promise<SchoolInfo | null> {
  const res = await api.get("/api/admin/school");
  return res.data;
}

export async function listTeachers(): Promise<AuthUser[]> {
  const res = await api.get("/api/admin/teachers");
  return res.data;
}

export async function listAdminUsers(): Promise<AuthUser[]> {
  const res = await api.get("/api/admin/users");
  return res.data;
}

export async function createManagedUser(data: {
  email: string;
  password: string;
  name: string;
  role: "school_admin" | "teacher" | "viewer";
  school_id: number | null;
}): Promise<AuthUser> {
  const res = await api.post("/api/admin/users", data);
  return res.data;
}

export async function updateAdminUserRole(
  id: number,
  role: "school_admin" | "teacher",
): Promise<AuthUser> {
  const res = await api.put(`/api/admin/users/${id}/role`, { role });
  return res.data;
}

export async function updateManagedUser(
  id: number,
  data: {
    name?: string;
    role?: "school_admin" | "teacher" | "viewer";
    school_id?: number | null;
    is_active?: boolean;
  },
): Promise<AuthUser> {
  const res = await api.put(`/api/admin/users/${id}`, data);
  return res.data;
}

export async function createTeacher(email: string, password: string, name: string): Promise<AuthUser> {
  const res = await api.post("/api/admin/teachers", { email, password, name });
  return res.data;
}

export async function assignExistingTeacher(email: string): Promise<AuthUser> {
  const res = await api.post("/api/admin/teachers/assign", { email });
  return res.data;
}

export async function updateTeacher(id: number, data: { name?: string; is_active?: boolean }): Promise<AuthUser> {
  const res = await api.put(`/api/admin/teachers/${id}`, data);
  return res.data;
}

export async function deleteTeacher(id: number): Promise<{ id: number; removed: boolean }> {
  const res = await api.delete(`/api/admin/teachers/${id}`);
  return res.data;
}

export async function resetManagedPassword(id: number, temporaryPassword: string): Promise<{ message: string }> {
  const res = await api.post(`/api/admin/users/${id}/reset-password`, { temporary_password: temporaryPassword });
  return res.data;
}

export async function transferTeacher(id: number, schoolId: number | null): Promise<AuthUser> {
  const res = await api.post(`/api/admin/teachers/${id}/transfer`, { school_id: schoolId });
  return res.data;
}

export async function deleteManagedUser(id: number): Promise<{ id: number; deleted: boolean }> {
  const res = await api.delete(`/api/admin/users/${id}`);
  return res.data;
}

export async function deleteSchool(id: number): Promise<{ id: number; deleted: boolean }> {
  const res = await api.delete(`/api/admin/schools/${id}`);
  return res.data;
}

export interface AuditLogItem {
  id: number;
  actor_user_id: number | null;
  action: string;
  target_type: string;
  target_id: number | null;
  school_id: number | null;
  details: Record<string, unknown>;
  created_at: string;
}

export async function listAuditLogs(): Promise<{ items: AuditLogItem[]; total: number }> {
  const res = await api.get("/api/admin/audit-logs", { params: { page_size: 50 } });
  return res.data;
}

// ── Axios interceptor: attach token ─────────────────
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token && !config.headers.has("Authorization")) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

function invalidateMatchingSession(authorization: unknown) {
  const token = getToken();
  // A delayed rejection for an old session must not clear a newer login.
  if (!token || authorization !== `Bearer ${token}`) return;
  removeToken();
  const hash = window.location.hash;
  const isAuthPage = hash.includes("/login") || hash.includes("/register") || hash.includes("/auth/");
  if (!isAuthPage) window.location.hash = "#/login";
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) invalidateMatchingSession(error.config?.headers?.Authorization);
    return Promise.reject(error);
  },
);

export { api };

export async function listCommunityTopics(filters: BankQuestionFilters & { page?: number }, signal?: AbortSignal): Promise<CommunityPage<CommunityTopic>> {
  return (await api.get("/api/community/topics", { params: filters, signal })).data;
}
export async function getCommunityTopic(id: number, signal?: AbortSignal): Promise<CommunityTopicDetail> {
  return (await api.get(`/api/community/topics/${id}`, { signal })).data;
}
export async function createCommunityTopic(title: string, question: CommunityQuestion): Promise<CommunityTopicDetail> {
  return (await api.post("/api/community/topics", { title, question })).data;
}
export async function publishBankQuestion(question_id: number, title: string): Promise<CommunityTopicDetail> {
  return (await api.post("/api/community/topics/from-bank", { question_id, title })).data;
}
export async function deleteCommunityTopic(id: number): Promise<void> {
  await api.delete(`/api/community/topics/${id}`);
}
export async function listCommunityComments(id: number, page = 1, signal?: AbortSignal): Promise<CommunityPage<CommunityComment>> {
  return (await api.get(`/api/community/topics/${id}/comments`, { params: { page }, signal })).data;
}
export async function addCommunityComment(id: number, body: string, parent_id?: number): Promise<{ id: number }> {
  return (await api.post(`/api/community/topics/${id}/comments`, { body, parent_id })).data;
}
export async function deleteCommunityComment(id: number, commentId: number): Promise<void> {
  await api.delete(`/api/community/topics/${id}/comments/${commentId}`);
}
export async function saveCommunityQuestion(id: number): Promise<{ id: number }> {
  return (await api.post(`/api/community/topics/${id}/save`)).data;
}

export async function searchBankQuestions(query: string, filters: BankQuestionFilters = {}, signal?: AbortSignal): Promise<BankQuestion[]> {
  const response = await api.get<{ question: BankQuestion; score: number }[]>("/api/question-bank/search/semantic", { params: { query, grade: filters.grade, type: filters.type, difficulty: filters.difficulty }, signal });
  return response.data.map(hit => hit.question);
}

export async function bankEditTemplate(examId: number, questionId: string, bankId: number, version: number): Promise<import("../components/QuestionEditor").QuestionEditPayload> {
  return (await api.get(`/api/exams/${examId}/questions/${questionId}/bank-template/${bankId}`, { params: { version_id: version } })).data;
}
