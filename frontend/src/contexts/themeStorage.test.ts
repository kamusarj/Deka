import { describe, expect, it } from "vitest";

import { setPrefersDark } from "../test/setup";
import {
  THEME_STORAGE_KEY,
  applyTheme,
  readStoredPreference,
  resolveTheme,
  storePreference,
} from "./themeStorage";

describe("readStoredPreference", () => {
  it("defaults to system when nothing is stored", () => {
    expect(readStoredPreference()).toBe("system");
  });

  it("returns a valid stored preference", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    expect(readStoredPreference()).toBe("dark");
  });

  it("falls back to system when the stored value is garbage", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "neon");
    expect(readStoredPreference()).toBe("system");
  });
});

describe("resolveTheme", () => {
  it("passes explicit choices through", () => {
    expect(resolveTheme("light")).toBe("light");
    expect(resolveTheme("dark")).toBe("dark");
  });

  it("follows the OS when set to system", () => {
    setPrefersDark(true);
    expect(resolveTheme("system")).toBe("dark");
    setPrefersDark(false);
    expect(resolveTheme("system")).toBe("light");
  });
});

describe("applyTheme", () => {
  it("writes the raw preference to data-theme so CSS owns the system case", () => {
    applyTheme("system");
    expect(document.documentElement.getAttribute("data-theme")).toBe("system");
  });

  it("sets colorScheme to the resolved theme", () => {
    setPrefersDark(true);
    applyTheme("system");
    expect(document.documentElement.style.colorScheme).toBe("dark");

    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
  });
});

describe("storePreference", () => {
  it("round-trips through localStorage", () => {
    storePreference("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(readStoredPreference()).toBe("dark");
  });
});
