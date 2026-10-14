import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { SchoolClass } from "../types";

interface ClassesContextValue {
  classes: SchoolClass[];
  loading: boolean;
  reload: () => void;
}

const ClassesContext = createContext<ClassesContextValue | null>(null);

/** The list of classes this login can see — every class for an admin, only
 * the assigned ones for a teacher, none for a student (who never browses
 * by class). Fetched once per login so the class switcher and the
 * post-login landing logic don't each re-fetch it. */
export function ClassesProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    if (!user || (user.role !== "admin" && user.role !== "teacher")) {
      setClasses([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .get<SchoolClass[]>("/school-classes")
      .then(setClasses)
      .catch(() => setClasses([]))
      .finally(() => setLoading(false));
  }, [user]);

  useEffect(() => {
    reload();
  }, [reload]);

  return <ClassesContext.Provider value={{ classes, loading, reload }}>{children}</ClassesContext.Provider>;
}

export function useClasses(): ClassesContextValue {
  const ctx = useContext(ClassesContext);
  if (!ctx) throw new Error("useClasses must be used within ClassesProvider");
  return ctx;
}
