import DataProcessingNotice from "../components/DataProcessingNotice";
import { DragEvent, useCallback, useContext, useEffect, useRef, useState } from "react";
import { SelectControl, SkeletonGrid } from "../components";
import { useToast } from "../contexts/useToast";
import { deleteDocument, getDocument, listDocuments, uploadDocument, updateDocumentSharing, reviewDocumentSharing } from "../services/api";
import type { DocumentDetailResponse, DocumentResponse, DocumentScope, DocumentLibrary } from "../types";
import { getApiErrorMessage } from "../utils/apiError";
import { validateDocumentFile } from "../utils/documentUpload";
import { AuthContext } from "../contexts/authContextValue";
import { canWriteContent, isSuperAdminRole } from "../auth/rolePolicy";
import { documentSharingLabel } from "../utils/documentSharing";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Documents() {
  const user = useContext(AuthContext)?.user ?? { role: "teacher" };
  const canWrite = canWriteContent(user?.role);
  const isSuperAdmin = isSuperAdminRole(user?.role);
  const [library, setLibrary] = useState<DocumentLibrary>("all");
  const [changingId, setChangingId] = useState<number | null>(null);
  const [reviewNotes, setReviewNotes] = useState<Record<number, string>>({});
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [ocrMode, setOcrMode] = useState<"auto" | "native" | "ocr">("auto");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [grade, setGrade] = useState<number | "">("");
  const [dragActive, setDragActive] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetailResponse | null>(null);
  const [viewingDocumentId, setViewingDocumentId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const listRequest = useRef(0);
  const detailRequest = useRef(0);
  const [refresh, setRefresh] = useState(0);
  const { notify } = useToast();

  const load = useCallback(async () => {
    const request = ++listRequest.current;
    ++detailRequest.current;
    setLoading(true);
    setError("");
    setDocuments([]);
    setSelectedDocument(null);
    setViewingDocumentId(null);
    try {
      const result = await listDocuments(grade === "" ? undefined : Number(grade), library);
      if (request === listRequest.current) setDocuments(result);
    } catch (err: unknown) {
      if (request === listRequest.current) setError(getApiErrorMessage(err, "Không tải được danh sách tài liệu"));
    } finally {
      if (request === listRequest.current) setLoading(false);
    }
  }, [grade, library]);

  useEffect(() => {
    void load();
    return () => {
      listRequest.current += 1;
      detailRequest.current += 1;
    };
  }, [load, refresh]);

  async function onUpload(file: File) {
    const validationError = validateDocumentFile(file);
    if (validationError) {
      setError(validationError);
      notify(validationError, "error");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setUploading(true);
    setError("");
    try {
      await uploadDocument(file, grade === "" ? undefined : Number(grade), ocrMode);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setRefresh(value => value + 1);
      notify(`Đã tải lên "${file.name}"`, "success");
    } catch (err: unknown) {
      const message = getApiErrorMessage(err, "Không upload được tài liệu");
      setError(message);
      notify(message, "error");
    } finally {
      setUploading(false);
    }
  }

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (!uploading) setDragActive(true);
  }

  function onDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);

    const file = event.dataTransfer.files?.[0];
    if (file && !uploading) onUpload(file);
  }

  async function onDelete(id: number) {
    if (!window.confirm("Xóa tài liệu này?")) return;
    setError("");
    try {
      await deleteDocument(id);
      setRefresh(value => value + 1);
      notify("Đã xóa tài liệu", "success");
    } catch (err: unknown) {
      const message = getApiErrorMessage(err, "Không xóa được tài liệu");
      setError(message);
      notify(message, "error");
    }
  }

  async function onView(id: number) {
    const request = ++detailRequest.current;
    setViewingDocumentId(id);
    setSelectedDocument(null);
    setError("");
    try {
      const document = await getDocument(id);
      if (request === detailRequest.current) setSelectedDocument(document);
    } catch (err: unknown) {
      if (request !== detailRequest.current) return;
      const message = getApiErrorMessage(err, "Không tải được nội dung tài liệu");
      setError(message);
      notify(message, "error");
    } finally {
      if (request === detailRequest.current) setViewingDocumentId(null);
    }
  }

  async function changeSharing(doc: DocumentResponse, scope: DocumentScope) {
    setChangingId(doc.id);
    setError("");
    try {
      await updateDocumentSharing(doc.id, scope, doc.version_id ?? 1);
      setRefresh(value => value + 1);
      notify(scope === "system" ? "Đã gửi yêu cầu chia sẻ toàn hệ thống, chờ Super Admin duyệt" : "Đã cập nhật phạm vi chia sẻ", "success");
    } catch (err) {
      const message = getApiErrorMessage(err, "Không cập nhật được chia sẻ. Hãy tải lại danh sách.");
      setError(message);
      notify(message, "error");
    } finally {
      setChangingId(null);
    }
  }

  async function reviewSharing(doc: DocumentResponse, decision: "approve" | "reject") {
    setChangingId(doc.id);
    setError("");
    try {
      await reviewDocumentSharing(doc.id, decision, doc.version_id ?? 1, reviewNotes[doc.id] ?? "");
      setRefresh(value => value + 1);
      notify(decision === "approve" ? "Đã đưa tài liệu vào kho toàn hệ thống" : "Tài liệu chưa được phép chia sẻ toàn hệ thống", "success");
    } catch (err) {
      const message = getApiErrorMessage(err, "Không duyệt được tài liệu. Hãy tải lại danh sách.");
      setError(message);
      notify(message, "error");
    } finally {
      setChangingId(null);
    }
  }

  return (
    <section className="content-page">
      <div className="panel-header">
        <h2>Thư viện tài liệu</h2>
      </div>
      <p className="muted">Tài liệu mới được lưu riêng tư. Bạn có thể chia sẻ trong trường hoặc gửi duyệt để dùng chung toàn hệ thống.</p>

      <DataProcessingNotice />
      <div className="list-toolbar">
        <label style={{ minWidth: 200 }}>
          Kho tài liệu
          <SelectControl
            ariaLabel="Chọn kho tài liệu"
            value={library}
            onChange={(value) => setLibrary(value as DocumentLibrary)}
            options={[
              { value: "all", label: "Tất cả được xem" },
              { value: "mine", label: "Của tôi" },
              { value: "school", label: "Trong trường" },
              { value: "system", label: "Toàn hệ thống" },
              ...(isSuperAdmin ? [{ value: "pending", label: "Chờ duyệt toàn hệ thống" }] : []),
            ]}
          />
        </label>
        <label style={{ minWidth: 160 }}>
          Khối
          <SelectControl
            ariaLabel="Lọc tài liệu theo khối"
            value={grade}
            onChange={(value) => setGrade(value === "" ? "" : Number(value))}
            options={[
              { value: "", label: "Tất cả" },
              ...[6, 7, 8, 9].map((item) => ({ value: item, label: `Lớp ${item}` })),
            ]}
          />
        </label>
        {canWrite && <label>Cách đọc tài liệu
          <SelectControl
            ariaLabel="Cách đọc tài liệu"
            value={ocrMode}
            disabled={uploading}
            onChange={setOcrMode}
            options={[
              { value: "auto", label: "Tự động · OCR khi cần" },
              { value: "native", label: "Chỉ đọc văn bản có sẵn" },
              { value: "ocr", label: "Đọc lại ảnh/trang bằng OCR · bố cục hoặc công thức khó" },
            ]}
          />
        </label>}
        {canWrite && <div
          className={`upload-dropzone ${dragActive ? "upload-dropzone-active" : ""}`}
          data-allow-file-drop="true"
          onDragOver={onDragOver}
          onDragEnter={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg"
            disabled={uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onUpload(file);
            }}
          />
          <strong>Kéo thả PDF, DOCX, XLSX hoặc ảnh PNG/JPEG vào đây</strong>
          <span className="muted">hoặc chọn file từ thiết bị · tối đa 20 MB</span>
        </div>}
        {uploading && <span className="muted">Đang upload & trích xuất…</span>}
        <button type="button" className="secondary compact" onClick={load} disabled={loading}>Tải lại danh sách</button>
      </div>

      {error && (
        <div className="error-box">
          <p className="error">{error}</p>
        </div>
      )}
      {loading && <SkeletonGrid count={3} label="Đang tải tài liệu" />}

      {!loading && documents.length === 0 && (
        <div className="empty-state">
          <h3>Chưa có tài liệu nào</h3>
          <p>{canWrite ? "Hãy upload tài liệu đầu tiên để dùng làm nguồn cho AI tạo đề." : "Chưa có tài liệu nào trong phạm vi bạn được xem."}</p>
        </div>
      )}

      {!loading && documents.length > 0 && (
        <div className="list">
          {documents.map((doc) => (
            <div className="list-item" key={doc.id}>
              <div className="list-item-head">
                <strong>{doc.filename}</strong>
                <span className="badge badge-accent">{doc.file_type.toUpperCase()}</span>
              </div>
              <div className="list-item-meta">
                <span>{formatSize(doc.size)}</span>
                {doc.grade != null && <span>Lớp {doc.grade}</span>}
                <span>{doc.text_length} ký tự</span>
                <span className="badge">{documentSharingLabel(doc)}</span>
                {!doc.can_manage && <span>Chỉ xem và dùng làm nguồn</span>}
              </div>
              {Array.isArray(doc.parsed_data?.extraction_warnings) && doc.parsed_data.extraction_warnings.length > 0 && <div role="status" className="warning-box"><strong>Cần kiểm tra nội dung trích xuất</strong><ul>{doc.parsed_data.extraction_warnings.map((warning, index) => <li key={index}>{String(warning)}</li>)}</ul></div>}
              {doc.can_manage && doc.review_note && <p className="muted">Ghi chú duyệt: {doc.review_note}</p>}
              {canWrite && doc.can_manage && <div className="list-toolbar">
                <label>
                  Phạm vi chia sẻ
                  <SelectControl
                    ariaLabel={`Phạm vi chia sẻ của ${doc.filename}`}
                    value={doc.sharing_scope ?? "private"}
                    disabled={changingId !== null}
                    onChange={(value) => changeSharing(doc, value as DocumentScope)}
                    options={[
                      { value: "private", label: "Cá nhân" },
                      { value: "school", label: "Trong trường", disabled: !doc.can_share_school },
                      { value: "system", label: "Toàn hệ thống · cần duyệt" },
                    ]}
                  />
                </label>
                {doc.sharing_scope === "system" && doc.sharing_status === "pending" && <small>Chờ duyệt: tài liệu chưa được mở cho người dùng khác; quản trị viên vẫn có quyền xem theo phạm vi quản lý.</small>}
                {doc.sharing_scope === "system" && doc.sharing_status === "rejected" && <button type="button" className="secondary compact" disabled={changingId !== null} onClick={() => changeSharing(doc, "system")}>Gửi duyệt lại</button>}
                {doc.sharing_scope && doc.sharing_scope !== "private" && <button type="button" className="secondary compact" disabled={changingId !== null} onClick={() => changeSharing(doc, "private")}>Thu hồi chia sẻ</button>}
              </div>}
              {isSuperAdmin && doc.can_review && <div className="list-toolbar">
                <label>
                  Ghi chú duyệt (không bắt buộc)
                  <input aria-label={`Ghi chú duyệt ${doc.filename}`} maxLength={1000} value={reviewNotes[doc.id] ?? ""} onChange={(event) => setReviewNotes((notes) => ({ ...notes, [doc.id]: event.target.value }))} />
                </label>
                {doc.sharing_status === "pending" && <button type="button" disabled={changingId !== null} onClick={() => reviewSharing(doc, "approve")}>Duyệt toàn hệ thống</button>}
                <button type="button" className="btn-danger compact" disabled={changingId !== null} onClick={() => reviewSharing(doc, "reject")}>{doc.sharing_status === "approved" ? "Thu hồi duyệt" : "Từ chối"}</button>
              </div>}
              <div className="list-item-footer list-item-footer-end">
                <button
                  type="button"
                  className="secondary compact"
                  onClick={() => onView(doc.id)}
                  disabled={viewingDocumentId === doc.id}
                >
                  {viewingDocumentId === doc.id ? "Đang mở…" : "Xem nội dung"}
                </button>
                {canWrite && doc.can_manage && <button
                  type="button"
                  className="btn-danger compact"
                  onClick={() => onDelete(doc.id)}
                  disabled={changingId !== null}
                >
                  Xóa
                </button>}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedDocument && (
        <section className="document-viewer" aria-labelledby="document-viewer-title">
          <div className="document-viewer-head">
            <div>
              <h3 id="document-viewer-title">{selectedDocument.filename}</h3>
              <p className="muted">Nội dung đã trích xuất · {selectedDocument.text_length} ký tự</p>
            </div>
            <button
              type="button"
              className="secondary compact"
              onClick={() => { ++detailRequest.current; setSelectedDocument(null); setViewingDocumentId(null); }}
            >
              Đóng
            </button>
          </div>
          <div className="document-content">
            {selectedDocument.extracted_text || "Tài liệu không có nội dung văn bản để hiển thị."}
          </div>
        </section>
      )}
    </section>
  );
}
