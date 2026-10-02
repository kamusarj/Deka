import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { makeExam, sampleTopics, type DemoExam } from "../data";

export default function CreateExam({
  onCreate,
}: {
  onCreate: (exam: DemoExam) => void;
}) {
  const navigate = useNavigate();
  const [grade, setGrade] = useState(8);
  const [term, setTerm] = useState("Giữa kỳ I");
  const [duration, setDuration] = useState(45);
  const [topic, setTopic] = useState("Áp suất và ứng dụng trong đời sống");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const exam = makeExam({
      grade,
      term,
      duration,
      topic: topic.trim() || "Nội dung Khoa học tự nhiên",
    });
    onCreate(exam);
    navigate(`/exams/${exam.id}`);
  }
  return (
    <section className="demo-page">
      <div className="demo-page-head">
        <p className="demo-kicker">Tạo đề kiểm tra</p>
        <h1>Bắt đầu từ nội dung đã dạy.</h1>
        <p>
          Thiết lập thông tin cơ bản để xem một bộ đề mẫu gồm ma trận, bản đặc
          tả và bốn dạng câu hỏi.
        </p>
      </div>
      <div className="demo-form-layout">
        <form className="demo-panel demo-form" onSubmit={submit}>
          <h2>Thông tin đề</h2>
          <div className="demo-form-grid">
            <label>
              Lớp
              <select
                value={grade}
                onChange={(event) => {
                  const selectedGrade = Number(event.target.value);
                  setGrade(selectedGrade);
                  setTopic(sampleTopics[selectedGrade]);
                }}
              >
                {[6, 7, 8, 9].map((value) => (
                  <option key={value} value={value}>
                    Lớp {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Loại kiểm tra
              <select
                value={term}
                onChange={(event) => setTerm(event.target.value)}
              >
                <option>Giữa kỳ I</option>
                <option>Cuối kỳ I</option>
                <option>Giữa kỳ II</option>
                <option>Cuối kỳ II</option>
              </select>
            </label>
          </div>
          <label>
            Thời gian làm bài
            <select
              value={duration}
              onChange={(event) => setDuration(Number(event.target.value))}
            >
              <option value={45}>45 phút</option>
              <option value={60}>60 phút</option>
              <option value={90}>90 phút</option>
            </select>
          </label>
          <label>
            Nội dung kiểm tra
            <textarea
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              rows={3}
              maxLength={240}
            />
          </label>
          <p className="demo-form-help">
            Bộ câu hỏi minh hoạ được chọn theo lớp. Nội dung bạn nhập dùng làm
            tên chủ đề của đề mẫu.
          </p>
          <button className="demo-button" type="submit">
            Tạo bộ đề mẫu <span aria-hidden="true">↗</span>
          </button>
        </form>
        <aside className="demo-panel demo-side-preview">
          <span className="demo-preview-mark">▦</span>
          <h2>Một bộ đề gồm những gì?</h2>
          <ol>
            <li>Ma trận phân bố câu hỏi</li>
            <li>Bản đặc tả theo yêu cầu cần đạt</li>
            <li>Câu hỏi và đáp án gợi ý</li>
            <li>Trạng thái duyệt của giáo viên</li>
          </ol>
          <p>
            Đây là mô phỏng quy trình. Không có lời gọi đến AI, API hoặc dữ liệu
            thật.
          </p>
        </aside>
      </div>
    </section>
  );
}
