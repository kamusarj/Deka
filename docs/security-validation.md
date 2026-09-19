# Security validation: US-184

Repository implementation and synthetic validation, 2026-09-14. This is not a production pentest or a claim that all audit gates pass. Exact outputs and remaining gates are in [the report](validation/production-audit/report.md).

The [generated inventory](validation/production-audit/api-inventory.md) lists registered HTTP routes, dependency guards and explicit AI operation policies. It supports review of browser → API → SQL/uploads/RAG → provider → response boundaries. Assets at risk are teacher documents/questions, account tokens, super admin authority, credit ledger and provider credentials. Client IDs, claims, rich content, file metadata and retrieved text are untrusted.

| Threat | Implemented boundary | Executed evidence |
| --- | --- | --- |
| Cross-user/school reads and forged roles | Current DB actor and resource predicates; unknown roles fail closed; current access checked on result replay | Existing authorization/document-sharing suites; direct API negative report tests |
| Hidden UI fields leak in JSON/SSE | Explicit accounting/report field lists; recursive content diagnostic removal for non-super-admin responses | Nested teacher/viewer/school-admin JSON and SSE sentinel tests |
| Implicit free AI bypass | Explicit registry, outer operation context, accounted SDK/OCR/embedding calls, pause checks | Unknown-operation/no-enrollment and free-operation usage tests |
| Concurrent or replayed credit spend | Account transaction, unique idempotency key/fingerprint, conditional settlement and result pointer | Dedicated PostgreSQL concurrent reserve/refund/recovery and key collision tests |
| Worker publishes after recovery/revocation | Lease owner/expiry fencing and current actor/source checks at transport and short persistence transaction | Atomic result/ledger, rollback, late worker, role/token/pause and shared-source revocation regressions |
| Admin API bypass | Password + TOTP/recovery proof, short-lived elevated token enforced on deployed admin API access | RFC TOTP vector, counter replay, one-use recovery, direct API MFA bypass rejection |
| Email transport outage locks registration UX | Unverified account remains; explicit delivery-pending response and resend UI | SMTP failure fixture plus existing verification/reset tests |
| Upload/resource abuse | Body/concurrency/owner quotas; signature and ZIP entry/ratio/path limits; bounded parser and SDK slots | ZIP bomb/path tests, rejection/no-call tests, cancellation capacity test |
| Deletion/restore resurrects source | Transactional tombstone, exact cleanup, retrieval deny rule, current journal import before reopening | Cleanup retry/idempotency and real-image PostgreSQL/uploads restore rehearsal |
| Internal services exposed | Standalone Compose, proxy-only ports, trusted proxy IP, nonroot backend | Rendered Compose inspector, Caddy validation, image smoke and production-mode restore readiness |
| Secrets in responses/logs | Sanitized provider exceptions; request IDs; no-store API responses | Sentinel error tests; secret scan triage below |

Accounting response fields are defined in `backend/app/services/ai/projections.py`: all authenticated users can receive their authorized request IDs, operation/status, credits, timestamps and result pointer/version; only super admins receive provider/model/upstream ID, raw tokens, latency and monetary cost diagnostics. Subscription responses can be null. Metrics follow the same rule; filters never widen tenant access. Content routes use a separate recursive diagnostic filter because their educational payload shapes differ. A future new diagnostic field must extend that filter and its negative tests.

JWT decoding is restricted to configured HS256 in deployed settings and current DB token versions. Role claims do not grant authority. The existing browser bearer-token storage and OAuth session design remain; no new refresh-token mechanism was added. OAuth cookies are secure in deployment with SameSite Lax. Actual identity-provider callbacks, browser CSP/CSRF behavior and external proxy trust still require staging checks. CSP is report-only; anti-framing and nosniff headers are configured.

## Scan triage and current boundaries

The current default Python environment reports no known vulnerabilities. LangChain and Chroma are absent by default; vector-cache remains an optional extra requiring separate acceptance. PyJWT replaces python-jose for the fixed-HS256 contract.

Every default runtime image is scanned. Frontend/proxy/PostgreSQL now have zero High/Critical entries; backend has 71 OS entries conditionally assessed under exact version, expiry and runtime facts in `deploy/security-review.json`. Raw findings remain in the [report](validation/production-audit/report.md). The gate fails for new/unreviewed versions, expired reviews or changed conditions; CI no longer ignores every unfixed finding.

Runtime-layer secret scanning covers all regular files from every saved image layer, including files deleted later, and image configuration. The only exclusion is the exact public CPython release-signing fingerprint; all four candidates report no remaining findings. Intermediate build stages are outside that scan. Prior Git history and selected-source results remain documented, including one educational answer-key phrase false positive.

Independent MFA keys and transactional rotation, strict Office XML/entity denial, sanitized OCR child environments, bounded orphan inventory and signed current-authority restore were added. Restore revokes sessions and sharing instead of resurrecting post-backup grants. Operator and current evidence contracts are in [ADR 0050](decisions/0050-release-recovery-and-verification.md).

External domain/TLS/OAuth/SMTP, actual provider accounts/retention/prices, representative load/restore, independent teacher acceptance, approved retention and off-host alerting remain real deployment gates. Local synthetic browser/SMTP evidence does not prove delivery through an external mail provider or certification of an unknown public host.
