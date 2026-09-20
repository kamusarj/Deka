import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { useAuth } from "../contexts/useAuth";
import { authResendVerification, getOAuthConfig } from "../services/api";
import BrandMark from "../components/BrandMark";
import SessionRecovery from "../components/SessionRecovery";
import { getApiErrorMessage } from "../utils/apiError";
import { getPostAuthPath } from "../utils/authNavigation";
import { DEMO_ACCOUNTS, DEMO_PASSWORD, isDemoLoginEnabled } from "../auth/demoAccounts";

export default function Login() {
  const { login, isAuthenticated, isLoading, sessionError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberLogin, setRememberLogin] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendMessage, setResendMessage] = useState("");
  const [oauth, setOauth] = useState({ google: false, facebook: false });

  useEffect(() => {
    getOAuthConfig().then(setOauth).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await signIn(email, password);
  }

  async function signIn(loginEmail: string, loginPassword: string) {
    if (loading) return;
    setError("");
    setResendMessage("");
    setLoading(true);
    try {
      await login(loginEmail, loginPassword, rememberLogin);
      navigate(getPostAuthPath(location.state), { replace: true });
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Đăng nhập thất bại"));
    } finally {
      setLoading(false);
    }
  }

  async function resendVerification() {
    setResendMessage("");
    try {
      setResendMessage((await authResendVerification(email)).message);
    } catch (reason) {
      setError(getApiErrorMessage(reason, "Không thể gửi lại email xác minh"));
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

  if (isLoading || sessionError) return <SessionRecovery />;
  if (isAuthenticated) return <Navigate to={getPostAuthPath(location.state)} replace />;

  return (
    <div className="auth-page auth-login-page">
      <div className="auth-layout">
      <aside className="auth-intro">
        <Link to="/" className="auth-brand"><BrandMark /><span className="brand-name">Deka</span></Link>
        <h2>Từ bài giảng,<br />đến đề kiểm tra.</h2>
        <p className="auth-intro-description">Một không gian để soạn đề, lưu học liệu và chia sẻ cùng đồng nghiệp.</p>
        {isDemoLoginEnabled() && (
          <section className="auth-demo" aria-labelledby="demo-login-title" aria-busy={loading}>
            <h2 id="demo-login-title">Đăng nhập nhanh để thử</h2>
            <p>Chọn vai trò để vào ứng dụng. Mật khẩu chung: <code>{DEMO_PASSWORD}</code></p>
            <div className="auth-demo-accounts">
              {DEMO_ACCOUNTS.map(account => (
                <button
                  key={account.role}
                  type="button"
                  className="auth-demo-account"
                  disabled={loading}
                  aria-label={`Đăng nhập thử: ${account.label}`}
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(DEMO_PASSWORD);
                    void signIn(account.email, DEMO_PASSWORD);
                  }}
                >
                  <span className="auth-demo-role">{account.label}<span aria-hidden="true">→</span></span>
                  <span className="auth-demo-email">{account.email}</span>
                </button>
              ))}
            </div>
            <p className="auth-demo-hint">Để đổi vai trò, đăng xuất rồi chọn tài khoản khác.</p>
          </section>
        )}
      </aside>
      <div className="auth-card">
        <Link to="/" className="auth-brand">
          <BrandMark />
          <span className="brand-name">Deka</span>
        </Link>

        <h1>Đăng nhập</h1>
        <p className="auth-welcome">Tiếp tục công việc của bạn tại Deka.</p>



        {error && <div className="auth-error" role="alert">{error}</div>}
        {error.toLowerCase().includes("xác minh") && email && (
          <button type="button" className="ghost-btn compact" onClick={resendVerification}>Gửi lại email xác minh</button>
        )}
        {resendMessage && <div className="account-success" role="status">{resendMessage}</div>}

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
            <span>hoặc đăng nhập bằng email</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              autoComplete="email"
              required
              autoFocus={!isDemoLoginEnabled()}
            />
          </label>
          <label>
            Mật khẩu
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </label>
          <label className="auth-remember">
            <input
              type="checkbox"
              checked={rememberLogin}
              onChange={(e) => setRememberLogin(e.target.checked)}
            />
            <span>Ghi nhớ đăng nhập</span>
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Đang đăng nhập…" : "Đăng nhập"}
          </button>
        </form>

        <p className="auth-footer"><Link to="/forgot-password">Quên mật khẩu?</Link></p>

        <p className="auth-footer">
          Chưa có tài khoản?{" "}
          <Link to="/register" state={location.state}>Đăng ký ngay</Link>
        </p>
      </div>
      </div>
    </div>
  );
}
