import { Link } from "react-router";
import type { DemoExam } from "../data";
import Action from "../components/Action";

export default function ExamList({ exams }: { exams: DemoExam[] }) {
  return (
    <section className="demo-page">
      <div className="demo-page-head demo-page-head-inline">
        <div>
          <p className="demo-kicker">Thư viện đề</p>
          <h1>Đề kiểm tra đã tạo</h1>
          <p>Danh sách minh hoạ được lưu trên trình duyệt của bạn.</p>
        </div>
        <Action to="/create">Tạo đề mẫu</Action>
      </div>
      <div className="demo-list">
        {exams.map((exam) => (
          <Link
            className="demo-exam-row"
            key={exam.id}
            to={`/exams/${exam.id}`}
          >
            <span className="demo-row-icon">▤</span>
            <span>
              <strong>{exam.title}</strong>
              <small>
                {exam.topic} · {exam.duration} phút · {exam.questions.length}{" "}
                câu hỏi
              </small>
            </span>
            <span className="demo-row-arrow">↗</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
