import { useState } from "react";
import type { Answer, Question, RubricCriterion, RubricItem, RichBlock } from "../types";
import BankReusePicker from "./BankReusePicker";
import RichContentEditor from "./RichContentEditor";
import SelectControl from "./SelectControl";
import { getApiErrorMessage } from "../utils/apiError";

export interface QuestionEditPayload {
  bank_question_id?: number;
  rich_content?: RichBlock[];
  version_id: number;
  content: string;
  options?: Record<string, string>;
  correct_answer?: string;
  explanation: string;
  option_explanations?: Record<string, string>;
  statements?: { id: string; content: string; is_true: boolean; explanation: string }[];
  sub_questions?: { id: string; content: string; score: number }[];
  model_answer?: string;
  rubric_criteria?: RubricCriterion[];
}

interface Props {
  examId?: number | null;
  question: Question;
  answer?: Answer;
  rubric?: RubricItem;
  version: number;
  onSave: (payload: QuestionEditPayload) => Promise<unknown>;
  onCancel: () => void;
}

export default function QuestionEditor({ question, answer, rubric, version, onSave, onCancel, examId }: Props) {
  const [draft, setDraft] = useState<QuestionEditPayload>(() => ({
    version_id: version,
    rich_content: structuredClone(question.rich_content ?? []),
    content: question.content,
    explanation: answer?.explanation ?? "",
    ...(question.type === "multiple_choice" ? {
      options: { ...question.options }, correct_answer: answer?.correct_answer ?? question.correct_answer ?? "A",
      option_explanations: { ...answer?.option_explanations },
    } : {}),
    ...(question.type === "true_false" ? {
      statements: (question.statements ?? []).map((item) => ({ ...item, explanation: answer?.answers?.find((value) => value.statement_id === item.id)?.explanation ?? "" })),
    } : {}),
    ...(question.type === "short_answer" ? { correct_answer: answer?.correct_answer ?? question.correct_answer ?? "" } : {}),
    ...(question.type === "essay" ? {
      model_answer: answer?.model_answer ?? "",
      sub_questions: (question.sub_questions ?? []).map((item) => ({ ...item })),
      rubric_criteria: structuredClone(rubric?.criteria ?? []),
    } : {}),
  }));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const updateCriterion = (index: number, change: Partial<RubricCriterion>) => {
    setDraft((current) => ({ ...current, rubric_criteria: current.rubric_criteria?.map((item, position) => position === index ? { ...item, ...change } : item) }));
  };

  return <form className="question-editor" aria-label={`Sửa câu ${question.number}`} onSubmit={async (event) => {
    event.preventDefault();
    setPending(true); setError("");
    try { await onSave(draft); onCancel(); }
    catch (failure) { setError(getApiErrorMessage(failure, "Không lưu được chỉnh sửa")); }
    finally { setPending(false); }
  }}>
    <fieldset disabled={pending}>
      <legend>Chỉnh sửa câu {question.number}</legend>
      {examId && <BankReusePicker examId={examId} question={question} version={draft.version_id} onChoose={payload => setDraft(payload)} />}
      <label>Nội dung câu hỏi<textarea required value={draft.content} onChange={(event) => setDraft({ ...draft, content: event.target.value })} /></label>
      <RichContentEditor blocks={draft.rich_content ?? []} disabled={pending} onChange={(blocks) => setDraft({ ...draft, rich_content: blocks })} />
      {question.type === "multiple_choice" && <>
        {["A", "B", "C", "D"].map((key) => <div key={key}>
          <label>Phương án {key}<textarea required value={draft.options?.[key] ?? ""} onChange={(event) => setDraft({ ...draft, options: { ...draft.options, [key]: event.target.value } })} /></label>
          <label>Giải thích phương án {key}<textarea required value={draft.option_explanations?.[key] ?? ""} onChange={(event) => setDraft({ ...draft, option_explanations: { ...draft.option_explanations, [key]: event.target.value } })} /></label>
        </div>)}
        <label>Đáp án đúng<SelectControl
          ariaLabel="Đáp án đúng"
          value={draft.correct_answer ?? "A"}
          disabled={pending}
          onChange={(correct_answer) => setDraft({ ...draft, correct_answer })}
          options={["A", "B", "C", "D"].map((key) => ({ value: key, label: key }))}
        /></label>
      </>}
      {question.type === "true_false" && draft.statements?.map((statement, index) => <fieldset key={statement.id}>
        <legend>Phát biểu {index + 1}</legend>
        <label>Nội dung phát biểu {index + 1}<textarea required value={statement.content} onChange={(event) => setDraft({ ...draft, statements: draft.statements?.map((item, position) => position === index ? { ...item, content: event.target.value } : item) })} /></label>
        <label className="checkline"><input type="checkbox" checked={statement.is_true} onChange={(event) => setDraft({ ...draft, statements: draft.statements?.map((item, position) => position === index ? { ...item, is_true: event.target.checked } : item) })} />Phát biểu {index + 1} đúng</label>
        <label>Giải thích phát biểu {index + 1}<textarea required value={statement.explanation} onChange={(event) => setDraft({ ...draft, statements: draft.statements?.map((item, position) => position === index ? { ...item, explanation: event.target.value } : item) })} /></label>
      </fieldset>)}
      {question.type === "short_answer" && <label>Đáp án dự kiến<input required value={draft.correct_answer} onChange={(event) => setDraft({ ...draft, correct_answer: event.target.value })} /></label>}
      {question.type === "essay" && <>
        <label>Đáp án mẫu<textarea required value={draft.model_answer} onChange={(event) => setDraft({ ...draft, model_answer: event.target.value })} /></label>
        {draft.sub_questions?.map((item, index) => <fieldset key={item.id}>
          <legend>Ý {index + 1}</legend>
          <label>Nội dung ý {index + 1}<textarea required value={item.content} onChange={(event) => setDraft({ ...draft, sub_questions: draft.sub_questions?.map((value, position) => position === index ? { ...value, content: event.target.value } : value) })} /></label>
          <label>Điểm ý {index + 1}<input type="number" step="0.25" min="0.25" required value={item.score} onChange={(event) => setDraft({ ...draft, sub_questions: draft.sub_questions?.map((value, position) => position === index ? { ...value, score: Number(event.target.value) } : value) })} /></label>
        </fieldset>)}
        {draft.rubric_criteria?.map((item, index) => <fieldset key={item.id}>
          <legend>Tiêu chí chấm {index + 1}</legend>
          <label>Tên tiêu chí {index + 1}<input required value={item.name} onChange={(event) => updateCriterion(index, { name: event.target.value })} /></label>
          <label>Điểm tối đa tiêu chí {index + 1}<input type="number" min="0.25" step="0.25" required value={item.max_score} onChange={(event) => updateCriterion(index, { max_score: Number(event.target.value) })} /></label>
          {item.levels.map((level, position) => <div key={position}>
            <label>Mô tả mức {position + 1}, tiêu chí {index + 1}<textarea required value={level.description} onChange={(event) => updateCriterion(index, { levels: item.levels.map((value, levelIndex) => levelIndex === position ? { ...value, description: event.target.value } : value) })} /></label>
            <label>Điểm mức {position + 1}, tiêu chí {index + 1}<input type="number" min="0" max={item.max_score} step="0.25" required value={level.score} onChange={(event) => updateCriterion(index, { levels: item.levels.map((value, levelIndex) => levelIndex === position ? { ...value, score: Number(event.target.value) } : value) })} /></label>
          </div>)}
        </fieldset>)}
      </>}
      {question.type !== "true_false" && <label>Lời giải<textarea required value={draft.explanation} onChange={(event) => setDraft({ ...draft, explanation: event.target.value })} /></label>}
      {error && <p role="alert" className="error">{error}</p>}
      <div className="question-review-actions">
        <button type="submit">{pending ? "Đang lưu và kiểm định…" : "Lưu và kiểm định"}</button>
        <button type="button" className="secondary" onClick={onCancel}>Hủy</button>
      </div>
    </fieldset>
    <p className="muted">Giữ nguyên phạm vi, mức độ và tổng điểm. Nội dung chưa qua kiểm định sẽ được giữ dưới dạng bản nháp.</p>
  </form>;
}
