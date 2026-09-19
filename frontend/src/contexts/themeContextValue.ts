import { createContext } from "react";

/** User-selectable theme. "system" follows the OS `prefers-color-scheme`. */
export type ThemePreference = "light" | "dark" | "system";

/** The theme actually painted after resolving "system". */
export type ResolvedTheme = "light" | "dark";

export interface ThemeContextType {
  /** What the user picked. Persisted. */
  preference: ThemePreference;
  /** What is on screen right now. */
  resolved: ResolvedTheme;
  setPreference: (next: ThemePreference) => void;
  /** Flips between light and dark, leaving "system" behind. */
  toggle: () => void;
}

export const ThemeContext = createContext<ThemeContextType | null>(null);
