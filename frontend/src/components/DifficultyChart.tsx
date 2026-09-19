import type { MatrixSummary } from "../types";

interface DifficultyChartProps {
  summary: MatrixSummary;
  /** compact: gọn hơn khi đặt cạnh bảng ma trận. */
  compact?: boolean;
}

type Level = "nhan_biet" | "thong_hieu" | "van_dung";

const LEVELS: {
  key: Level;
  label: string;
  colorClass: string;
}[] = [
  { key: "nhan_biet", label: "Nhận biết", colorClass: "lvl-nhan_biet" },
  { key: "thong_hieu", label: "Thông hiểu", colorClass: "lvl-thong_hieu" },
  { key: "van_dung", label: "Vận dụng", colorClass: "lvl-van_dung" },
];

/**
 * Biểu đồ tỷ lệ mức độ thực tế của đề (dựa trên matrix summary).
 * Hiển thị dạng stacked bar + legend với số câu, điểm, phần trăm.
 */
export default function DifficultyChart({ summary, compact = false }: DifficultyChartProps) {
  const totalScore = summary.total_score || 1;
  const totalQuestions =
    summary.total_questions ??
    summary.nhan_biet.total_count +
      summary.thong_hieu.total_count +
      summary.van_dung.total_count;

  return (
    <div className={`difficulty-chart ${compact ? "compact" : ""}`}>
      {/* Stacked bar theo điểm số (tổng 10đ) — trực quan nhất cho giáo viên */}
      <div
        className="chart-stacked-bar"
        role="img"
        aria-label={`Phân bổ điểm: Nhận biết ${summary.nhan_biet.total_score}đ, Thông hiểu ${summary.thong_hieu.total_score}đ, Vận dụng ${summary.van_dung.total_score}đ`}
      >
        {LEVELS.map((lvl) => {
          const score = summary[lvl.key].total_score;
          if (score <= 0) return null;
          const widthPct = (score / totalScore) * 100;
          return (
            <div
              key={lvl.key}
              className={`chart-segment ${lvl.colorClass}`}
              style={{ width: `${widthPct}%` }}
              title={`${lvl.label}: ${summary[lvl.key].total_count} câu · ${score}đ (${summary[lvl.key].percentage}%)`}
            >
              {widthPct >= 12 && (
                <span className="chart-segment-value">
                  {score}đ
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend: mỗi mức 1 dòng với dot màu + số câu + điểm + % */}
      <div className="chart-legend">
        {LEVELS.map((lvl) => {
          const cell = summary[lvl.key];
          return (
            <div className="chart-legend-item" key={lvl.key}>
              <span className={`ratio-dot ${lvl.colorClass}`} aria-hidden="true" />
              <span className="chart-legend-label">{lvl.label}</span>
              <span className="chart-legend-stat">
                {cell.total_count} câu · {cell.total_score}đ
              </span>
              <span className={`chart-legend-pct ${lvl.colorClass}`}>
                {cell.percentage}%
              </span>
            </div>
          );
        })}
        <div className="chart-legend-item chart-legend-total">
          <span className="chart-legend-label">Tổng</span>
          <span className="chart-legend-stat">{totalQuestions} câu</span>
          <span className="chart-legend-pct">{summary.total_score}đ</span>
        </div>
      </div>
    </div>
  );
}
