import type { MatrixRow, MatrixSummary } from "../types";
import DifficultyChart from "./DifficultyChart";

const DIFFICULTY_LABELS = {
  nhan_biet: "Nhận biết",
  thong_hieu: "Thông hiểu",
  van_dung: "Vận dụng",
} as const;

interface MatrixTableProps {
  matrix: MatrixRow[];
  summary: MatrixSummary;
}

export default function MatrixTable({ matrix, summary }: MatrixTableProps) {
  if (!matrix || matrix.length === 0) {
    return (
      <div className="empty-state" style={{ padding: "1.5rem" }}>
        <p>Chưa có ma trận đề</p>
      </div>
    );
  }

  return (
    <div className="matrix-table-wrapper">
      {/* Biểu đồ phân bổ mức độ (stacked bar + legend) */}
      <DifficultyChart summary={summary} compact />
      {summary.calculation_requirement && summary.calculation_requirement.required_count > 0 && (
        <p className="matrix-calculation-summary">
          <strong>
            {summary.calculation_requirement.actual_count} câu tính toán bắt buộc
            {summary.auto_distribute_scores ? " · điểm tự phân bổ" : ""}
          </strong>
          <span>
            {!summary.auto_distribute_scores
              ? `${summary.calculation_requirement.score_per_question} điểm/câu`
              : ""}
            {(summary.calculation_requirement.actual_difficulties ?? []).length > 0
              ? ` · ${(summary.calculation_requirement.actual_difficulties ?? [])
              .map((difficulty, index) => {
                const score = summary.calculation_requirement?.actual_scores?.[index];
                return `Câu ${index + 1}: ${DIFFICULTY_LABELS[difficulty]}${score !== undefined ? ` (${score}đ)` : ""}`;
              })
              .join(" · ")}`
              : ` · tổng ${summary.calculation_requirement.total_score} điểm`}
          </span>
        </p>
      )}
      <table className="matrix-table">
        <colgroup>
          <col className="matrix-topic-col" />
          <col className="matrix-level-col" />
          <col className="matrix-level-col" />
          <col className="matrix-level-col" />
          <col className="matrix-score-col" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">Chủ đề / Bài học</th>
            <th scope="col" className="cell-center">
              Nhận biết
              <br />
              <small>({summary.nhan_biet.percentage}%)</small>
            </th>
            <th scope="col" className="cell-center">
              Thông hiểu
              <br />
              <small>({summary.thong_hieu.percentage}%)</small>
            </th>
            <th scope="col" className="cell-center">
              Vận dụng
              <br />
              <small>({summary.van_dung.percentage}%)</small>
            </th>
            <th scope="col" className="cell-center">Tổng điểm</th>
          </tr>
        </thead>
        <tbody>
          {matrix.map((row) => (
            <tr key={row.id}>
              <td className="lesson-cell">{row.lesson_name}</td>
              <td className="cell-center">
                {row.nhan_biet.count > 0
                  ? `${row.nhan_biet.count} câu (${row.nhan_biet.score}đ)`
                  : "—"}
              </td>
              <td className="cell-center">
                {row.thong_hieu.count > 0
                  ? `${row.thong_hieu.count} câu (${row.thong_hieu.score}đ)`
                  : "—"}
              </td>
              <td className="cell-center">
                {row.van_dung.count > 0
                  ? `${row.van_dung.count} câu (${row.van_dung.score}đ)`
                  : "—"}
              </td>
              <td className="cell-center score">{row.total_score}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td className="lesson-cell"><strong>Tổng</strong></td>
            <td className="cell-center">
              {summary.nhan_biet.total_count} câu ({summary.nhan_biet.total_score}đ)
            </td>
            <td className="cell-center">
              {summary.thong_hieu.total_count} câu ({summary.thong_hieu.total_score}đ)
            </td>
            <td className="cell-center">
              {summary.van_dung.total_count} câu ({summary.van_dung.total_score}đ)
            </td>
            <td className="cell-center score"><strong>{summary.total_score}</strong></td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
