import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, vi } from 'vitest';
import SubscriptionPlans from './SubscriptionPlans';
import { getPlans } from '../services/usageReports';
let signedIn = false;
vi.mock('../contexts/useAuth', () => ({ useAuth: () => ({ isAuthenticated: signedIn }) }));
vi.mock('../services/usageReports', () => ({ getPlans: vi.fn() }));
beforeEach(() => { signedIn = false; vi.resetAllMocks(); vi.mocked(getPlans).mockResolvedValue([{ id: 'FREE', monthly_credits: 51 }, { id: 'BASIC', monthly_credits: 501 }, { id: 'PRO', monthly_credits: 1501 }]); });
it('displays three server-configured tiers and honest registration actions', async () => {
  render(<MemoryRouter><SubscriptionPlans /></MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'FREE' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'BASIC' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'PRO' })).toBeInTheDocument();
  expect(screen.getByText('51')).toBeInTheDocument();
  expect(screen.getByText('501')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Bắt đầu với Free' })).toHaveAttribute('href', '/register');
  expect(screen.getByText(/Chưa áp dụng thanh toán/)).toBeInTheDocument();
});
it('offers retry and routes signed-in users to their existing account', async () => {
  signedIn = true; vi.mocked(getPlans).mockRejectedValueOnce(new Error('offline'));
  render(<MemoryRouter><SubscriptionPlans /></MemoryRouter>);
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
  expect((await screen.findAllByRole('link', { name: 'Xem gói của tôi' }))[0]).toHaveAttribute('href', '/account');
});
