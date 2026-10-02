import { Link } from "react-router";
import type { DemoExam } from "../data";
import Action from "../components/Action";

export default function Dashboard({ exams }: { exams: DemoExam[] }) {
  const latest = exams[0];
  const approved = exams.reduce(
    (sum, exam) =>
      sum + exam.questions.filter((question) => question.approved).length,
    0,
  );
  return (
    <section className="demo-page">
      <div className="demo-page-head">
        <p className="demo-kicker">Bàn làm việc</p>
        <h1>Chào mừng đến với Deka.</h1>
        <p>
          Khám phá một quy trình tạo đề Khoa học tự nhiên hoàn chỉnh bằng dữ
          liệu minh hoạ.
        </p>
        <div className="demo-actions">
          <Action to="/create">Tạo đề mẫu</Action>
          <Action to="/exams" secondary>
            Xem đề đã tạo
          </Action>
        </div>
      </div>
      <div className="demo-stats">
        <div>
          <strong>{exams.length}</strong>
          <span>đề kiểm tra</span>
        </div>
        <div>
          <strong>
            {exams.reduce((sum, exam) => sum + exam.questions.length, 0)}
          </strong>
          <span>câu hỏi</span>
        </div>
        <div>
          <strong>{approved}</strong>
          <span>câu đã duyệt</span>
        </div>
      </div>
      <div className="demo-section-title">
        <h2>Tiếp tục với đề gần đây</h2>
        <Link to="/exams">Xem tất cả</Link>
      </div>
      <Link className="demo-exam-row" to={`/exams/${latest.id}`}>
        <span className="demo-row-icon">▤</span>
        <span>
          <strong>{latest.title}</strong>
          <small>
            {latest.topic} · {latest.duration} phút
          </small>
        </span>
        <span className="demo-row-arrow">↗</span>
      </Link>
      <div className="demo-tip">
        <span>✳</span>
        <p>
          Trong bản demo, đề mới được ghép từ bộ câu hỏi mẫu theo lớp. Những
          thay đổi bạn thực hiện được lưu trên trình duyệt này.
        </p>
      </div>
    </section>
  );
}
