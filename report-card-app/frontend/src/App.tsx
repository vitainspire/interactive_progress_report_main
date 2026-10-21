import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./auth/AuthContext";
import { BatchPage } from "./pages/BatchPage";
import { DashboardPage } from "./pages/DashboardPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { StudentPage } from "./pages/StudentPage";
import { TimetablePage } from "./pages/TimetablePage";
import { ToolsHubPage } from "./pages/ToolsHubPage";
import { UploadPage } from "./pages/UploadPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function Root() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/tools" replace />;
  return <LandingPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Root />} />
      <Route path="login" element={<LoginPage />} />
      <Route path="signup" element={<SignupPage />} />
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
      </Route>
    </Routes>
  );
}
