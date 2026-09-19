import { useState } from "react";

const sections = ["Ma trận", "Câu hỏi", "Hướng dẫn chấm"] as const;

/** Illustrative content, never represented as a saved or verified exam. */
export default function ExamPreview() {
  const [section, setSection] = useState<(typeof sections)[number]>("Ma trận");
  return <div className="exam-sample">
    <div className="exam-sample-toolbar"><span className="exam-sample-caption">Ví dụ minh họa</span><div className="exam-sample-switch" role="group" aria-label="Phần xem trước">{sections.map(label => <button key={label} type="button" aria-pressed={section === label} onClick={() => setSection(label)}>{label}</button>)}</div><span className="exam-sample-format">KHTN 8</span></div>
    <div className="exam-sample-paper">
      <div className="exam-sample-header"><div><span>Khoa học tự nhiên · Lớp 8</span><h3>Kiểm tra giữa học kỳ I</h3></div><span className="exam-sample-duration">45 phút</span></div>
      <div className="exam-sample-content" key={section} aria-live="polite">
        {section === "Ma trận" && <><div className="exam-sample-table-wrap"><table><caption className="sr-only">Minh họa ma trận phân bổ 10 câu hỏi</caption><thead><tr><th>Chủ đề</th><th>Nhận biết</th><th>Thông hiểu</th><th>Vận dụng</th></tr></thead><tbody><tr><th>Phản ứng hóa học</th><td>2 câu</td><td>1 câu</td><td>1 câu</td></tr><tr><th>Khối lượng riêng</th><td>1 câu</td><td>1 câu</td><td>1 câu</td></tr><tr><th>Áp suất</th><td>1 câu</td><td>1 câu</td><td>1 câu</td></tr></tbody></table></div><p className="exam-sample-summary">10 câu hỏi <span>4 nhận biết · 3 thông hiểu · 3 vận dụng</span></p></>}
        {section === "Câu hỏi" && <div className="exam-sample-question"><span>Câu 1 · Khối lượng riêng</span><h4>Một vật có khối lượng 540 g và thể tích 200 cm³. Khối lượng riêng của vật là bao nhiêu?</h4><div className="exam-sample-options"><span>A. 0,37 g/cm³</span><span>B. 2,7 g/cm³</span><span>C. 340 g/cm³</span><span>D. 740 g/cm³</span></div><p className="muted">Bản câu hỏi dành cho học sinh không hiển thị đáp án.</p></div>}
        {section === "Hướng dẫn chấm" && <div className="exam-sample-question"><span>Câu 1 · Đáp án B</span><h4>Áp dụng công thức tính khối lượng riêng.</h4><p className="exam-sample-formula">D = m / V = 540 / 200 = 2,7 g/cm³</p><p>Khối lượng và thể tích đã cùng hệ đơn vị. Học sinh chọn đáp án B.</p><p className="muted">Lời giải và đáp án nằm trong hướng dẫn dành cho giáo viên.</p></div>}
      </div>
      <div className="exam-sample-bottom"><span>Ma trận · Đề kiểm tra · Hướng dẫn chấm</span><span>Word / PDF</span></div>
    </div>
  </div>;
}
