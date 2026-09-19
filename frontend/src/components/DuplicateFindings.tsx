import type { DuplicateReport } from "../types";

export default function DuplicateFindings({ report }: { report?: DuplicateReport }) {
  if (!report?.findings.length) return null;
  return (
    <details className="quality-findings">
      <summary>Câu hỏi tương tự ({report.findings.length})</summary>
      <ul>
        {report.findings.map((finding, index) => (
          <li key={`${finding.question_id}-${finding.scope}-${finding.matched_question_id}-${index}`}>
            <a href={`#question-${finding.question_id}`}>Câu {finding.question_number ?? finding.question_id.replace(/^q_/, "")}</a>
            {" · "}{finding.scope === "bank" ? "Có câu tương tự trong ngân hàng" : "Có câu tương tự trong đề"}.
            <p>{finding.reason}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}
