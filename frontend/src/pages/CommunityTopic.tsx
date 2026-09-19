import { useContext, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import BankQuestionBody from "../components/BankQuestionBody";
import { AuthContext } from "../contexts/authContextValue";
import { canWriteContent } from "../auth/rolePolicy";
import { addCommunityComment, deleteCommunityComment, deleteCommunityTopic, getCommunityTopic, listCommunityComments, saveCommunityQuestion } from "../services/api";
import { getApiErrorMessage } from "../utils/apiError";
import { formatDifficulty, formatQuestionType } from "../utils/labels";
import type { CommunityComment, CommunityPage, CommunityTopicDetail } from "../types";

export default function CommunityTopicPage() {
  const { id } = useParams();
  return <TopicDiscussion key={id} id={Number(id)} />;
}

function TopicDiscussion({ id }: { id: number }) {
  const navigate = useNavigate();
  const user = useContext(AuthContext)?.user;
  const [topic, setTopic] = useState<CommunityTopicDetail | null>(null);
  const [comments, setComments] = useState<CommunityPage<CommunityComment> | null>(null);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [body, setBody] = useState("");
  const [reply, setReply] = useState<CommunityComment | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true); setLoadError("");
      try {
        const [nextTopic, nextComments] = await Promise.all([getCommunityTopic(id, controller.signal), listCommunityComments(id, page, controller.signal)]);
        if (!controller.signal.aborted) { setTopic(nextTopic); setComments(nextComments); }
      } catch (err) {
        if (!controller.signal.aborted) { setTopic(null); setComments(null); setLoadError(getApiErrorMessage(err, "Không tải được chủ đề")); }
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => controller.abort();
  }, [id, page, refresh]);

  async function send(event: React.FormEvent) {
    event.preventDefault(); if (!body.trim()) return;
    setBusy(true); setError("");
    try {
      await addCommunityComment(id, body.trim(), reply?.id);
      setBody(""); setReply(null);
      const latest = await listCommunityComments(id);
      setPage(Math.max(1, Math.ceil(latest.total/latest.page_size)));
      setRefresh(value => value+1);
    } catch (err) { setError(getApiErrorMessage(err, "Không gửi được bình luận")); }
    finally { setBusy(false); }
  }
  async function remove(commentId?: number) {
    if (!window.confirm(commentId ? "Gỡ bình luận này?" : "Gỡ chủ đề khỏi cộng đồng? Mọi người sẽ không thể xem hoặc bình luận thêm.")) return;
    setBusy(true); setError("");
    try {
      if (commentId) {
        await deleteCommunityComment(id, commentId);
        if (reply?.id === commentId) setReply(null);
        setRefresh(value => value+1);
      } else { await deleteCommunityTopic(id); navigate("/community"); }
    } catch (err) { setError(getApiErrorMessage(err, "Không gỡ được nội dung")); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setError("");
    try { await saveCommunityQuestion(id); setSaved(true); }
    catch (err) { setError(getApiErrorMessage(err, "Không lưu được câu hỏi")); }
    finally { setBusy(false); }
  }
  return <section className="content-page community-page">
    <Link to="/community">← Ngân hàng câu hỏi cộng đồng</Link>
    {loadError && <div role="alert" className="error-box"><p>{loadError}</p><button className="btn-secondary" onClick={() => setRefresh(value => value+1)}>Thử lại</button></div>}
    {error && <p role="alert" className="error">{error}</p>}
    {loading && <p role="status">Đang tải thảo luận…</p>}
    {topic && <>
      <article className="question-card community-topic-card">
        <h2>{topic.title}</h2>
        <p className="muted">{topic.author.name} · {new Date(topic.created_at).toLocaleString("vi-VN")}</p>
        <div className="tag-row"><span className="tag">{formatQuestionType(topic.type)}</span>{topic.grade && <span className="tag">Lớp {topic.grade}</span>}<span className="tag">{formatDifficulty(topic.difficulty)}</span></div>
        <BankQuestionBody question={{ ...topic.question, id: topic.id, usage_count: 0 }} collapsibleAnswer />
        <div className="community-actions">
          {canWriteContent(user?.role) && <button className="btn-secondary" disabled={busy || loading || saved} onClick={save}>{saved ? "Đã lưu vào ngân hàng" : "Lưu vào ngân hàng của tôi"}</button>}
          {saved && <Link to="/question-bank">Mở ngân hàng của tôi →</Link>}
          {topic.can_manage && <button className="btn-danger compact" disabled={busy || loading} onClick={() => remove()}>Gỡ chủ đề</button>}
        </div>
      </article>
      <section aria-labelledby="discussion-title" className="community-discussion">
        <div className="panel-header"><h3 id="discussion-title">Trao đổi · {topic.comment_count} bình luận</h3><button className="btn-secondary compact" disabled={busy || loading} onClick={() => setRefresh(value => value+1)}>Tải lại thảo luận</button></div>
        {!comments?.items.length && !loading && <p className="muted">Chưa có bình luận. Hãy chia sẻ cách giải hoặc đặt câu hỏi đầu tiên.</p>}
        {comments?.items.map(comment => <article key={comment.id} id={`comment-${comment.id}`} className={`community-comment${comment.parent_id ? " is-reply" : ""}`}>
          <div className="community-topic-footer"><strong>{comment.author.name}</strong><small>{new Date(comment.created_at).toLocaleString("vi-VN")} · #{comment.id}</small></div>
          {comment.parent_id && <small className="muted">Trả lời bình luận #{comment.parent_id}{comments.items.find(item => item.id === comment.parent_id)?.author.name ? ` của ${comments.items.find(item => item.id === comment.parent_id)?.author.name}` : ""}</small>}
          <p className="community-text">{comment.deleted ? "Bình luận đã được gỡ." : comment.body}</p>
          {!comment.deleted && <div className="community-actions"><button className="btn-secondary compact" disabled={busy || loading} onClick={() => { setReply(comment); document.getElementById("community-reply")?.focus(); }}>Trả lời</button>
            {comment.can_manage && <button className="btn-danger compact" disabled={busy || loading} onClick={() => remove(comment.id)}>Gỡ bình luận</button>}</div>}
        </article>)}
        {comments && comments.total > comments.page_size && <nav className="community-actions" aria-label="Phân trang bình luận"><button className="btn-secondary" disabled={page === 1 || loading} onClick={() => setPage(value => value-1)}>Bình luận trước</button><span>Trang {page} / {Math.ceil(comments.total/comments.page_size)}</span><button className="btn-secondary" disabled={page*comments.page_size >= comments.total || loading} onClick={() => setPage(value => value+1)}>Bình luận sau</button></nav>}
        <form className="community-composer" onSubmit={send}>
          {reply && <div className="community-reply-context"><p>Đang trả lời {reply.author.name} · #{reply.id}</p><blockquote>{reply.body?.slice(0, 250)}</blockquote><button type="button" className="btn-secondary compact" disabled={busy} onClick={() => setReply(null)}>Hủy trả lời</button></div>}
          <label htmlFor="community-reply">Bình luận của bạn</label><textarea id="community-reply" rows={4} required maxLength={5000} placeholder="Trao đổi cách giải, đặt câu hỏi hoặc góp ý…" value={body} onChange={e => setBody(e.target.value)} />
          <button className="btn-primary" disabled={busy || loading || !body.trim()}>{busy ? "Đang xử lý…" : "Gửi bình luận"}</button>
        </form>
      </section>
    </>}
  </section>;
}
