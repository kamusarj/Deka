import { useContext } from "react";

import { ToastContext } from "./toastContextValue";
import type { ToastContextType } from "./toastContextValue";

export function useToast(): ToastContextType {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
