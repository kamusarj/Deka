import { useState } from "react";
import { Link } from "react-router";

import BrandMark from "../components/BrandMark";
import { authForgotPassword } from "../services/api";
import { getApiErrorMessage } from "../utils/apiError";


export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setMessage((await authForgotPassword(email)).message);
    } catch (reason) {
      setError(getApiErrorMessage(reason, "Không thể gửi hướng dẫn lúc này"));
    } finally {
      setLoading(false);
    }
  }

  return <div className="auth-page"><div className="auth-card">
    <Link to="/" className="auth-brand"><BrandMark /><span className="brand-name">Smart Exam</span></Link>
    <h1>Quên mật khẩu</h1>
    <p>Nhập email đăng nhập để nhận liên kết đặt lại mật khẩu.</p>
    {error && <div className="auth-error">{error}</div>}
    {message && <div className="account-success" role="status">{message}</div>}
    {!message && <form className="auth-form" onSubmit={submit}>
      <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoFocus /></label>
      <button disabled={loading}>{loading ? "Đang gửi…" : "Gửi hướng dẫn"}</button>
    </form>}
    <p className="auth-footer"><Link to="/login">Quay lại đăng nhập</Link></p>
  </div></div>;
}
