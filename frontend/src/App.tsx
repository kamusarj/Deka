import { useEffect } from "react";
import { HashRouter, Routes, Route, Outlet } from "react-router";
import {
  ErrorBoundary,
  Layout,
  ProtectedRoute,
  ToastViewport,
  AppFooter,
} from "./components";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { ToastProvider } from "./contexts/ToastContext";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import VerifyEmail from "./pages/VerifyEmail";
import OAuthCallback from "./pages/OAuthCallback";
import Home from "./pages/Home";
import CreateExam from "./pages/CreateExam";
import ExamDetail from "./pages/ExamDetail";
import ExamList from "./pages/ExamList";
import Documents from "./pages/Documents";
import QuestionBank from "./pages/QuestionBank";
import Community from "./pages/Community";
import CommunityTopic from "./pages/CommunityTopic";
import Account from "./pages/Account";
import AiSettings from "./pages/AiSettings";
import SchoolAdmin from "./pages/SchoolAdmin";
import UsageReports from "./pages/UsageReports";
import "./styles.css";
import "./styles/paper.css";
import RouteScroll from "./components/RouteScroll";

function App() {
  useEffect(() => {
    const stopBrowserFileNavigation = (event: DragEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest("[data-allow-file-drop='true']")) return;
      event.preventDefault();
    };
    window.addEventListener("dragover", stopBrowserFileNavigation);
    window.addEventListener("drop", stopBrowserFileNavigation);
    return () => {
      window.removeEventListener("dragover", stopBrowserFileNavigation);
      window.removeEventListener("drop", stopBrowserFileNavigation);
    };
  }, []);

  return (
    <HashRouter>
      <RouteScroll />
      <ErrorBoundary>
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <ToastViewport />
              <div className="app-shell">
                <div className="app-shell-content">
                  <Routes>
                    {/* Public routes */}
                    <Route element={<><Outlet /><AppFooter /></>}>
                      <Route path="/" element={<Landing />} />
                      <Route path="/login" element={<Login />} />
                      <Route path="/register" element={<Register />} />
                      <Route path="/forgot-password" element={<ForgotPassword />} />
                      <Route path="/reset-password" element={<ResetPassword />} />
                      <Route path="/verify-email" element={<VerifyEmail />} />
                      <Route path="/auth/callback" element={<OAuthCallback />} />

                      {/* Fallback */}
                      <Route path="*" element={<Landing />} />
                    </Route>
                    {/* Protected app workspace */}
                    <Route
                      element={
                        <ProtectedRoute>
                          <Layout />
                        </ProtectedRoute>
                      }
                    >
                      <Route path="/dashboard" element={<Home />} />
                      <Route path="/create" element={
                        <ProtectedRoute requiredCapability="content_write">
                          <CreateExam />
                        </ProtectedRoute>
                      } />
                      <Route path="/exams" element={<ExamList />} />
                      <Route path="/exams/:id" element={<ExamDetail />} />
                      <Route path="/documents" element={<Documents />} />
                      <Route path="/question-bank" element={<QuestionBank />} />
                      <Route path="/community" element={<Community />} />
                      <Route path="/community/:id" element={<CommunityTopic />} />
                      <Route path="/account" element={<Account />} />
                      <Route path="/usage" element={<UsageReports />} />
                      <Route
                        path="/ai-settings"
                        element={
                          <ProtectedRoute requiredCapability="ai_provider_mutation">
                            <AiSettings />
                          </ProtectedRoute>
                        }
                      />
                      <Route
                        path="/school-admin"
                        element={
                          <ProtectedRoute requiredCapability="school_teacher_admin">
                            <SchoolAdmin />
                          </ProtectedRoute>
                        }
                      />
                    </Route>

                  </Routes>
                </div>
              </div>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </ErrorBoundary>
    </HashRouter>
  );
}

export default App;
