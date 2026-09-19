import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";
import type { ReactNode } from "react";
import { useAuth } from "../contexts/useAuth";
import {
  canManageSchoolTeachers,
  canSelectAiProvider,
  canUseAuthenticatedWorkspace,
  canWriteContent,
  getRoleBadgeClass,
  getStoredRoleLabel,
  isSuperAdminRole,
} from "../auth/rolePolicy";
import ThemeToggle from "./ThemeToggle";
import BrandMark from "./BrandMark";

interface LayoutProps {
  children?: ReactNode;
}

/* ── Inline SVG icons (Feather style) ───────────────── */
const icons = {
  overview: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  ),
  create: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 5v14M5 12h14" /><circle cx="12" cy="12" r="10" />
    </svg>
  ),
  exams: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
    </svg>
  ),
  documents: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  ),
  bank: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  ),
  settings: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  user: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
    </svg>
  ),
  chevron: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  ),
  school: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  ),
  menu: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  ),
  close: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
} as const;

/* ── Nav items ──────────────────────────────────────── */
const navItems = [
  { to: "/dashboard", label: "Tổng quan", icon: icons.overview, end: true },
  { to: "/create", label: "Tạo đề", icon: icons.create, end: false, write: true },
  { to: "/exams", label: "Đề đã tạo", icon: icons.exams, end: false },
  { to: "/documents", label: "Tài liệu", icon: icons.documents, end: false, workspace: true },
  { to: "/question-bank", label: "Ngân hàng", icon: icons.bank, end: false, workspace: true },
  { to: "/community", label: "Cộng đồng", icon: icons.bank, end: false, workspace: true },
  { to: "/usage", label: "Thống kê sử dụng", icon: icons.overview, end: false, workspace: true },
  { to: "/school-admin", label: "Quản trị", icon: icons.school, end: false, admin: true },
  { to: "/ai-settings", label: "Cấu hình AI", icon: icons.settings, end: false, superOnly: true },
];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);

  /* Close dropdown on outside click */
  useEffect(() => {
    function handleDocClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleDocClick);
    return () => document.removeEventListener("mousedown", handleDocClick);
  }, []);

  /* Escape closes whichever overlay is open */
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setMenuOpen(false);
      setNavOpen(false);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, []);

  /* Close overlays on route change */
  useEffect(() => {
    setMenuOpen(false);
    setNavOpen(false);
    if (mainRef.current) mainRef.current.scrollTop = 0;
  }, [location.pathname]);

  const isActive = (path: string, end: boolean) => {
    if (end) return location.pathname === path ? "current" : "";
    return location.pathname.startsWith(path) ? "current" : "";
  };

  /* Profile initial from auth user */
  const profileInitial = user?.name
    ? user.name.trim().slice(0, 1).toUpperCase()
    : user?.email?.slice(0, 1).toUpperCase() || "G";

  function handleLogout() {
    void logout();
    setMenuOpen(false);
    navigate(import.meta.env.VITE_ENABLE_DEMO_LOGIN === "true" ? "/login" : "/");
  }

  const canManageSchool = canManageSchoolTeachers(user?.role);
  const canManageAi = canSelectAiProvider(user?.role);
  const visibleNavItems = navItems.filter((item) => {
    if (item.write && !canWriteContent(user?.role)) return false;
    if (item.workspace && !canUseAuthenticatedWorkspace(user?.role)) return false;
    if (item.admin && !canManageSchool) return false;
    if (item.superOnly && !canManageAi) return false;
    return true;
  });

  return (
    <div className="app-layout">
      <Link className="skip-link" to={{ pathname: location.pathname, search: location.search, hash: "#main-content" }}>
        Bỏ qua điều hướng
      </Link>

      {/* ── Top Bar ──────────────────────────────────── */}
      <header className="topbar">
        <button
          type="button"
          className="nav-toggle"
          aria-label={navOpen ? "Đóng menu" : "Mở menu"}
          aria-expanded={navOpen}
          aria-controls="mobile-drawer"
          onClick={() => setNavOpen((v) => !v)}
        >
          {navOpen ? icons.close : icons.menu}
        </button>

        <Link to="/dashboard" className="topbar-brand">
          <BrandMark />
          <span className="brand-name">Smart Exam</span>
        </Link>

        <div className="topbar-actions">
          <div className="workspace-location">{visibleNavItems.find(item => isActive(item.to, item.end))?.label ?? "Tài khoản"}</div>
          <ThemeToggle />

          {/* User dropdown */}
          <div className="user-menu" ref={menuRef}>
            <button
              type="button"
              className="user-menu-trigger"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
              aria-label="Tài khoản"
            >
              <span className="user-avatar">{profileInitial}</span>
              <span className="user-menu-chevron" aria-hidden="true">{icons.chevron}</span>
            </button>

            {menuOpen && (
              <div className="user-menu-dropdown" role="menu">
                <div className="user-menu-head">
                  <span className="user-menu-head-avatar">{profileInitial}</span>
                  <div>
                    <strong>{user?.name || "Giáo viên"}</strong>
                    <span>{user?.email || ""}</span>
                    <span
                      className={`user-role-badge ${getRoleBadgeClass(user?.role)}`}
                      title={getStoredRoleLabel(user?.role)}
                    >
                      {getStoredRoleLabel(user?.role)}
                    </span>
                  </div>
                </div>
                <div className="user-menu-divider" />
                {canManageSchool && (
                  <Link to="/school-admin" className="user-menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                    <span className="user-menu-item-icon" aria-hidden="true">{icons.school}</span>
                    <div>
                      <strong>{isSuperAdminRole(user?.role) ? "Quản trị hệ thống" : "Quản lý Teacher"}</strong>
                    </div>
                  </Link>
                )}
                {canManageAi && (
                  <Link to="/ai-settings" className="user-menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                    <span className="user-menu-item-icon" aria-hidden="true">{icons.settings}</span>
                    <div>
                      <strong>Chọn AI provider</strong>
                    </div>
                  </Link>
                )}
                <Link to="/account" className="user-menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                  <span className="user-menu-item-icon" aria-hidden="true">{icons.user}</span>
                  <div>
                    <strong>Tài khoản</strong>
                  </div>
                </Link>
                <div className="user-menu-divider" />
                <button type="button" className="user-menu-logout" onClick={handleLogout}>
                  Đăng xuất
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <aside className="app-sidebar">
        <p className="sidebar-heading">Không gian làm việc</p>
        <nav className="sidebar-nav" aria-label="Điều hướng chính">
          {visibleNavItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`sidebar-link ${isActive(item.to, item.end)}`}
              aria-current={isActive(item.to, item.end) ? "page" : undefined}
            >
              <span className="sidebar-icon" aria-hidden="true">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-note"><span aria-hidden="true">✧</span><strong>Cùng bạn chuẩn bị bài.</strong><small>Khoa học tự nhiên, lớp 6–9</small></div>
      </aside>

      {/* ── Mobile drawer — the sidebar is hidden at 1024px and below ── */}
      {navOpen && (
        <>
          <div className="drawer-scrim" onClick={() => setNavOpen(false)} aria-hidden="true" />
          <nav id="mobile-drawer" className="mobile-drawer" aria-label="Điều hướng chính (di động)">
            {visibleNavItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`mobile-drawer-link ${isActive(item.to, item.end)}`}
                aria-current={isActive(item.to, item.end) ? "page" : undefined}
              >
                <span aria-hidden="true">{item.icon}</span>
                {item.label}
              </Link>
            ))}
            <div className="mobile-drawer-divider" />
            {canManageSchool && (
              <Link to="/school-admin" className="mobile-drawer-link">
                <span aria-hidden="true">{icons.school}</span>
                {isSuperAdminRole(user?.role) ? "Quản trị hệ thống" : "Quản lý Teacher"}
              </Link>
            )}
            {canManageAi && (
              <Link to="/ai-settings" className="mobile-drawer-link">
                <span aria-hidden="true">{icons.settings}</span>
                Chọn AI provider
              </Link>
            )}
            <Link to="/account" className="mobile-drawer-link">
              <span aria-hidden="true">{icons.user}</span>
              Tài khoản
            </Link>
          </nav>
        </>
      )}

      {/* ── Main Content ─────────────────────────────── */}
      <div className="main" ref={mainRef}>
        <main className="page" id="main-content" tabIndex={-1}>{children ?? <Outlet />}</main>
        <footer className="workspace-footer">© 2026 Smart Exam AI.</footer>
      </div>
    </div>
  );
}
