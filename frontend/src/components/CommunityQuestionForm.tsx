import { useState } from "react";
import { useNavigate } from "react-router";
import { SelectControl } from "./index";
import { createCommunityTopic } from "../services/api";
import { getApiErrorMessage } from "../utils/apiError";
import { formatDifficulty, formatQuestionType } from "../utils/labels";
import type { Difficulty, QuestionType } from "../types";

export default function CommunityQuestionForm({ onCancel }: { onCancel: () => void }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [type, setType] = useState<QuestionType>("multiple_choice");
  const [difficulty, setDifficulty] = useState<Difficulty>("thong_hieu");
  const [grade, setGrade] = useState(6);
  const [choices, setChoices] = useState(["", "", "", ""]);
  const [truth, setTruth] = useState(["", "", "", ""]);
  const [answer, setAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await createCommunityTopic(title.trim(), {
        content: content.trim(), type, difficulty, grade, subject: "Khoa học tự nhiên", tags: [],
        options: type === "multiple_choice" ? Object.fromEntries(choices.map((value, i) => [String.fromCharCode(65 + i), value.trim()])) : null,
        statements: type === "true_false" ? choices.map((value, i) => ({ id: `s${i + 1}`, content: value.trim() })) : null,
        answer: type === "true_false" ? { answers: truth.flatMap((value, i) => value === "" ? [] : [{ statement_id: `s${i + 1}`, is_true: value === "true" }]), explanation }
          : { [type === "essay" ? "model_answer" : "correct_answer"]: answer.trim(), explanation },
      });
      navigate(`/community/${result.id}`);
    } catch (err) { setError(getApiErrorMessage(err, "Không đăng được câu hỏi")); }
    finally { setBusy(false); }
  }
  return <form className="community-composer" onSubmit={submit}>
    <h3>Đăng câu hỏi mới</h3>
    <p className="muted">Câu hỏi và đáp án sẽ hiển thị ngay cho thành viên toàn hệ thống.</p>
    <label>Tiêu đề chủ đề<input required maxLength={160} value={title} onChange={e => setTitle(e.target.value)} /></label>
    <div className="list-toolbar">
      <SelectControl ariaLabel="Khối lớp câu hỏi mới" value={grade} onChange={value => setGrade(Number(value))} options={[6,7,8,9].map(value => ({ value, label: `Lớp ${value}` }))} />
      <SelectControl ariaLabel="Dạng câu hỏi mới" value={type} onChange={value => { setType(value as QuestionType); setAnswer(""); }} options={(["multiple_choice", "true_false", "short_answer", "essay"] as QuestionType[]).map(value => ({ value, label: formatQuestionType(value) }))} />
      <SelectControl ariaLabel="Mức độ câu hỏi mới" value={difficulty} onChange={value => setDifficulty(value as Difficulty)} options={(["nhan_biet", "thong_hieu", "van_dung"] as Difficulty[]).map(value => ({ value, label: formatDifficulty(value) }))} />
    </div>
    <label>Nội dung câu hỏi<textarea required rows={5} maxLength={20000} value={content} onChange={e => setContent(e.target.value)} /></label>
    {(type === "multiple_choice" || type === "true_false") && choices.map((value, i) => <div key={i} className="community-choice">
      <label>{type === "multiple_choice" ? `Phương án ${String.fromCharCode(65+i)}` : `Mệnh đề ${i+1}`}<input required maxLength={2000} value={value} onChange={e => setChoices(previous => previous.map((item, index) => index === i ? e.target.value : item))} /></label>
      {type === "true_false" && <SelectControl ariaLabel={`Đáp án mệnh đề ${i+1}`} value={truth[i]} onChange={value => setTruth(previous => previous.map((item, index) => index === i ? value : item))} options={[{ value: "", label: "Chưa có đáp án" }, { value: "true", label: "Đúng" }, { value: "false", label: "Sai" }]} />}
    </div>)}
    {type === "multiple_choice" ? <SelectControl ariaLabel="Đáp án đúng" value={answer} onChange={setAnswer} options={[{ value: "", label: "Chưa có đáp án" }, ...["A","B","C","D"].map(value => ({ value, label: value }))]} />
      : type !== "true_false" && <label>Đáp án tham khảo (không bắt buộc)<textarea rows={3} maxLength={5000} value={answer} onChange={e => setAnswer(e.target.value)} /></label>}
    <label>Giải thích (không bắt buộc)<textarea rows={3} maxLength={5000} value={explanation} onChange={e => setExplanation(e.target.value)} /></label>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="community-actions"><button className="btn-primary" disabled={busy || !title.trim() || !content.trim()}>{busy ? "Đang đăng…" : "Đăng lên cộng đồng"}</button><button type="button" className="btn-secondary" disabled={busy} onClick={onCancel}>Hủy</button></div>
  </form>;
}
