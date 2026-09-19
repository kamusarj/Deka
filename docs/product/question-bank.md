# Question Bank

## Saved Question Contract

- A question saved from an exam keeps the complete learner-facing content for
  its type: choices, true/false statements, or essay sub-questions.
- The saved answer is directly readable by clients and may include an attached
  rubric for essay questions.
- Clients remain able to display records written with the legacy nested
  `answer`/`rubric` envelope.

## Presentation Contract

- Question-bank cards show the question, its choices or component statements,
  and a clear answer section instead of exposing raw JSON or only metadata.
- Generated-exam cards read like a conventional test paper. Technical type,
  difficulty, source, and AI-oriented labels do not compete with the question
  text; review and quality details remain available when relevant.
- The displayed total equals the number of question cards returned by the
  active filters, and visible cards use contiguous display numbers.

## Retrieval, Validation and Reuse

Bank search offers semantic search using the same hybrid infrastructure as
document retrieval, filtered by current read permissions, type and level.
Generation and teacher edits compare questions with the readable bank. Exact
repeats are rejected on direct/exam saves; fuzzy/semantic findings warn and are
returned to the teacher. Embeddings are optional; exact/fuzzy and BM25 work
without them. No bank item outside read scope participates in exposed findings.

Rich blocks and original generation metadata survive exam-to-bank saves. The
editor can load a compatible bank item as an edit template and revalidate it
against the current matrix before Save; a read-only preview never bumps usage.
See [authoring capabilities](authoring-capabilities.md) for thresholds, legacy
compatibility, source rules and limits.
