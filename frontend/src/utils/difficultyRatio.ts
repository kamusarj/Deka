import type { DifficultyRatio } from "../types";

function percentage(value: number) {
  return Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : 0;
}

export function difficultyRatioLimit(value: DifficultyRatio, level: keyof DifficultyRatio) {
  return level === "nhan_biet" ? 100 : 100 - percentage(value.nhan_biet);
}

export function isValidDifficultyRatio(value: DifficultyRatio) {
  const values = [value.nhan_biet, value.thong_hieu, value.van_dung];
  return values.every((n) => Number.isInteger(n) && n >= 0 && n <= 100)
    && values.reduce((sum, n) => sum + n, 0) === 100;
}

/** Balance from the top down; lower levels never change recognition. */
export function updateDifficultyRatio(
  value: DifficultyRatio,
  level: keyof DifficultyRatio,
  raw: number,
): DifficultyRatio {
  if (!Number.isFinite(raw)) return { ...value };
  const requested = percentage(raw);
  if (level === "nhan_biet") {
    const understanding = Math.min(percentage(value.thong_hieu), 100 - requested);
    return { nhan_biet: requested, thong_hieu: understanding, van_dung: 100 - requested - understanding };
  }
  const recognition = percentage(value.nhan_biet);
  const remaining = 100 - recognition;
  const next = Math.min(requested, remaining);
  return {
    nhan_biet: recognition,
    thong_hieu: level === "thong_hieu" ? next : remaining - next,
    van_dung: level === "van_dung" ? next : remaining - next,
  };
}
