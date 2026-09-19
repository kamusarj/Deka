# Interface Design

## Visual Direction

Smart Exam uses a paper and olive palette, reading-oriented headings and a
compact workspace for Khoa học tự nhiên teachers in grades 6–9. The public
PaperPulse reference informed palette, whitespace and interaction restraint;
Smart Exam retains its own verified-sheet mark, teaching content and workflows.

## Source Files

- `frontend/src/styles/tokens.css`: shared light/dark/system colors, typography,
  spacing and motion tokens.
- `frontend/src/styles/paper.css`: public pages, shared workspace and responsive
  presentation. Domain-specific tables and exam controls remain in `styles.css`.
- `frontend/src/styles/fonts.css` and `frontend/public/fonts/`: local Newsreader
  and Be Vietnam Pro subsets and their SIL Open Font licenses.

Newsreader is used for headings and large statistics. Be Vietnam Pro is used
for controls and body content. Small text and status colors retain semantic
tokens; dark buttons use a dark foreground against pale sage.

## Interaction Contract

- Public landing content is immediately present, without scroll/reveal gates.
  The labelled illustrative preview switches between matrix, student question
  and teacher answer guidance using keyboard-operable pressed-state buttons.
- Before the finished-exam preview, the landing page explains four ordered
  steps: choose content, configure structure, generate/review, export/reuse.
  All summaries are visible at once. Selecting a step shows the user's action,
  a labelled KHTN 8 example and its outcome; a next-step control helps explore
  the sequence. Steps never auto-advance or start real generation.
- Workflow copy explains optional uploaded sources, teacher review, separate
  Word/PDF documents, later question reuse and same-browser form autosave.
  Creation links retain the existing protected `/create` destination, while
  section links preserve the HashRouter's inner fragments.
- Auth keeps ordinary email/password, OAuth, persistence and opt-in demo-role
  shortcuts. The desktop login separates introduction/demo accounts from the
  credential form; phone layouts stack them without shrinking the form.
- The desktop sidebar preserves role filtering and selected routes. Mobile
  retains the existing navigation drawer. Dashboard shortcuts lead to existing
  documents, question bank and community routes.
- Workspace pages use a viewport-height frame: only the main pane scrolls while
  the header and sidebar stay in place. A compact copyright footer follows the
  content inside that pane, appearing at the end of long pages and resting at
  the bottom of short pages. The full footer remains on public pages. Changing
  workspace routes resets the main pane; skip links and public anchors still work.
- Native text and pointer cursors remain visible. No pointermove-rendered cursor,
  moving marquee, hidden scroll-reveal content or continuous marketing animation.
- Brief fades and state transitions respect reduced-motion preference. Focus
  indication remains visible and instructional tables can scroll locally.
- Dashboard statistics, failures and empty states use actual API results. No
  success rates, fabricated user counts or verified-preview claims are introduced.
- Exam detail resets local selections when its route identity changes, not in a
  delayed post-load effect that could override a user's first tab selection.

## Shared Control and Color Contract

- Native checkbox/radio inputs inherit the olive accent with compact dimensions
  and visible keyboard focus. Checked, unchecked, disabled and native keyboard
  semantics remain intact across authoring, review, bank, admin and login forms.
- File-picker buttons use the same olive surface and text tokens. OCR choices,
  correct-answer choices and rich-content options use the shared SelectControl,
  including its keyboard navigation, popup placement and disabled handling.
- Disabling a SelectControl closes its popup and prevents stale portal choices
  from changing the value; re-enabling does not reopen the previous popup.
- Ordinary configuration panels, valid score summaries, metadata/source/type
  badges, account decorations and progress fills use olive or neutral tokens.
  Difficulty dots, tags and charts share the ratio palette, with a darker
  application chart fill to keep embedded text readable in the light theme.
- On narrow screens, the question-structure score summary follows its heading
  and description so the badge does not squeeze explanatory text into a column.
- Semantic error/warning, accepted/rejected, correct/incorrect, availability and
  toast feedback retain their distinct colors. Official OAuth provider logos
  and teacher-authored diagrams/images preserve their own content colors.
- These styles apply to light, dark and system themes without changing roles,
  curriculum, form values or API payloads.

## Validation Boundary

Maintain functional frontend tests and check screenshots at desktop, tablet and
phone sizes in light/dark themes. A visual refactor must preserve login, role
visibility, field validation, exam generation inputs and existing data flows.
