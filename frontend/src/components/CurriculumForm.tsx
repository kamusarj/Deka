import type { CurriculumItem } from "../types";

interface CurriculumFormProps {
  curriculum: CurriculumItem[];
  onChange: (index: number, field: keyof CurriculumItem, value: string) => void;
  onAdd: () => void;
}

export default function CurriculumForm({
  curriculum,
  onChange,
  onAdd,
}: CurriculumFormProps) {
  return (
    <div>
      <h3 className="subsection-title">Phân phối chương trình</h3>
      <div
        className="curriculum-table"
        role="table"
        aria-label="Phân phối chương trình"
      >
        <div className="curriculum-head" role="row">
          <span>Chủ đề / bài học</span>
          <span>Số tiết</span>
          <span>Yêu cầu cần đạt</span>
        </div>
        {curriculum.map((item, index) => (
          <div className="curriculum-row" role="row" key={index}>
            <textarea
              aria-label="Chủ đề hoặc bài học"
              className="curriculum-cell"
              rows={1}
              value={item.topic}
              onChange={(event) => onChange(index, "topic", event.target.value)}
              required
            />
            <input
              aria-label="Số tiết"
              type="number"
              min={1}
              value={item.periods}
              onChange={(event) => onChange(index, "periods", event.target.value)}
            />
            <textarea
              aria-label="Yêu cầu cần đạt"
              className="curriculum-cell"
              rows={2}
              value={item.achievements[0] || ""}
              onChange={(event) =>
                onChange(index, "achievements", event.target.value)
              }
            />
          </div>
        ))}
        {curriculum.length === 0 && (
          <div className="curriculum-row muted" role="row" style={{ padding: "0.8rem" }}>
            <span>Chưa có chủ đề nào. Nhấn “Thêm bài học” để bắt đầu.</span>
          </div>
        )}
      </div>
      <button type="button" className="secondary compact" onClick={onAdd}>
        + Thêm bài học
      </button>
    </div>
  );
}
