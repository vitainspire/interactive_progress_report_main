import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./auth/AuthContext";
import { BatchPage } from "./pages/BatchPage";
import { DashboardPage } from "./pages/DashboardPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { LoginPage } from "./pages/LoginPage";
import { SchoolProfilePage } from "./pages/SchoolProfilePage";
import { SchoolSetupPage } from "./pages/SchoolSetupPage";
import { SignupPage } from "./pages/SignupPage";
import { StudentPage } from "./pages/StudentPage";
import { TimetablePage } from "./pages/TimetablePage";
import { ToolsHubPage } from "./pages/ToolsHubPage";
import { UploadPage } from "./pages/UploadPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.default_school_name) return <Navigate to="/school-setup" replace />;
  return <>{children}</>;
}

function Root() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.default_school_name ? "/tools" : "/school-setup"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Root />} />
      <Route path="login" element={<LoginPage />} />
      <Route path="signup" element={<SignupPage />} />
      <Route path="school-setup" element={<SchoolSetupPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="tools" element={<ToolsHubPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="timetable" element={<TimetablePage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="batches/:id" element={<BatchPage />} />
        <Route path="batches/:id/students/:studentId" element={<StudentPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="school-profile" element={<SchoolProfilePage />} />
      </Route>
    </Routes>
  );
}
