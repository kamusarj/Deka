import { api } from './api';
import type { Subscription, UsageEntry } from './aiAccount';

export interface Plan { id: string; monthly_credits: number }
export interface Metrics {
  requests: number; success: number; failed: number; pending: number;
  credits_charged: number; reserved_credits: number; provider_calls: number;
  input_tokens?: number; output_tokens?: number; unknown_token_calls?: number;
  known_cost_usd?: string; estimated_cost_usd?: string | null; unpriced_calls?: number;
}
export interface ReportUser extends Metrics {
  id: number; name: string; email: string; role: string; is_active: boolean;
  plan: string | null; credit_balance: number | null;
}
export interface UsageReport {
  scope: 'self' | 'school' | 'platform'; date_from: string; date_to: string; timezone: string;
  summary: Metrics & { active_users: number };
  daily: (Metrics & { day: string })[]; roles: (Metrics & { role: string })[];
  users: ReportUser[]; total_users: number; limit: number; offset: number;
}
export interface ReportFilters { date_from: string; date_to: string; role?: string; search?: string; user_id?: number; offset?: number }
export interface AccountUsage {
  summary: Metrics;
  user: Pick<ReportUser, 'id' | 'name' | 'email' | 'role'>;
  subscription: (Subscription & { settings_version: number }) | null;
  items: (UsageEntry & { provider?: string | null; model?: string | null; input_tokens?: number | null;
    output_tokens?: number | null; estimated_cost_usd?: string | number | null; latency_ms?: number })[];
  total: number; limit: number; offset: number;
}
export interface SubscriptionEdit {
  plan: string; status: string; credit_allowance: number; credit_adjustment: number;
  settings_version: number; reason: string;
}
export async function getPlans(signal?: AbortSignal): Promise<Plan[]> {
  return (await api.get('/api/subscription-plans', { signal })).data.plans;
}
export async function getUsageReport(params: ReportFilters, signal?: AbortSignal): Promise<UsageReport> {
  return (await api.get('/api/usage/report', { params, signal })).data;
}
export async function getAccountUsage(id: number, params: ReportFilters, signal?: AbortSignal): Promise<AccountUsage> {
  return (await api.get(`/api/usage/users/${id}`, { params, signal })).data;
}
export async function updateSubscription(id: number, payload: SubscriptionEdit, signal?: AbortSignal): Promise<Subscription> {
  return (await api.patch(`/api/admin/users/${id}/subscription`, payload, { signal })).data;
}
