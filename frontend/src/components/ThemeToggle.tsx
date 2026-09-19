import { useTheme } from "../contexts/useTheme";

const sun = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

const moon = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
);

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { resolved, toggle } = useTheme();
  const goingDark = resolved === "light";

  return (
    <button
      type="button"
      className={`theme-toggle ${className}`.trim()}
      onClick={toggle}
      aria-label={goingDark ? "Chuyển sang giao diện tối" : "Chuyển sang giao diện sáng"}
      title={goingDark ? "Giao diện tối" : "Giao diện sáng"}
    >
      <span className="theme-toggle-icon" aria-hidden="true">
        {goingDark ? moon : sun}
      </span>
    </button>
  );
}
