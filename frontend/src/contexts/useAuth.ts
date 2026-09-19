import { useContext } from "react";

import { AuthContext } from "./authContextValue";
import type { AuthContextType } from "./authContextValue";

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
