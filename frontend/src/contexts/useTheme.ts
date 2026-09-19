import { useContext } from "react";

import { ThemeContext } from "./themeContextValue";
import type { ThemeContextType } from "./themeContextValue";

export function useTheme(): ThemeContextType {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
