import { useMemo } from "react";
import { Link } from "react-router";
import type { DemoExam } from "../data";
import { typeLabel } from "../labels";
import Action from "../components/Action";

export default function QuestionBank({ exams }: { exams: DemoExam[] }) {
  const questions = useMemo(
    () =>
      exams.flatMap((exam) =>
        exam.questions
          .filter((question) => question.approved)
          .map((question) => ({ ...question, exam })),
      ),
    [exams],
  );
  return (
    <section className="demo-page">
      <div className="demo-page-head">
        <p className="demo-kicker">Ngân hàng câu hỏi</p>
        <h1>Những câu hỏi đã duyệt</h1>
        <p>Câu hỏi bạn duyệt trong đề mẫu sẽ xuất hiện tại đây.</p>
      </div>
      {questions.length ? (
        <div className="demo-list">
          {questions.map((question) => (
            <Link
              className="demo-bank-row"
              to={`/exams/${question.exam.id}`}
              key={`${question.exam.id}-${question.id}`}
            >
              <span className="demo-bank-type">{typeLabel[question.type]}</span>
              <strong>{question.prompt}</strong>
              <small>{question.exam.title}</small>
            </Link>
          ))}
        </div>
      ) : (
        <div className="demo-empty">
          <span>▤</span>
          <h2>Chưa có câu hỏi được duyệt</h2>
          <p>Mở một đề mẫu và chọn “Duyệt câu hỏi” để thêm câu vào đây.</p>
          <Action to={`/exams/${exams[0].id}`}>Duyệt đề mẫu</Action>
        </div>
      )}
    </section>
  );
}
