import { useEffect } from "react";
import { useLocation } from "react-router";

/** Scroll to the router's inner fragment without replacing the HashRouter path. */
export default function RouteScroll() {
  const { pathname, hash, key } = useLocation();
  useEffect(() => {
    if (!hash) {
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });
      return;
    }
    let id: string;
    try { id = decodeURIComponent(hash.slice(1)); }
    catch { return; }
    const target = document.getElementById(id);
    if (!target) return;
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
      block: "start",
    });
    if (id === "main-content") target.focus({ preventScroll: true });
  }, [pathname, hash, key]);
  return null;
}
