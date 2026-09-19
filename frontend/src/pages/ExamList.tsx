import { useEffect, useState } from "react";
import { Link } from "react-router";

import { canWriteContent } from "../auth/rolePolicy";
import { SelectControl, SkeletonGrid } from "../components";
import { useAuth } from "../contexts/useAuth";
import { searchExams } from "../services/api";
import type { ExamListItem } from "../types";
import { getApiErrorMessage } from "../utils/apiError";


const PAGE_SIZE = 10;

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("vi-VN", {
    year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function ExamList() {
  const { user } = useAuth();
  const [items, setItems] = useState<ExamListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [subject, setSubject] = useState("");
  const [examType, setExamType] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [grade, setGrade] = useState<number | "">("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const canWrite = canWriteContent(user?.role);
  const canFilterOwner = user?.role === "super_admin" || user?.role === "school_admin";

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      searchExams({
        subject: subject.trim() || undefined,
        exam_type: examType.trim() || undefined,
        grade: grade === "" ? undefined : Number(grade),
        owner_user_id: canFilterOwner && ownerId ? Number(ownerId) : undefined,
        page,
        page_size: PAGE_SIZE,
      }).then((result) => {
        if (!controller.signal.aborted) {
          setItems(result.items);
          setTotal(result.total);
        }
      }).catch((reason) => {
        if (!controller.signal.aborted) setError(getApiErrorMessage(reason, "Không tải được danh sách đề"));
      }).finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    }, 250);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [subject, examType, ownerId, grade, page, canFilterOwner]);

  useEffect(() => setPage(1), [subject, examType, ownerId, grade]);

  return <section className="content-page">
    <div className="panel-header">
      <div><h2>Đề kiểm tra</h2><p className="muted">Phạm vi: {user?.role === "super_admin" ? "toàn hệ thống" : user?.role === "school_admin" ? "trong trường" : "của tôi"}</p></div>
      {canWrite && <Link to="/create" className="button-link compact">Tạo đề mới</Link>}
    </div>

    <div className="list-toolbar">
      <input className="search-input" value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="Tìm theo môn học…" />
      <input className="search-input" value={examType} onChange={(event) => setExamType(event.target.value)} placeholder="Loại kiểm tra…" />
      <SelectControl ariaLabel="Lọc đề theo khối" value={grade} onChange={(value) => setGrade(value === "" ? "" : Number(value))} options={[
        { value: "", label: "Tất cả khối" },
        ...[6, 7, 8, 9].map((value) => ({ value, label: `Lớp ${value}` })),
      ]} />
      {canFilterOwner && <input className="search-input" type="number" min="1" value={ownerId} onChange={(event) => setOwnerId(event.target.value)} placeholder="ID người tạo…" />}
    </div>

    {loading && <SkeletonGrid count={4} label="Đang tải danh sách đề" />}
    {error && <div className="error-box"><p className="error">{error}</p></div>}
    {!loading && !error && items.length === 0 && <div className="empty-state"><h3>Không tìm thấy đề phù hợp</h3><p>Thử thay đổi bộ lọc hoặc tạo đề mới.</p></div>}

    {!loading && items.length > 0 && <>
      <div className="exam-count">Hiển thị {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} / tổng {total} đề</div>
      <div className="list">{items.map((exam) => <Link to={`/exams/${exam.id}`} className="list-item" key={exam.id}>
        <div className="list-item-head"><strong>{exam.school}</strong>{exam.exam_number != null && <span className="badge badge-primary" title="Số thứ tự đề của người tạo">#{exam.exam_number}</span>}</div>
        <div className="list-item-meta"><span>{exam.exam_type}</span><span>Lớp {exam.grade}</span><span>{exam.subject}</span><span>{exam.duration_minutes} phút</span>{exam.owner_name && <span>Người tạo: {exam.owner_name}</span>}</div>
        <div className="list-item-footer">
          <small className="muted">{formatDate(exam.created_at)}</small>
          {exam.publication_status === "draft" && <span className="badge">Bản nháp · chưa kiểm định</span>}
        </div>
      </Link>)}</div>
      {totalPages > 1 && <div className="pagination">
        <button type="button" className="secondary compact" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Trước</button>
        <span>Trang {page}/{totalPages}</span>
        <button type="button" className="secondary compact" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Sau</button>
      </div>}
    </>}
  </section>;
}
