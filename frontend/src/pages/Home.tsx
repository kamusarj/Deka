import { useEffect, useState } from "react";
import { Link } from "react-router";

import { canWriteContent, getStoredRoleLabel } from "../auth/rolePolicy";
import { useAuth } from "../contexts/useAuth";
import { getDashboardSummary, searchExams } from "../services/api";
import type { DashboardSummary, ExamListItem } from "../types";
import { getApiErrorMessage } from "../utils/apiError";


export default function Home() {
  const { user } = useAuth();
  const [recent, setRecent] = useState<ExamListItem[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [recentError, setRecentError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const canWrite = canWriteContent(user?.role);

  useEffect(() => {
    let active = true;
    setLoaded(false);
    setSummary(null);
    setRecent([]);
    setSummaryError("");
    setRecentError("");
    void Promise.allSettled([getDashboardSummary(), searchExams({ page: 1, page_size: 4 })])
      .then(([result, examPage]) => {
        if (!active) return;
        if (result.status === "fulfilled") setSummary(result.value);
        else setSummaryError(getApiErrorMessage(result.reason, "Không tải được thống kê"));
        if (examPage.status === "fulfilled") setRecent(examPage.value.items);
        else setRecentError(getApiErrorMessage(examPage.reason, "Không tải được đề gần đây"));
        setLoaded(true);
      });
    return () => { active = false; };
  }, [refresh]);

  const extraStat = user?.role === "super_admin"
    ? { value: summary?.users, label: "Tài khoản hoạt động" }
    : user?.role === "school_admin"
      ? { value: summary?.teachers, label: "Giáo viên trong trường" }
      : { value: summary?.documents, label: "Tài liệu" };

  return <div className="dashboard">
    <section className="dash-hero"><div className="dash-hero-content">
      <span className="badge badge-primary">{getStoredRoleLabel(user?.role)} · {summary?.scope_label ?? (loaded ? "Chưa tải được thống kê" : "Đang tải")}</span>
      <h1>{canWrite ? "Hôm nay, bạn muốn chuẩn bị gì?" : "Khám phá học liệu của bạn."}</h1>
      <p>{canWrite ? "Một đề kiểm tra mới, một ý tưởng hay, hay tiếp tục công việc đang dở. Mọi thứ bạn cần đều ở đây." : "Xem đề kiểm tra, đọc tài liệu và cùng thảo luận với cộng đồng giáo viên."}</p>
      <div className="dash-hero-actions">
        {canWrite && <Link to="/create" className="dash-cta">Tạo đề mới</Link>}
        <Link to="/exams" className="dash-cta dash-cta-outline">Xem đề kiểm tra</Link>
      </div>
    </div></section>

    {(summaryError || recentError) && <div className="error-box" role="alert">
      {summaryError && <p>{summaryError}</p>}
      {recentError && <p>{recentError}</p>}
      <button type="button" className="secondary" onClick={() => setRefresh(value => value + 1)}>Thử lại</button>
    </div>}

    <section><div className="dash-section-head"><h2>Tổng quan</h2><span className="muted">{summary?.scope_label}</span></div>
      <div className="stat-grid">
        <div className="stat-card"><span className="stat-value">{loaded && summary ? summary.exams ?? 0 : "—"}</span><span className="stat-label">Đề kiểm tra</span></div>
        <div className="stat-card"><span className="stat-value">{loaded && summary ? summary.questions ?? 0 : "—"}</span><span className="stat-label">Câu hỏi đã sinh</span></div>
        <div className="stat-card"><span className="stat-value">{loaded && summary ? summary.bank_questions ?? 0 : "—"}</span><span className="stat-label">Câu trong ngân hàng</span></div>
        <div className="stat-card"><span className="stat-value">{loaded && summary ? extraStat.value ?? 0 : "—"}</span><span className="stat-label">{extraStat.label}</span></div>
      </div>
    </section>

    <section className="workspace-shortcuts" aria-label="Lối tắt công việc">
      <Link to="/documents"><span className="shortcut-symbol" aria-hidden="true">▤</span><div><h3>Bắt đầu từ tài liệu</h3><p>Kho học liệu cho những câu hỏi sát bài dạy.</p></div><span aria-hidden="true">↗</span></Link>
      <Link to="/question-bank"><span className="shortcut-symbol" aria-hidden="true">▦</span><div><h3>Tìm lại câu hỏi hay</h3><p>Đọc và tái sử dụng từ ngân hàng của bạn.</p></div><span aria-hidden="true">↗</span></Link>
      <Link to="/community"><span className="shortcut-symbol" aria-hidden="true">✧</span><div><h3>Cùng nhau chia sẻ</h3><p>Thêm một góc nhìn từ cộng đồng giáo viên.</p></div><span aria-hidden="true">↗</span></Link>
    </section>

    <section><div className="dash-section-head"><h2>Đề gần đây</h2><Link to="/exams" className="ghost-btn compact">Xem tất cả →</Link></div>
      {!loaded && <p className="muted">Đang tải…</p>}
      {loaded && !recentError && recent.length === 0 && <div className="empty-state"><span className="empty-paper-mark" aria-hidden="true">▤</span><h3>Chưa có đề nào trong phạm vi này</h3><p>{canWrite ? "Bắt đầu một đề mới. Bạn có thể lưu và quay lại hoàn thiện bất cứ lúc nào." : "Những đề được chia sẻ trong phạm vi của bạn sẽ xuất hiện tại đây."}</p>{canWrite && <Link to="/create" className="paper-button paper-button-quiet">Tạo đề đầu tiên</Link>}</div>}
      {recent.length > 0 && <div className="list">{recent.map((exam) => <Link to={`/exams/${exam.id}`} className="list-item" key={exam.id}>
        <div className="list-item-head"><strong>{exam.school}</strong>{exam.exam_number != null && <span className="badge badge-primary" title="Số thứ tự đề của người tạo">#{exam.exam_number}</span>}</div>
        <div className="list-item-meta"><span>{exam.exam_type}</span><span>Lớp {exam.grade}</span><span>{exam.subject}</span></div>
      </Link>)}</div>}
    </section>
  </div>;
}
