import BankQuestionBody from "../components/BankQuestionBody";
import PublishQuestionButton from "../components/PublishQuestionButton";
import { useCallback, useContext, useEffect, useState } from "react";
import { SelectControl, SkeletonGrid } from "../components";
import { deleteBankQuestion, listBankQuestions, searchBankQuestions } from "../services/api";
import { formatDifficulty, formatQuestionType } from "../utils/labels";
import { getApiErrorMessage } from "../utils/apiError";
import type { BankQuestion, BankQuestionFilters, Difficulty, QuestionType } from "../types";
import { AuthContext } from "../contexts/authContextValue";
import { canWriteContent } from "../auth/rolePolicy";

const QUESTION_TYPES: QuestionType[] = [
  "multiple_choice",
  "true_false",
  "short_answer",
  "essay",
];
const DIFFICULTIES: Difficulty[] = ["nhan_biet", "thong_hieu", "van_dung"];

export default function QuestionBank() {
  const user = useContext(AuthContext)?.user ?? { role: "teacher" };
  const canWrite = canWriteContent(user?.role);
  const [questions, setQuestions] = useState<BankQuestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<BankQuestionFilters>({});
  const [semantic, setSemantic] = useState(false);
  const [search, setSearch] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const result = semantic && search.trim() ? await searchBankQuestions(search.trim(), filters, signal) : await listBankQuestions(
        { ...filters, search: search.trim() || undefined },
        signal,
      );
      if (!signal?.aborted) setQuestions(result);
    } catch (err: unknown) {
      if (!signal?.aborted) {
        setError(getApiErrorMessage(err, "Không tải được ngân hàng câu hỏi"));
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [filters, search, semantic]);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => load(controller.signal), 300);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [load]);

  async function onDelete(id: number) {
    if (!window.confirm("Xóa câu hỏi này khỏi ngân hàng?")) return;
    try {
      await deleteBankQuestion(id);
      await load();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Không xóa được câu hỏi"));
    }
  }

  function updateFilter<K extends keyof BankQuestionFilters>(
    key: K,
    value: BankQuestionFilters[K] | undefined,
  ) {
    setFilters((prev) => {
      const next = { ...prev };
      if (value === undefined || value === ("" as unknown)) delete next[key];
      else next[key] = value;
      return next;
    });
  }

  return (
    <section className="content-page">
      <div className="panel-header">
        <h2>Ngân hàng câu hỏi</h2>
      </div>

      <div className="list-toolbar">
        <label className="checkline"><input type="checkbox" checked={semantic} onChange={event => setSemantic(event.target.checked)} />Tìm câu có ý nghĩa tương tự</label>
        <input
          type="text"
          placeholder="Tìm theo nội dung..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="search-input"
        />
        <SelectControl
          ariaLabel="Lọc câu hỏi theo khối"
          value={filters.grade ?? ""}
          onChange={(value) =>
            updateFilter("grade", value === "" ? undefined : Number(value))
          }
          options={[
            { value: "", label: "Tất cả khối" },
            ...[6, 7, 8, 9].map((grade) => ({ value: grade, label: `Lớp ${grade}` })),
          ]}
        />
        <SelectControl
          ariaLabel="Lọc câu hỏi theo dạng"
          value={filters.type ?? ""}
          onChange={(value) =>
            updateFilter("type", (value || undefined) as QuestionType | undefined)
          }
          options={[
            { value: "", label: "Tất cả dạng" },
            ...QUESTION_TYPES.map((type) => ({ value: type, label: formatQuestionType(type) })),
          ]}
        />
        <SelectControl
          ariaLabel="Lọc câu hỏi theo mức độ"
          value={filters.difficulty ?? ""}
          onChange={(value) =>
            updateFilter(
              "difficulty",
              (value || undefined) as Difficulty | undefined,
            )
          }
          options={[
            { value: "", label: "Tất cả mức độ" },
            ...DIFFICULTIES.map((difficulty) => ({
              value: difficulty,
              label: formatDifficulty(difficulty),
            })),
          ]}
        />
      </div>

      {error && (
        <div className="error-box">
          <p className="error">{error}</p>
        </div>
      )}
      {loading && <SkeletonGrid count={4} label="Đang tải ngân hàng câu hỏi" />}

      {!loading && questions.length === 0 && (
        <div className="empty-state">
          <h3>Chưa có câu hỏi nào</h3>
          <p>Lưu câu đã duyệt từ trang chi tiết đề để xây dựng ngân hàng.</p>
        </div>
      )}

      {!loading && questions.length > 0 && (
        <>
          <div className="exam-count">Tổng {questions.length} câu hỏi</div>
          <div className="list">
            {questions.map((q, index) => (
              <article className="question-card" key={q.id}>
                <div className="bank-question-head">
                  <strong>Câu {index + 1}</strong>
                  <span>{formatQuestionType(q.type)}</span>
                </div>
                <BankQuestionBody question={q} />
                <div className="question-meta">
                  <small className="muted">
                    {[q.topic, q.grade != null ? `Lớp ${q.grade}` : "", formatDifficulty(q.difficulty)]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                </div>
                {q.tags.length > 0 && (
                  <div className="tag-row">
                    {q.tags.map((tag) => (
                      <span className="tag" key={tag}>
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
                <div className="list-item-footer list-item-footer-end">
                  {canWrite && q.can_publish && <PublishQuestionButton question={q} />}
                  {canWrite && <button
                    type="button"
                    className="btn-danger compact"
                    onClick={() => onDelete(q.id)}
                  >
                    Xóa
                  </button>}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
