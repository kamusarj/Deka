import { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import type { ReactNode } from "react";
import { authLogin, authRegister, authGetMe, authLogout } from "../services/api";
import { AUTH_INVALIDATED_EVENT, getToken, isTokenStorageEvent, removeToken, setToken } from "./authStorage";
import { AuthContext } from "./authContextValue";
import type { AuthUser } from "./authContextValue";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const verification = useRef(0);
  const authOperation = useRef(0);
  const identityToken = useRef<string | null>(null);

  const refreshUser = useCallback(async () => {
    const request = ++verification.current;
    const token = getToken();
    if (identityToken.current !== token) setUser(null);
    identityToken.current = token;
    setSessionError(null);
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const me = await authGetMe();
      if (request !== verification.current || getToken() !== token) return;
      setUser(me);
    } catch (error) {
      if (request !== verification.current || getToken() !== token) return;
      setUser(null);
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        removeToken();
      } else {
        setSessionError("Chưa thể kết nối để khôi phục đăng nhập. Ứng dụng sẽ tự thử lại khi có kết nối.");
      }
    } finally {
      if (request === verification.current) setIsLoading(false);
    }
  }, []);

  /* Load user on mount */
  useEffect(() => {
    refreshUser();
    return () => {
      verification.current += 1;
      authOperation.current += 1;
    };
  }, [refreshUser]);

  useEffect(() => {
    const invalidate = () => {
      verification.current += 1;
      identityToken.current = null;
      setUser(null);
      setSessionError(null);
      setIsLoading(false);
    };
    window.addEventListener(AUTH_INVALIDATED_EVENT, invalidate);
    return () => window.removeEventListener(AUTH_INVALIDATED_EVENT, invalidate);
  }, []);

  useEffect(() => {
    const syncSession = (event: StorageEvent) => {
      if (!isTokenStorageEvent(event) || getToken() === identityToken.current) return;
      authOperation.current += 1;
      void refreshUser();
    };
    window.addEventListener("storage", syncSession);
    return () => window.removeEventListener("storage", syncSession);
  }, [refreshUser]);

  useEffect(() => {
    if (!sessionError) return;
    const retry = () => { void refreshUser(); };
    window.addEventListener("online", retry);
    const timer = window.setTimeout(retry, 5000);
    return () => {
      window.removeEventListener("online", retry);
      window.clearTimeout(timer);
    };
  }, [sessionError, refreshUser]);

  const login = useCallback(async (email: string, password: string, rememberLogin: boolean) => {
    const operation = ++authOperation.current;
    verification.current += 1;
    setSessionError(null);
    setIsLoading(true);
    try {
      const res = await authLogin(email, password);
      if (operation !== authOperation.current) {
        throw new DOMException("Yêu cầu đăng nhập đã được thay thế.", "AbortError");
      }
      verification.current += 1;
      setToken(res.access_token, rememberLogin);
      identityToken.current = res.access_token;
      setUser(res.user);
      setSessionError(null);
    } finally {
      if (operation === authOperation.current) setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const res = await authRegister(email, password, name);
    return res;
  }, []);

  const logout = useCallback(async () => {
    authOperation.current += 1;
    verification.current += 1;
    // The transport captures the bearer before local state is discarded.
    const revocation = authLogout();
    removeToken();
    try {
      await revocation;
    } catch {
      // The remote token may remain valid until expiry, but local logout must
      // still complete when the API is unreachable.
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        sessionError,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
