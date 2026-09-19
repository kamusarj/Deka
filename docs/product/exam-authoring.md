# Exam Authoring

## Account Exam Numbers

- Dashboard/list badges and saved/generated exam headings use `exam_number`,
  the sequence of existing exams within the creator's account (oldest is 1).
  Drafts and verified exams share that sequence. The list remains newest first.
- Search, filters, pagination and the viewer's role do not change an exam's
  number. Administrators can see the same number for different creators.
- Numbers are derived from stored ownership and creation IDs on read, so
  existing owned exams work without a migration. Deleting an exam compacts the
  remaining sequence; it is a display ordinal, not a permanent identifier.
- API calls, links, bank references, variants and export identity still use
  the original `id`. Legacy ownerless exams have no display number; responses
  without the optional field render without a numeric badge.

## Unfinished Form Autosave

- The Create Exam form automatically saves its configuration in the current
  browser, separately for each authenticated user and school context. Reloading,
  leaving the route, or reopening the browser restores the latest saved inputs.
- The snapshot includes all exam input fields, curriculum and edit intent,
  question counts/points, difficulty ratios, variants, calculation requirements
  (including an unfinished count input), and selected document ids. Incomplete
  values are saved even when they cannot yet pass generation validation.
- A small status bar shows successful save time, restored state, and the browser
  scope. Storage failures are visible and retryable; editing remains possible.
  Malformed or incompatible snapshots fall back to defaults with feedback.
- Document choices survive loading and transient errors. Successful loading
  removes inaccessible/deleted source ids with a notice. Changing grade clears
  the previous source selection. Generation waits while restored selections
  remain unverified due to loading or an error.
- “Tạo đề mới” asks for confirmation before replacing the current local draft
  with defaults and resetting the result view. Cancellation preserves edits;
  another account's draft and existing server exams are unaffected.
- Generation success or failure keeps the input draft. Restoring it never starts
  AI work or reapplies global provider settings. Existing server-saved exams and
  verification drafts remain separate from this form snapshot.
- Drafts are local to this browser/origin and are removed with browser site data;
  this feature does not synchronize devices or resume a running generation job.

## Curriculum Input Contract

- Resource collection may populate curriculum suggestions while the teacher has
  not edited the curriculum form.
- Once the teacher edits or adds curriculum content, later resource collection
  must preserve that unsaved input.
- Collected suggestions remain informational even when they are not applied to
  the form automatically.

## Question Shape Contract

- Every true/false question contains exactly four complete statements.
- Optional structured-output collections may be null. Variant construction
  treats null statements, sub-questions, and answer key points as empty
  collections so existing and newly generated exams remain renderable.
- AI output with missing or malformed type-specific fields may be normalized
  into a safe temporary shape, but the semantic gate marks that replacement as
  invalid and regenerates it. Temporary replacement content is never persisted
  as a production question.
- Extra valid statements are truncated to four and the answer key references
  only the four displayed statement ids.

## Quality Feedback Contract

- Exam screens do not expose the general validation score or pass/fail banner.
- Quality feedback is absent when no teacher action is required.
- Actionable findings use the displayed question number, never an internal id
  such as `q_3`, and present only the issue and suggested edit.
- Independent answer comparison is question-type aware: multiple-choice labels
  and true/false maps remain exact; short answers allow conservative numeric
  word equivalence; essays require majority coverage of meaningful answer-key
  points rather than verbatim prose.
- Answer equivalence never suppresses separate ambiguity, scope, distractor, or
  difficulty findings.
- Interactive full exams use the label “Trợ lý kiểm định” for a single reviewer
  or “Đối chiếu 2 trợ lý kiểm định” for dual review, according to the deployment
  review mode. Provider/model names and provider attribution prefixes in
  findings are omitted from this presentation. A one-reviewer run never claims
  consensus. Raw prompts, credentials, and hidden reasoning are never displayed.

## Saved Exam and Regeneration State

Saved-exam workspace state belongs to the current route id. Navigating to another
exam clears previous content and controls, including when the new load fails;
late loads or actions from the old route cannot replace the current exam.

Regeneration validates every selected id against the stored questions and
specification before provider work. Unknown ids reject the whole request. A
failed regeneration remains an error in the UI and retains the selection for
retry; it never triggers a success reload or notification.

## Student Preview

The saved-exam audience selector controls both on-screen preview and exports.
Student preview shows prompts, options, true/false statements, essay subquestions
and question points. It omits answer indicators, explanations, suggested answers,
rubrics, source evidence, quality findings, teacher review controls and status,
difficulty/topic hints, and matrix/specification panels. Switching back to teacher
restores these details, including when viewing a variant. This is a preview inside
the existing teacher workspace; it does not create a student role or submission flow.

## Separate Export Documents

The teacher workspace has a separate “Nội dung hiển thị” selector for the question
paper, matrix or specification. The chosen content opens directly in the main
workspace. Specification numbers follow the selected variant. Student preview
always shows questions and hides this selector. Display selection does not change
the independently selected download document.

- Word/PDF downloads select exactly one document: `exam` (default, questions
  only), `answers` (answer key and grading guide), `matrix`, or `specification`.
- The teacher audience controls preview details and availability of supporting
  downloads; it no longer appends answers or supporting documents to the paper.
  Student downloads always select `exam`.
- An omitted `variant_code` exports the original. A selected code exports only
  that variant, with its code once in the document header. Invalid codes fail.
- Deterministic variants preserve verified question, statement, subquestion and
  answer wording. Only ordering and identifiers change; statement answers and
  explanations follow the reordered statements. MCQ options and their correct
  keys/option explanations are remapped together; position-dependent legacy
  options keep their original order. No code-specific context or
  extra learning requirements are appended.
- Answer keys, rubric and specification numbering follow the selected variant.
  Stored exam data is unchanged; ownership and publication checks still apply.

## Scientific Review Input Contract

- Independent review receives the public question type and student-facing
  statement text without embedded true/false answer labels.
- The single-correct-option rule applies only to multiple-choice items. A
  true/false item must instead match all four unique statement ids and truth
  values exactly; duplicates, missing statements and wrong values fail.
- Curriculum provenance and citations are scope evidence, not answer prose.
  Objective-copy findings concern pedagogical objectives substituted for actual
  scientific explanations; correctly testing an objective is not copying it.
- Normalization preserves supplied nonempty explanation/model-answer prose.
  Concise content is assessed scientifically rather than replaced by a
  character-length threshold. Missing-answer messages never satisfy generation
  quality checks.
- Application-level items require a concrete application of their knowledge
  target. Repair prompts include the recorded diagnosis and suggested correction
  as well as the stable failure code.

## Saved Exam Review Contract

- Reopening an exam starts on the original question order, even when generated
  variants exist.
- The original and each numbered variant are explicit choices. Review actions
  apply only to the original questions and persist immediately.
- Deterministic question fixtures are test-only. Production generation fails
  closed after the configured provider and quality retries are exhausted.
- Exam review navigation is derived from the question types present in the
  loaded exam. Empty types are not shown and filtering does not alter question
  ids, answers, review state, or the relative order within a type.
- Each generated question has a concise collapsed review summary and a complete
  expanded view. True/false statements remain children of their shared prompt;
  short-answer and essay questions use separate answer presentations.
- Existing answer, explanation, rubric, review, regeneration-selection, bank,
  variant, and export workflows remain available without changing their API.

## Verification Draft Contract

- A primary-only interactive run that has already produced real AI questions,
  answers, and rubric preserves its latest payload as `draft` when an exhausted
  post-generation deterministic or mandatory semantic gate rejects it.
- Draft persistence is not provider fallback and does not approve the content.
  Production never substitutes a deterministic fixture, placeholder, or mock
  question for failed provider output.
- Draft responses retain sanitized failure metadata and failed question ids,
  omit variants, and identify themselves through `publication_status=draft`.
  Existing saved exams default to `verified`.
- Drafts remain owner-scoped and readable, but export and question-bank reuse
  are blocked by the backend until the same row becomes `verified`.
- Paid repair is explicit. The browser sends `allow_provider_fallback=false`,
  regenerates and semantically reviews only selected failed ids, merges their
  replacement reports, and promotes the row only when no whole-exam
  deterministic or mandatory semantic hard failure remains.

## Document Library Contract

- Every authorized reader can open the full extracted text for a document from
  the document list; upload and delete actions remain role-scoped.
- The viewer clearly distinguishes extracted text from filename and metadata and
  provides an explicit close action.

## Provider Degradation Contract

- Exam generation and semantic verification use one immutable provider order:
  OpenAI primary, Gemini fallback 1, and DeepSeek fallback 2.
- JSON generation through OpenAI uses a task-specific Pydantic contract with
  the Responses API structured parsing helper. Question generation, answer and
  rubric generation, independent solving, and quality review have separate
  schemas; a missing schema-conformant payload counts as provider failure.
- Gemini and DeepSeek remain compatible fallbacks. Their decoded JSON is
  validated against the same Pydantic task contract, then remains subject to
  the existing server normalization, completeness, scope, and structural
  checks before it can be persisted or shown.
- Unconfigured providers are skipped. A provider, transport, empty-response, or
  JSON-decoding failure advances to the next configured provider; calls stop at
  the first valid response.
- Mistral, OpenRouter, arbitrary compatible endpoints, and manual provider
  reordering are not part of the generation contract.
- RAG query diagnostics report the backend that actually answered, including a
  runtime fallback from embeddings to BM25.
- One external verification failure stops further AI verification calls for
  the current exam while deterministic checks continue. For newly generated or
  regenerated content, a skipped independent semantic review is a hard failure:
  retry/regeneration must succeed before persistence.
- Interactive full-exam generation is a specialization of this legacy
  degradation contract: Luna generates without fallback. In the default mode,
  DeepSeek V4 Pro and Gemini 3.7 Flash both verify as peers rather than
  fallbacks. An explicitly configured temporary mode uses DeepSeek alone and
  makes no Gemini call. Persistence stops when any reviewer required by the
  selected mode is unavailable, before a quality-repair generation call is
  spent. Verified publication remains blocked, while an authenticated
  primary-only run may preserve already-generated real content as an explicit
  non-publishable draft under the Verification Draft Contract.

## KHTN Generation Quality Contract

- The generator serves Khoa học tự nhiên grades 6-9. Mathematics is supported
  as a reasoning tool inside KHTN, not as a standalone subject.
- A learning objective defines student capability and curriculum scope; it is
  never accepted as the scientific answer itself.
- Generation separates knowledge target, knowledge intent, cognitive level,
  public question type, internal domain context, reasoning mode, required
  skills, and controlled source context.
- Physics-, chemistry-, biology-, earth-science-, and integrated content do not
  imply a fixed reasoning mode. Any domain may use conceptual, causal,
  quantitative, experimental, data-analysis, or application reasoning when the
  selected source and grade support it.
- Type-homogeneous bounded batches are semantically validated before
  persistence. Meta-learning answers, copied objectives, missing referenced
  data, unsafe/invalid calculations, or incompatible type shapes are rejected
  and regenerated with explicit reasons.
- Supported numerical items are independently solved through whitelisted
  formulas and unit conversions. No model-authored expression or code is
  executed.
- Formula availability is question-specific. Local curriculum grounding uses
  the exact grade/objective id; uploaded-document grounding requires an allowed
  grade and formula cues in the retrieved passage/knowledge target. The prompt,
  structured schema, semantic gate, and solver registry must advertise the same
  formula ids.
- The controlled registry covers source-backed speed; molecular/molar mass;
  molar gas volume; gas relative density; concentration; density; pressure when
  a retrieved source explicitly supplies its relation; moment; Ohm; heat;
  kinetic, potential and mechanical energy; electrical power/energy; series and
  two-resistor parallel equivalent resistance; and generic grounded data
  difference/percent-change operations.
- Exhausted hard-quality retries abort verified publication; the system does
  not replace them with generic printable content. Real primary-only output
  may be retained only as the labelled, non-publishable draft defined above.

## Required Calculation Contract

- The teacher authoring form requires a positive calculation count and a score
  for each calculation question. It also requires the teacher to select the
  cognitive level of every calculation slot individually (`nhan_biet`,
  `thong_hieu`, or `van_dung`). Calculation items remain a subset of the public
  short-answer section rather than becoming a fifth question type.
- A calculation slot replaces an ordinary short-answer slot and may override
  its score. The effective sum of all configured slots must equal the declared
  exam total before generation starts.
- A positive calculation requirement is exact: planning must mark the requested
  number of formula-capable curriculum objectives, every marked item must pass
  the safe numerical verifier, and whole-exam validation must find the same
  count, score, and ordered per-question difficulty configuration before
  persistence. The fixed calculation levels consume their corresponding score
  buckets first; the planner allocates all remaining questions around them to
  preserve the requested whole-exam difficulty ratio.
- If the selected curriculum has no exact grade/objective capability, generation
  fails before an AI provider is called and tells the teacher to select suitable
  quantitative content. Similar topic wording alone is not sufficient.
- Model-authored known values and calculation steps are used only for internal
  deterministic verification. Persisted questions expose a safe calculation
  marker and the teacher answer explanation; student exports do not expose
  answers or internal verification data.
- API clients that omit this newer option retain the historical zero-required-
  calculation behavior. API clients that submit a calculation requirement but
  omit its `difficulties` list retain automatic difficulty allocation. The
  interactive teacher form always submits a positive requirement with exactly
  one selected level per calculation question.
- The interactive form lets the calculation count drive the minimum
  short-answer count. Raising calculations adds the required short-answer slots
  instead of clamping the teacher's input; lowering calculations does not delete
  ordinary short-answer slots. The form displays the effective total question
  count and explains this relationship before generation.

## Difficulty Ratio Controls

- The three controls use a fixed top-down rule. Changing Nhận biết preserves
  Thông hiểu if it still fits, otherwise reduces it to the available share;
  Vận dụng receives the remainder. Changing either lower level preserves
  Nhận biết and balances the other lower level.
- Example: `30/40/30` becomes `35/40/25` when Nhận biết is set to 35;
  setting Thông hiểu to 50 then produces `35/50/15`.
- Lower sliders and numeric inputs have a maximum of `100 - Nhận biết`.
  All committed adjustments use whole percentages and sum to 100. Teachers
  can change Nhận biết again to make more room for the lower levels.
- Slider changes apply immediately. Numeric fields allow clearing/typing and
  commit on blur or Enter, with bounds applied then. Escape restores the
  current value; blank input restores it on blur. Presets replace all three
  values. Existing form autosave persists the committed ratio.
- Each row retains its visible level label on mobile, a filled slider track,
  a percentage field and its available range. The total indicator reflects
  the actual total, including an invalid total from an unfinished old draft.
- Ratio tracks, dots and preview segments use three olive shades from the
  theme tokens, with palettes for light, dark and system modes. The valid
  total badge uses the same olive theme; invalid ratios retain error styling.

## Automatic Score Distribution Contract

- The interactive form enables `auto_distribute_scores` by default. Existing
  API clients that omit the flag keep fixed per-type and per-calculation scores.
- In automatic mode configured scores are relative planning weights. After
  difficulty assignment, the server converts the declared total into 0.25-point
  units. Requested difficulty ratios are rounded deterministically to the
  closest feasible quarter-point budgets with largest remainders, then those
  units are divided among questions by their planning weights.
- Every question and scoring idea receives at least 0.25 point. Multiple-choice
  and short-answer items reserve one unit, four-statement true/false items
  reserve four units, and two-part essay items reserve two units. Question,
  sub-question, and rubric scores use only multiples of 0.25.
- Teacher-selected calculation levels never change to satisfy scoring. Every
  level with a positive requested ratio must contain at least one question; an
  impossible score-unit capacity fails before provider generation with a
  Vietnamese diagnostic.
- The final question scores, whole-exam total, and feasible actual difficulty
  percentages are authoritative in the matrix/specification. The total remains
  exact, while a ratio such as `19/18/63` on a ten-point exam becomes
  `2.00/1.75/6.25` points. Summary metadata records automatic mode, the 0.25
  increment, and the actual score of every calculation question for validation
  and regeneration.

## Document Source Selection

- Grade-specific document choices are cleared when the grade changes. Late
  responses from previous grades cannot replace the current sources; load errors
  are shown with a retry action instead of silently hiding the document selector.

## Answer Evidence Contract

- Generated answers explain the conclusion in question-specific language;
  multiple-choice answers may explain each displayed option and true/false
  answers explain every child statement.
- Source evidence is derived from controlled curriculum data or the retrieved
  document chunk, not from a model-authored citation.
- The server marks evidence `verified` only when its excerpt exactly matches the
  stored curriculum achievement or retrieved RAG chunk and the required source
  locator exists. An excerpt mismatch is `rejected`; missing historical context
  is `unverified`.
- Only verified evidence is rendered as a quotation. Rejected or unverified
  evidence may retain safe document/section locators, but the UI shows the
  reason instead of presenting unsupported text as a quotation.
- When available, verified evidence identifies the document, page or section,
  and exact excerpt used. Missing historical locator data is disclosed rather
  than invented.
- Citation fields are optional so saved exams and bank records created before
  this contract remain readable.
- Legacy exams that lack duplicated question answer fields retain valid stored
  answer-key truth in original and variant read/export output. Explicit canonical
  question truth takes precedence; normalization does not rewrite saved JSON.

## Direct Editing and Rich Content

See [integrated authoring capabilities](authoring-capabilities.md) for the current
versioned edit API, bank reuse, shared quality/duplicate gates, rich blocks, math
and diagram rendering, optional hybrid retrieval and selective OCR. All four
question types can be edited directly in CreateExam and the saved original.
Save preserves matrix/domain/source metadata and rechecks the revision; failure
to verify preserves a draft. Cancel discards local edits. Generation settings and
regeneration controls remain available. A viewed variant is derived/read-only.
