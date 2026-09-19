import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ThemeContext } from "./themeContextValue";
import type { ResolvedTheme, ThemePreference } from "./themeContextValue";
import {
  applyTheme,
  prefersDark,
  readStoredPreference,
  resolveTheme,
  storePreference,
} from "./themeStorage";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() =>
    readStoredPreference(),
  );
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    resolveTheme(readStoredPreference()),
  );

  /* Paint the palette whenever the preference changes. */
  useEffect(() => {
    applyTheme(preference);
    setResolved(resolveTheme(preference));
  }, [preference]);

  /* While following the OS, track its changes so `resolved` stays truthful. */
  useEffect(() => {
    if (preference !== "system") return;
    if (typeof window.matchMedia !== "function") return;

    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setResolved(prefersDark() ? "dark" : "light");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [preference]);

  const setPreference = useCallback((next: ThemePreference) => {
    storePreference(next);
    setPreferenceState(next);
  }, []);

  const toggle = useCallback(() => {
    setPreference(resolveTheme(readStoredPreference()) === "dark" ? "light" : "dark");
  }, [setPreference]);

  const value = useMemo(
    () => ({ preference, resolved, setPreference, toggle }),
    [preference, resolved, setPreference, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
