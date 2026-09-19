import { useState } from "react";
import type { BankQuestion, Question } from "../types";
import type { QuestionEditPayload } from "./QuestionEditor";
import { bankEditTemplate, searchBankQuestions } from "../services/api";
import { getApiErrorMessage } from "../utils/apiError";
import BankQuestionBody from "./BankQuestionBody";

export default function BankReusePicker({ examId, question, version, onChoose }: { examId: number; question: Question; version: number; onChoose: (payload: QuestionEditPayload) => void }) {
  const [query, setQuery] = useState(question.content.slice(0, 2000));
  const [items, setItems] = useState<BankQuestion[]>([]);
  const [pending, setPending] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  return <details className="bank-reuse-picker"><summary>Lấy nội dung từ ngân hàng</summary>
    <p className="muted">Chọn câu cùng dạng và mức độ. Khi lưu, câu được kiểm định lại theo ma trận hiện tại.</p>
    <label>Tìm câu ngân hàng<input maxLength={2000} value={query} onChange={event => setQuery(event.target.value)} /></label>
    <button type="button" className="secondary" disabled={pending || !query.trim()} onClick={async () => {
      setPending(true); setError("");
      try { setItems(await searchBankQuestions(query, { type: question.type, difficulty: question.difficulty })); setSearched(true); }
      catch (failure) { setError(getApiErrorMessage(failure, "Không tìm được câu ngân hàng")); }
      finally { setPending(false); }
    }}>{pending ? "Đang xử lý…" : "Tìm câu tương tự"}</button>
    {error && <p role="alert">{error}</p>}
    {searched && !items.length && <p>Chưa tìm được câu phù hợp.</p>}
    {items.map(item => <article key={item.id}>
      <small>Câu ngân hàng {item.id} · {item.grade ? `Lớp ${item.grade}` : "Chưa ghi khối"}</small>
      <BankQuestionBody question={item} collapsibleAnswer />
      <button type="button" disabled={pending} onClick={async () => {
        setPending(true); setError("");
        try { onChoose(await bankEditTemplate(examId, question.id, item.id, version)); }
        catch (failure) { setError(getApiErrorMessage(failure, "Không thể dùng câu này cho ô ma trận hiện tại")); }
        finally { setPending(false); }
      }}>Thay nội dung bằng câu này</button>
    </article>)}
  </details>;
}
