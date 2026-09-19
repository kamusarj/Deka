// ── Shared TypeScript types for Smart Exam Matrix AI ──
// Maps to backend schemas defined in backend/app/schemas/exam.py

// ── Difficulty & Question Types ──────────────────────
export type Difficulty = "nhan_biet" | "thong_hieu" | "van_dung";

export type QuestionType =
  | "multiple_choice"
  | "true_false"
  | "short_answer"
  | "essay";

export type ReviewStatus = "pending" | "accepted" | "needs_revision" | "rejected";
export type PublicationStatus = "verified" | "draft";

// ── Curriculum & Exam Input ─────────────────────────
export interface CurriculumItem {
  topic: string;
  periods: number;
  achievements: string[];
}

export interface DifficultyRatio {
  nhan_biet: number;
  thong_hieu: number;
  van_dung: number;
}

export interface QuestionTypeConfig {
  enabled: boolean;
  count: number;
  score_per_question: number;
}

export interface QuestionTypes {
  multiple_choice: QuestionTypeConfig;
  true_false: QuestionTypeConfig;
  short_answer: QuestionTypeConfig;
  essay: QuestionTypeConfig;
}

export interface CalculationRequirement {
  count: number;
  score_per_question: number;
  difficulties: Difficulty[];
}

export interface ExamInput {
  school: string;
  grade: number;
  subject: string;
  exam_type: string;
  duration_minutes: number;
  school_year: string;
  total_score: number;
}

export interface ExamPayload extends ExamInput {
  curriculum: CurriculumItem[];
  difficulty_ratio: DifficultyRatio;
  question_types: QuestionTypes;
  calculation_requirement: CalculationRequirement;
  auto_distribute_scores: boolean;
  allow_provider_fallback: boolean;
  variant_count: number;
  use_uploaded_docs?: number[];
}

// ── Documents (Phase 2) ─────────────────────────────
export type DocumentScope = "private" | "school" | "system";
export type DocumentLibrary = "all" | "mine" | "school" | "system" | "pending";

export interface DocumentResponse {
  id: number;
  owner_user_id?: number | null;
  school_id?: number | null;
  sharing_scope?: DocumentScope;
  sharing_status?: "none" | "pending" | "approved" | "rejected";
  review_note?: string;
  reviewed_at?: string | null;
  version_id?: number;
  can_manage?: boolean;
  can_share_school?: boolean;
  can_review?: boolean;
  filename: string;
  file_type: string;
  size: number;
  status: string;
  grade?: number | null;
  text_preview: string;
  text_length: number;
  parsed_data?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface DocumentDetailResponse extends DocumentResponse {
  extracted_text: string;
}

export interface AiProviderStatus {
  provider: string;
  model: string;
  verify_model: string;
  configured: boolean;
  key_exposed: false;
  priority: number;
  role: "primary" | "fallback";
}

export type AiProvider = "openai" | "gemini" | "deepseek";

export interface AiProvidersResponse {
  effective_config?: { primary_only_model: string; review_mode: string; embedding_model: string; default_provider_override: string; tier_overrides: Record<string, string> };
  configuration_source?: "environment" | "process";
  active_provider: AiProvider;
  providers: AiProviderStatus[];
}

export interface AiModelInfo {
  suggested: string[];
  current: string;
  current_verify: string;
}

export type AiModelsResponse = Record<string, AiModelInfo>;

// ── Question Bank (Phase 2) ─────────────────────────
export interface BankQuestion {
  rich_content?: RichBlock[] | null;
  content_metadata?: Record<string, unknown> | null;
  can_publish?: boolean;
  id: number;
  content: string;
  type: QuestionType;
  difficulty: Difficulty;
  topic?: string | null;
  grade?: number | null;
  subject: string;
  tags: string[];
  options?: unknown;
  statements?: unknown;
  sub_questions?: unknown;
  answer?: Record<string, unknown> | null;
  source?: QuestionSource | null;
  usage_count: number;
  rating?: number | null;
  created_at?: string | null;
}

export interface BankQuestionFilters {
  grade?: number;
  subject?: string;
  topic?: string;
  type?: QuestionType;
  difficulty?: Difficulty;
  search?: string;
}

export interface SaveFromExamResponse {
  duplicate_findings?: Pick<DuplicateFinding, "matched_question_id" | "reason" | "severity">[];
  saved: BankQuestion[];
  count: number;
  message: string;
}

// ── RAG (Phase 2) ───────────────────────────────────
export interface RagHit {
  id: string;
  text: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface RagQueryResponse {
  query: string;
  hits: RagHit[];
  count: number;
}

// ── Matrix ──────────────────────────────────────────
export interface MatrixCell {
  count: number;
  score: number;
  question_type: string | null;
  question_ids?: string[];
}

export interface MatrixRow {
  id: string;
  topic_id: string;
  topic_name: string;
  lesson_id: string;
  lesson_name: string;
  nhan_biet: MatrixCell;
  thong_hieu: MatrixCell;
  van_dung: MatrixCell;
  total_score: number;
}

export interface MatrixSummary {
  nhan_biet: { total_count: number; total_score: number; percentage: number };
  thong_hieu: { total_count: number; total_score: number; percentage: number };
  van_dung: { total_count: number; total_score: number; percentage: number };
  total_score: number;
  total_questions?: number;
  auto_distribute_scores?: boolean;
  score_increment?: number | null;
  calculation_requirement?: {
    required_count: number;
    actual_count: number;
    score_per_question: number;
    requested_difficulties?: Difficulty[];
    actual_difficulties?: Difficulty[];
    actual_scores?: number[];
    total_score: number;
    question_ids: string[];
  };
}

// ── Specification ───────────────────────────────────
export interface SpecificationItem {
  question_id: string;
  question_number: number;
  question_type: QuestionType;
  difficulty: Difficulty;
  score: number;
  topic: string;
  lesson: string;
  knowledge_unit: string;
  achievement: string;
  bloom_level: string;
  content_hint?: string;
  variant_note?: string;
  requires_calculation?: boolean;
}

// ── Questions ───────────────────────────────────────
export interface QuestionOption {
  [key: string]: string; // "A": "...", "B": "...", etc.
}

export interface Statement {
  id: string;
  content: string;
  is_true: boolean;
}

export interface QuestionMetadata {
  teacher_edited?: boolean;
  revision?: number;
  edited_at?: string;
  topic: string;
  lesson: string;
  knowledge_unit: string;
  achievement: string;
  bloom_level: string;
  is_calculation?: boolean;
  calculation_verified?: boolean;
}

export interface QuestionSource {
  source_type: string;
  source_name: string;
  confidence_score: number;
  source_page?: number | null;
  source_section?: string | null;
  source_excerpt?: string | null;
  doc_id?: number | null;
  retrieved_chunk_id?: string;
}

export interface Question {
  rich_content?: RichBlock[] | null;
  id: string;
  original_id?: string;
  number: number;
  type: QuestionType;
  difficulty: Difficulty;
  score: number;
  content: string;
  options?: QuestionOption;
  statements?: Statement[];
  sub_questions?: { id: string; content: string; score: number }[];
  metadata: QuestionMetadata;
  source?: QuestionSource;
  correct_answer?: string;
}

export interface DiagramObject {
  type: "line" | "circle" | "rectangle" | "text" | "polyline";
  x?: number; y?: number; x2?: number; y2?: number;
  width?: number; height?: number; radius?: number; text?: string;
  points?: { x: number; y: number }[];
}

export interface DiagramSpec {
  type: "drawing";
  width: number;
  height: number;
  objects: DiagramObject[];
}

export type RichBlock =
  | { type: "text"; content: string }
  | { type: "latex"; content: string; display: "inline" | "block" }
  | { type: "table"; headers: string[]; rows: string[][]; caption?: string }
  | { type: "image"; src: string; alt: string; caption?: string }
  | { type: "diagram"; spec: DiagramSpec; alt: string; caption?: string };

export interface VerificationIssue {
  severity: "critical" | "major" | "medium";
  type: string;
  description: string;
  suggestion: string;
}

export interface QuestionVerificationReport {
  question_id: string;
  question_number: number;
  verification_score: number | null;
  status: "approved" | "needs_review" | "not_verified";
  issues: VerificationIssue[];
  verification_error?: string;
}

export interface VerificationReport {
  overall_score: number | null;
  overall_status: string;
  summary: { total_questions: number; auto_approved: number; needs_review: number; auto_rejected: number; not_verified?: number };
  question_reports: QuestionVerificationReport[];
  action_required: { priority: string; question_id: string; message: string; fix: string }[];
  reviewer_summary?: {
    mode: "dual_mandatory" | "deepseek_only";
    reviewers: { label: string; provider: string; model: string }[];
    consensus_questions: number;
    reviewed_questions?: number;
    disagreement_questions: number;
    unavailable_questions: number;
    total_questions: number;
  };
}

// ── Answers & Rubric ────────────────────────────────
export type ExportDocument = "exam" | "answers" | "matrix" | "specification";

export interface ExamExportOptions {
  document?: ExportDocument;
  variant_code?: string;
}

export interface AnswerCitation {
  source_type: string;
  source_name: string;
  source_page?: number | null;
  source_section?: string | null;
  excerpt?: string | null;
  doc_id?: number | null;
  retrieved_chunk_id?: string;
  verification_status?: "verified" | "unverified" | "rejected";
  verification_reason?: string;
  verified_against?: "curriculum_record" | "retrieved_chunk";
}

export interface Answer {
  question_id: string;
  question_number: number;
  type: QuestionType;
  correct_answer?: string;
  explanation?: string;
  option_explanations?: Record<string, string>;
  citations?: AnswerCitation[];
  answers?: { statement_id: string; is_true: boolean; explanation: string; citations?: AnswerCitation[] }[];
  keywords?: string[];
  accept_variations?: boolean;
  model_answer?: string;
  key_points?: string[];
}

export interface RubricLevel {
  score: number;
  description: string;
  criteria: string;
}

export interface RubricCriterion {
  id: string;
  name: string;
  max_score: number;
  levels: RubricLevel[];
}

export interface RubricItem {
  question_id: string;
  question_number: number;
  type: QuestionType;
  total_score: number;
  criteria: RubricCriterion[];
  grading_guide: string[];
}

// ── Validation ──────────────────────────────────────
export interface ValidationCheck {
  name: string;
  category?: "format" | "content" | "matrix" | "rubric";
  severity?: "critical" | "major" | "medium" | "low";
  passed: boolean;
  expected?: unknown;
  actual?: unknown;
  message: string;
}

export interface ValidationResult {
  duplicate_report?: DuplicateReport;
  passed: boolean;
  score: number;
  checks: ValidationCheck[];
  warnings: string[];
  errors: string[];
  verification_report?: VerificationReport;
  persistence?: {
    status: PublicationStatus;
    publishable: boolean;
    failure_stage?: string;
    message?: string;
    gate_message?: string;
    question_failures?: Record<string, string[]>;
    errors?: string[];
  };
  deterministic_passed?: boolean;
}

export interface DuplicateFinding {
  question_id: string;
  question_number?: number;
  matched_question_id: string;
  scope: "exam" | "bank";
  duplicate_type: "exact" | "fuzzy" | "semantic";
  is_duplicate: boolean;
  confidence: number;
  severity: "ERROR" | "WARNING" | "INFO";
  reason: string;
}

export interface DuplicateReport {
  findings: DuplicateFinding[];
  semantic_available: boolean;
}

// ── Review ──────────────────────────────────────────
export interface QuestionReview {
  status: ReviewStatus;
  regenerated?: boolean;
  reason?: string;
  reviewed_at?: string;
  reviewed_by?: string;
  comment?: string;
}

export interface ReviewStatusMap {
  [question_id: string]: QuestionReview;
}

// ── Resource Package ────────────────────────────────
export interface ResourcePackage {
  curriculum_suggestions: {
    topic: string;
    periods: number;
    knowledge_units?: string[];
    achievements: string[];
  }[];
  sample_questions: {
    total_questions: number;
  };
  variant_count?: number;
  sample_matrix?: unknown;
  difficulty_guidelines?: unknown;
  raw_data?: {
    curriculum_file?: string;
    [key: string]: unknown;
  };
}

// ── Full Exam Response ──────────────────────────────
export interface FullExamResponse {
  /** Display order within the owner's remaining exams; use id for API calls. */
  exam_number?: number | null;
  version_id?: number;
  id: number | null;
  owner_user_id?: number | null;
  school_id?: number | null;
  publication_status?: PublicationStatus;
  exam_info: {
    school: string;
    grade: number;
    subject: string;
    exam_type: string;
    duration_minutes: number;
    school_year: string;
    total_score: number;
    variant_count?: number;
  };
  matrix: MatrixRow[];
  summary: MatrixSummary;
  specification: SpecificationItem[];
  questions: Question[];
  answer_key: Answer[];
  rubric: RubricItem[];
  validation: ValidationResult;
  resource_package?: ResourcePackage | null;
  review_status: ReviewStatusMap;
  variants?: ExamVariant[];
  created_at?: string | null;
}

export interface ExamVariant {
  code: string;
  questions: Question[];
  answer_key: Answer[];
}

// ── API Request/Response types ──────────────────────
export interface CollectResourcesRequest {
  grade: number;
  subject: string;
  exam_type: string;
}

export interface CollectResourcesResponse {
  resource_package: ResourcePackage;
}

export interface ReviewQuestionsRequest {
  accepted_question_ids: string[];
  needs_revision_question_ids: string[];
  rejected_question_ids: string[];
}

export interface RegenerateQuestionsRequest {
  exam_id: number;
  question_ids: string[];
  reason: string;
  allow_provider_fallback: boolean;
}

export interface RegenerateQuestionsResponse extends FullExamResponse {
  regenerated_question_ids: string[];
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

// ── Flat Exam Response (from list endpoint) ─────────
export interface ExamResponse {
  exam_number?: number | null;
  id: number;
  owner_user_id?: number | null;
  school_id?: number | null;
  publication_status?: PublicationStatus;
  school: string;
  grade: number;
  subject: string;
  exam_type: string;
  duration_minutes: number;
  school_year: string;
  total_score: number;
  matrix: MatrixRow[];
  summary: MatrixSummary;
  specification: SpecificationItem[];
  questions: Question[];
  answer_key: Answer[];
  rubric: RubricItem[];
  validation: ValidationResult;
  resource_package?: ResourcePackage | null;
  review_status: ReviewStatusMap;
  created_at: string;
}

export interface ExamListItem {
  exam_number?: number | null;
  id: number;
  school: string;
  grade: number;
  subject: string;
  exam_type: string;
  duration_minutes: number;
  school_year: string;
  total_score: number;
  owner_user_id: number | null;
  owner_name: string | null;
  school_id: number | null;
  publication_status?: PublicationStatus;
  created_at: string;
}

export interface ExamSearchResponse {
  items: ExamListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardSummary {
  role: string;
  scope_label: string;
  exams: number;
  questions: number;
  documents: number;
  bank_questions: number;
  schools?: number | null;
  users?: number | null;
  teachers?: number | null;
  recent_exam_ids: number[];
}

// ── Pipeline Progress (SSE) ──────────────────────────
export type PipelineStageId =
  | "collect_resources"
  | "generate_matrix"
  | "generate_specification"
  | "apply_rag"
  | "generate_questions"
  | "validate"
  | "verify"
  | "persist"
  | "build_variants"
  | "done"
  | "error";

export type PipelineStageStatus = "pending" | "running" | "completed" | "skipped" | "error";

export interface PipelineStageEvent {
  stage: PipelineStageId;
  status: PipelineStageStatus;
  message: string;
  data?: Record<string, unknown>;
}

export interface PipelineStageInfo {
  id: PipelineStageId;
  label: string;
  icon: string;
  status: PipelineStageStatus;
  message: string;
}

export const PIPELINE_STAGES: Omit<PipelineStageInfo, "status" | "message">[] = [
  { id: "collect_resources", label: "Thu thập tài liệu", icon: "📡" },
  { id: "generate_matrix", label: "Tạo ma trận", icon: "📊" },
  { id: "generate_specification", label: "Tạo đặc tả", icon: "📋" },
  { id: "apply_rag", label: "Truy xuất RAG", icon: "🔍" },
  { id: "generate_questions", label: "Sinh câu hỏi", icon: "🤖" },
  { id: "validate", label: "Kiểm tra đề", icon: "✅" },
  { id: "verify", label: "Kiểm chứng AI", icon: "🔬" },
  { id: "persist", label: "Lưu đề", icon: "💾" },
  { id: "build_variants", label: "Tạo mã đề", icon: "📄" },
];

export type CommunityQuestion = Pick<BankQuestion, "content" | "type" | "difficulty" | "grade" | "subject" | "tags" | "options" | "statements" | "sub_questions" | "answer" | "topic">;
export interface CommunityAuthor { id: number | null; name: string }
export interface CommunityTopic {
  id: number; title: string; preview: string; grade?: number | null;
  type: QuestionType; difficulty: Difficulty; author: CommunityAuthor;
  created_at: string; can_manage: boolean; comment_count: number;
}
export interface CommunityTopicDetail extends CommunityTopic { question: CommunityQuestion }
export interface CommunityComment {
  id: number; parent_id: number | null; body: string | null; deleted: boolean;
  author: CommunityAuthor; created_at: string; can_manage: boolean;
}
export interface CommunityPage<T> { items: T[]; total: number; page: number; page_size: number }
