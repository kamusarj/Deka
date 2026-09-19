import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getToken, removeToken, setToken } from "./authStorage";

describe("authStorage", () => {
  it("does not resurrect a persisted token removed by another tab", () => {
    setToken("remembered-token", true);
    expect(getToken()).toBe("remembered-token");
    localStorage.removeItem("smart-exam-token");
    expect(getToken()).toBeNull();
  });

  it("preserves opt-out persistence when storage recovers before token rotation", () => {
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied");
    });
    setToken("session-token", false);
    expect(getToken()).toBe("session-token");
    write.mockRestore();
    setToken("rotated-token");
    expect(sessionStorage.getItem("smart-exam-token")).toBe("rotated-token");
    expect(localStorage.getItem("smart-exam-token")).toBeNull();
  });

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    removeToken();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    removeToken();
  });

  it("persists a remembered token across browser sessions", () => {
    setToken("remembered-token", true);

    expect(localStorage.getItem("smart-exam-token")).toBe("remembered-token");
    expect(sessionStorage.getItem("smart-exam-token")).toBeNull();
    expect(getToken()).toBe("remembered-token");
  });

  it("keeps a non-remembered token in the current browser session", () => {
    setToken("session-token", false);

    expect(sessionStorage.getItem("smart-exam-token")).toBe("session-token");
    expect(localStorage.getItem("smart-exam-token")).toBeNull();
    expect(getToken()).toBe("session-token");
  });

  it.each([true, false])("restores only remembered tokens in a fresh browser runtime (remember=%s)", async (remember) => {
    setToken("restart-token", remember);
    sessionStorage.clear();
    vi.resetModules();
    const freshStorage = await import("./authStorage");

    expect(freshStorage.getToken()).toBe(remember ? "restart-token" : null);
    freshStorage.removeToken();
  });

  it("removes obsolete token copies when the persistence choice changes", () => {
    localStorage.setItem("smart-exam-token", "old-token");

    setToken("new-token", false);

    expect(localStorage.getItem("smart-exam-token")).toBeNull();
    expect(sessionStorage.getItem("smart-exam-token")).toBe("new-token");
  });

  it("preserves the current storage scope when replacing a token", () => {
    setToken("session-token", false);
    setToken("rotated-token");

    expect(sessionStorage.getItem("smart-exam-token")).toBe("rotated-token");
    expect(localStorage.getItem("smart-exam-token")).toBeNull();
  });

  it("clears tokens from both storage scopes", () => {
    localStorage.setItem("smart-exam-token", "local-token");
    sessionStorage.setItem("smart-exam-token", "session-token");

    removeToken();

    expect(localStorage.getItem("smart-exam-token")).toBeNull();
    expect(sessionStorage.getItem("smart-exam-token")).toBeNull();
    expect(getToken()).toBeNull();
  });

  it("does not crash when localStorage is denied", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("denied");
    });

    expect(getToken()).toBeNull();
    expect(() => setToken("token", true)).not.toThrow();
    expect(getToken()).toBe("token");
    expect(() => removeToken()).not.toThrow();
  });
});
