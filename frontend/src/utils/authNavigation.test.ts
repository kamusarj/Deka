import { describe, expect, it } from "vitest";
import { getPostAuthPath } from "./authNavigation";

describe("getPostAuthPath", () => {
  it("preserves a protected deep link", () => {
    expect(
      getPostAuthPath({ from: { pathname: "/exams/42", search: "?tab=matrix", hash: "" } }),
    ).toBe("/exams/42?tab=matrix");
  });

  it("rejects unsafe and recursive auth destinations", () => {
    expect(getPostAuthPath({ from: { pathname: "//evil.test" } })).toBe("/dashboard");
    expect(getPostAuthPath({ from: { pathname: "/login" } })).toBe("/dashboard");
  });
});
