import { getToken } from "../contexts/authStorage";

const storageKey = "smart-exam-pending-generation";
let memory: { fingerprint: string; key: string; requestId?: string } | null = null;

// Store only a digest and opaque key. The server independently checks ownership
// and payload identity. Keep uncertain requests across reloads; never auto-retry.
export async function generationRequest(payload: unknown): Promise<string> {
  const token = getToken() ?? "anonymous";
  let account = token;
  try { account = String(JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).sub); } catch { /* Test or absent JWT. */ }
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify([account, payload])));
  const fingerprint = Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, "0")).join("");
  try {
    const stored = sessionStorage.getItem(storageKey);
    if (stored) memory = JSON.parse(stored);
  } catch { /* Storage may be unavailable. */ }
  if (memory?.fingerprint !== fingerprint) memory = { fingerprint, key: crypto.randomUUID() };
  try { sessionStorage.setItem(storageKey, JSON.stringify(memory)); } catch { /* Retain in this tab. */ }
  return memory.key;
}

export function completeGenerationRequest(key: string) {
  if (memory?.key !== key) return;
  memory = null;
  try { sessionStorage.removeItem(storageKey); } catch { /* Storage may be unavailable. */ }
}

export function rememberGenerationRequest(key: string, requestId: string) {
  if (memory?.key !== key) return;
  memory.requestId = requestId;
  try { sessionStorage.setItem(storageKey, JSON.stringify(memory)); } catch { /* Retain in this tab. */ }
}
