import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import UsageReports from './UsageReports';
import * as service from '../services/usageReports';

let role = 'super_admin';
vi.mock('../contexts/useAuth', () => ({ useAuth: () => ({ user: { id: 3, role, school_id: 1 } }) }));
vi.mock('../services/usageReports');
const metrics = { requests: 2, success: 1, failed: 1, pending: 0, credits_charged: 10, reserved_credits: 0, provider_calls: 3, input_tokens: 100, output_tokens: 20, unknown_token_calls: 1, known_cost_usd: '0.01', estimated_cost_usd: null, unpriced_calls: 1 };
const report: service.UsageReport = { scope: 'platform', date_from: '2026-09-01', date_to: '2026-09-12', timezone: 'UTC', summary: { ...metrics, active_users: 1 }, daily: [{ ...metrics, day: '2026-09-12' }], roles: [{ ...metrics, role: 'teacher' }], users: [{ ...metrics, id: 1, name: 'Cô Lan', email: 'lan@test.local', role: 'teacher', is_active: true, plan: 'FREE', credit_balance: 40 }], total_users: 1, limit: 20, offset: 0 };
const detail: service.AccountUsage = { summary: metrics, user: { id: 1, name: 'Cô Lan', email: 'lan@test.local', role: 'teacher' }, subscription: { plan: 'FREE', status: 'active', credit_allowance: 50, credit_balance: 40, settings_version: 1, current_period_start: '2026-09-01', current_period_end: '2026-10-01' }, items: [{ id: 'request-1', operation: 'exam_generation', status: 'failed', credits_charged: 0, reserved_credits: 0, created_at: '2026-09-12T10:00:00Z', provider: 'openai', model: 'test', input_tokens: 100, output_tokens: 20, estimated_cost_usd: null, latency_ms: 1000 }], total: 1, limit: 20, offset: 0 };
beforeEach(() => {
  role = 'super_admin'; vi.resetAllMocks();
  vi.mocked(service.getUsageReport).mockResolvedValue(report);
  vi.mocked(service.getAccountUsage).mockResolvedValue(detail);
  vi.mocked(service.getPlans).mockResolvedValue([{ id: 'FREE', monthly_credits: 50 }, { id: 'BASIC', monthly_credits: 500 }, { id: 'PRO', monthly_credits: 1500 }]);
});

describe('Scoped usage reports', () => {
  it.each(['teacher', 'viewer', 'school_admin'])('shows %s reports without subscription mutation or platform cost', async currentRole => {
    role = currentRole;
    render(<UsageReports />);
    fireEvent.click(await screen.findByRole('button', { name: 'Xem lan@test.local' }));
    await screen.findByRole('heading', { name: 'Cô Lan' });
    expect(screen.queryByText('Tùy chỉnh subscription')).not.toBeInTheDocument();
    expect(screen.queryByText('Chi phí AI ước tính')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Vai trò') !== null).toBe(currentRole === 'school_admin');
    expect(screen.getByText('Thất bại')).toBeInTheDocument();
  });
  it('filters reports and edits a per-account allowance without replacing current balance', async () => {
    vi.mocked(service.updateSubscription).mockResolvedValue({ ...detail.subscription!, credit_allowance: 900 });
    render(<UsageReports />);
    await screen.findByText('Chi phí AI ước tính');
    expect(screen.getAllByText('Chưa đủ dữ liệu').length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText('Tìm tài khoản'), { target: { value: 'Lan' } });
    fireEvent.click(screen.getByRole('combobox', { name: 'Vai trò' }));
    fireEvent.click(screen.getByRole('option', { name: 'Teacher' }));
    fireEvent.click(screen.getByRole('button', { name: 'Xem báo cáo' }));
    await waitFor(() => expect(service.getUsageReport).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'Lan', role: 'teacher', offset: 0 }), expect.any(AbortSignal)));
    fireEvent.click(await screen.findByRole('button', { name: 'Xem lan@test.local' }));
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Gói sử dụng' })).toBeEnabled());
    fireEvent.click(screen.getByRole('combobox', { name: 'Gói sử dụng' }));
    fireEvent.click(screen.getByRole('option', { name: 'PRO' }));
    expect(screen.getByLabelText('Hạn mức credit mỗi tháng')).toHaveValue(1500);
    fireEvent.change(screen.getByLabelText('Hạn mức credit mỗi tháng'), { target: { value: '900' } });
    fireEvent.change(screen.getByLabelText('Lý do điều chỉnh'), { target: { value: 'Học kỳ mới' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu subscription' }));
    await waitFor(() => expect(service.updateSubscription).toHaveBeenCalledWith(1, { plan: 'PRO', status: 'active', credit_allowance: 900, credit_adjustment: 0, settings_version: 1, reason: 'Học kỳ mới' }, expect.any(AbortSignal)));
    expect(await screen.findByText('Đã lưu subscription và ghi nhận điều chỉnh.')).toBeInTheDocument();
    expect(service.getAccountUsage).toHaveBeenCalledTimes(2);
  });
  it('keeps a stale-edit error visible and allows reloading the account', async () => {
    vi.mocked(service.updateSubscription).mockRejectedValue({ response: { data: { detail: 'Gói đã thay đổi. Hãy tải lại tài khoản trước khi lưu.' } } });
    render(<UsageReports />);
    fireEvent.click(await screen.findByRole('button', { name: 'Xem lan@test.local' }));
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Gói sử dụng' })).toBeEnabled());
    fireEvent.change(screen.getByLabelText('Lý do điều chỉnh'), { target: { value: 'Cập nhật' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu subscription' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Gói đã thay đổi');
    fireEvent.click(screen.getByRole('button', { name: 'Tải lại tài khoản' }));
    await waitFor(() => expect(service.getAccountUsage).toHaveBeenCalledTimes(2));
  });
  it('recovers from load errors and renders empty reports', async () => {
    vi.mocked(service.getUsageReport).mockRejectedValueOnce(new Error('Kết nối gián đoạn'));
    render(<UsageReports />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Kết nối gián đoạn');
    vi.mocked(service.getUsageReport).mockResolvedValue({ ...report, users: [], daily: [], roles: [], total_users: 0 });
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByText('Chưa có lượt sử dụng trong khoảng đã chọn.')).toBeInTheDocument();
  });
});
