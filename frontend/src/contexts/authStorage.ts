const TOKEN_KEY = "smart-exam-token";
export const AUTH_INVALIDATED_EVENT = "smart-exam-auth-invalidated";

type TokenStorage = "local" | "session";

let volatileToken: string | null = null;
let volatileScope: TokenStorage | null = null;

function browserStorage(scope: TokenStorage): Storage | null {
  try {
    return scope === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

function readStorage(scope: TokenStorage): string | null {
  try {
    return browserStorage(scope)?.getItem(TOKEN_KEY) ?? null;
  } catch {
    return null;
  }
}

function storedTokenLocation(): TokenStorage | null {
  if (readStorage("session")) return "session";
  if (readStorage("local")) return "local";
  return null;
}

function clearStoredTokens() {
  for (const scope of ["session", "local"] as const) {
    try {
      browserStorage(scope)?.removeItem(TOKEN_KEY);
    } catch {
      // Clearing the other store and in-memory fallback should still continue.
    }
  }
}

export function getToken(): string | null {
  if (volatileToken) return volatileToken;
  for (const scope of ["session", "local"] as const) {
    const token = readStorage(scope);
    if (token) return token;
  }
  return null;
}

export function setToken(token: string, rememberLogin?: boolean) {
  const target: TokenStorage = rememberLogin === undefined
    ? volatileScope ?? storedTokenLocation() ?? "local"
    : rememberLogin ? "local" : "session";

  clearStoredTokens();
  volatileToken = token;
  volatileScope = target;

  try {
    const storage = browserStorage(target);
    if (storage) {
      storage.setItem(TOKEN_KEY, token);
      volatileToken = null;
      volatileScope = null;
    }
  } catch {
    // Private/locked-down browsers can deny storage; retain the active tab in memory.
  }
}

export function removeToken() {
  clearStoredTokens();
  volatileToken = null;
  volatileScope = null;
  window.dispatchEvent(new Event(AUTH_INVALIDATED_EVENT));
}

export function isTokenStorageEvent(event: StorageEvent): boolean {
  return (event.key === TOKEN_KEY || event.key === null)
    && event.storageArea !== null
    && (event.storageArea === browserStorage("local") || event.storageArea === browserStorage("session"));
}
