import { useState } from "react";
import { useNavigate } from "react-router";
import { publishBankQuestion } from "../services/api";
import { getApiErrorMessage } from "../utils/apiError";
import type { BankQuestion } from "../types";

export default function PublishQuestionButton({ question }: { question: BankQuestion }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function publish() {
    if (!window.confirm("Đăng câu hỏi và đáp án này lên cộng đồng toàn hệ thống để mọi người xem và trao đổi?")) return;
    setBusy(true); setError("");
    try {
      const topic = await publishBankQuestion(question.id, question.content.trim().slice(0, 160));
      navigate(`/community/${topic.id}`);
    } catch (err) { setError(getApiErrorMessage(err, "Không đăng được câu hỏi")); }
    finally { setBusy(false); }
  }
  return <div><button type="button" className="btn-secondary compact" disabled={busy} onClick={publish}>
    {busy ? "Đang đăng…" : "Chia sẻ lên cộng đồng"}
  </button>{error && <p role="alert" className="error">{error}</p>}</div>;
}
