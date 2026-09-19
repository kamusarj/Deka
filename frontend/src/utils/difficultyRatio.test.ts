import { describe, expect, it } from "vitest";
import type { DifficultyRatio } from "../types";
import { updateDifficultyRatio } from "./difficultyRatio";

const standard: DifficultyRatio = { nhan_biet: 30, thong_hieu: 40, van_dung: 30 };

describe("updateDifficultyRatio", () => {
  it("keeps the first ratio at 35 while later adjustments share the remainder", () => {
    let ratio = updateDifficultyRatio(standard, "nhan_biet", 35);
    expect(ratio).toEqual({ nhan_biet: 35, thong_hieu: 40, van_dung: 25 });

    ratio = updateDifficultyRatio(ratio, "thong_hieu", 50);
    expect(ratio).toEqual({ nhan_biet: 35, thong_hieu: 50, van_dung: 15 });

    ratio = updateDifficultyRatio(ratio, "van_dung", 30);
    expect(ratio).toEqual({ nhan_biet: 35, thong_hieu: 35, van_dung: 30 });
  });

  it("supports reversing a lower slider without accumulating rounding drift", () => {
    const initial = { nhan_biet: 35, thong_hieu: 40, van_dung: 25 };
    let ratio = initial;
    for (const next of [41, 58, 65, 39, 0, 40]) {
      ratio = updateDifficultyRatio(ratio, "thong_hieu", next);
      expect(ratio.nhan_biet).toBe(35);
    }
    expect(ratio).toEqual(initial);
  });

  it("only reduces the next level when a higher level leaves insufficient room", () => {
    const ratio = updateDifficultyRatio(standard, "nhan_biet", 80);
    expect(ratio).toEqual({ nhan_biet: 80, thong_hieu: 20, van_dung: 0 });
    expect(updateDifficultyRatio(ratio, "nhan_biet", 35)).toEqual({
      nhan_biet: 35, thong_hieu: 20, van_dung: 45,
    });
  });

  it.each(["thong_hieu", "van_dung"] as const)(
    "clamps %s to the available share while retaining Nhận biết",
    (level) => {
      const ratio = updateDifficultyRatio(
        { nhan_biet: 35, thong_hieu: 40, van_dung: 25 }, level, 100,
      );
      expect(ratio.nhan_biet).toBe(35);
      expect(ratio[level]).toBe(65);
      expect(ratio[level === "thong_hieu" ? "van_dung" : "thong_hieu"]).toBe(0);
    },
  );

  it("handles the full range including all share assigned to the first level", () => {
    expect(updateDifficultyRatio(standard, "nhan_biet", -10)).toEqual({
      nhan_biet: 0, thong_hieu: 40, van_dung: 60,
    });
    const fullFirst = updateDifficultyRatio(standard, "nhan_biet", 110);
    expect(fullFirst).toEqual({ nhan_biet: 100, thong_hieu: 0, van_dung: 0 });
    expect(updateDifficultyRatio(fullFirst, "thong_hieu", 50)).toEqual(fullFirst);
    expect(updateDifficultyRatio(fullFirst, "van_dung", 50)).toEqual(fullFirst);
    expect(updateDifficultyRatio(fullFirst, "nhan_biet", 0)).toEqual({
      nhan_biet: 0, thong_hieu: 0, van_dung: 100,
    });
  });

  it("rounds entered percentages to whole numbers without changing the input object", () => {
    const input = Object.freeze({ ...standard });
    expect(updateDifficultyRatio(input, "thong_hieu", 40.6)).toEqual({
      nhan_biet: 30, thong_hieu: 41, van_dung: 29,
    });
    expect(input).toEqual(standard);
  });

  it("normalizes an out-of-range restored first level before balancing a lower level", () => {
    expect(updateDifficultyRatio(
      { nhan_biet: 120, thong_hieu: -10, van_dung: -10 }, "thong_hieu", 50,
    )).toEqual({ nhan_biet: 100, thong_hieu: 0, van_dung: 0 });
  });

  it("normalizes a negative restored second level when changing the first level", () => {
    expect(updateDifficultyRatio(
      { nhan_biet: 30, thong_hieu: -5, van_dung: 75 }, "nhan_biet", 35,
    )).toEqual({ nhan_biet: 35, thong_hieu: 0, van_dung: 65 });
  });

  it("normalizes fractional restored anchors to integer percentages on adjustment", () => {
    const restored = { nhan_biet: 35.6, thong_hieu: 40.2, van_dung: 24.2 };
    expect(updateDifficultyRatio(restored, "thong_hieu", 45)).toEqual({
      nhan_biet: 36, thong_hieu: 45, van_dung: 19,
    });
    expect(updateDifficultyRatio(restored, "nhan_biet", 35)).toEqual({
      nhan_biet: 35, thong_hieu: 40, van_dung: 25,
    });
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])(
    "ignores non-finite input %s", (raw) => {
      expect(updateDifficultyRatio(standard, "nhan_biet", raw)).toEqual(standard);
    },
  );

  it("preserves integer percentages and total 100 across all levels and boundary inputs", () => {
    const levels: (keyof DifficultyRatio)[] = ["nhan_biet", "thong_hieu", "van_dung"];
    for (const first of [0, 1, 33, 35, 99, 100]) {
      for (const second of [0, Math.floor((100 - first) / 2), 100 - first]) {
        const input = { nhan_biet: first, thong_hieu: second, van_dung: 100 - first - second };
        for (const level of levels) {
          for (const raw of [-1, 0, 0.4, 35.5, 65, 99, 100, 101]) {
            const result = updateDifficultyRatio(input, level, raw);
            expect(Object.values(result).reduce((sum, value) => sum + value, 0)).toBe(100);
            for (const percentage of Object.values(result)) {
              expect(Number.isInteger(percentage)).toBe(true);
              expect(percentage).toBeGreaterThanOrEqual(0);
              expect(percentage).toBeLessThanOrEqual(100);
            }
            if (level !== "nhan_biet") expect(result.nhan_biet).toBe(first);
          }
        }
      }
    }
  });
});
