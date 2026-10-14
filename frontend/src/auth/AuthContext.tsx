import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "../api/client";
import type { Role, TeacherAssignment } from "../types";

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  school_name: string | null;
  is_demo: boolean;
  role: Role;
  school_code?: string;
  assignments?: TeacherAssignment[];
  class_ids?: number[];
  student_id?: number;
  roll_no?: string;
}

interface AuthResponse {
  token: string;
  user: AuthUser;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName: string, schoolName?: string) => Promise<void>;
  loginDemo: () => Promise<void>;
  loginStudent: (schoolCode: string, rollNo: string, pin: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .get<AuthUser>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const applyAuth = useCallback((res: AuthResponse) => {
    setToken(res.token);
    setUser(res.user);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      applyAuth(await api.post<AuthResponse>("/auth/login", { email, password }));
    },
    [applyAuth],
  );

  const signup = useCallback(
    async (email: string, password: string, displayName: string, schoolName?: string) => {
      applyAuth(
        await api.post<AuthResponse>("/auth/signup", {
          email,
          password,
          display_name: displayName,
          school_name: schoolName || undefined,
        }),
      );
    },
    [applyAuth],
  );

  const loginDemo = useCallback(async () => {
    applyAuth(await api.post<AuthResponse>("/auth/demo-login"));
  }, [applyAuth]);

  const loginStudent = useCallback(
    async (schoolCode: string, rollNo: string, pin: string) => {
      applyAuth(await api.post<AuthResponse>("/auth/student-login", { school_code: schoolCode, roll_no: rollNo, pin }));
    },
    [applyAuth],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, loginDemo, loginStudent, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
