import { describe, expect, it } from "vitest";
import { parseMaxUploadBytes, validateDocumentFile } from "./documentUpload";

describe("validateDocumentFile", () => {
  it("rejects unsupported, empty, and oversized drag/drop files", () => {
    expect(validateDocumentFile(new File(["x"], "notes.txt"))).toContain("PDF");
    expect(validateDocumentFile(new File([], "empty.pdf"))).toContain("trống");
    const oversized = new File([new Uint8Array(20 * 1024 * 1024 + 1)], "large.pdf");
    expect(validateDocumentFile(oversized)).toContain("20 MB");
  });

  it("accepts a supported non-empty file", () => {
    expect(validateDocumentFile(new File(["x"], "matrix.XLSX"))).toBeNull();
  });

  it("uses a positive deployment value and safely falls back otherwise", () => {
    expect(parseMaxUploadBytes("1048576")).toBe(1024 * 1024);
    expect(parseMaxUploadBytes("invalid")).toBe(20 * 1024 * 1024);
    expect(parseMaxUploadBytes("0")).toBe(20 * 1024 * 1024);
  });
});

it("accepts PNG/JPEG scan uploads for OCR", () => {
  expect(validateDocumentFile(new File(["image"], "scan.PNG"))).toBeNull();
  expect(validateDocumentFile(new File(["image"], "scan.jpeg"))).toBeNull();
});
