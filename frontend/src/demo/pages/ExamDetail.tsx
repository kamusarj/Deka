import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import {
  getLearningObjective,
  getScoringGuide,
  regenerateQuestion,
  type DemoExam,
  type DemoQuestion,
} from "../data";
import { typeLabel } from "../labels";
import Action from "../components/Action";

export default function ExamDetail({
  exams,
  onUpdate,
  onDuplicate,
}: {
  exams: DemoExam[];
  onUpdate: (exam: DemoExam) => void;
  onDuplicate: (exam: DemoExam) => DemoExam;
}) {
  const { id } = useParams();
  const navigate = useNavigate();
  const exam = exams.find((item) => item.id === id);
  const [tab, setTab] = useState<"questions" | "matrix" | "spec" | "answers">(
    "questions",
  );
  const [showAnswers, setShowAnswers] = useState(false);
  if (!exam)
    return (
      <section className="demo-page">
        <h1>Không tìm thấy đề mẫu</h1>
        <Action to="/exams">Về danh sách đề</Action>
      </section>
    );
  const approvedCount = exam.questions.filter(
    (question) => question.approved,
  ).length;
  const levelCounts = ["Nhận biết", "Thông hiểu", "Vận dụng"].map(
    (level) =>
      exam.questions.filter((question) => question.level === level).length,
  );
  function updateQuestion(questionId: string, change: Partial<DemoQuestion>) {
    onUpdate({
      ...exam!,
      questions: exam!.questions.map((question) =>
        question.id === questionId ? { ...question, ...change } : question,
      ),
    });
  }
  const tabs = [
    { id: "questions", label: "Câu hỏi" },
    { id: "matrix", label: "Ma trận" },
    { id: "spec", label: "Bản đặc tả" },
    { id: "answers", label: "Đáp án & rubric" },
  ] as const;
  return (
    <section className="demo-page demo-detail">
      <Link className="demo-back" to="/exams">
        ← Đề đã tạo
      </Link>
      <div className="demo-page-head demo-page-head-inline">
        <div>
          <p className="demo-kicker">Hồ sơ đề kiểm tra</p>
          <h1>{exam.title}</h1>
          <p>
            {exam.topic} · {exam.duration} phút · 10 điểm
          </p>
        </div>
        <button
          className="demo-button demo-button-secondary"
          onClick={() => navigate(`/exams/${onDuplicate(exam).id}`)}
        >
          Nhân bản đề
        </button>
      </div>
      <div className="demo-progress">
        <span>
          Giáo viên đã duyệt{" "}
          <strong>
            {approvedCount}/{exam.questions.length} câu
          </strong>
        </span>
        <div
          aria-label={`${approvedCount} trên ${exam.questions.length} câu đã duyệt`}
        >
          <i
            style={{
              width: `${(approvedCount / exam.questions.length) * 100}%`,
            }}
          />
        </div>
      </div>
      <div
        className="demo-tabs"
        role="tablist"
        aria-label="Thành phần hồ sơ đề"
      >
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "active" : ""}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === "questions" && (
        <div className="demo-question-list">
          <div className="demo-inline-head">
            <h2>Đề kiểm tra</h2>
            <button
              type="button"
              className="demo-text-button"
              onClick={() => setShowAnswers(!showAnswers)}
            >
              {showAnswers ? "Ẩn đáp án" : "Hiện đáp án"}
            </button>
          </div>
          {exam.questions.map((question, index) => (
            <article className="demo-question" key={question.id}>
              <div className="demo-question-meta">
                <span>
                  Câu {index + 1} · {typeLabel[question.type]}
                </span>
                <span>{question.level} · 2,5 điểm</span>
              </div>
              <h3>{question.prompt}</h3>
              {question.options && (
                <ol type="A" className="demo-options">
                  {question.options.map((option) => (
                    <li key={option}>{option}</li>
                  ))}
                </ol>
              )}
              {showAnswers && (
                <div className="demo-answer-inline">
                  <b>Đáp án gợi ý</b>
                  <p>{question.answer}</p>
                  <small>{question.explanation}</small>
                </div>
              )}
              <div className="demo-question-actions">
                <button
                  className={question.approved ? "demo-approved" : ""}
                  onClick={() =>
                    updateQuestion(question.id, {
                      approved: !question.approved,
                    })
                  }
                >
                  {question.approved ? "✓ Đã duyệt" : "Duyệt câu hỏi"}
                </button>
                <button
                  onClick={() =>
                    updateQuestion(
                      question.id,
                      regenerateQuestion(exam.grade, index, question),
                    )
                  }
                >
                  Tạo lại bản mẫu
                </button>
                {question.revision > 0 && (
                  <small>Bản mẫu lần {question.revision + 1}</small>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      {tab === "matrix" && (
        <div className="demo-panel">
          <div className="demo-inline-head">
            <h2>Ma trận đề kiểm tra</h2>
            <span>KHTN {exam.grade} · 10 điểm</span>
          </div>
          <div className="demo-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Chủ đề</th>
                  <th>Nhận biết</th>
                  <th>Thông hiểu</th>
                  <th>Vận dụng</th>
                  <th>Tổng</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>{exam.topic}</th>
                  {levelCounts.map((count, index) => (
                    <td key={index}>{count} câu</td>
                  ))}
                  <td>{exam.questions.length} câu</td>
                </tr>
                <tr>
                  <th>Tỉ lệ điểm minh hoạ</th>
                  {levelCounts.map((count, index) => (
                    <td key={index}>
                      {(count / exam.questions.length) * 100}%
                    </td>
                  ))}
                  <td>100%</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="demo-table-note">
            Bộ đề mẫu chia đều 2,5 điểm cho mỗi câu. Ma trận này minh hoạ cách
            trình bày hồ sơ đề.
          </p>
        </div>
      )}
      {tab === "spec" && (
        <div className="demo-panel">
          <h2>Bản đặc tả</h2>
          <div className="demo-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Câu</th>
                  <th>Dạng</th>
                  <th>Mức độ</th>
                  <th>Yêu cầu cần đạt minh hoạ</th>
                </tr>
              </thead>
              <tbody>
                {exam.questions.map((question, index) => (
                  <tr key={question.id}>
                    <td>{index + 1}</td>
                    <td>{typeLabel[question.type]}</td>
                    <td>{question.level}</td>
                    <td>{getLearningObjective(exam.grade, index)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {tab === "answers" && (
        <div className="demo-panel">
          <h2>Đáp án và hướng dẫn chấm</h2>
          <div className="demo-answer-list">
            {exam.questions.map((question, index) => (
              <div key={question.id}>
                <b>Câu {index + 1}</b>
                <p>{question.answer}</p>
                <small>{question.explanation}</small>
                <p className="demo-scoring">
                  {getScoringGuide(exam.grade, index)}
                </p>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="demo-button demo-button-secondary"
            onClick={() => window.print()}
          >
            In bản xem trước
          </button>
        </div>
      )}
    </section>
  );
}
