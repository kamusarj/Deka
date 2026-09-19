interface SkeletonProps {
  /** CSS width, e.g. "60%" or "8rem". Defaults to full width. */
  width?: string;
  /** CSS height. Defaults to one text line. */
  height?: string;
  /** Renders a circle instead of a rounded bar. */
  circle?: boolean;
  className?: string;
}

export function Skeleton({ width, height, circle = false, className = "" }: SkeletonProps) {
  return (
    <span
      className={`skeleton ${circle ? "skeleton-circle" : ""} ${className}`.trim()}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

/** Placeholder matching the shape of a list/exam card. */
export function SkeletonCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <Skeleton width="35%" height="0.7rem" />
      <Skeleton width="75%" height="1.25rem" />
      <Skeleton width="55%" height="0.85rem" />
      <div className="skeleton-card-foot">
        <Skeleton width="4.5rem" height="1.5rem" />
        <Skeleton width="6rem" height="1.5rem" />
      </div>
    </div>
  );
}

/**
 * A grid of card placeholders. Announces loading to assistive tech once,
 * rather than letting every bar speak.
 */
export function SkeletonGrid({ count = 3, label = "Đang tải dữ liệu" }: { count?: number; label?: string }) {
  return (
    <div className="skeleton-grid" role="status" aria-label={label} aria-busy="true">
      {Array.from({ length: count }, (_, index) => (
        <SkeletonCard key={index} />
      ))}
    </div>
  );
}

export default Skeleton;
