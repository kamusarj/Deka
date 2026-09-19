import { describe, expect, it, vi } from "vitest";
import { createDefaultExamPayload, examFormDraftKey, readExamFormDraft, removeExamFormDraft, writeExamFormDraft } from "./examFormDraft";

const draftData = () => ({
  payload: createDefaultExamPayload(), calculationCountInput: "", curriculumEdited: true, selectedDocIds: [12, 19],
});

describe("exam form draft storage", () => {
  it("round-trips incomplete inputs independently of submission validation", () => {
    const data = draftData();
    data.payload.school = "";
    data.payload.duration_minutes = 0;
    data.payload.difficulty_ratio.nhan_biet = 70;
    data.payload.curriculum.push({ topic: "Đang soạn dở", periods: 1, achievements: [""] });
    writeExamFormDraft("12:4", data);
    expect(readExamFormDraft("12:4").draft?.data).toEqual(data);
  });

  it("isolates both account and school context and removes only the requested draft", () => {
    for (const scope of ["12:4", "13:4", "12:5"]) {
      const data = draftData();
      data.payload.school = scope;
      writeExamFormDraft(scope, data);
    }
    removeExamFormDraft("12:4");
    expect(readExamFormDraft("12:4").draft).toBeNull();
    expect(readExamFormDraft("13:4").draft?.data.payload.school).toBe("13:4");
    expect(readExamFormDraft("12:5").draft?.data.payload.school).toBe("12:5");
  });

  it.each([
    "{broken", "null", JSON.stringify({ version: 2 }),
  ])("handles invalid or incompatible stored envelopes: %s", (raw) => {
    localStorage.setItem(examFormDraftKey("12:4"), raw);
    expect(readExamFormDraft("12:4")).toMatchObject({ draft: null, warning: expect.any(String) });
    expect(readExamFormDraft("12:4").warning).not.toBe("");
  });

  it.each(["missing payload", "bad array", "bad number", "bad difficulty", "wrong owner", "bad ids"])("rejects %s before rendering", (failure) => {
    writeExamFormDraft("12:4", draftData());
    const stored = JSON.parse(localStorage.getItem(examFormDraftKey("12:4"))!);
    if (failure === "missing payload") delete stored.data.payload.question_types;
    if (failure === "bad array") stored.data.payload.curriculum = null;
    if (failure === "bad number") stored.data.payload.duration_minutes = null;
    if (failure === "bad difficulty") stored.data.payload.calculation_requirement.difficulties = ["unknown"];
    if (failure === "wrong owner") stored.scope = "13:4";
    if (failure === "bad ids") stored.data.selectedDocIds = [null];
    localStorage.setItem(examFormDraftKey("12:4"), JSON.stringify(stored));
    expect(readExamFormDraft("12:4").draft).toBeNull();
  });

  it("strips unrelated payload fields and cannot restore provider fallback", () => {
    writeExamFormDraft("12:4", draftData());
    const stored = JSON.parse(localStorage.getItem(examFormDraftKey("12:4"))!);
    stored.data.payload.allow_provider_fallback = true;
    stored.data.payload.secret = "unrelated";
    stored.data.payload.use_uploaded_docs = [999];
    localStorage.setItem(examFormDraftKey("12:4"), JSON.stringify(stored));
    const restored = readExamFormDraft("12:4").draft!.data.payload;
    expect(restored.allow_provider_fallback).toBe(false);
    expect(restored).not.toHaveProperty("secret");
    expect(restored).not.toHaveProperty("use_uploaded_docs");
  });

  it("reports blocked reads and lets write failures reach the save indicator", () => {
    const read = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Blocked"); });
    expect(readExamFormDraft("12:4").draft).toBeNull();
    read.mockRestore();
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Full"); });
    expect(() => writeExamFormDraft("12:4", draftData())).toThrow("Full");
    write.mockRestore();
  });
});
