import { useId, useState, type CSSProperties } from "react";
import type { DifficultyRatio } from "../types";
import { difficultyRatioLimit, isValidDifficultyRatio, updateDifficultyRatio } from "../utils/difficultyRatio";

interface DifficultyRatioInputProps {
  value: DifficultyRatio;
  onChange: (next: DifficultyRatio) => void;
}

type Level = "nhan_biet" | "thong_hieu" | "van_dung";

// Định nghĩa từng mức độ: key, nhãn tiếng Việt, class màu (đồng bộ với tag-difficulty).
const LEVELS: { key: Level; label: string; colorClass: string }[] = [
  { key: "nhan_biet", label: "Nhận biết", colorClass: "lvl-nhan_biet" },
  { key: "thong_hieu", label: "Thông hiểu", colorClass: "lvl-thong_hieu" },
  { key: "van_dung", label: "Vận dụng", colorClass: "lvl-van_dung" },
];

// Các preset tỷ lệ thường dùng theo Công văn 7991.
const PRESETS: { name: string; ratio: DifficultyRatio }[] = [
  { name: "Cân bằng", ratio: { nhan_biet: 33, thong_hieu: 34, van_dung: 33 } },
  { name: "Tiêu chuẩn 30/40/30", ratio: { nhan_biet: 30, thong_hieu: 40, van_dung: 30 } },
  { name: "Nặng vận dụng 20/40/40", ratio: { nhan_biet: 20, thong_hieu: 40, van_dung: 40 } },
];

function RatioNumberInput({ value, max, label, onCommit }: {
  value: number;
  max: number;
  label: string;
  onCommit: (next: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <span className="ratio-number-field">
      <input
        type="number" min={0} max={max} step={1}
        value={draft ?? value}
        onFocus={() => setDraft(String(value))}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => {
          if (draft !== null && draft.trim() !== "" && Number.isFinite(Number(draft))) {
            onCommit(Number(draft));
          }
          setDraft(null);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            event.currentTarget.blur();
          } else if (event.key === "Escape") {
            event.preventDefault();
            setDraft(String(value));
          }
        }}
        className="ratio-number"
        aria-label={`Tỷ lệ ${label} (phần trăm)`}
      />
      <span className="ratio-percent" aria-hidden="true">%</span>
    </span>
  );
}

export default function DifficultyRatioInput({ value, onChange }: DifficultyRatioInputProps) {
  const hintId = useId();
  const total = value.nhan_biet + value.thong_hieu + value.van_dung;
  const valid = isValidDifficultyRatio(value);

  function setLevel(level: Level, raw: number) {
    onChange(updateDifficultyRatio(value, level, raw));
  }

  function applyPreset(ratio: DifficultyRatio) {
    onChange({ ...ratio });
  }

  return (
    <div className="difficulty-input">
      <div className="ratio-summary">
        <span className="ratio-summary-label">Phân bổ theo mức độ</span>
        <span className={`ratio-total ${valid ? "pass" : "error"}`}>
          Tổng: {total}%{valid ? " ✓" : ""}
        </span>
      </div>
      {/* Stacked bar preview — phản hồi trực quan ngay khi kéo slider */}
      <div
        className="ratio-stacked-bar"
        role="img"
        aria-label={`Tỷ lệ: Nhận biết ${value.nhan_biet}%, Thông hiểu ${value.thong_hieu}%, Vận dụng ${value.van_dung}%`}
      >
        {LEVELS.map((lvl) => {
          const pct = value[lvl.key];
          if (pct <= 0) return null;
          return (
            <div
              key={lvl.key}
              className={`ratio-segment ${lvl.colorClass}`}
              style={{ width: `${(pct / Math.max(total, 1)) * 100}%` }}
              title={`${lvl.label}: ${pct}%`}
            />
          );
        })}
      </div>

      <p className="ratio-hint muted" id={hintId}>
        Chỉnh từ trên xuống. Khi chỉnh Thông hiểu hoặc Vận dụng, Nhận biết giữ nguyên;
        hai mức còn lại cân bằng để tổng bằng 100%.
      </p>
      {!valid && <p className="error ratio-hint" role="alert">
        Mỗi mức cần là số nguyên từ 0 đến 100, tổng bằng 100%. Chỉnh lại tỷ lệ hoặc chọn một mẫu bên dưới.
      </p>}

      {/* Keep level names visible alongside numeric input at every viewport. */}
      <div className="ratio-sliders">
        {LEVELS.map((lvl) => {
          const max = difficultyRatioLimit(value, lvl.key);
          const rangeId = `${hintId}-${lvl.key}`;
          return (
          <div className={`ratio-row ${lvl.colorClass}`} key={lvl.key}>
            <label className="ratio-label" htmlFor={rangeId}>
              <span className="ratio-dot" aria-hidden="true" />
              {lvl.label}
            </label>
            <RatioNumberInput
              value={value[lvl.key]} max={max} label={lvl.label}
              onCommit={(next) => setLevel(lvl.key, next)}
            />
            <input
              id={rangeId}
              type="range"
              min={0}
              max={max}
              step={1}
              value={value[lvl.key]}
              disabled={max === 0}
              onChange={(e) => setLevel(lvl.key, Number(e.target.value))}
              className="ratio-range"
              style={{ "--ratio-fill": `${max > 0 ? Math.max(0, Math.min(100, value[lvl.key] / max * 100)) : 0}%` } as CSSProperties}
              aria-label={`Tỷ lệ ${lvl.label}`}
              aria-valuetext={`${value[lvl.key]} phần trăm`}
              aria-describedby={hintId}
            />
            <div className="ratio-range-scale" aria-hidden="true">
              <span>0%</span>
              <span>{lvl.key === "nhan_biet" ? "100%" : `Tối đa ${max}%`}</span>
            </div>
          </div>
          );
        })}
      </div>

      {/* Presets + tổng */}
      <div className="ratio-footer">
        <div className="ratio-presets">
          {PRESETS.map((p) => (
            <button
              key={p.name}
              type="button"
              className="ratio-preset"
              aria-pressed={LEVELS.every(({ key }) => value[key] === p.ratio[key])}
              onClick={() => applyPreset(p.ratio)}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
