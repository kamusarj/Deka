interface LoadingSpinnerProps {
  message?: string;
  size?: "small" | "medium" | "large";
}

export default function LoadingSpinner({
  message = "Đang tải...",
  size = "medium",
}: LoadingSpinnerProps) {
  const sizeMap = {
    small: "spinner-sm",
    medium: "spinner-md",
    large: "spinner-lg",
  };

  return (
    <div className="loading-container" role="status" aria-live="polite">
      <div className={`spinner ${sizeMap[size]}`} aria-hidden="true" />
      <p className="muted loading-message">{message}</p>
    </div>
  );
}
