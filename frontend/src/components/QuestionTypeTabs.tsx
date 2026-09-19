import type { Question, QuestionType } from "../types";
import { QUESTION_TYPE_SECTIONS } from "./questionTypeSections";

export type QuestionTypeFilter = "all" | QuestionType;

interface QuestionTypeTabsProps {
  questions: Question[];
  value: QuestionTypeFilter;
  onChange: (value: QuestionTypeFilter) => void;
}

export default function QuestionTypeTabs({
  questions,
  value,
  onChange,
}: QuestionTypeTabsProps) {
  const counts = questions.reduce<Partial<Record<QuestionType, number>>>((result, question) => {
    result[question.type] = (result[question.type] ?? 0) + 1;
    return result;
  }, {});
  const available = QUESTION_TYPE_SECTIONS.filter((section) => counts[section.type]);

  if (questions.length === 0) return null;

  return (
    <div className="question-type-tabs" role="tablist" aria-label="Lọc câu hỏi theo phần">
      <button
        type="button"
        role="tab"
        aria-label={`Tất cả · ${questions.length} câu`}
        aria-selected={value === "all"}
        aria-controls="exam-question-list"
        className={`question-type-tab ${value === "all" ? "is-active" : ""}`}
        onClick={() => onChange("all")}
      >
        <span>Tất cả</span>
        <span className="question-type-count">{questions.length}</span>
      </button>
      {available.map((section) => (
        <button
          key={section.type}
          type="button"
          role="tab"
          aria-label={`${section.part ? `${section.part}. ` : ""}${section.label} · ${counts[section.type]} câu`}
          aria-selected={value === section.type}
          aria-controls="exam-question-list"
          className={`question-type-tab ${value === section.type ? "is-active" : ""}`}
          onClick={() => onChange(section.type)}
        >
          {section.part && <span className="question-type-part">{section.part} · </span>}
          <span>{section.label}</span>
          <span className="question-type-count">{counts[section.type]}</span>
        </button>
      ))}
    </div>
  );
}
