import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import BrandMark from "../components/BrandMark";
import { authResetPassword } from "../services/api";
import { getApiErrorMessage } from "../utils/apiError";


export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState(token ? "" : "Liên kết thiếu token đặt lại mật khẩu");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Mật khẩu xác nhận không khớp");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setMessage((await authResetPassword(token, password)).message);
    } catch (reason) {
      setError(getApiErrorMessage(reason, "Không thể đặt lại mật khẩu"));
    } finally {
      setLoading(false);
    }
  }

  return <div className="auth-page"><div className="auth-card">
    <Link to="/" className="auth-brand"><BrandMark /><span className="brand-name">Smart Exam</span></Link>
    <h1>Đặt lại mật khẩu</h1>
    {error && <div className="auth-error">{error}</div>}
    {message && <div className="account-success" role="status">{message}</div>}
    {!message && token && <form className="auth-form" onSubmit={submit}>
      <label>Mật khẩu mới<input type="password" minLength={6} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} required autoFocus /></label>
      <label>Xác nhận mật khẩu<input type="password" minLength={6} maxLength={128} value={confirm} onChange={(event) => setConfirm(event.target.value)} required /></label>
      <button disabled={loading}>{loading ? "Đang lưu…" : "Đặt lại mật khẩu"}</button>
    </form>}
    <p className="auth-footer"><Link to="/login">Đăng nhập</Link></p>
  </div></div>;
}
