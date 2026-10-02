import { isDemoExam, seedExam, type DemoExam } from "./data";

export const storageKey = "deka-public-demo-v1";

export function readExams(): { exams: DemoExam[]; readFailed: boolean } {
  let stored: string | null;
  try {
    stored = localStorage.getItem(storageKey);
  } catch {
    return { exams: [seedExam], readFailed: true };
  }

  try {
    const value: unknown = JSON.parse(stored || "null");
    if (
      Array.isArray(value) &&
      value.length > 0 &&
      value.every(isDemoExam) &&
      new Set(value.map((exam) => exam.id)).size === value.length
    ) {
      return { exams: value, readFailed: false };
    }
  } catch {
    // A malformed saved demo can be replaced without disabling persistence.
  }
  return { exams: [seedExam], readFailed: false };
}
