# Security

This repository contains a static public demo with sample exam data. It has
no backend, authentication service, API credentials, database or LLM connection.
Browser storage holds only local demo changes and is not shared across devices.

Vercel serves scripts, styles and fonts from the same site. The committed
`vercel.json` includes `connect-src 'none'` to block API connections from the demo.

## Dependency checks

Install the committed dependency lockfile and run:

```bash
npm ci --prefix frontend
npm run check
npm run audit
```

GitHub Actions runs these checks on pushes and pull requests. Dependency
updates must preserve the offline demo workflow and pass the production bundle
check.

## Reporting a vulnerability

Use the repository's private vulnerability reporting feature when available.
Include reproduction steps and the affected commit. Do not include credentials,
personal data or private documents in public issues or pull requests.
