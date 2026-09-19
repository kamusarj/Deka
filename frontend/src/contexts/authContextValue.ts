import { createContext } from "react";

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  school_id: number | null;
  avatar_url?: string | null;
  created_at: string | null;
  can_change_password: boolean;
  email_verified?: boolean;
  must_change_password?: boolean;
}

export interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  sessionError: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string, rememberLogin: boolean) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<{ message: string } | void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);
