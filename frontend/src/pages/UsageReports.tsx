import { Link } from "react-router";
import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/useAuth';
import { getToken } from '../contexts/authStorage';
import { getStoredRoleLabel, isSuperAdminRole } from '../auth/rolePolicy';
import { getAccountUsage, getUsageReport, type AccountUsage, type Metrics, type ReportFilters, type UsageReport } from '../services/usageReports';
import SelectControl from '../components/SelectControl';
import SubscriptionEditor from '../components/SubscriptionEditor';
import { getApiErrorMessage } from '../utils/apiError';
import '../styles/usage-reports.css';

const number = (value: number | undefined) => value === undefined ? '—' : value.toLocaleString('vi-VN');
const money = (value: string | number | null | undefined) => value == null ? 'Chưa đủ dữ liệu' : `$${Number(value).toLocaleString('vi-VN', { maximumFractionDigits: 6 })}`;
const operationNames: Record<string, string> = { exam_generation: 'Tạo đề', question_generation: 'Tạo câu hỏi', question_regeneration: 'Tạo lại câu hỏi', answer_generation: 'Tạo đáp án', exam_review: 'Kiểm tra đề', rag_query: 'Tra cứu tài liệu' };
const statusNames: Record<string, string> = { success: 'Hoàn tất', failed: 'Thất bại', reserved: 'Đang xử lý' };
function defaultFilters(): ReportFilters {
  const end = new Date(); const start = new Date(end); start.setUTCDate(start.getUTCDate() - 29);
  return { date_from: start.toISOString().slice(0, 10), date_to: end.toISOString().slice(0, 10) };
}
function MetricsStrip({ value, admin }: { value: Metrics; admin: boolean }) {
  return <div className="report-metrics">
    <div><span>Yêu cầu AI</span><strong>{number(value.requests)}</strong><small>{number(value.success)} hoàn tất · {number(value.failed)} thất bại · {number(value.pending)} đang xử lý</small></div>
    <div><span>Credit đã dùng</span><strong>{number(value.credits_charged)}</strong><small>{number(value.reserved_credits)} credit đang tạm giữ</small></div>
    <div><span>Lần gọi AI</span><strong>{number(value.provider_calls)}</strong><small>Một yêu cầu có thể gọi AI nhiều lần</small></div>
    {admin && <div><span>Chi phí AI ước tính</span><strong className="report-cost">{money(value.estimated_cost_usd)}</strong><small>{value.unpriced_calls ? `${number(value.unpriced_calls)} lần chưa có giá; phần đã biết ${money(value.known_cost_usd)}` : 'Theo giá model đã cấu hình'}</small></div>}
  </div>;
}
function Pager({ offset, limit, total, onChange }: { offset: number; limit: number; total: number; onChange: (offset: number) => void }) {
  return <div className="report-pager"><span>{total ? `${offset + 1}–${Math.min(offset + limit, total)} / ${number(total)}` : '0 kết quả'}</span><button className="secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Trang trước</button><button className="secondary" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Trang sau</button></div>;
}

function AccountDetail({ id, filters, admin, onClose, onSaved }: { id: number; filters: ReportFilters; admin: boolean; onClose: () => void; onSaved: () => void }) {
  const [data, setData] = useState<AccountUsage | null>(null);
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController(); const token = getToken();
    setLoading(true); setError('');
    getAccountUsage(id, { date_from: filters.date_from, date_to: filters.date_to, offset }, controller.signal)
      .then(result => { if (!controller.signal.aborted && getToken() === token) { setData(result); setLoading(false); } })
      .catch(err => { if (!controller.signal.aborted && getToken() === token) { setData(null); setLoading(false); setError(getApiErrorMessage(err, 'Chưa tải được tài khoản.')); } });
    return () => controller.abort();
  }, [id, filters.date_from, filters.date_to, offset, refresh]);
  return <section className="panel account-usage" aria-labelledby="account-usage-heading">
    <header className="report-section-head"><h2 id="account-usage-heading">Chi tiết tài khoản</h2><div className="report-actions"><button className="secondary" onClick={() => setRefresh(n => n + 1)}>Tải lại tài khoản</button><button className="secondary" onClick={onClose}>Đóng chi tiết</button></div></header>
    {saved && <p role="status" className="report-success">Đã lưu subscription và ghi nhận điều chỉnh.</p>}
    {error && <p role="alert" className="error-box">{error}</p>}
    {!data && !error && <p role="status">Đang tải chi tiết…</p>}
    {data && <><div className="report-account-heading"><div><h3>{data.user.name}</h3><p>{data.user.email} · {getStoredRoleLabel(data.user.role)}</p></div><p>{data.subscription ? <><strong>{data.subscription.plan} · {number(data.subscription.credit_balance)} credit</strong><br />{number(data.subscription.credit_allowance)} credit/tháng · {data.subscription.status === 'active' ? 'Đang hoạt động' : 'Tạm dừng'}</> : 'Chưa kích hoạt gói'}</p></div>
      <MetricsStrip value={data.summary} admin={admin} />
      {admin && <SubscriptionEditor disabled={loading} key={`${id}-${data.subscription?.settings_version ?? 0}-${refresh}`} account={data} onSaved={() => { setSaved(true); setRefresh(n => n + 1); onSaved(); }} />}
      <h3>Lịch sử yêu cầu trong khoảng đã chọn</h3>
      {data.items.length === 0 ? <p>Chưa có yêu cầu AI trong khoảng thời gian này.</p> : <div className="report-table-scroll" tabIndex={0} role="region" aria-label="Lịch sử yêu cầu AI"><table className="report-table"><thead><tr><th>Thời gian (UTC)</th><th>Thao tác</th><th>Trạng thái</th><th>Credit</th>{admin && <><th>Provider / model</th><th>Token vào / ra</th><th>Chi phí</th><th>Thời gian chờ</th></>}</tr></thead><tbody>{data.items.map(row => <tr key={row.id}>
        <td><time>{row.created_at.replace('T', ' ').slice(0, 16)}</time></td><td>{operationNames[row.operation] ?? row.operation}<small className="report-request-id">{row.id}</small>{row.result_exam_id && <Link to={`/exams/${row.result_exam_id}`}>Mở đề đã lưu</Link>}</td><td>{statusNames[row.status] ?? row.status}</td><td>{row.status === 'reserved' ? `${number(row.reserved_credits)} tạm giữ` : number(row.credits_charged)}</td>
        {admin && <><td>{row.provider ?? '—'}<small>{row.model ?? '—'}</small></td><td>{row.input_tokens === null ? '—' : number(row.input_tokens)} / {row.output_tokens === null ? '—' : number(row.output_tokens)}</td><td>{money(row.estimated_cost_usd)}</td><td>{((row.latency_ms ?? 0) / 1000).toLocaleString('vi-VN')} s</td></>}
      </tr>)}</tbody></table></div>}
      <Pager offset={data.offset} limit={data.limit} total={data.total} onChange={setOffset} />
    </>}
  </section>;
}

export default function UsageReports() {
  const { user } = useAuth();
  return <UsageReportPage key={`${user?.id}-${user?.role}-${user?.school_id}`} />;
}
function UsageReportPage() {
  const { user } = useAuth();
  const admin = isSuperAdminRole(user?.role);
  const manager = admin || user?.role === 'school_admin';
  const [draft, setDraft] = useState(defaultFilters);
  const [filters, setFilters] = useState(defaultFilters);
  const [data, setData] = useState<UsageReport | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  useEffect(() => {
    const controller = new AbortController(); const token = getToken();
    setLoading(true); setError('');
    getUsageReport(filters, controller.signal).then(result => {
      if (controller.signal.aborted || getToken() !== token) return;
      setData(result); setLoading(false);
    }).catch(err => { if (!controller.signal.aborted && getToken() === token) { setData(null); setError(getApiErrorMessage(err, 'Chưa tải được thống kê.')); setLoading(false); } });
    return () => controller.abort();
  }, [filters, refresh]);
  const scopeLabel = admin ? 'Toàn hệ thống' : user?.role === 'school_admin' ? 'Bạn và giáo viên thuộc trường' : 'Tài khoản của bạn';
  return <div className="usage-reports">
    <header className="report-hero"><p>{scopeLabel}</p><h1>Thống kê sử dụng</h1><p>Theo dõi lượt sử dụng AI, credit và hoạt động soạn đề theo thời gian.</p></header>
    <form className="panel report-filters" onSubmit={e => { e.preventDefault(); setSelected(null); setFilters({ ...draft, offset: 0 }); }}>
      <label>Từ ngày (UTC)<input type="date" required value={draft.date_from} max={draft.date_to} onChange={e => setDraft({ ...draft, date_from: e.target.value })} /></label>
      <label>Đến ngày (UTC)<input type="date" required value={draft.date_to} min={draft.date_from} onChange={e => setDraft({ ...draft, date_to: e.target.value })} /></label>
      {manager && <><label>Vai trò<SelectControl ariaLabel="Vai trò" value={draft.role ?? ''} onChange={role => setDraft({ ...draft, role: role || undefined })} options={[{ value: '', label: 'Tất cả vai trò' }, ...(admin ? ['super_admin', 'school_admin', 'teacher', 'viewer'] : ['school_admin', 'teacher']).map(role => ({ value: role, label: getStoredRoleLabel(role) }))]} /></label><label>Tìm tài khoản<input type="search" maxLength={100} value={draft.search ?? ''} onChange={e => setDraft({ ...draft, search: e.target.value })} placeholder="Tên hoặc email" /></label></>}
      <button disabled={loading} type="submit">Xem báo cáo</button>
    </form>
    {loading && <p role="status">Đang tải báo cáo…</p>}
    {error && <div role="alert" className="error-box">{error} <button className="secondary" onClick={() => setRefresh(n => n + 1)}>Thử lại</button></div>}
    {data && <><MetricsStrip value={data.summary} admin={admin} />
      <div className="report-breakdowns"><section className="panel"><h2>Hoạt động theo ngày</h2><p>{data.date_from} → {data.date_to} · UTC</p>
        {data.daily.length === 0 ? <p>Chưa có lượt sử dụng trong khoảng đã chọn.</p> : <div className="report-daily" role="list" aria-label="Số yêu cầu AI theo ngày">{data.daily.map(day => <div role="listitem" key={day.day} className="report-day"><time>{day.day.slice(5)}</time><div className="report-bar-track" aria-hidden="true"><span style={{ width: `${Math.max(1, day.requests / Math.max(1, ...data.daily.map(d => d.requests)) * 100)}%` }} /></div><span>{number(day.requests)} lượt</span></div>)}</div>}
      </section><section className="panel"><h2>{manager ? 'Sử dụng theo vai trò' : 'Kết quả sử dụng'}</h2><p>{number(data.summary.active_users)} tài khoản có yêu cầu AI trong kỳ.</p>
        <div className="report-table-scroll" tabIndex={0} role="region" aria-label="Thống kê theo vai trò"><table className="report-table"><thead><tr><th>Vai trò</th><th>Yêu cầu AI</th><th>Credit đã dùng</th></tr></thead><tbody>{data.roles.map(role => <tr key={role.role}><td>{getStoredRoleLabel(role.role)}</td><td>{number(role.requests)}</td><td>{number(role.credits_charged)}</td></tr>)}</tbody></table></div>
        {admin && <p className="report-note">{number(data.summary.input_tokens)} token vào / {number(data.summary.output_tokens)} token ra.{(data.summary.unknown_token_calls ?? 0) > 0 && ` ${number(data.summary.unknown_token_calls)} lần gọi thiếu dữ liệu token.`}</p>}
      </section></div>
      <section className="panel"><header className="report-section-head"><h2>{manager ? 'Sử dụng theo tài khoản' : 'Gói và lịch sử của bạn'}</h2><span>{number(data.total_users)} tài khoản</span></header>
        {data.users.length === 0 ? <p>Không tìm thấy tài khoản. Thử đổi tên, vai trò hoặc khoảng thời gian.</p> : <div className="report-table-scroll" tabIndex={0} role="region" aria-label="Thống kê tài khoản"><table className="report-table"><thead><tr><th>Tài khoản</th><th>Vai trò</th><th>Gói / số dư</th><th>Yêu cầu AI</th><th>Credit đã dùng</th>{admin && <th>Chi phí ước tính</th>}<th>Chi tiết</th></tr></thead><tbody>{data.users.map(row => <tr key={row.id} className={selected === row.id ? 'report-row-selected' : ''}>
          <td>{row.name}<small>{row.email}{!row.is_active && ' · Đã khóa'}</small></td><td>{getStoredRoleLabel(row.role)}</td><td>{row.plan ?? 'Chưa kích hoạt'}<small>{row.credit_balance === null ? '—' : `${number(row.credit_balance)} credit`}</small></td><td>{number(row.requests)}<small>{number(row.failed)} thất bại</small></td><td>{number(row.credits_charged)}</td>{admin && <td>{money(row.estimated_cost_usd)}</td>}<td><button className="secondary" aria-label={`Xem ${row.email}`} aria-expanded={selected === row.id} onClick={() => setSelected(row.id)}>Xem tài khoản</button></td>
        </tr>)}</tbody></table></div>}
        <Pager offset={data.offset} limit={data.limit} total={data.total_users} onChange={offset => { setSelected(null); setFilters({ ...filters, offset }); }} />
      </section>
    </>}
    {selected !== null && <AccountDetail key={`${selected}-${filters.date_from}-${filters.date_to}`} id={selected} filters={filters} admin={admin} onClose={() => setSelected(null)} onSaved={() => setRefresh(n => n + 1)} />}
    <p className="report-note">Báo cáo tính các thao tác AI đã được ghi nhận, không tính lượt đăng nhập hay lượt xem trang. Vai trò và số dư hiển thị theo hiện tại; số liệu hoạt động theo khoảng ngày đã chọn. Mỗi yêu cầu chỉ được tính một lần, dù AI gọi nhiều model.</p>
  </div>;
}
