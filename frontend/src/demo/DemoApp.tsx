import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { HashRouter, Link, NavLink, Route, Routes, useNavigate, useParams } from "react-router";
import BrandMark from "../components/BrandMark";
import { getLearningObjective, getScoringGuide, isDemoExam, makeExam, regenerateQuestion, sampleDocuments, sampleTopics, seedExam, type DemoExam, type DemoQuestion } from "./data";
import "./demo.css";

const storageKey = "deka-public-demo-v1";

function readExams(): { exams: DemoExam[]; readFailed: boolean } {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (Array.isArray(value) && value.length > 0 && value.every(isDemoExam)) return { exams: value, readFailed: false };
  } catch {
    return { exams: [seedExam], readFailed: true };
  }
  return { exams: [seedExam], readFailed: false };
}

const typeLabel: Record<DemoQuestion["type"], string> = {
  multiple_choice: "Trắc nghiệm",
  true_false: "Đúng / Sai",
  short_answer: "Trả lời ngắn",
  essay: "Tự luận",
};

function Action({ children, to, secondary = false }: { children: ReactNode; to: string; secondary?: boolean }) {
  return <Link className={`demo-button${secondary ? " demo-button-secondary" : ""}`} to={to}>{children}</Link>;
}

function DemoShell({ children }: { children: ReactNode }) {
  return <div className="demo-shell">
    <header className="demo-topbar">
      <Link className="demo-brand" to="/"><BrandMark /><span>Deka</span></Link>
      <span className="demo-header-label">Không gian làm việc mẫu</span>
      <span className="demo-pill">Bản trải nghiệm · dữ liệu giả</span>
    </header>
    <div className="demo-frame">
      <aside className="demo-sidebar" aria-label="Điều hướng">
        <p className="demo-sidebar-title">Không gian của giáo viên</p>
        <nav>
          <NavLink to="/dashboard">Tổng quan</NavLink>
          <NavLink to="/create">Tạo đề kiểm tra</NavLink>
          <NavLink to="/exams">Đề đã tạo</NavLink>
          <NavLink to="/question-bank">Ngân hàng câu hỏi</NavLink>
          <NavLink to="/documents">Tài liệu</NavLink>
        </nav>
        <div className="demo-sidebar-note"><span>✳</span><p>Một bàn làm việc mẫu để bạn khám phá quy trình soạn đề của Deka.</p></div>
      </aside>
      <main className="demo-main" id="main-content">{children}</main>
    </div>
  </div>;
}

function Intro() {
  return <div className="demo-intro">
    <header className="demo-landing-nav"><Link className="demo-brand" to="/"><BrandMark /><span>Deka</span></Link><Action to="/dashboard" secondary>Khám phá bản demo</Action></header>
    <main className="demo-landing-main">
      <div className="demo-landing-copy">
        <p className="demo-kicker">Một bàn làm việc dành cho giáo viên KHTN</p>
        <h1>Soạn đề chỉn chu.<br />Dành tâm sức cho bài giảng.</h1>
        <p>Chọn phạm vi kiến thức, xem ma trận và bản đặc tả, rồi duyệt từng câu hỏi trước khi hoàn thiện đề kiểm tra.</p>
        <div className="demo-actions"><Action to="/create">Thử tạo đề mẫu <span aria-hidden="true">↗</span></Action><Action to="/exams/de-minh-hoa-khtn-8" secondary>Xem đề minh hoạ</Action></div>
        <p className="demo-disclaimer">Bản trải nghiệm công khai sử dụng dữ liệu giả. Các bước tạo đề và duyệt câu hỏi diễn ra ngay trên trình duyệt.</p>
      </div>
      <div className="demo-hero-sheet" aria-label="Xem trước hồ sơ đề kiểm tra">
        <div className="demo-sheet-head"><span>Deka / Hồ sơ đề</span><span>KHTN 8</span></div>
        <h2>Kiểm tra giữa kỳ I</h2><p>Chủ đề: Áp suất và ứng dụng trong đời sống</p>
        <div className="demo-sheet-rule" />
        <div className="demo-sheet-cols"><div><span>01</span><strong>Ma trận đề</strong><small>Phân bố nội dung, mức độ và điểm</small></div><div><span>02</span><strong>Bản đặc tả</strong><small>Yêu cầu cần đạt cho từng câu</small></div><div><span>03</span><strong>Đề & đáp án</strong><small>Câu hỏi sẵn sàng để giáo viên duyệt</small></div></div>
        <div className="demo-sheet-footer">4 dạng câu hỏi <span>·</span> 45 phút <span>·</span> 10 điểm</div>
      </div>
    </main>
    <section className="demo-landing-steps"><div><b>01</b><h3>Thiết lập</h3><p>Chọn lớp, thời gian và nội dung kiểm tra.</p></div><div><b>02</b><h3>Xem hồ sơ</h3><p>Ma trận, bản đặc tả, câu hỏi và đáp án cùng một nơi.</p></div><div><b>03</b><h3>Duyệt từng câu</h3><p>Giáo viên quyết định câu hỏi nào được giữ lại.</p></div></section>
    <footer className="demo-landing-footer">Deka · Bản demo công khai · Không kết nối API hoặc mô hình AI</footer>
  </div>;
}

function Dashboard({ exams }: { exams: DemoExam[] }) {
  const latest = exams[0];
  const approved = exams.reduce((sum, exam) => sum + exam.questions.filter((question) => question.approved).length, 0);
  return <section className="demo-page">
    <div className="demo-page-head"><p className="demo-kicker">Bàn làm việc</p><h1>Chào mừng đến với Deka.</h1><p>Khám phá một quy trình tạo đề Khoa học tự nhiên hoàn chỉnh bằng dữ liệu minh hoạ.</p><div className="demo-actions"><Action to="/create">Tạo đề mẫu</Action><Action to="/exams" secondary>Xem đề đã tạo</Action></div></div>
    <div className="demo-stats"><div><strong>{exams.length}</strong><span>đề kiểm tra</span></div><div><strong>{exams.reduce((sum, exam) => sum + exam.questions.length, 0)}</strong><span>câu hỏi</span></div><div><strong>{approved}</strong><span>câu đã duyệt</span></div></div>
    <div className="demo-section-title"><h2>Tiếp tục với đề gần đây</h2><Link to="/exams">Xem tất cả</Link></div>
    <Link className="demo-exam-row" to={`/exams/${latest.id}`}><span className="demo-row-icon">▤</span><span><strong>{latest.title}</strong><small>{latest.topic} · {latest.duration} phút</small></span><span className="demo-row-arrow">↗</span></Link>
    <div className="demo-tip"><span>✳</span><p>Trong bản demo, đề mới được ghép từ bộ câu hỏi mẫu theo lớp. Những thay đổi bạn thực hiện được lưu trên trình duyệt này.</p></div>
  </section>;
}

function CreateExam({ onCreate }: { onCreate: (exam: DemoExam) => void }) {
  const navigate = useNavigate();
  const [grade, setGrade] = useState(8);
  const [term, setTerm] = useState("Giữa kỳ I");
  const [duration, setDuration] = useState(45);
  const [topic, setTopic] = useState("Áp suất và ứng dụng trong đời sống");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const exam = makeExam({ grade, term, duration, topic: topic.trim() || "Nội dung Khoa học tự nhiên" });
    onCreate(exam);
    navigate(`/exams/${exam.id}`);
  }
  return <section className="demo-page"><div className="demo-page-head"><p className="demo-kicker">Tạo đề kiểm tra</p><h1>Bắt đầu từ nội dung đã dạy.</h1><p>Thiết lập thông tin cơ bản để xem một bộ đề mẫu gồm ma trận, bản đặc tả và bốn dạng câu hỏi.</p></div>
    <div className="demo-form-layout"><form className="demo-panel demo-form" onSubmit={submit}>
      <h2>Thông tin đề</h2>
      <div className="demo-form-grid"><label>Lớp<select value={grade} onChange={(event) => { const selectedGrade = Number(event.target.value); setGrade(selectedGrade); setTopic(sampleTopics[selectedGrade]); }}>{[6, 7, 8, 9].map((value) => <option key={value} value={value}>Lớp {value}</option>)}</select></label><label>Loại kiểm tra<select value={term} onChange={(event) => setTerm(event.target.value)}><option>Giữa kỳ I</option><option>Cuối kỳ I</option><option>Giữa kỳ II</option><option>Cuối kỳ II</option></select></label></div>
      <label>Thời gian làm bài<select value={duration} onChange={(event) => setDuration(Number(event.target.value))}><option value={45}>45 phút</option><option value={60}>60 phút</option><option value={90}>90 phút</option></select></label>
      <label>Nội dung kiểm tra<textarea value={topic} onChange={(event) => setTopic(event.target.value)} rows={3} maxLength={240} /></label>
      <p className="demo-form-help">Bộ câu hỏi minh hoạ được chọn theo lớp. Nội dung bạn nhập dùng làm tên chủ đề của đề mẫu.</p>
      <button className="demo-button" type="submit">Tạo bộ đề mẫu <span aria-hidden="true">↗</span></button>
    </form><aside className="demo-panel demo-side-preview"><span className="demo-preview-mark">▦</span><h2>Một bộ đề gồm những gì?</h2><ol><li>Ma trận phân bố câu hỏi</li><li>Bản đặc tả theo yêu cầu cần đạt</li><li>Câu hỏi và đáp án gợi ý</li><li>Trạng thái duyệt của giáo viên</li></ol><p>Đây là mô phỏng quy trình. Không có lời gọi đến AI, API hoặc dữ liệu thật.</p></aside></div>
  </section>;
}

function ExamList({ exams }: { exams: DemoExam[] }) {
  return <section className="demo-page"><div className="demo-page-head demo-page-head-inline"><div><p className="demo-kicker">Thư viện đề</p><h1>Đề kiểm tra đã tạo</h1><p>Danh sách minh hoạ được lưu trên trình duyệt của bạn.</p></div><Action to="/create">Tạo đề mẫu</Action></div><div className="demo-list">{exams.map((exam) => <Link className="demo-exam-row" key={exam.id} to={`/exams/${exam.id}`}><span className="demo-row-icon">▤</span><span><strong>{exam.title}</strong><small>{exam.topic} · {exam.duration} phút · {exam.questions.length} câu hỏi</small></span><span className="demo-row-arrow">↗</span></Link>)}</div></section>;
}

function ExamDetail({ exams, onUpdate, onDuplicate }: { exams: DemoExam[]; onUpdate: (exam: DemoExam) => void; onDuplicate: (exam: DemoExam) => DemoExam }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const exam = exams.find((item) => item.id === id);
  const [tab, setTab] = useState<"questions" | "matrix" | "spec" | "answers">("questions");
  const [showAnswers, setShowAnswers] = useState(false);
  if (!exam) return <section className="demo-page"><h1>Không tìm thấy đề mẫu</h1><Action to="/exams">Về danh sách đề</Action></section>;
  const approvedCount = exam.questions.filter((question) => question.approved).length;
  const levelCounts = ["Nhận biết", "Thông hiểu", "Vận dụng"].map((level) => exam.questions.filter((question) => question.level === level).length);
  function updateQuestion(questionId: string, change: Partial<DemoQuestion>) {
    onUpdate({ ...exam!, questions: exam!.questions.map((question) => question.id === questionId ? { ...question, ...change } : question) });
  }
  const tabs = [{ id: "questions", label: "Câu hỏi" }, { id: "matrix", label: "Ma trận" }, { id: "spec", label: "Bản đặc tả" }, { id: "answers", label: "Đáp án & rubric" }] as const;
  return <section className="demo-page demo-detail"><Link className="demo-back" to="/exams">← Đề đã tạo</Link><div className="demo-page-head demo-page-head-inline"><div><p className="demo-kicker">Hồ sơ đề kiểm tra</p><h1>{exam.title}</h1><p>{exam.topic} · {exam.duration} phút · 10 điểm</p></div><button className="demo-button demo-button-secondary" onClick={() => navigate(`/exams/${onDuplicate(exam).id}`)}>Nhân bản đề</button></div>
    <div className="demo-progress"><span>Giáo viên đã duyệt <strong>{approvedCount}/{exam.questions.length} câu</strong></span><div aria-label={`${approvedCount} trên ${exam.questions.length} câu đã duyệt`}><i style={{ width: `${approvedCount / exam.questions.length * 100}%` }} /></div></div>
    <div className="demo-tabs" role="tablist" aria-label="Thành phần hồ sơ đề">{tabs.map((item) => <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.label}</button>)}</div>
    {tab === "questions" && <div className="demo-question-list"><div className="demo-inline-head"><h2>Đề kiểm tra</h2><button type="button" className="demo-text-button" onClick={() => setShowAnswers(!showAnswers)}>{showAnswers ? "Ẩn đáp án" : "Hiện đáp án"}</button></div>{exam.questions.map((question, index) => <article className="demo-question" key={question.id}><div className="demo-question-meta"><span>Câu {index + 1} · {typeLabel[question.type]}</span><span>{question.level} · 2,5 điểm</span></div><h3>{question.prompt}</h3>{question.options && <ol type="A" className="demo-options">{question.options.map((option) => <li key={option}>{option}</li>)}</ol>}{showAnswers && <div className="demo-answer-inline"><b>Đáp án gợi ý</b><p>{question.answer}</p><small>{question.explanation}</small></div>}<div className="demo-question-actions"><button className={question.approved ? "demo-approved" : ""} onClick={() => updateQuestion(question.id, { approved: !question.approved })}>{question.approved ? "✓ Đã duyệt" : "Duyệt câu hỏi"}</button><button onClick={() => updateQuestion(question.id, regenerateQuestion(exam.grade, index, question))}>Tạo lại bản mẫu</button>{question.revision > 0 && <small>Bản mẫu lần {question.revision + 1}</small>}</div></article>)}</div>}
    {tab === "matrix" && <div className="demo-panel"><div className="demo-inline-head"><h2>Ma trận đề kiểm tra</h2><span>KHTN {exam.grade} · 10 điểm</span></div><div className="demo-table-wrap"><table><thead><tr><th>Chủ đề</th><th>Nhận biết</th><th>Thông hiểu</th><th>Vận dụng</th><th>Tổng</th></tr></thead><tbody><tr><th>{exam.topic}</th>{levelCounts.map((count, index) => <td key={index}>{count} câu</td>)}<td>{exam.questions.length} câu</td></tr><tr><th>Tỉ lệ điểm minh hoạ</th>{levelCounts.map((count, index) => <td key={index}>{count / exam.questions.length * 100}%</td>)}<td>100%</td></tr></tbody></table></div><p className="demo-table-note">Bộ đề mẫu chia đều 2,5 điểm cho mỗi câu. Ma trận này minh hoạ cách trình bày hồ sơ đề.</p></div>}
    {tab === "spec" && <div className="demo-panel"><h2>Bản đặc tả</h2><div className="demo-table-wrap"><table><thead><tr><th>Câu</th><th>Dạng</th><th>Mức độ</th><th>Yêu cầu cần đạt minh hoạ</th></tr></thead><tbody>{exam.questions.map((question, index) => <tr key={question.id}><td>{index + 1}</td><td>{typeLabel[question.type]}</td><td>{question.level}</td><td>{getLearningObjective(exam.grade, index)}</td></tr>)}</tbody></table></div></div>}
    {tab === "answers" && <div className="demo-panel"><h2>Đáp án và hướng dẫn chấm</h2><div className="demo-answer-list">{exam.questions.map((question, index) => <div key={question.id}><b>Câu {index + 1}</b><p>{question.answer}</p><small>{question.explanation}</small><p className="demo-scoring">{getScoringGuide(exam.grade, index)}</p></div>)}</div><button type="button" className="demo-button demo-button-secondary" onClick={() => window.print()}>In bản xem trước</button></div>}
  </section>;
}

function QuestionBank({ exams }: { exams: DemoExam[] }) {
  const questions = useMemo(() => exams.flatMap((exam) => exam.questions.filter((question) => question.approved).map((question) => ({ ...question, exam }))), [exams]);
  return <section className="demo-page"><div className="demo-page-head"><p className="demo-kicker">Ngân hàng câu hỏi</p><h1>Những câu hỏi đã duyệt</h1><p>Câu hỏi bạn duyệt trong đề mẫu sẽ xuất hiện tại đây.</p></div>{questions.length ? <div className="demo-list">{questions.map((question) => <Link className="demo-bank-row" to={`/exams/${question.exam.id}`} key={`${question.exam.id}-${question.id}`}><span className="demo-bank-type">{typeLabel[question.type]}</span><strong>{question.prompt}</strong><small>{question.exam.title}</small></Link>)}</div> : <div className="demo-empty"><span>▤</span><h2>Chưa có câu hỏi được duyệt</h2><p>Mở một đề mẫu và chọn “Duyệt câu hỏi” để thêm câu vào đây.</p><Action to={`/exams/${exams[0].id}`}>Duyệt đề mẫu</Action></div>}</section>;
}

function Documents() {
  return <section className="demo-page"><div className="demo-page-head"><p className="demo-kicker">Tài liệu dạy học</p><h1>Nguồn tham khảo mẫu</h1><p>Trong sản phẩm đầy đủ, giáo viên có thể dùng tài liệu của mình khi soạn đề. Danh sách dưới đây chỉ để minh hoạ giao diện.</p></div><div className="demo-list">{sampleDocuments.map((document) => <div className="demo-document-row" key={document.name}><span className="demo-row-icon">▤</span><span><strong>{document.name}</strong><small>{document.note}</small></span><span className="demo-file-type">{document.kind}</span></div>)}</div><div className="demo-tip"><span>✳</span><p>Bản demo không nhận tệp tải lên và không gửi tài liệu ra máy chủ.</p></div></section>;
}

export default function DemoApp() {
  const [initialState] = useState(readExams);
  const [exams, setExams] = useState(initialState.exams);
  const [storageUnavailable, setStorageUnavailable] = useState(initialState.readFailed);
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(exams));
      setStorageUnavailable(initialState.readFailed);
    } catch {
      setStorageUnavailable(true);
    }
  }, [exams, initialState.readFailed]);
  function duplicate(exam: DemoExam) {
    const copy = { ...exam, id: `demo-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, title: `${exam.title} (bản sao)`, createdAt: new Date().toISOString(), questions: exam.questions.map((question) => ({ ...question })) };
    setExams((current) => [copy, ...current]);
    return copy;
  }
  return <HashRouter>{storageUnavailable && <div className="demo-storage-notice" role="status">Trình duyệt không thể lưu dữ liệu demo. Bạn vẫn có thể trải nghiệm; thay đổi sẽ mất khi tải lại trang.</div>}<Routes><Route path="/" element={<Intro />} /><Route path="/*" element={<DemoShell><Routes><Route path="/dashboard" element={<Dashboard exams={exams} />} /><Route path="/create" element={<CreateExam onCreate={(exam) => setExams((current) => [exam, ...current])} />} /><Route path="/exams" element={<ExamList exams={exams} />} /><Route path="/exams/:id" element={<ExamDetail exams={exams} onUpdate={(exam) => setExams((current) => current.map((item) => item.id === exam.id ? exam : item))} onDuplicate={duplicate} />} /><Route path="/question-bank" element={<QuestionBank exams={exams} />} /><Route path="/documents" element={<Documents />} /><Route path="*" element={<Dashboard exams={exams} />} /></Routes></DemoShell>} /></Routes></HashRouter>;
}
