import type { VerificationReport } from "../types";

interface QualityFindingsProps {
  report?: VerificationReport | null;
}

function displayNumber(report: VerificationReport, questionId: string): string {
  const questionNumber = report.question_reports.find(
    (item) => item.question_id === questionId,
  )?.question_number;
  if (questionNumber != null) return String(questionNumber);

  const fallback = questionId.match(/(\d+)$/);
  return fallback?.[1] ?? questionId.replace(/^q_/, "");
}

function cleanFindingText(text: string): string {
  return text
    .replace(/\[(?:DeepSeek|Gemini|OpenAI)\b[^\]\r\n]*\]\s*/gi, "")
    .replace(/\bs_\d+_(\d+)\b/gi, (_match, position: string) => {
      const index = Number(position) - 1;
      return index >= 0 && index < 26 ? `${String.fromCharCode(97 + index)})` : position;
    })
    .replace(/\bq_(\d+)\b/gi, "câu $1")
    .trim();
}

export default function QualityFindings({ report }: QualityFindingsProps) {
  if (!report) return null;

  const comparison = report.reviewer_summary;
  if (!comparison && report.action_required.length === 0) return null;
  const singleReviewer = comparison?.mode === "deepseek_only";

  return (
    <section className="quality-findings" aria-labelledby="quality-findings-title">
      {comparison && (
        <div className="quality-reviewer-summary">
          <h2 id="quality-findings-title">
            {singleReviewer ? "Trợ lý kiểm định" : "Đối chiếu 2 trợ lý kiểm định"}
          </h2>
          <small>
            {singleReviewer
              ? `${comparison.reviewed_questions ?? 0}/${comparison.total_questions} câu đã kiểm định`
              : `${comparison.consensus_questions}/${comparison.total_questions} câu đồng thuận`}
            {!singleReviewer && comparison.disagreement_questions > 0
              ? ` · ${comparison.disagreement_questions} câu bất đồng trọng yếu`
              : ""}
          </small>
        </div>
      )}
      {report.action_required.length > 0 && <details>
        <summary>
          <span className="quality-findings-icon" aria-hidden="true">!</span>
          <span>
            <h2 id={comparison ? undefined : "quality-findings-title"}>Cần xem lại</h2>
            <small>{report.action_required.length} câu có gợi ý cần giáo viên kiểm tra</small>
          </span>
          <span className="quality-findings-action">Xem danh sách</span>
        </summary>
        <div className="quality-findings-content">
          <ul>
            {report.action_required.map((action) => {
              const number = displayNumber(report, action.question_id);
              return (
                <li key={action.question_id}>
                  <a href={`#question-${action.question_id}`}>Câu {number}</a>
                  <div>
                    <p>{cleanFindingText(action.message)}</p>
                    {action.fix && <p className="muted">Gợi ý: {cleanFindingText(action.fix)}</p>}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </details>}
    </section>
  );
}
