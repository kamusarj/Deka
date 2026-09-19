import { beforeEach, describe, expect, it } from "vitest";
import { generationRequest, completeGenerationRequest } from "./generationRequest";
import { setToken, removeToken } from "../contexts/authStorage";

describe("generation request identity", () => {
  beforeEach(() => { sessionStorage.clear(); removeToken(); });
  it("reuses uncertain requests without storing content and separates changed input", async () => {
    const first = await generationRequest({ text: "private-document-sentinel" });
    expect(await generationRequest({ text: "private-document-sentinel" })).toBe(first);
    expect(sessionStorage.getItem("smart-exam-pending-generation")).not.toContain("private-document-sentinel");
    expect(await generationRequest({ text: "different" })).not.toBe(first);
  });
  it("separates accounts and allows an explicit new generation after success", async () => {
    setToken("account-a");
    const first = await generationRequest({ number: 7 });
    setToken("account-b");
    const next = await generationRequest({ number: 7 });
    expect(next).not.toBe(first);
    completeGenerationRequest(next);
    expect(await generationRequest({ number: 7 })).not.toBe(next);
  });
});
