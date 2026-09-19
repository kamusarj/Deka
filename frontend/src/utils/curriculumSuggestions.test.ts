import { describe, expect, it } from "vitest";
import { curriculumAfterCollection } from "./curriculumSuggestions";
import type { CurriculumItem } from "../types";

const manual: CurriculumItem[] = [{
  topic: "Chủ đề giáo viên nhập",
  periods: 3,
  achievements: ["Yêu cầu riêng"],
}];
const suggested: CurriculumItem[] = [{
  topic: "Chủ đề hệ thống gợi ý",
  periods: 5,
  achievements: ["Yêu cầu gợi ý"],
}];

describe("curriculumAfterCollection", () => {
  it("preserves teacher-edited curriculum", () => {
    expect(curriculumAfterCollection(manual, suggested, true)).toBe(manual);
  });

  it("applies suggestions before the teacher edits", () => {
    expect(curriculumAfterCollection(manual, suggested, false)).toBe(suggested);
  });
});
