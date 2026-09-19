import type { CurriculumItem } from "../types";

export function curriculumAfterCollection(
  current: CurriculumItem[],
  suggestions: CurriculumItem[],
  hasTeacherEdits: boolean,
): CurriculumItem[] {
  return hasTeacherEdits ? current : suggestions;
}
