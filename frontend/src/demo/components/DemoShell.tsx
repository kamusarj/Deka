import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";
import BrandMark from "../../components/BrandMark";

export default function DemoShell({ children }: { children: ReactNode }) {
  return (
    <div className="demo-shell">
      <header className="demo-topbar">
        <Link className="demo-brand" to="/">
          <BrandMark />
          <span>Deka</span>
        </Link>
        <span className="demo-header-label">Không gian làm việc mẫu</span>
        <span className="demo-pill">Bản trải nghiệm · dữ liệu giả</span>
      </header>
      <div className="demo-frame">
        <aside className="demo-sidebar" aria-label="Điều hướng">
          <p className="demo-sidebar-title">Không gian của giáo viên</p>
          <nav>
            <NavLink to="/dashboard">Tổng quan</NavLink>
            <NavLink to="/create">Tạo đề kiểm tra</NavLink>
            <NavLink to="/exams">Đề đã tạo</NavLink>
            <NavLink to="/question-bank">Ngân hàng câu hỏi</NavLink>
            <NavLink to="/documents">Tài liệu</NavLink>
          </nav>
          <div className="demo-sidebar-note">
            <span>✳</span>
            <p>
              Một bàn làm việc mẫu để bạn khám phá quy trình soạn đề của Deka.
            </p>
          </div>
        </aside>
        <main className="demo-main" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
