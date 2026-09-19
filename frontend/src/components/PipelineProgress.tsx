import type { PipelineStageInfo } from "../types";

interface PipelineProgressProps {
  stages: PipelineStageInfo[];
}

export default function PipelineProgress({ stages }: PipelineProgressProps) {
  const completedCount = stages.filter(
    (s) => s.status === "completed" || s.status === "skipped",
  ).length;
  const hasError = stages.some((s) => s.status === "error");
  const totalStages = stages.length;
  const progressPct = totalStages > 0 ? (completedCount / totalStages) * 100 : 0;

  if (totalStages === 0) return null;

  return (
    <div className="pipeline-progress" role="status" aria-live="polite">
      {/* Progress bar */}
      <div className="pipeline-bar-wrapper">
        <div className="pipeline-bar">
          <div
            className={`pipeline-bar-fill ${hasError ? "pipeline-bar-error" : ""}`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <span className="pipeline-bar-label">
          {completedCount}/{totalStages} bước
        </span>
      </div>

      {/* Stage list */}
      <div className="pipeline-stages">
        {stages.map((stage) => (
          <div key={stage.id} className={`pipeline-stage pipeline-stage-${stage.status}`}>
            <span className="pipeline-stage-icon" aria-hidden="true">
              {stage.status === "completed"
                ? "✓"
                : stage.status === "running"
                  ? "●"
                  : stage.status === "error"
                    ? "✕"
                    : stage.status === "skipped"
                      ? "⊘"
                      : stage.icon}
            </span>
            <div className="pipeline-stage-info">
              <span className="pipeline-stage-label">
                {stage.label}
                {stage.status === "skipped" && " (bỏ qua)"}
              </span>
              {stage.message && stage.status !== "skipped" && (
                <span className="pipeline-stage-message">{stage.message}</span>
              )}
            </div>
            {stage.status === "running" && (
              <span className="pipeline-stage-spinner" aria-label="Đang xử lý" />
            )}
            {stage.status === "completed" && (
              <span className="pipeline-stage-done">✓</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
