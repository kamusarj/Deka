import { describe, expect, it } from "vitest";
import { getApiErrorMessage } from "./apiError";

describe("getApiErrorMessage", () => {
  it("prefers the backend detail over Axios' generic Error message", () => {
    const error = Object.assign(new Error("Request failed with status code 422"), {
      response: { data: { detail: "Tổng tỷ lệ mức độ phải bằng 100%" } },
    });
    expect(getApiErrorMessage(error, "fallback")).toBe(
      "Tổng tỷ lệ mức độ phải bằng 100%",
    );
  });

  it("formats Pydantic validation details", () => {
    const error = { response: { data: { detail: [{ msg: "Field required" }] } } };
    expect(getApiErrorMessage(error, "fallback")).toBe("Field required");
  });
});
