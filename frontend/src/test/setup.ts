import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

/**
 * jsdom ships no matchMedia. The theme layer depends on it, so provide a
 * controllable stub that defaults to "light" and can be flipped per test via
 * `setPrefersDark(true)`.
 */
let prefersDark = false;

export function setPrefersDark(value: boolean) {
  prefersDark = value;
}

Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("prefers-color-scheme: dark") ? prefersDark : false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.colorScheme = "";
  prefersDark = false;
});
