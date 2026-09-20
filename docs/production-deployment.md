# Production deployment

The release candidate uses `docker-compose.production.yml` **as a standalone file**. Do not merge it with the development Compose file. No public deployment has been performed by US-184. See [validation](validation/production-audit/report.md) before rollout.

Copy `deploy/production.env.example` and `deploy/backend.staging.env.example` to restricted, ignored environment files. Use a distinct project, database password, JWT secret, independent MFA encryption key, backend provider accounts and uploads volume for each environment. Set the real domain, certificate email, SMTP sender and OAuth callback. Use distinct `INTERNAL_SUBNET`/`PROXY_INTERNAL_IP` pairs for concurrently running environments. Provider keys belong only in the backend file. Registration is disabled in the sample until SMTP is ready. Never put a secret in a `VITE_*` variable.

Build the patched proxy with `docker build -f deploy/Dockerfile.proxy -t deka-proxy:ready-184 deploy` and PostgreSQL with `docker build -f deploy/Dockerfile.postgres -t deka-postgres:ready-184 deploy`. Build backend with `docker build -t deka-backend:RELEASE backend` and frontend with `docker build --build-arg VITE_ENABLE_DEMO_LOGIN=false -t deka-frontend:RELEASE frontend`. Docker uses `uv sync --frozen` and `npm ci`; Node is the same version as CI. Supply the tested image tags/digests through the deployment environment. Record a manifest with `python3 scripts/operations/release-manifest.py --help`; the script records dirty state as well as image IDs. A dirty checkout is not a reproducible release commit.

Render and inspect configuration without printing secrets:

```bash
docker compose --env-file deploy/staging.env -f docker-compose.production.yml config --format json | python3 scripts/operations/check-compose.py
```

Only Caddy publishes host ports. PostgreSQL, Chroma, frontend and backend remain on the internal network; backend has a separate outbound network for providers and SMTP. Caddy handles certificates and HTTP redirects. Backend trusts only the configured proxy IP for forwarded headers. Check the actual client IP, scheme, external ports and OAuth flow from outside the host. HSTS remains off until those checks pass.

Before an upgrade, stop writes and create a verified consistent backup using the runbook. Start PostgreSQL, then run the explicit migration job; the backend depends on its successful completion:

```bash
docker compose --env-file deploy/staging.env -f docker-compose.production.yml up -d --wait postgres
docker compose --env-file deploy/staging.env -f docker-compose.production.yml run --rm migrate
docker compose --env-file deploy/staging.env -f docker-compose.production.yml up -d backend frontend proxy
```

Alembic head is `0007_admin_mfa`. Migrations 0000/0004 adopt known legacy tables/compatibility columns; 0005 adds request lifecycle, 0006 cleanup tombstones and 0007 MFA. The migration command upgrades and validates required tables/columns, type affinities, nullability, primary keys, uniqueness and named checks. Production process startup never repairs a schema. A legacy revision marker with missing columns fails readiness; a production-sized restore still needs a representative dataset. Never manually stamp an unverified database.

Backend runs as UID 10001. Check uploads volume ownership on staging before opening uploads; do not make it world-writable. `/health` is liveness; `/ready` checks DB, schema and configuration without paid AI calls. The image has one Uvicorn worker. Increasing workers/replicas invalidates in-memory rate/concurrency bounds and requires shared admission first.

On failed rollout, keep admission closed and inspect readiness/migration logs. Return to the previous image only after verifying its code supports the additive schema and API contracts. Do not run an automatic destructive downgrade. If restoring is necessary, stop all writers, use a fresh target and reconcile the current deletion journal before access; record the actual data-loss window. The runbook contains the commands and required checks.


## Candidate preparation and release gate

`python3 scripts/operations/configure-release.py --directory /restricted/NEW_DIRECTORY --domain YOUR_DOMAIN --email CERTIFICATE_CONTACT` creates private environment files with independent random keys and registration disabled. It refuses an existing destination. Fill provider credentials, SMTP and actual dated model prices in `backend.env`; do not paste secrets into chat or commit those files. Select a subnet that does not overlap existing environments.

Run the gate from the repository root:

```bash
python3 scripts/operations/preflight.py --env-file /restricted/NEW_DIRECTORY/deployment.env \
  --manifest docs/validation/production-audit/release-manifest.json \
  --security-dir docs/validation/production-audit/release-security \
  --acceptance /restricted/NEW_DIRECTORY/acceptance.json
```

The gate is read-only and returns nonzero for placeholders, missing/mismatched images, dirty release source, failed/stale security evidence or missing operator acceptance. Fill acceptance only from actual checks with timestamp, operator and evidence; `--synthetic` is solely for disposable rehearsals. The sample provider requirements reflect the current generation/reviewer/embedding defaults. Changing the enabled provider policy requires matching outbound and pricing validation.

The backend root filesystem is read-only; uploads are the persistent writable volume and temporary parser data lives in bounded tmpfs. Chroma is disabled by default and absent from the default backend image; build/install the `vector-cache` extra and obtain separate security/cleanup proof before enabling it. The frontend starts after backend readiness and exposes its own health check, so the proxy waits for usable static assets.

Provision the first super admin with `python -m app.services.bootstrap_admin --email OPERATOR_EMAIL` inside the configured image, using an interactive password prompt or a restricted runtime environment. Inspect dry-run, then add `--apply`. Verify ownership of that email out of band. It refuses subsequent bootstrap attempts; enroll MFA before administrative use.
