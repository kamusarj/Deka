import { useEffect, useRef, useState } from 'react';
import { getPlans, updateSubscription, type AccountUsage, type Plan } from '../services/usageReports';
import { getApiErrorMessage } from '../utils/apiError';
import SelectControl from './SelectControl';
import { getToken } from '../contexts/authStorage';

export default function SubscriptionEditor({ account, onSaved, disabled = false }: { account: AccountUsage; onSaved: () => void; disabled?: boolean }) {
  const sub = account.subscription;
  const [plans, setPlans] = useState<Plan[]>([]);
  const [plan, setPlan] = useState(sub?.plan ?? 'FREE');
  const [status, setStatus] = useState(sub?.status ?? 'active');
  const [allowance, setAllowance] = useState(sub ? String(sub.credit_allowance) : '');
  const [adjustment, setAdjustment] = useState('0');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [catalogError, setCatalogError] = useState(false);
  const [retry, setRetry] = useState(0);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  useEffect(() => {
    const request = new AbortController();
    setCatalogError(false);
    getPlans(request.signal).then(value => {
      if (request.signal.aborted) return;
      setPlans(value);
      if (!sub) setAllowance(String(value.find(p => p.id === 'FREE')?.monthly_credits ?? ''));
    }).catch(() => { if (!request.signal.aborted) setCatalogError(true); });
    return () => request.abort();
  }, [sub, retry]);
  async function save(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || disabled) return;
    setBusy(true); setError('');
    const controller = new AbortController();
    pending.current = controller;
    const token = getToken();
    try {
      await updateSubscription(account.user.id, { plan, status, credit_allowance: Number(allowance),
        credit_adjustment: Number(adjustment), settings_version: sub?.settings_version ?? 0, reason: reason.trim() }, controller.signal);
      if (!controller.signal.aborted && token === getToken()) onSaved();
    } catch (err) {
      if (!controller.signal.aborted && token === getToken()) setError(getApiErrorMessage(err, 'Chưa lưu được thay đổi. Hãy tải lại tài khoản.'));
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <form className="subscription-editor" onSubmit={save}>
    <h3>Tùy chỉnh subscription</h3>
    <p>Hạn mức mới áp dụng cho kỳ cấp credit tiếp theo. Số dư chỉ thay đổi theo khoản cộng/trừ bên dưới.</p>
    {!sub && <p>Tài khoản chưa kích hoạt gói. Lần lưu đầu cấp credit Free ban đầu, sau đó áp dụng điều chỉnh.</p>}
    {catalogError && <p role="alert">Chưa tải được danh mục gói. <button type="button" onClick={() => setRetry(n => n + 1)}>Thử lại</button></p>}
    <fieldset disabled={disabled || busy || !plans.length}><legend className="sr-only">Cài đặt gói cho {account.user.name}</legend>
      <div className="report-form-grid">
        <label>Gói sử dụng<SelectControl ariaLabel="Gói sử dụng" disabled={disabled || busy || !plans.length} value={plan} onChange={value => { setPlan(value); setAllowance(String(plans.find(p => p.id === value)?.monthly_credits ?? 0)); }} options={plans.map(p => ({ value: p.id, label: p.id }))} /></label>
        <label>Trạng thái gói<SelectControl ariaLabel="Trạng thái gói" disabled={disabled || busy || !plans.length} value={status} onChange={setStatus} options={[{ value: "active", label: "Đang hoạt động" }, { value: "paused", label: "Tạm dừng" }]} /></label>
        <label>Hạn mức credit mỗi tháng<input type="number" required min="0" max="1000000" step="1" value={allowance} onChange={e => setAllowance(e.target.value)} /></label>
        <label>Cộng/trừ credit hiện tại<input type="number" required min="-1000000" max="1000000" step="1" value={adjustment} onChange={e => setAdjustment(e.target.value)} /><small>Số dương để cộng, số âm để trừ; 0 giữ số dư.</small></label>
      </div>
      <label>Lý do điều chỉnh<input required maxLength={200} value={reason} onChange={e => setReason(e.target.value)} placeholder="Ví dụ: Cấp hạn mức cho đợt kiểm tra học kỳ" /></label>
      <button type="submit" disabled={!reason.trim()}>{busy ? 'Đang lưu…' : 'Lưu subscription'}</button>
    </fieldset>
    {error && <p role="alert" className="error-box">{error}</p>}
  </form>;
}
