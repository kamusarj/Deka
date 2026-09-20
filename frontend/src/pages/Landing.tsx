import { Link } from "react-router";
import BrandMark from "../components/BrandMark";
import ThemeToggle from "../components/ThemeToggle";
import ExamPreview from "../components/ExamPreview";
import ExamWorkflow from "../components/ExamWorkflow";
import SubscriptionPlans from "../components/SubscriptionPlans";
import { useAuth } from "../contexts/useAuth";

const features = [
  { title: "Ma trận rõ ràng", text: "Xem cách phân bổ câu hỏi theo chủ đề, mức độ và dạng câu trong ma trận của đề đã tạo.", symbol: "▦" },
  { title: "Bám sát tài liệu dạy học", text: "Dùng sách, bài giảng và tài liệu của bạn làm nguồn cho nội dung kiểm tra.", symbol: "▤" },
  { title: "Giáo viên giữ quyền duyệt", text: "Đọc lời giải, xem điểm cần kiểm tra và yêu cầu chỉnh sửa từng câu hỏi.", symbol: "✓" },
  { title: "Tích lũy cho những lần sau", text: "Lưu câu hỏi vào ngân hàng, chia sẻ tài liệu và cùng thảo luận với cộng đồng giáo viên.", symbol: "↗" },
];

export default function Landing() {
  const { isAuthenticated } = useAuth();
  return <div className="landing paper-landing">
    <header className="paper-nav">
      <Link to="/" className="landing-brand"><BrandMark /><span className="brand-name">Deka</span></Link>
      <nav aria-label="Điều hướng landing"><Link to="/#tinh-nang">Tính năng</Link><Link to="/#quy-trinh">Quy trình</Link><Link to="/#goi-su-dung">Gói sử dụng</Link><Link to="/community">Cộng đồng</Link></nav>
      <div className="paper-nav-actions"><ThemeToggle /><Link to={isAuthenticated ? "/dashboard" : "/login"} className="paper-button paper-button-quiet">{isAuthenticated ? "Vào ứng dụng" : "Đăng nhập"}</Link>{!isAuthenticated && <Link to="/register" className="paper-button paper-nav-register">Bắt đầu</Link>}</div>
    </header>
    <section className="paper-hero">
      <p className="paper-hero-note"><span aria-hidden="true">✧</span> Một người trợ giảng, thêm thời gian cho bạn</p>
      <h1>Soạn đề chỉn chu.<br />Dành tâm sức cho bài giảng.</h1>
      <p className="paper-hero-description">Chọn bài đã dạy, thiết lập cấu trúc để AI tạo đề. Sau đó, bạn duyệt từng câu và xuất đề, ma trận cùng hướng dẫn chấm ra Word hoặc PDF.</p>
      <div className="paper-actions"><Link to="/create" className="paper-button">Bắt đầu tạo đề <span aria-hidden="true">↗</span></Link><Link to="/#quy-trinh" className="paper-button paper-button-quiet">Tìm hiểu quy trình</Link></div>
      <p className="paper-hero-footnote">Khoa học tự nhiên · Lớp 6 đến lớp 9</p>
    </section>
    <ExamWorkflow />
    <section id="uu-diem" className="paper-preview-section" aria-labelledby="preview-heading"><div className="paper-section-heading"><h2 id="preview-heading">Một bộ đề, đầy đủ từng phần.</h2><p>Thử chuyển giữa các phần để hình dung thành phẩm.</p></div><ExamPreview /></section>
    <section id="tinh-nang" className="paper-section"><div className="paper-section-heading"><h2>Được làm cho công việc của giáo viên.</h2><p>Những công cụ cần thiết, cùng trong một không gian.</p></div><div className="paper-features">{features.map(feature => <article key={feature.title}><span aria-hidden="true" className="paper-feature-icon">{feature.symbol}</span><div><h3>{feature.title}</h3><p>{feature.text}</p></div></article>)}</div></section>
    <SubscriptionPlans />
    <section className="paper-closing"><h2>Bài kiểm tra tiếp theo,<br />bắt đầu từ đây.</h2><p>Mở không gian làm việc và tạo bộ đề của bạn.</p><Link to={isAuthenticated ? "/dashboard" : "/register"} className="paper-button">{isAuthenticated ? "Vào ứng dụng" : "Tạo tài khoản"}</Link></section>
  </div>;
}
