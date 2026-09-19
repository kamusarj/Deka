import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buildReviewRequest, useExam } from "./useExam";

const { regenerateMock } = vi.hoisted(() => ({ regenerateMock: vi.fn() }));
vi.mock("../services/api", async importOriginal => ({
  ...await importOriginal<typeof import("../services/api")>(),
  regenerateQuestions: regenerateMock,
}));

describe("useExam regeneration failures", () => {
  it("propagates failure so callers cannot report a successful repair", async () => {
    const failure = new Error("Reviewer unavailable");
    regenerateMock.mockRejectedValueOnce(failure);
    const { result } = renderHook(() => useExam());
    await act(async () => {
      await expect(result.current.onRegenerateQuestions({
        exam_id: 42, question_ids: ["q_1"], reason: "Sửa câu lỗi", allow_provider_fallback: false,
      })).rejects.toBe(failure);
    });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe("Reviewer unavailable");
    expect(result.current.result).toBeNull();
  });
});

describe("buildReviewRequest", () => {
  it.each([
    ["accepted", "accepted_question_ids"],
    ["needs_revision", "needs_revision_question_ids"],
    ["rejected", "rejected_question_ids"],
  ] as const)("places %s in only its matching request array", (status, field) => {
    const request = buildReviewRequest("q_1", status);

    expect(request[field]).toEqual(["q_1"]);
    expect(Object.values(request).flat()).toEqual(["q_1"]);
  });
});
