import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
import { useAuth } from "../contexts/useAuth";
import { getOAuthConfig, authResendVerification } from "../services/api";
import BrandMark from "../components/BrandMark";
import { getApiErrorMessage } from "../utils/apiError";
import { getPostAuthPath } from "../utils/authNavigation";

export default function Register() {
  const { register } = useAuth();
  const location = useLocation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState("");
  const [oauth, setOauth] = useState({ google: false, facebook: false });

  useEffect(() => {
    getOAuthConfig().then(setOauth).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password !== confirm) {
      setError("Mật khẩu xác nhận không khớp");
      return;
    }
    if (!name.trim()) {
      setError("Vui lòng nhập họ và tên");
      return;
    }

    setLoading(true);
    try {
      const result = await register(email, password, name.trim());
      setSuccess(result?.message ?? "Đăng ký thành công. Vui lòng kiểm tra email để xác minh tài khoản.");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Đăng ký thất bại"));
    } finally {
      setLoading(false);
    }
  }

  function handleOAuth(provider: string) {
    try {
      sessionStorage.setItem("smart-exam-auth-return", getPostAuthPath(location.state));
    } catch {
      // Continue OAuth even if browser storage is unavailable.
    }
    const base = import.meta.env.VITE_API_BASE_URL ?? "";
    window.location.href = `${base}/api/auth/login/${provider}`;
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="auth-brand">
          <BrandMark />
          <span className="brand-name">Smart Exam</span>
        </Link>

        <h1>Tạo tài khoản</h1>

        {error && <div className="auth-error">{error}</div>}
        {success && <div className="account-success" role="status">{success}</div>}

        {success && <button type="button" disabled={loading} onClick={async () => {
          setLoading(true); setError("");
          try { const result = await authResendVerification(email); setSuccess(result.message); }
          catch (err) { setError(getApiErrorMessage(err, "Chưa gửi được email. Vui lòng thử lại sau.")); }
          finally { setLoading(false); }
        }}>Gửi lại email xác minh</button>}

        {/* OAuth buttons */}
        {(oauth.google || oauth.facebook) && (
          <div className="auth-oauth">
            {oauth.google && (
              <button type="button" className="auth-oauth-btn auth-oauth-google" onClick={() => handleOAuth("google")}>
                <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
                Google
              </button>
            )}
            {oauth.facebook && (
              <button type="button" className="auth-oauth-btn auth-oauth-facebook" onClick={() => handleOAuth("facebook")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#1877F2"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
                Facebook
              </button>
            )}
          </div>
        )}

        {(oauth.google || oauth.facebook) && (
          <div className="auth-divider">
            <span>hoặc đăng ký bằng email</span>
          </div>
        )}

        {!success && <form onSubmit={handleSubmit} className="auth-form">
          <label>
            Họ và tên
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nguyễn Văn A"
              required
              autoFocus
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              required
            />
          </label>
          <label>
            Mật khẩu
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Tối thiểu 6 ký tự"
              required
              minLength={6}
            />
          </label>
          <label>
            Xác nhận mật khẩu
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Nhập lại mật khẩu"
              required
              minLength={6}
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Đang tạo tài khoản…" : "Đăng ký"}
          </button>
        </form>}

        <p className="auth-footer">
          Đã có tài khoản?{" "}
          <Link to="/login" state={location.state}>Đăng nhập</Link>
        </p>
      </div>
    </div>
  );
}
