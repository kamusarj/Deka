#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm run test:run -- src/pages/Account.test.tsx src/components/AccountSubscription.test.tsx
npm run lint
npm run build
