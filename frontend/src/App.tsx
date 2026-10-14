import { Link, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./auth/AuthContext";
import { ClassesProvider, useClasses } from "./context/ClassesContext";
import { AccountsPage } from "./pages/AccountsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ManageClassesPage } from "./pages/ManageClassesPage";
import { SectionsPage } from "./pages/SectionsPage";
import { SectionStudentsPage } from "./pages/SectionStudentsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SchoolOverviewPage } from "./pages/SchoolOverviewPage";
import { SignupPage } from "./pages/SignupPage";
import { StudentDetailPage } from "./pages/StudentDetailPage";
import { StudentLoginPage } from "./pages/StudentLoginPage";
import { UploadsPage } from "./pages/UploadsPage";
import type { Role } from "./types";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** Gates a route to specific roles, once RequireAuth has already confirmed
 * someone is logged in. Anyone else is bounced to "/" (which itself routes
 * a student straight to their own report via HomeRedirect). */
function RequireRole({ allowed, children }: { allowed: Role[]; children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user || !allowed.includes(user.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

/** A simple "pick a class" landing for an admin/teacher with more than one
 * class — deliberately never auto-picks one for them (a remembered last
 * class would be wrong the first time and stale afterward). */
function ClassPickerPage() {
  const { classes } = useClasses();
  const { user } = useAuth();
  return (
    <div className="mx-auto max-w-md space-y-3">
      <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
        Choose a class
      </h1>
      {classes.length === 0 && (
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {user?.role === "admin" ? "No classes yet." : "You haven't been assigned to a class yet — ask your headmaster."}
        </p>
      )}
      <div className="space-y-2">
        {classes.map((c) => (
          <Link
            key={c.id}
            to={`/c/${c.id}`}
            className="soft-card block p-4 font-medium transition-shadow hover:shadow-md"
            style={{ color: "var(--text-primary)" }}
          >
            {c.name}
          </Link>
        ))}
      </div>
    </div>
  );
}

/** Where "/" sends each role. A student always goes straight to their own
 * report — they never browse by class. An admin always sees the School
 * Overview first (every class at a glance, including the empty state when
 * there are none yet) rather than being dropped straight into one class's
 * dashboard — picking a class from there is how they reach the per-class
 * view. A teacher with exactly one class goes straight in instead (less
 * friction for the common case); with several, a plain picker (never a
 * silently remembered "last class", which would be wrong the first time
 * and stale afterward). */
function HomeRedirect() {
  const { user } = useAuth();
  const { classes, loading } = useClasses();

  if (user?.role === "student" && user.student_id) {
    return <Navigate to={`/students/${user.student_id}`} replace />;
  }
  if (loading) return null;
  if (user?.role === "admin") {
    return <SchoolOverviewPage />;
  }
  if (classes.length === 1) {
    return <Navigate to={`/c/${classes[0].id}`} replace />;
  }
  return <ClassPickerPage />;
}

export default function App() {
  return (
    <ClassesProvider>
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route path="signup" element={<SignupPage />} />
        <Route path="student-login" element={<StudentLoginPage />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<HomeRedirect />} />
          <Route
            path="manage-classes"
            element={
              <RequireRole allowed={["admin"]}>
                <ManageClassesPage />
              </RequireRole>
            }
          />
          <Route
            path="accounts"
            element={
              <RequireRole allowed={["admin"]}>
                <AccountsPage />
              </RequireRole>
            }
          />
          <Route
            path="settings"
            element={
              <RequireRole allowed={["admin"]}>
                <SettingsPage />
              </RequireRole>
            }
          />
          <Route path="students/:id" element={<StudentDetailPage />} />
          <Route
            path="c/:classId"
            element={
              <RequireRole allowed={["admin", "teacher"]}>
                <DashboardPage />
              </RequireRole>
            }
          />
          <Route
            path="c/:classId/sections"
            element={
              <RequireRole allowed={["admin", "teacher"]}>
                <SectionsPage />
              </RequireRole>
            }
          />
          <Route
            path="c/:classId/sections/:section"
            element={
              <RequireRole allowed={["admin", "teacher"]}>
                <SectionStudentsPage />
              </RequireRole>
            }
          />
          <Route
            path="c/:classId/uploads"
            element={
              <RequireRole allowed={["admin"]}>
                <UploadsPage />
              </RequireRole>
            }
          />
          {/* "Ask" moved to the floating button on the Dashboard — send old links there. */}
          <Route path="ask" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ClassesProvider>
  );
}
