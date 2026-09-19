import type { ExamPayload } from "../types";

export function createDefaultExamPayload(): ExamPayload {
  return {
    school: "THCS Nguyễn Du",
    grade: 8,
    subject: "Khoa học tự nhiên",
    exam_type: "Giữa học kì I",
    duration_minutes: 45,
    school_year: "2025-2026",
    total_score: 10,
    curriculum: [
      { topic: "Hệ tuần hoàn ở người", periods: 6, achievements: ["Mô tả được cấu tạo và chức năng của tim người."] },
      { topic: "Hô hấp ở người", periods: 5, achievements: ["Giải thích được vai trò của hệ hô hấp đối với cơ thể"] },
      { topic: "Mol và tỉ khối chất khí", periods: 4, achievements: ["Tính được khối lượng mol từ công thức hóa học."] },
    ],
    difficulty_ratio: { nhan_biet: 30, thong_hieu: 40, van_dung: 30 },
    question_types: {
      multiple_choice: { enabled: true, count: 8, score_per_question: 0.25 },
      true_false: { enabled: true, count: 4, score_per_question: 1 },
      short_answer: { enabled: true, count: 2, score_per_question: 0.5 },
      essay: { enabled: true, count: 2, score_per_question: 1.5 },
    },
    calculation_requirement: { count: 2, score_per_question: 0.5, difficulties: ["thong_hieu", "van_dung"] },
    auto_distribute_scores: true,
    allow_provider_fallback: false,
    variant_count: 4,
  };
}

export interface ExamFormDraftData {
  payload: ExamPayload;
  calculationCountInput: string;
  curriculumEdited: boolean;
  selectedDocIds: number[];
}

interface StoredExamFormDraft {
  version: 1;
  scope: string;
  updatedAt: string;
  data: ExamFormDraftData;
}

export function examFormDraftKey(scope: string): string {
  return `smart-exam:create-form:v1:${scope}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// Validate storage structure, not submission rules: incomplete/invalid edits
// must survive. Rebuild known fields so unrelated stored properties stay out.
function parseShape(value: unknown, shape: unknown): unknown {
  if (Array.isArray(shape)) {
    if (!Array.isArray(value)) throw new Error("Expected array");
    return value.map((item) => parseShape(item, shape[0]));
  }
  if (isRecord(shape)) {
    if (!isRecord(value)) throw new Error("Expected object");
    return Object.fromEntries(Object.entries(shape).map(([key, example]) => [key, parseShape(value[key], example)]));
  }
  if (typeof value !== typeof shape || (typeof value === "number" && !Number.isFinite(value))) {
    throw new Error("Invalid draft field");
  }
  return value;
}

export function readExamFormDraft(scope: string): { draft: StoredExamFormDraft | null; warning: string } {
  try {
    const raw = localStorage.getItem(examFormDraftKey(scope));
    if (!raw) return { draft: null, warning: "" };
    const stored: unknown = JSON.parse(raw);
    if (!isRecord(stored) || stored.version !== 1 || stored.scope !== scope ||
      typeof stored.updatedAt !== "string" || !Number.isFinite(Date.parse(stored.updatedAt)) || !isRecord(stored.data)) {
      throw new Error("Invalid draft envelope");
    }
    const data = stored.data;
    const payload = parseShape(data.payload, createDefaultExamPayload()) as ExamPayload;
    if (!payload.calculation_requirement.difficulties.every((value) =>
      value === "nhan_biet" || value === "thong_hieu" || value === "van_dung") ||
      typeof data.calculationCountInput !== "string" || typeof data.curriculumEdited !== "boolean" ||
      !Array.isArray(data.selectedDocIds) || !data.selectedDocIds.every((id) => Number.isSafeInteger(id) && id > 0)) {
      throw new Error("Invalid draft controls");
    }
    // A restored form must never change the existing primary-only generation policy.
    payload.allow_provider_fallback = false;
    return {
      draft: {
        version: 1, scope, updatedAt: stored.updatedAt,
        data: { payload, calculationCountInput: data.calculationCountInput, curriculumEdited: data.curriculumEdited, selectedDocIds: [...new Set(data.selectedDocIds)] },
      },
      warning: "",
    };
  } catch {
    return { draft: null, warning: "Không khôi phục được bản nháp cũ. Bạn có thể tiếp tục với mẫu đề mặc định." };
  }
}

export function writeExamFormDraft(scope: string, data: ExamFormDraftData): string {
  const updatedAt = new Date().toISOString();
  const stored: StoredExamFormDraft = { version: 1, scope, updatedAt, data };
  localStorage.setItem(examFormDraftKey(scope), JSON.stringify(stored));
  return updatedAt;
}

export function removeExamFormDraft(scope: string): void {
  localStorage.removeItem(examFormDraftKey(scope));
}
