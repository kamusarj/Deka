import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import BrandMark from "../components/BrandMark";
import { authVerifyEmail } from "../services/api";
import { getApiErrorMessage } from "../utils/apiError";


export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [message, setMessage] = useState("");
  const [error, setError] = useState(token ? "" : "Liên kết xác minh thiếu token");

  useEffect(() => {
    if (!token) return;
    authVerifyEmail(token).then((result) => setMessage(result.message)).catch((reason) => {
      setError(getApiErrorMessage(reason, "Không thể xác minh email"));
    });
  }, [token]);

  return <div className="auth-page"><div className="auth-card">
    <Link to="/" className="auth-brand"><BrandMark /><span className="brand-name">Smart Exam</span></Link>
    <h1>Xác minh email</h1>
    {!message && !error && <p>Đang xác minh…</p>}
    {error && <div className="auth-error">{error}</div>}
    {message && <div className="account-success" role="status">{message}</div>}
    <p className="auth-footer"><Link to="/login">Đi đến đăng nhập</Link></p>
  </div></div>;
}
