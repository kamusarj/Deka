const difficultyLabels: Record<string, string> = {
  nhan_biet: "Nhận biết",
  thong_hieu: "Thông hiểu",
  van_dung: "Vận dụng",
};

const questionTypeLabels: Record<string, string> = {
  multiple_choice: "Trắc nghiệm",
  true_false: "Đúng/Sai",
  short_answer: "Trả lời ngắn",
  essay: "Tự luận",
};

const sourceTypeLabels: Record<string, string> = {
  local_json: "Dữ liệu chương trình",
  uploaded_file: "Tài liệu upload",
  rag_retrieval: "Truy xuất tài liệu",
  question_bank: "Ngân hàng câu hỏi",
  manual_input: "Nhập thủ công",
};

const reviewStatusLabels: Record<string, string> = {
  pending: "Chờ duyệt",
  accepted: "Đã duyệt",
  needs_revision: "Cần sửa",
  rejected: "Từ chối",
};

export function formatDifficulty(value: string): string {
  return difficultyLabels[value] ?? value;
}

export function formatQuestionType(value: string): string {
  return questionTypeLabels[value] ?? value;
}

export function formatSourceType(value: string): string {
  return sourceTypeLabels[value] ?? value;
}

export function formatReviewStatus(value: string): string {
  return reviewStatusLabels[value] ?? value;
}
