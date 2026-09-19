import type { ResolvedTheme, ThemePreference } from "./themeContextValue";

export const THEME_STORAGE_KEY = "smart-exam-theme";

function isPreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

export function readStoredPreference(): ThemePreference {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(raw) ? raw : "system";
  } catch {
    // Private mode / storage disabled — fall back to following the OS.
    return "system";
  }
}

export function storePreference(preference: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Persisting is best-effort; the in-memory preference still applies.
  }
}

export function prefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === "system") return prefersDark() ? "dark" : "light";
  return preference;
}

/**
 * `data-theme` drives the CSS palette. It always carries the raw preference so
 * the `@media (prefers-color-scheme: dark)` block in styles.css can own the
 * "system" case without JS re-painting on every OS change.
 */
export function applyTheme(preference: ThemePreference): void {
  const root = document.documentElement;
  root.setAttribute("data-theme", preference);
  root.style.colorScheme = resolveTheme(preference);
}
