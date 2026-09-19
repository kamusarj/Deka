import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { getPlans, type Plan } from '../services/usageReports';
import { useAuth } from '../contexts/useAuth';
import '../styles/usage-reports.css';

const descriptions: Record<string, { title: string; description: string }> = {
  FREE: { title: 'Làm quen với cách soạn đề mới', description: 'Bắt đầu với những bộ đề đầu tiên, tìm quy trình phù hợp với bạn.' },
  BASIC: { title: 'Đồng hành cùng tiết dạy', description: 'Dành cho giáo viên soạn đề và điều chỉnh câu hỏi thường xuyên.' },
  PRO: { title: 'Chuẩn bị cho nhiều lớp học', description: 'Hạn mức rộng hơn cho nhiều lớp, nhiều chủ đề và các đợt kiểm tra.' },
};
export default function SubscriptionPlans() {
  const { isAuthenticated } = useAuth();
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    getPlans(controller.signal).then(value => {
      if (!controller.signal.aborted) setPlans(value);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [retry]);
  return <section id="goi-su-dung" className="paper-section plan-section" aria-labelledby="plans-heading">
    <div className="paper-section-heading"><h2 id="plans-heading">Một gói phù hợp với nhịp dạy của bạn.</h2><p>Chọn hạn mức credit theo nhu cầu chuẩn bị bài kiểm tra.</p></div>
    {error ? <div role="alert" className="error-box">Chưa tải được các gói sử dụng. <button className="secondary" onClick={() => setRetry(n => n + 1)}>Thử lại</button></div>
      : !plans ? <p role="status">Đang tải các gói sử dụng…</p> : <div className="plan-grid">{plans.map(plan => <article key={plan.id} className={`plan-card ${plan.id === 'BASIC' ? 'plan-card-featured' : ''}`}>
        <h3>{plan.id}</h3><p className="plan-purpose">{descriptions[plan.id]?.title}</p>
        <p className="plan-allowance"><strong>{plan.monthly_credits.toLocaleString('vi-VN')}</strong><span>credit / tháng</span></p>
        <p>{descriptions[plan.id]?.description}</p>
        <ul><li>Tạo đề từ nội dung và tài liệu của bạn</li><li>Duyệt, chỉnh sửa câu hỏi và đáp án</li><li>Theo dõi credit và lịch sử sử dụng</li></ul>
        <Link className={`paper-button ${plan.id === 'BASIC' ? '' : 'paper-button-quiet'}`} to={isAuthenticated ? '/account' : '/register'}>
          {isAuthenticated ? 'Xem gói của tôi' : plan.id === 'FREE' ? 'Bắt đầu với Free' : 'Tạo tài khoản'}
        </Link>
      </article>)}</div>}
    <p className="plan-note">Các hạn mức đang trong giai đoạn thử nghiệm. Tài khoản mới bắt đầu với Free; liên hệ quản trị viên để được cấp Basic, Pro hoặc hạn mức riêng. Chưa áp dụng thanh toán.</p>
  </section>;
}
