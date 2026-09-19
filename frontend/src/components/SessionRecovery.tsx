import { useAuth } from "../contexts/useAuth";

export default function SessionRecovery() {
  const { isLoading, sessionError, refreshUser } = useAuth();
  return (
    <div className="auth-loading" role="status">
      {isLoading ? (
        <>
          <div className="auth-loading-spinner" />
          <p>Đang tải…</p>
        </>
      ) : (
        <>
          <p>{sessionError}</p>
          <button type="button" className="ghost-btn" onClick={() => void refreshUser()}>
            Thử lại
          </button>
        </>
      )}
    </div>
  );
}
