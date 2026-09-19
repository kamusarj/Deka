import { api } from "./api";

export interface Subscription {
  renewal_due?: boolean;
  plan: string;
  status: string;
  credit_allowance: number;
  credit_balance: number;
  current_period_start: string;
  current_period_end: string;
}

export interface CreditEntry {
  id: number;
  amount: number;
  type: string;
  created_at: string;
}

export interface UsageEntry {
  result_exam_id?: number | null;
  id: string;
  operation: string;
  status: string;
  credits_charged: number;
  reserved_credits: number;
  created_at: string;
}

export async function getSubscription(signal?: AbortSignal): Promise<Subscription | null> {
  return (await api.get("/api/me/subscription", { signal })).data;
}
export async function getCredits(signal?: AbortSignal): Promise<{ balance: number; transactions: CreditEntry[] }> {
  return (await api.get("/api/me/credits", { signal, params: { limit: 10 } })).data;
}
export async function getUsage(signal?: AbortSignal): Promise<{ items: UsageEntry[] }> {
  return (await api.get("/api/me/usage", { signal, params: { kind: "request", limit: 10 } })).data;
}
