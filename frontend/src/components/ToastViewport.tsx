import { useToast } from "../contexts/useToast";
import type { ToastTone } from "../contexts/toastContextValue";

const toneIcon: Record<ToastTone, string> = {
  success: "✓",
  error: "!",
  info: "i",
};

export default function ToastViewport() {
  const { toasts, dismiss } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-viewport" role="region" aria-label="Thông báo">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast-${toast.tone}`}
          role={toast.tone === "error" ? "alert" : "status"}
        >
          <span className="toast-icon" aria-hidden="true">
            {toneIcon[toast.tone]}
          </span>
          <span className="toast-message">{toast.message}</span>
          <button
            type="button"
            className="toast-close"
            onClick={() => dismiss(toast.id)}
            aria-label="Đóng thông báo"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
