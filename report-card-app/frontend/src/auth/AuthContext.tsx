import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "../api/client";
import type { AuthUser, WhatsappChannelMode, WhatsappLanguage } from "../types";

interface AuthResponse {
  token: string;
  user: AuthUser;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName: string, schoolName: string) => Promise<void>;
  setSchoolName: (schoolName: string) => Promise<void>;
  setSchoolAddress: (schoolAddress: string) => Promise<void>;
  setSchoolPhoto: (file: File) => Promise<void>;
  removeSchoolPhoto: () => Promise<void>;
  setWhatsappSettings: (settings: {
    whatsapp_language: WhatsappLanguage;
    whatsapp_channel_mode: WhatsappChannelMode;
    default_country_code: string;
  }) => Promise<void>;
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
    async (email: string, password: string, displayName: string, schoolName: string) => {
      applyAuth(await api.post<AuthResponse>("/auth/signup", { email, password, display_name: displayName, school_name: schoolName }));
    },
    [applyAuth],
  );

  const setSchoolName = useCallback(async (schoolName: string) => {
    setUser(await api.put<AuthUser>("/auth/school-name", { school_name: schoolName }));
  }, []);

  const setSchoolAddress = useCallback(async (schoolAddress: string) => {
    setUser(await api.put<AuthUser>("/auth/school-address", { school_address: schoolAddress }));
  }, []);

  const setSchoolPhoto = useCallback(async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    setUser(await api.upload<AuthUser>("/auth/school-photo", form));
  }, []);

  const removeSchoolPhoto = useCallback(async () => {
    setUser(await api.del<AuthUser>("/auth/school-photo"));
  }, []);

  const setWhatsappSettings = useCallback(
    async (settings: { whatsapp_language: WhatsappLanguage; whatsapp_channel_mode: WhatsappChannelMode; default_country_code: string }) => {
      setUser(await api.put<AuthUser>("/auth/whatsapp-settings", settings));
    },
    [],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        signup,
        setSchoolName,
        setSchoolAddress,
        setSchoolPhoto,
        removeSchoolPhoto,
        setWhatsappSettings,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
