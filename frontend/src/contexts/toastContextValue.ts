import { createContext } from "react";

export type ToastTone = "success" | "error" | "info";

export interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
}

export interface ToastContextType {
  toasts: Toast[];
  /** Shows a toast and returns its id so callers can dismiss it early. */
  notify: (message: string, tone?: ToastTone) => number;
  dismiss: (id: number) => void;
}

export const ToastContext = createContext<ToastContextType | null>(null);
