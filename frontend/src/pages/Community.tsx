import { useEffect, useState } from "react";
import { Link } from "react-router";
import { SelectControl, SkeletonGrid } from "../components";
import CommunityQuestionForm from "../components/CommunityQuestionForm";
import { listCommunityTopics } from "../services/api";
import { getApiErrorMessage } from "../utils/apiError";
import { formatDifficulty, formatQuestionType } from "../utils/labels";
import type { BankQuestionFilters, CommunityPage, CommunityTopic, Difficulty, QuestionType } from "../types";

export default function Community() {
  const [result, setResult] = useState<CommunityPage<CommunityTopic> | null>(null);
  const [filters, setFilters] = useState<BankQuestionFilters>({});
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [composing, setComposing] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true); setError("");
      try {
        const data = await listCommunityTopics({ ...filters, page }, controller.signal);
        if (!controller.signal.aborted) setResult(data);
      } catch (err) { if (!controller.signal.aborted) setError(getApiErrorMessage(err, "Không tải được cộng đồng")); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [filters, page, refresh]);
  function filter(next: BankQuestionFilters) { setFilters(previous => ({ ...previous, ...next })); setPage(1); }
  return <section className="content-page community-page">
    <div className="panel-header"><div><h2>Ngân hàng câu hỏi cộng đồng</h2><p className="muted">Mỗi câu hỏi là một cuộc thảo luận. Cùng chia sẻ cách giải và học hỏi từ nhau.</p></div>
      <button className="btn-primary" onClick={() => setComposing(value => !value)}>{composing ? "Đóng khung đăng" : "Đăng câu hỏi"}</button></div>
    {composing && <CommunityQuestionForm onCancel={() => setComposing(false)} />}
    <div className="list-toolbar">
      <input className="search-input" aria-label="Tìm câu hỏi cộng đồng" placeholder="Tìm câu hỏi, chủ đề..." maxLength={200} value={filters.search ?? ""} onChange={e => filter({ search: e.target.value })} />
      <SelectControl ariaLabel="Lọc cộng đồng theo khối" value={filters.grade ?? ""} onChange={value => filter({ grade: value ? Number(value) : undefined })} options={[{ value: "", label: "Tất cả khối" }, ...[6,7,8,9].map(value => ({ value, label: `Lớp ${value}` }))]} />
      <SelectControl ariaLabel="Lọc cộng đồng theo dạng" value={filters.type ?? ""} onChange={value => filter({ type: (value || undefined) as QuestionType | undefined })} options={[{ value: "", label: "Tất cả dạng" }, ...(["multiple_choice", "true_false", "short_answer", "essay"] as QuestionType[]).map(value => ({ value, label: formatQuestionType(value) }))]} />
      <SelectControl ariaLabel="Lọc cộng đồng theo mức độ" value={filters.difficulty ?? ""} onChange={value => filter({ difficulty: (value || undefined) as Difficulty | undefined })} options={[{ value: "", label: "Tất cả mức độ" }, ...(["nhan_biet", "thong_hieu", "van_dung"] as Difficulty[]).map(value => ({ value, label: formatDifficulty(value) }))]} />
      <button className="btn-secondary compact" onClick={() => setRefresh(value => value+1)}>Tải lại</button>
    </div>
    {error && <p role="alert" className="error">{error}</p>}
    {loading ? <SkeletonGrid count={3} label="Đang tải câu hỏi cộng đồng" /> : !error && <>
      {result?.items.length ? <><p className="muted">{result.total} chủ đề</p><div className="list">
        {result.items.map(topic => <article key={topic.id} className="question-card community-topic-card">
          <div className="tag-row"><span className="tag">{formatQuestionType(topic.type)}</span>{topic.grade && <span className="tag">Lớp {topic.grade}</span>}<span className="tag">{formatDifficulty(topic.difficulty)}</span></div>
          <h3><Link to={`/community/${topic.id}`}>{topic.title}</Link></h3><p className="community-text">{topic.preview}</p>
          <div className="community-topic-footer"><span>{topic.author.name} · {new Date(topic.created_at).toLocaleDateString("vi-VN")}</span><Link to={`/community/${topic.id}`}>{topic.comment_count} bình luận · Thảo luận →</Link></div>
        </article>)}
      </div></> : <div className="empty-state"><h3>Chưa có câu hỏi phù hợp</h3><p>Đăng câu hỏi đầu tiên hoặc chia sẻ câu từ ngân hàng riêng của bạn.</p></div>}
      {result && result.total > result.page_size && <nav className="community-actions" aria-label="Phân trang chủ đề"><button className="btn-secondary" disabled={page === 1} onClick={() => setPage(value => value-1)}>Trang trước</button><span>Trang {page} / {Math.ceil(result.total/result.page_size)}</span><button className="btn-secondary" disabled={page*result.page_size >= result.total} onClick={() => setPage(value => value+1)}>Trang sau</button></nav>}
    </>}
  </section>;
}
