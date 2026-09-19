# AI data handling

This is an inventory of implemented paths and conditions to verify before real-user pilot, dated 2026-09-14. Synthetic provider spies prove code boundaries; they do not prove the retention settings or billing tier of a real provider account. Credentials, password hashes, JWTs, recovery codes and billing ledgers are not legitimate prompt inputs.

| Destination/path | Content sent | Configuration and boundary | Account-specific evidence still required |
| --- | --- | --- | --- |
| OpenAI generation/edit/answer/matrix | Teacher instructions, requested subject/grade, selected retrieved document excerpts, candidate questions/answers and repair context as required by the operation | Interactive generation uses `OPENAI_PRIMARY_ONLY_MODEL`; other tiers follow the registry. SDK calls explicitly set `store=False`; allowed-provider check and accounting precede transport | Project data-control settings, region, retention agreement, enabled models and price schedule |
| Gemini reviewer/fallback | Candidate question/answer material and verification context; fallback may receive the task prompt | Dual review includes Gemini; primary-only generation does not disable reviewer or embedding calls | Paid/unpaid service status and applicable terms; model availability and quotas |
| Gemini embedding | Query strings and selected text chunks, including authorized document/bank content | `RAG_EMBEDDING_MODEL`; standalone query/index and nested calls are accounted even when user credit price is zero | Embedding retention/region and actual project account settings |
| Gemini OCR | Bounded PNG/JPEG image/page and transcription instruction | Only when configured OCR provider selects Gemini; native parsing/local Tesseract do not send image data upstream | Whether images may contain personal data and permitted account/retention setting |
| DeepSeek reviewer/fallback | Candidate questions, answers and required context; configured fallback task content | Reviewer mode `dual` or `deepseek_only`; explicit provider allowlist still applies | Applicable API contract, retention/deletion, region and training use must be confirmed for this account |
| Local PostgreSQL/uploads | Accounts, exams, source files, ledger, request/result pointer and deletion evidence | Access-controlled authoritative storage; backup and deletion runbook applies | Chosen retention periods and off-host backup policy |
| Optional Chroma | Chunk text/vectors and owner/chunk identifiers | Internal-only cache; exact owner/document cleanup plus retrieval tombstones; default staging sample disables it | Security triage and cleanup/restore rehearsal with the actual Chroma version |

Provider failover and a second reviewer can send related content to more than one provider. A failed primary call may still have been processed upstream. Provider allowlisting restricts the destination adapters; the operator must also review outbound base URLs and environment overrides. Do not enable LangSmith/LangChain tracing or other telemetry exporters with user content without a separate data-flow review.

OpenAI's data-control documentation distinguishes response storage from abuse-monitoring retention and account-level controls; `store=False` alone does not establish zero retention. Confirm the actual project settings against [OpenAI data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint).

Google's terms distinguish paid and unpaid services in their treatment of prompts and responses. The existence of an API key is not proof of paid-service data handling. Confirm the project billing/account status against [Gemini API terms](https://ai.google.dev/gemini-api/terms).

DeepSeek's published [privacy policy](https://platform.deepseek.com/downloads/DeepSeek%20Privacy%20Policy.pdf) is a source to review with the specific API agreement; this implementation has not established an account-specific retention guarantee. Do not label it zero-retention.

The Documents page now shows a notice that selected text/questions and, for cloud OCR, images may be processed by the configured external providers. Document consent/notice requirements for the school's actual use and jurisdiction. Account-specific contractual and school acceptance remain pending; no real teacher material was used in automated validation.

`AI_MODEL_PRICING` maps `provider:model` to decimal USD per million `input`, `output`, and optional `cached_input` tokens. Each configured price needs its official source, model ID, effective date, currency and any batch/cache assumptions recorded alongside the release. Prices were not fabricated for unverified model/account settings. Unknown counts/prices remain null and raise operational attention; stored cost snapshots are not retroactively repriced by a settings change.
