import type { DemoQuestion } from "./data";

export const typeLabel: Record<DemoQuestion["type"], string> = {
  multiple_choice: "Trắc nghiệm",
  true_false: "Đúng / Sai",
  short_answer: "Trả lời ngắn",
  essay: "Tự luận",
};
