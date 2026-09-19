import { useLayoutEffect, useRef, useState } from "react";
import { writeExamFormDraft, type ExamFormDraftData } from "../utils/examFormDraft";

export function useExamFormAutosave(scope: string, data: ExamFormDraftData, initialSavedAt: string | null) {
  const [savedAt, setSavedAt] = useState(initialSavedAt);
  const [saveError, setSaveError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const lastSaved = useRef(initialSavedAt ? JSON.stringify(data) : null);

  useLayoutEffect(() => {
    const serialized = JSON.stringify(data);
    if (lastSaved.current === serialized) {
      setSaveError(false);
      return;
    }
    try {
      const updatedAt = writeExamFormDraft(scope, data);
      lastSaved.current = serialized;
      setSavedAt(updatedAt);
      setSaveError(false);
    } catch {
      setSaveError(true);
    }
  }, [scope, data, attempt]);

  return { savedAt, saveError, retrySave: () => setAttempt((value) => value + 1) };
}
