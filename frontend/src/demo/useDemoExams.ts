import { useEffect, useState } from "react";
import type { DemoExam } from "./data";
import { readExams, storageKey } from "./storage";

export function useDemoExams() {
  const [initialState] = useState(readExams);
  const [exams, setExams] = useState(initialState.exams);
  const [storageUnavailable, setStorageUnavailable] = useState(
    initialState.readFailed,
  );

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(exams));
      setStorageUnavailable(initialState.readFailed);
    } catch {
      setStorageUnavailable(true);
    }
  }, [exams, initialState.readFailed]);

  function create(exam: DemoExam) {
    setExams((current) => [exam, ...current]);
  }

  function update(exam: DemoExam) {
    setExams((current) =>
      current.map((item) => (item.id === exam.id ? exam : item)),
    );
  }

  function duplicate(exam: DemoExam): DemoExam {
    const copy = {
      ...exam,
      id: `demo-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      title: `${exam.title} (bản sao)`,
      createdAt: new Date().toISOString(),
      questions: exam.questions.map((question) => ({
        ...question,
        options: question.options ? [...question.options] : undefined,
      })),
    };
    create(copy);
    return copy;
  }

  return { exams, storageUnavailable, create, update, duplicate };
}
