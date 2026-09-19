import { useState } from "react";
import { Link } from "react-router";

const steps = [
  {
    title: "Chọn nội dung",
    summary: "Khối lớp, bài học và yêu cầu cần đạt.",
    location: "Ở trang Tạo đề",
    action: "Chọn khối lớp và loại kiểm tra, rồi nhập các bài đã dạy cùng yêu cầu cần đạt. Bạn có thể chọn thêm tài liệu đã tải lên làm nguồn tham khảo.",
    example: [
      ["Môn và lớp", "Khoa học tự nhiên 8"],
      ["Bài học", "Khối lượng riêng, áp suất"],
      ["Yêu cầu cần đạt", "Vận dụng công thức tính khối lượng riêng."],
    ],
    outcome: "Phạm vi kiến thức rõ ràng để câu hỏi bám sát nội dung cần kiểm tra.",
    note: "Chưa có tài liệu tải lên? Bạn vẫn có thể bắt đầu bằng nội dung bài học.",
  },
  {
    title: "Thiết lập cấu trúc",
    summary: "Số câu, điểm, mức độ và số mã đề.",
    location: "Trong cùng form Tạo đề",
    action: "Đặt thời gian, số câu cho từng dạng và tỷ lệ nhận biết, thông hiểu, vận dụng. Chọn số câu tính toán bắt buộc và số mã đề muốn tạo.",
    example: [
      ["Thời gian", "45 phút"],
      ["Cấu trúc", "16 câu, tổng 10 điểm"],
      ["Mức độ", "30% nhận biết, 40% thông hiểu, 30% vận dụng"],
      ["Số mã đề", "4 mã đề"],
    ],
    outcome: "Cấu hình hoàn chỉnh để AI xây ma trận và phân bổ câu hỏi.",
    note: "Có thể bật tự động phân bổ điểm hoặc tự đặt điểm cho từng dạng câu.",
  },
  {
    title: "Tạo và duyệt đề",
    summary: "AI soạn đề; bạn rà soát từng câu.",
    location: "Ở phần kết quả của đề",
    action: "Bấm “Tạo đề kiểm tra” và chờ xử lý. Khi có kết quả, xem ma trận, đọc câu hỏi, đáp án và lời giải. Đánh dấu câu cần sửa và yêu cầu tạo lại khi cần.",
    example: [
      ["AI chuẩn bị", "Ma trận, câu hỏi, đáp án và hướng dẫn chấm"],
      ["Bạn kiểm tra", "Nội dung, lời giải và các điểm cần rà soát"],
      ["Khi cần sửa", "Chọn câu hỏi và yêu cầu tạo lại"],
    ],
    outcome: "Bộ đề được bạn rà soát trước khi sử dụng cho lớp học.",
    note: "Nếu đề còn lỗi kiểm định, xử lý các câu được đánh dấu trước khi xuất.",
  },
  {
    title: "Xuất và dùng lại",
    summary: "Tải Word/PDF, lưu câu hỏi cho lần sau.",
    location: "Trong trang chi tiết đề",
    action: "Chọn mã đề và loại tài liệu để tải về. Bạn có thể mở lại đề trong “Đề đã tạo” hoặc lưu các câu phù hợp vào ngân hàng câu hỏi để dùng về sau.",
    example: [
      ["Cho học sinh", "Đề kiểm tra"],
      ["Cho giáo viên", "Đáp án và hướng dẫn chấm"],
      ["Tài liệu kèm theo", "Ma trận và bản đặc tả"],
      ["Định dạng tải về", "Word hoặc PDF, riêng từng tài liệu"],
    ],
    outcome: "Các tệp phục vụ in ấn, chấm bài và nguồn câu hỏi cho những lần tiếp theo.",
    note: "Bản dành cho học sinh không hiển thị đáp án và lời giải.",
  },
];

export default function ExamWorkflow() {
  const [selected, setSelected] = useState(0);
  const step = steps[selected];

  return (
    <section id="quy-trinh" className="paper-section paper-workflow" aria-labelledby="workflow-heading">
      <div className="paper-section-heading">
        <h2 id="workflow-heading">Một đề kiểm tra đi qua những bước nào?</h2>
        <p>Bạn chọn nội dung và duyệt kết quả. AI hỗ trợ xây dựng bộ đề.<br />Chọn từng bước để hình dung cách làm.</p>
      </div>
      <div className="workflow-layout">
        <ol className="workflow-steps" aria-label="Bốn bước tạo đề">
          {steps.map((item, index) => (
            <li key={item.title}>
              <button
                type="button"
                aria-pressed={selected === index}
                aria-controls="workflow-detail"
                aria-label={`Bước ${index + 1}: ${item.title}`}
                onClick={() => setSelected(index)}
              >
                <span className="workflow-number" aria-hidden="true">{index + 1}</span>
                <span className="workflow-step-copy"><strong>{item.title}</strong><span>{item.summary}</span></span>
                <span className="workflow-step-indicator" aria-hidden="true">↗</span>
              </button>
            </li>
          ))}
        </ol>
        <section id="workflow-detail" className="workflow-detail" aria-labelledby="workflow-detail-heading">
          <div aria-live="polite" aria-atomic="true">
            <div className="workflow-detail-meta"><span>{step.location}</span><span>Bước {selected + 1} / 4</span></div>
            <h3 id="workflow-detail-heading">{step.title}</h3>
            <p className="workflow-action">{step.action}</p>
            <div className="workflow-example">
              <p>Ví dụ minh họa cho đề KHTN 8</p>
              <dl>{step.example.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
            </div>
            <div className="workflow-outcome"><strong>Sau bước này</strong><p>{step.outcome}</p></div>
            <p className="workflow-note">{step.note}</p>
          </div>
          <div className="workflow-detail-actions">
            {selected < steps.length - 1
              ? <button type="button" className="secondary compact" onClick={() => setSelected((current) => current + 1)}>Tiếp theo: {steps[selected + 1].title}</button>
              : <Link to="/#uu-diem" className="button-link secondary compact">Xem bộ đề minh họa</Link>}
          </div>
        </section>
      </div>
      <div className="workflow-start">
        <div><h3>Có việc cần dừng lại giữa chừng?</h3><p>Form tạo đề tự lưu theo tài khoản trên trình duyệt đang dùng, để bạn quay lại tiếp tục phần đang soạn.</p></div>
        <Link to="/create" className="paper-button">Bắt đầu tạo đề của bạn</Link>
      </div>
    </section>
  );
}
