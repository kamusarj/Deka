#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && .venv/bin/python -m pytest tests/test_usage_reports.py tests/test_ai_account_migration.py tests/test_ai_credits.py -q)
(cd frontend && npm run test:run -- src/pages/UsageReports.test.tsx src/components/SubscriptionPlans.test.tsx && npm run lint && npm run build)
