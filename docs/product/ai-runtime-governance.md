# AI Runtime Governance

## Provider Policy

OpenAI is the primary generation provider. Legacy API clients may use the fixed
OpenAI, Gemini, DeepSeek fallback chain defined by ADR-0021.

Interactive full-exam authoring is primary-only for generation. The browser
sends `allow_provider_fallback=false`; generation calls use OpenAI only. A
transient OpenAI rate limit or transport timeout is retried with bounded
backoff. If OpenAI remains unavailable, the request fails closed and no backup
generation provider is called.

Once real OpenAI question, answer, and rubric output exists, an exhausted
post-generation quality or mandatory-review gate preserves the latest payload
as a non-publishable draft instead of repeating the entire paid run. This does
not weaken the gate: draft export, variants, and question-bank reuse remain
blocked. No automatic paid call occurs after the draft result is returned.

Primary-only full exams use the official OpenAI `gpt-5.6-luna` Responses API by
default with low reasoning effort and low response verbosity. Luna is selected
for price/performance on cost-sensitive, high-volume work, not as a provider
fallback. Deterministic quality gates remain unchanged and repair retries remain
scoped to rejected question IDs.

Semantic verification is deliberately separate from generation. The default
`dual` mode gives every interactive question one combined solve-and-quality
review from DeepSeek `deepseek-v4-pro` and one from Google
`gemini-3.7-flash`. Both are mandatory peers and run concurrently; neither is
a fallback for the other. A deployment may explicitly select temporary
`deepseek_only` mode when Gemini capacity is unavailable. That mode never calls
Gemini, still fails closed when DeepSeek is unavailable, and does not claim
two-model consensus. Deterministic quality gates remain unchanged in both
modes.

The per-operation timeout is 180 seconds in primary-only mode so bounded
backoff can finish. The legacy three-provider chain retains its 90-second
ceiling.

The policy is request-scoped. It does not mutate global provider order, expose
keys, or grant provider controls to teaching roles.

Structured question generation uses batches of two questions by default so a
single request does not consume the primary provider's entire minute-level token
budget. Quality repair still targets only rejected question IDs.

Draft repair is also request-scoped primary-only. The client must explicitly
send `allow_provider_fallback=false`; only selected failed question ids are
regenerated and sent to the mandatory reviewer set. Omitting the flag on a
draft is rejected before provider work begins.

## Observability

Provider telemetry records provider, model, operation, outcome, latency, and
token usage without prompts, response bodies, credentials, or exception text.
Primary retry logs include only the operation, retry number, and delay.

## Development Gateway and Accounts

ADR-0047 adds configurable routing overrides while preserving the defaults above.
SDK transports now run behind normalized Gateway adapters, including mandatory
reviewers. Authenticated full-exam HTTP/SSE, regeneration, question and answer
flows reserve a configurable integer operation charge before work and refund
unsuccessful/unverified output. Mock output without provider calls is uncharged.
Usage retains each actual provider attempt and one credit-bearing request summary.

Self-account APIs show plan, balance, ledger and the user's own provider usage.
Global AI settings remain restricted. FREE/BASIC/PRO values are development
allowances only; a local CLI assigns plans and adjusts credits without payment.
Details, migration instructions and recovery: [AI architecture](../ai-architecture.md).

## Production audit implementation

All registered AI operations have explicit credit policy, including free RAG/index/OCR/upload and configuration tests. Missing policy fails closed before enrollment. Production model settings are environment-owned and the admin UI displays the effective generation/review/embedding settings. Only allowed providers may run through an accounting context. Operation admission and provider/parser capacity are separately bounded so cancellation cannot release a still-running SDK slot.

Historical platform cost includes soft-deleted accounts; role groupings mean current role, request dates are start dates, and provider costs use attempt record dates in UTC. See [ADR 0049](../decisions/0049-production-audit-boundaries.md) for balance, response and recovery decisions and [data handling](../ai-data-handling.md) for account-specific provider gates.
