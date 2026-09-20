import { Link } from "react-router";
import BrandMark from "./BrandMark";

export default function AppFooter() {
  return (
    <footer className="landing-footer paper-footer">
      <div className="landing-footer-inner">
        <div className="landing-footer-brand">
          <Link to="/" className="landing-brand">
            <BrandMark />
            <span className="brand-name">Deka</span>
          </Link>
        </div>
        <div className="landing-footer-links">
          <div>
            <strong>Sản phẩm</strong>
            <Link to="/#tinh-nang">Tính năng</Link>
            <Link to="/#quy-trinh">Quy trình</Link>
            <Link to="/dashboard">Vào workspace</Link>
          </div>
          <div>
            <strong>Dự án</strong>
            <a href="https://github.com/kamusarj/Deka" target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>
        </div>
      </div>
      <div className="landing-footer-bottom">
        <span>© 2026 Deka.</span>
      </div>
    </footer>
  );
}
