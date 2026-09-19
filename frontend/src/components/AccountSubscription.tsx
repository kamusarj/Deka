import { useEffect, useState } from "react";
import { getCredits, getSubscription, type CreditEntry, type Subscription } from "../services/aiAccount";
import { Link } from "react-router";
import { getToken } from "../contexts/authStorage";
import "../styles/subscription.css";

const numbers = new Intl.NumberFormat("vi-VN");
const transactionNames: Record<string, string> = {
  subscription: "Cấp credit theo gói", reserve: "Tạm giữ cho lượt sử dụng AI",
  settle: "Hoàn tất lượt sử dụng", refund: "Hoàn credit", adjustment: "Điều chỉnh credit",
};

function dateLabel(value: string, time = false) {
  // Legacy SQLite timestamps have no offset; backend writes them in UTC.
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return "Chưa có thông tin";
  return date.toLocaleDateString("vi-VN", time
    ? { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }
    : { day: "2-digit", month: "2-digit", year: "numeric" });
}

type Snapshot = { subscription: Subscription | null; balance: number; transactions: CreditEntry[] };

export default function AccountSubscription() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const token = getToken();
    setLoading(true);
    setError(false);
    Promise.all([getSubscription(controller.signal), getCredits(controller.signal)])
      .then(([subscription, credits]) => {
        if (controller.signal.aborted || getToken() !== token) return;
        setSnapshot({ subscription, ...credits });
        setLoading(false);
      })
      .catch(() => {
        if (controller.signal.aborted || getToken() !== token) return;
        setSnapshot(null);
        setError(true);
        setLoading(false);
      });
    return () => controller.abort();
  }, [refresh]);

  const subscription = snapshot?.subscription;
  return (
    <section className="subscription-panel" aria-labelledby="subscription-heading" aria-busy={loading}>
      <header className="subscription-heading">
        <div>
          <h2 id="subscription-heading">Gói sử dụng</h2>
        </div>
        <button type="button" className="subscription-refresh" aria-label="Tải lại số dư" title="Tải lại số dư" disabled={loading} onClick={() => setRefresh(value => value + 1)}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5" /><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1" /></svg>
        </button>
      </header>
      {loading && !snapshot && <div className="subscription-loading" role="status">Đang tải gói sử dụng và số dư credit…</div>}
      {error && <div className="subscription-error" role="alert">
        <strong>Chưa tải được gói sử dụng</strong>
        <p>Vui lòng kiểm tra kết nối và chọn Tải lại để xem số dư mới nhất.</p>
      </div>}
      {snapshot && !subscription && <p className="subscription-empty">Chưa kích hoạt gói. Credit thử nghiệm sẽ được cấp khi bạn bắt đầu thao tác AI đầu tiên.</p>}
      {snapshot && subscription && <>
        {subscription.renewal_due && <p role="status">Kỳ sử dụng đã kết thúc. Gói đang hoạt động sẽ được gia hạn một kỳ khi bạn bắt đầu thao tác AI tiếp theo.</p>}
        <div className="subscription-overview">
          <div className="subscription-plan">
            <strong>{subscription.plan}</strong>
            <span className={`subscription-status ${subscription.status === "active" ? "is-active" : "is-inactive"}`}>
              {subscription.status === "active" ? "Đang hoạt động" : "Tạm dừng"}
            </span>
          </div>
          <div className="subscription-balance">
            <span className="subscription-label">Credit khả dụng</span>
            <div><strong>{numbers.format(snapshot.balance)}</strong><span>credit</span></div>
            <p>{numbers.format(subscription.credit_allowance)} credit mỗi kỳ; gia hạn khi sử dụng AI, không truy lĩnh tháng bỏ lỡ.</p>
          </div>
          <dl className="subscription-period">
            <div><dt>Kỳ sử dụng hiện tại</dt><dd>{dateLabel(subscription.current_period_start)} – {dateLabel(subscription.current_period_end)}</dd></div>
            <div><dt>Credit chưa dùng</dt><dd>Được giữ lại cho kỳ tiếp theo</dd></div>
          </dl>
        </div>
        {snapshot.balance === 0 && <p className="subscription-zero" role="status">Bạn đã dùng hết credit khả dụng. Liên hệ quản trị viên để bổ sung trước khi tạo đề mới.</p>}
        <p className="subscription-note">Cần thêm credit hoặc đổi gói? Liên hệ quản trị viên để được hỗ trợ.</p>
        <Link to="/usage" className="subscription-report-link">Xem thống kê sử dụng <span aria-hidden="true">↗</span></Link>
        <details className="subscription-ledger">
          <summary><span>Lịch sử credit</span><span aria-hidden="true">⌄</span></summary>
          <p className="subscription-history-caption">10 giao dịch gần nhất</p>
          {snapshot.transactions.length ? <ul className="subscription-history" aria-label="Biến động credit gần đây">
            {snapshot.transactions.map(item => <li key={item.id}>
              <div><strong>{transactionNames[item.type] || "Cập nhật credit"}</strong><time dateTime={item.created_at}>{dateLabel(item.created_at, true)}</time></div>
              <strong className={`subscription-delta ${item.amount > 0 ? "is-positive" : ""}`}>
                {item.amount > 0 ? "+" : ""}{numbers.format(item.amount)}<span> credit</span>
              </strong>
            </li>)}
          </ul> : <div className="subscription-empty"><strong>Chưa có biến động credit</strong><p>Các lần cấp, sử dụng và hoàn credit sẽ được lưu tại đây.</p></div>}
        </details>
      </>}
    </section>
  );
}
