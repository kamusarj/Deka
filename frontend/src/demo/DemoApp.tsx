import { HashRouter, Route, Routes } from "react-router";
import DemoShell from "./components/DemoShell";
import CreateExam from "./pages/CreateExam";
import Dashboard from "./pages/Dashboard";
import Documents from "./pages/Documents";
import ExamDetail from "./pages/ExamDetail";
import ExamList from "./pages/ExamList";
import Intro from "./pages/Intro";
import QuestionBank from "./pages/QuestionBank";
import { useDemoExams } from "./useDemoExams";
import "./demo.css";

export default function DemoApp() {
  const { exams, storageUnavailable, create, update, duplicate } =
    useDemoExams();
  return (
    <HashRouter>
      {storageUnavailable && (
        <div className="demo-storage-notice" role="status">
          Trình duyệt không thể lưu dữ liệu demo. Bạn vẫn có thể trải nghiệm;
          thay đổi sẽ mất khi tải lại trang.
        </div>
      )}
      <Routes>
        <Route path="/" element={<Intro />} />
        <Route
          path="/*"
          element={
            <DemoShell>
              <Routes>
                <Route
                  path="/dashboard"
                  element={<Dashboard exams={exams} />}
                />
                <Route
                  path="/create"
                  element={<CreateExam onCreate={create} />}
                />
                <Route path="/exams" element={<ExamList exams={exams} />} />
                <Route
                  path="/exams/:id"
                  element={
                    <ExamDetail
                      exams={exams}
                      onUpdate={update}
                      onDuplicate={duplicate}
                    />
                  }
                />
                <Route
                  path="/question-bank"
                  element={<QuestionBank exams={exams} />}
                />
                <Route path="/documents" element={<Documents />} />
                <Route path="*" element={<Dashboard exams={exams} />} />
              </Routes>
            </DemoShell>
          }
        />
      </Routes>
    </HashRouter>
  );
}
