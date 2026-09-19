# Integrated KHTN authoring capabilities

Implemented in US-168, 2026-09-09. Scope remains KHTN grades 6–9 with the existing
curriculum, matrix, descriptor, formula registry, quarter-point scoring and
school/owner permissions. [Quizify's project description](https://demo.edufun.ai/p/team-510-c2-team-067)
is a capability benchmark, not evidence of measured parity or accuracy.

## One generation flow

Teacher configuration → matrix/specification → optional authorized documents →
native/OCR processing → structured chunks → BM25 + vector candidates → RRF →
local reranking → deduplication/budget → question/answer/rubric generation →
existing scientific/numeric/source/independent review → duplicate findings →
teacher review/edit/regenerate → optional bank save/reuse → deterministic variants
→ separate Word/PDF documents.

Documents are processed at upload. Indexes are built lazily when a selected
source is first queried. No selected documents means generation keeps its
controlled curriculum source path. Mandatory calculations retain the authoritative
local formula capability even when other questions use uploaded sources.

## Retrieval and duplicates

`BaseRetriever`, `BM25Retriever` and `EmbeddingRetriever` remain the shared
infrastructure for documents, bank search and duplicate candidates. New
`HybridRetriever` combines rankings with `sum(1 / (RAG_RRF_K + rank))`, using
one-based ranks and one vote per channel. Retrieval traces retain lexical/vector
scores and ranks, RRF/rerank score, source, page and section. Local reranking uses
query coverage and existing vector similarity. `Reranker` supports dependency
injection; exceptions/invalid candidate sets fall back to the working local
implementation. No external reranker adapter or key is currently required.

Context selection deduplicates normalized text and admits whole chunks under a
conservative UTF-8-byte/3 budget. This is a planning estimate, not the provider's
exact tokenizer. A whole table/formula exceeding the budget is omitted rather
than cut into an invalid source quotation. Specifications retain the primary
exact quotation plus the selected context list. Vector cache keys include model,
chunk id and content hash; edits cannot reuse stale vectors. The default bounded
memory cache holds vectors, with optional existing Chroma persistence. Reads
resolve document/bank access before querying cached data.

Duplicate detection checks all readable bank rows, including other KHTN grades,
and earlier questions in the same exam. Exact normalized task comparisons run
before fuzzy lexical candidates and vector neighbors. Comparisons use stem,
options, answer/expected answer, statements, rich data, reasoning and cognitive
level; shared knowledge targets alone do not establish duplication. Different
numeric data are distinct tasks. Image bytes contribute a digest, not base64
text sent for embedding. Semantic scores are similarities, not probabilities.
No per-bank-row LLM judge is used. Fuzzy/semantic findings warn, identical tasks
are rejected on direct bank/exam-save writes; conflicting answer keys warn.
Generation/edit findings remain reviewable, and bank-save warnings reach the UI.
Without embeddings the exact/fuzzy/BM25 paths remain usable, with semantic
availability recorded internally.

## Teacher editing and bank reuse

QuestionCard offers Edit → Save/Cancel for MCQ, four-statement true/false, short
answer and essay with rubric levels. Existing review/select/regenerate controls
remain. Changes stay local until Save; Cancel discards the local edit; failed
Save retains it. Save updates the active exam response without reloading the
configuration or losing the generation session. Unsaved question edits are not
browser-autosaved; the existing configuration autosave is a separate feature.

`PATCH /api/exams/{id}/questions/{question_id}` requires write ownership, AI rate
limits and the version captured when editing began. A version change returns
409 rather than overwriting another edit. Type, score, grade/domain, target,
intent, reasoning, source references and original generation metadata are kept.
Teacher revision/time metadata is appended. The same deterministic quality gate
and independent reviewers validate the revision. Numeric edits obtain a typed
calculation specification and run the existing grade-specific safe solver.
Unverified changes are saved as drafts, blocking export/bank save until repaired.

Semantic bank search is available in the bank page and editor. Choosing a bank
item loads a read-only edit template; nothing is written until Save. Backend
checks access, grade, type, level and essay score/part shape. Adaptation preserves
the current matrix and marks `reused_from_bank_id`; final Save rechecks access and
increments usage within the exam transaction. Exact-repeat bank saves offer the
existing item instead of creating another copy. Legacy incomplete bank items
remain readable; an item missing required edit data cannot be used as a template.

## Rich content and exports

The legacy `content` field remains. Optional `rich_content` blocks supplement it:
`text`, `latex` (inline/block), rectangular `table`, embedded PNG/JPEG `image`, and
`diagram` with bounded `drawing` objects (line, circle, rectangle, text, polyline).
No raw HTML, SVG input, executable plotting code or arbitrary remote image URL.
Images are limited to approximately 1.5 MB/16 million pixels; blocks to 32 per
question and 4 MB combined. Data and captions survive edits, bank saves, public
community snapshots, variants and exports. Public snapshots still omit private
source and generation metadata.

KaTeX renders `$...$`, `$$...$$`, `\(...\)` and `\[...\]` in cards, preview,
review and bank content, with trust disabled. The editor adds formulas, tables,
local images and drawing primitives. Declarative diagrams render as safe SVG in
React and Pillow PNG in Word/PDF. The tested use case is a distance/time graph
with axes, a polyline and Vietnamese labels; this is not a generic geometry or
scientific illustration engine.

Word uses `MathConverter`: LaTeX → MathML → OMML, with Matplotlib PNG fallback.
PDF uses in-memory formula/image fragments and ReportLab; URL loading stays
disabled. Formulas must belong to the renderable math subset used by both export
paths; invalid/unsafe expressions fail validation with a visible reason instead
of exporting raw LaTeX. Arbitrary TeX packages/macros are unsupported. Existing
legacy text continues to export. Word/PDF remain separate exam, answer/rubric,
matrix and specification documents, with original or selected variant numbering.

Text-only independent reviewers see image alt text/captions, not pixels. Teacher
edits containing images explicitly warn to inspect the original. Full automatic
visual-answer validation is outside this implementation.

## Native extraction and OCR

`DocumentExtractor`/`NativeDocumentExtractor`, `OCRProvider` and `DocumentProcessor`
extend the existing upload service. PDF native extraction runs first, page by
page; sparse, broken-encoding or unreadable-layout pages receive OCR fallback.
Good text pages never call OCR in default mode. PNG/JPEG uploads use OCR directly.
DOCX/XLSX retain native extraction. `ocr_mode=auto|native|ocr` is selectable at upload;
explicit `ocr` rereads PDF pages for layouts/formulas that evade quality heuristics,
subject to the same page/time limits. It does not OCR Office documents.

PDFium renders only candidate pages, bounded by DPI/side length and serialized
for its thread safety. OCR adapters are Gemini Vision (existing google-genai SDK)
and local Tesseract (subprocess without a shell). Auto prefers configured Gemini,
then an available Tesseract executable. Gemini transcribes Markdown/LaTeX;
Tesseract is useful for printed text but does not reconstruct mathematical LaTeX.
Native content survives OCR failures with page warnings. Fully unreadable files
return HTTP 400 before saving file/row. Partial OCR and page/time limits are
visible in the document UI. Never imply that OCR output is independently factual.

`parsed_data.blocks` retains id, page_number, content_type, text, normalized_text
and extraction metadata; `chunk_document` adds document ids and source locators.
Headings, tables, display formulas and captions are identified; tables/formulas
remain atomic during chunking. Legacy spans/chunks still work. Native Office
extraction does not convert existing OMML equations or embedded Office drawings;
for such material upload a PDF/image and select OCR when necessary.

## Configuration

All variables below are optional, documented in `backend/.env.example`.

| Variables | Default / behavior |
| --- | --- |
| `HYBRID_RETRIEVAL_ENABLED`, `LEXICAL_RETRIEVAL_ENABLED`, `VECTOR_RETRIEVAL_ENABLED`, `RERANKER_ENABLED` | true; independent switches; no usable channels yields no retrieved context |
| `RAG_EMBEDDING_MODEL` | `gemini-embedding-001`; requires existing `GEMINI_API_KEY`; no key/outage falls back to lexical |
| `RAG_EMBEDDING_BATCH_SIZE`, `RAG_MEMORY_CACHE_SIZE` | 64 texts/call, 4096 cached vectors |
| `RAG_CANDIDATE_LIMIT`, `RAG_RRF_K`, `RAG_CONTEXT_TOKEN_BUDGET`, `RAG_RERANK_LEXICAL_WEIGHT` | 30, 60, 2400, 0.65 |
| `DUPLICATE_DETECTION_ENABLED` | true |
| `DUPLICATE_FUZZY_THRESHOLD`, `DUPLICATE_WARNING_THRESHOLD`, `DUPLICATE_SEMANTIC_THRESHOLD`, `DUPLICATE_CANDIDATE_LIMIT` | 0.94, 0.86, 0.94, 30; warning threshold cannot exceed semantic threshold |
| `OCR_PROVIDER` | auto; alternatives none, gemini, tesseract |
| `OCR_MODEL` | empty → existing `GEMINI_MODEL`; Gemini needs existing key |
| `OCR_TESSERACT_COMMAND`, `OCR_LANGUAGES` | tesseract, vie+eng; Docker installs executable and languages |
| `OCR_PAGE_TIMEOUT_SECONDS`, `OCR_DOCUMENT_TIMEOUT_SECONDS`, `OCR_MAX_PAGES` | 30, 120, 12; document budget checked before each page (an in-flight page can add its timeout) |
| `OCR_MAX_OUTPUT_TOKENS` | 8192 per Gemini page |
| `OCR_NATIVE_MIN_CHARS`, `OCR_NATIVE_MIN_ALNUM_RATIO` | 40, 0.4; quality heuristics, not confidence probabilities |
| `OCR_RENDER_DPI`, `OCR_RENDER_MAX_SIDE`, `OCR_MAX_IMAGE_PIXELS`, `DOCUMENT_MAX_PAGES` | 180, 2400, 16000000, 300 |

The old `text-embedding-004` default was replaced because it was retired; a local
`.env` explicitly selecting it must select a supported model. Model namespaces
keep old/new vectors separate and rebuild lazily. `gemini-embedding-001` matches
the existing one-vector-per-text batch contract; `gemini-embedding-2` aggregates
multiple inputs and needs a different adapter. See [Google embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
and [model lifecycle](https://ai.google.dev/gemini-api/docs/deprecations).

## Data and operational limits

The existing automatic SQL compatibility runner adds nullable JSON columns
`bank_questions.rich_content` and `bank_questions.content_metadata` idempotently.
Exam questions and document blocks use existing JSON columns. No records are
deleted, no pgvector extension, no second vector store and no manual migration.

Vector ranking currently scans the authorized cached vectors in process. Large
banks need measured capacity/ANN work; external reranker quality, semantic
thresholds and OCR accuracy need evaluation on the school's Vietnamese corpus.
No real paid-provider end-to-end claim is made by mocked contract tests. Local
Tesseract, PDF rasterization, math conversion, DOCX/PDF and browser components
are exercised by real implementations in tests.
