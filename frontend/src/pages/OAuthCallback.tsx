import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { setToken } from "../contexts/authStorage";
import { useAuth } from "../contexts/useAuth";

export default function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  useEffect(() => {
    const token = searchParams.get("token");
    let active = true;
    if (token) {
      setToken(token);
      let destination = "/dashboard";
      try {
        const stored = sessionStorage.getItem("smart-exam-auth-return");
        if (stored?.startsWith("/") && !stored.startsWith("//")) destination = stored;
      } catch {
        // Use the safe default when browser storage is unavailable.
      }
      void refreshUser().then(() => {
        if (!active) return;
        try {
          sessionStorage.removeItem("smart-exam-auth-return");
        } catch {
          // Navigation also works when storage is unavailable.
        }
        navigate(destination, { replace: true });
      });
    } else {
      navigate("/login", { replace: true });
    }
    return () => { active = false; };
  }, [searchParams, navigate, refreshUser]);

  return (
    <div className="auth-loading">
      <div className="auth-loading-spinner" />
      <p>Đang xác thực…</p>
    </div>
  );
}
