import { Link } from "react-router";
import BrandMark from "../../components/BrandMark";
import Action from "../components/Action";

export default function Intro() {
  return (
    <div className="demo-intro">
      <header className="demo-landing-nav">
        <Link className="demo-brand" to="/">
          <BrandMark />
          <span>Deka</span>
        </Link>
        <Action to="/dashboard" secondary>
          Khám phá bản demo
        </Action>
      </header>
      <main className="demo-landing-main">
        <div className="demo-landing-copy">
          <p className="demo-kicker">
            Một bàn làm việc dành cho giáo viên KHTN
          </p>
          <h1>
            Soạn đề chỉn chu.
            <br />
            Dành tâm sức cho bài giảng.
          </h1>
          <p>
            Chọn phạm vi kiến thức, xem ma trận và bản đặc tả, rồi duyệt từng
            câu hỏi trước khi hoàn thiện đề kiểm tra.
          </p>
          <div className="demo-actions">
            <Action to="/create">
              Thử tạo đề mẫu <span aria-hidden="true">↗</span>
            </Action>
            <Action to="/exams/de-minh-hoa-khtn-8" secondary>
              Xem đề minh hoạ
            </Action>
          </div>
          <p className="demo-disclaimer">
            Bản trải nghiệm công khai sử dụng dữ liệu giả. Các bước tạo đề và
            duyệt câu hỏi diễn ra ngay trên trình duyệt.
          </p>
        </div>
        <div
          className="demo-hero-sheet"
          aria-label="Xem trước hồ sơ đề kiểm tra"
        >
          <div className="demo-sheet-head">
            <span>Deka / Hồ sơ đề</span>
            <span>KHTN 8</span>
          </div>
          <h2>Kiểm tra giữa kỳ I</h2>
          <p>Chủ đề: Áp suất và ứng dụng trong đời sống</p>
          <div className="demo-sheet-rule" />
          <div className="demo-sheet-cols">
            <div>
              <span>01</span>
              <strong>Ma trận đề</strong>
              <small>Phân bố nội dung, mức độ và điểm</small>
            </div>
            <div>
              <span>02</span>
              <strong>Bản đặc tả</strong>
              <small>Yêu cầu cần đạt cho từng câu</small>
            </div>
            <div>
              <span>03</span>
              <strong>Đề & đáp án</strong>
              <small>Câu hỏi sẵn sàng để giáo viên duyệt</small>
            </div>
          </div>
          <div className="demo-sheet-footer">
            4 dạng câu hỏi <span>·</span> 45 phút <span>·</span> 10 điểm
          </div>
        </div>
      </main>
      <section className="demo-landing-steps">
        <div>
          <b>01</b>
          <h3>Thiết lập</h3>
          <p>Chọn lớp, thời gian và nội dung kiểm tra.</p>
        </div>
        <div>
          <b>02</b>
          <h3>Xem hồ sơ</h3>
          <p>Ma trận, bản đặc tả, câu hỏi và đáp án cùng một nơi.</p>
        </div>
        <div>
          <b>03</b>
          <h3>Duyệt từng câu</h3>
          <p>Giáo viên quyết định câu hỏi nào được giữ lại.</p>
        </div>
      </section>
      <footer className="demo-landing-footer">
        Deka · Bản demo công khai · Không kết nối API hoặc mô hình AI
      </footer>
    </div>
  );
}
