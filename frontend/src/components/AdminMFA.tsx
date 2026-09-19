import { useState } from 'react';
import { api } from '../services/api';
import { getToken, setToken } from '../contexts/authStorage';
import { getApiErrorMessage } from '../utils/apiError';

export default function AdminMFA() {
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [secret, setSecret] = useState('');
  const [recovery, setRecovery] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(setup: boolean) {
    const token = getToken();
    setBusy(true); setError(''); setMessage('');
    try {
      const { data } = await api.post(`/api/auth/mfa/${setup ? 'setup' : 'verify'}`, { password, code });
      if (getToken() !== token) return;
      if (setup) {
        setSecret(data.secret);
        setMessage('Thêm khóa này vào ứng dụng xác thực, rồi nhập mã 6 chữ số để kích hoạt.');
      } else {
        setToken(data.access_token);
        setRecovery(data.recovery_codes);
        setSecret(''); setPassword(''); setCode('');
        setMessage('Đã xác thực MFA. Quyền quản trị có hiệu lực 10 phút.');
      }
    } catch (err) {
      if (getToken() === token) setError(getApiErrorMessage(err, 'Chưa xác thực được MFA.'));
    } finally { setBusy(false); }
  }

  return <section className="panel" aria-labelledby="mfa-heading">
    <h2 id="mfa-heading">Xác thực MFA quản trị</h2>
    <p>Ở môi trường triển khai, Super Admin cần mật khẩu và mã xác thực để sử dụng quyền quản trị.</p>
    <form className="auth-form" onSubmit={event => { event.preventDefault(); void submit(false); }}>
      <label>Mật khẩu hiện tại<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required maxLength={72} /></label>
      <label>Mã xác thực hoặc mã khôi phục<input autoComplete="one-time-code" value={code} onChange={event => setCode(event.target.value)} maxLength={32} /></label>
      <div className="report-actions">
        <button type="submit" disabled={busy || !password || !code}>Xác thực MFA</button>
        <button type="button" className="secondary" disabled={busy || !password} onClick={() => void submit(true)}>Thiết lập lần đầu</button>
      </div>
    </form>
    {secret && <p>Khóa thiết lập: <code>{secret}</code></p>}
    {message && <p role="status">{message}</p>}
    {error && <p role="alert">{error}</p>}
    {recovery.length > 0 && <div><p>Lưu các mã khôi phục tại nơi riêng tư. Mỗi mã dùng một lần; danh sách chỉ hiển thị lúc kích hoạt.</p><pre>{recovery.join('\n')}</pre><button className="secondary" onClick={() => setRecovery([])}>Đã lưu mã</button></div>}
  </section>;
}
