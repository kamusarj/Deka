import RichContent, { MathText } from "./RichContent";
import type { BankQuestion } from "../types";

type JsonObject = Record<string, unknown>;

function asObject(value: unknown): JsonObject | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : null;
}

function asText(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function optionEntries(value: unknown): Array<[string, string]> {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => {
      const record = asObject(item);
      const text = asText(record?.text ?? record?.content ?? item);
      return text ? [[asText(record?.key) || String.fromCharCode(65 + index), text]] : [];
    });
  }
  const record = asObject(value);
  return record
    ? Object.entries(record).flatMap(([key, item]) => {
        const nested = asObject(item);
        const text = asText(nested?.text ?? nested?.content ?? item);
        return text ? [[key, text]] : [];
      })
    : [];
}

function itemEntries(value: unknown): JsonObject[] {
  return Array.isArray(value)
    ? value.map(asObject).filter((item): item is JsonObject => item !== null)
    : [];
}

function answerPayload(value: unknown): JsonObject | null {
  const stored = asObject(value);
  return asObject(stored?.answer) ?? stored;
}

function textItems(value: unknown): string[] {
  return Array.isArray(value) ? value.map(asText).filter(Boolean) : [];
}

function AnswerDetails({ question }: { question: BankQuestion }) {
  const answer = answerPayload(question.answer);
  if (!answer) return null;
  const explanation = asText(answer.explanation);
  const statements = itemEntries(question.statements);
  const rubric = asObject(answer.rubric) ?? asObject(asObject(question.answer)?.rubric);
  const keyPoints = textItems(answer.key_points);
  const keywords = textItems(answer.keywords);
  const guide = textItems(rubric?.grading_guide);
  const criteria = itemEntries(rubric?.criteria);

  return <>
    {explanation && <p><MathText text={explanation} /></p>}
    {question.type === "multiple_choice" && optionEntries(answer.option_explanations).map(([key, text]) => (
      <p key={key}><strong>{key}.</strong> <MathText text={text} /></p>
    ))}
    {question.type === "true_false" && itemEntries(answer.answers).map((item, index) => {
      const position = statements.findIndex(statement => asText(statement.id) === asText(item.statement_id));
      const text = asText(item.explanation);
      return text ? <p key={asText(item.statement_id) || index}>
        <strong>{String.fromCharCode(97 + (position < 0 ? index : position))})</strong> <MathText text={text} />
      </p> : null;
    })}
    {keywords.length > 0 && <p><strong>Từ khóa:</strong> {keywords.join(", ")}</p>}
    {keyPoints.length > 0 && <><strong>Ý chính</strong><ul>{keyPoints.map((point, index) => <li key={index}>{point}</li>)}</ul></>}
    {rubric && (guide.length > 0 || criteria.length > 0) && <div>
      <h4>Hướng dẫn chấm{asText(rubric.total_score) && ` · ${asText(rubric.total_score)} điểm`}</h4>
      {guide.length > 0 && <ul>{guide.map((line, index) => <li key={index}>{line}</li>)}</ul>}
      {criteria.map((criterion, index) => <div key={asText(criterion.id) || index}>
        <p><strong>{asText(criterion.name)}</strong>{asText(criterion.max_score) && ` · tối đa ${asText(criterion.max_score)} điểm`}</p>
        <ul>{itemEntries(criterion.levels).map((level, levelIndex) => <li key={levelIndex}>
          {asText(level.score) && `${asText(level.score)} điểm: `}
          {[asText(level.description), asText(level.criteria)].filter(Boolean).join(" — ")}
        </li>)}</ul>
      </div>)}
    </div>}
  </>;
}

function answerSummary(question: BankQuestion): string {
  const answer = answerPayload(question.answer);
  if (!answer) return "Chưa có đáp án kèm theo.";

  if (question.type === "multiple_choice") {
    const correct = asText(answer.correct_answer);
    const option = optionEntries(question.options).find(([key]) => key === correct)?.[1];
    return correct ? `${correct}${option ? `. ${option}` : ""}` : "Chưa có đáp án kèm theo.";
  }

  if (question.type === "true_false") {
    const statements = itemEntries(question.statements);
    const statementIndex = new Map(
      statements.map((statement, index) => [asText(statement.id), index]),
    );
    const values = itemEntries(answer.answers).map((item, index) => {
      const position = statementIndex.get(asText(item.statement_id)) ?? index;
      return `${String.fromCharCode(97 + position)}) ${item.is_true === true ? "Đúng" : "Sai"}`;
    });
    return values.length > 0 ? values.join("; ") : "Chưa có đáp án kèm theo.";
  }

  if (question.type === "short_answer") {
    return asText(answer.correct_answer) || "Chưa có đáp án kèm theo.";
  }

  return asText(answer.model_answer) || "Xem hướng dẫn chấm kèm theo.";
}

export default function BankQuestionBody({ question, collapsibleAnswer = false }: { question: BankQuestion; collapsibleAnswer?: boolean }) {
  const options = optionEntries(question.options);
  const statements = itemEntries(question.statements);
  const subQuestions = itemEntries(question.sub_questions);

  return (
    <>
      <div className="question-body">
        <p><MathText text={question.content} /></p>
        <RichContent blocks={question.rich_content} />
        {options.length > 0 && (
          <div className="options-list">
            {options.map(([key, value]) => (
              <div className="option-item" key={key}><strong>{key}.</strong> <MathText text={value} /></div>
            ))}
          </div>
        )}
        {statements.length > 0 && (
          <div className="statements-list">
            {statements.map((statement, index) => (
              <div className="statement-item" key={asText(statement.id) || index}>
                {String.fromCharCode(97 + index)}) <MathText text={asText(statement.content)} />
              </div>
            ))}
          </div>
        )}
        {subQuestions.length > 0 && (
          <div className="sub-questions">
            {subQuestions.map((item, index) => (
              <p className="sub-question" key={asText(item.id) || index}>
                {String.fromCharCode(97 + index)}) <MathText text={asText(item.content)} />
                {asText(item.score) && <span className="muted"> ({asText(item.score)} điểm)</span>}
              </p>
            ))}
          </div>
        )}
      </div>
      {collapsibleAnswer ? <details className="bank-answer"><summary>Xem đáp án và giải thích</summary>
        <p><MathText text={answerSummary(question)} /></p>
        <AnswerDetails question={question} />
      </details> : <div className="bank-answer"><strong>Đáp án</strong><span><MathText text={answerSummary(question)} /></span></div>}
    </>
  );
}
