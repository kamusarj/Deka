import type { QuestionType } from "../types";

export const QUESTION_TYPE_SECTIONS: ReadonlyArray<{
  type: QuestionType;
  part?: string;
  label: string;
  heading: string;
}> = [
  {
    type: "multiple_choice",
    part: "Phần I",
    label: "Nhiều lựa chọn",
    heading: "Phần I. Câu trắc nghiệm nhiều phương án lựa chọn",
  },
  {
    type: "true_false",
    part: "Phần II",
    label: "Đúng/Sai",
    heading: "Phần II. Câu trắc nghiệm đúng sai",
  },
  {
    type: "short_answer",
    part: "Phần III",
    label: "Trả lời ngắn",
    heading: "Phần III. Câu trắc nghiệm trả lời ngắn",
  },
  {
    type: "essay",
    label: "Tự luận",
    heading: "Tự luận",
  },
];
