# Document Sharing

Uploads and existing documents default to **Cá nhân**. Files remain stored once;
sharing grants use of the original and does not transfer ownership.

| Scope | Readers beyond owner and existing admin oversight | Approval |
| --- | --- | --- |
| Cá nhân | None | None |
| Trong trường | Members of the document's school | Owner chooses |
| Toàn hệ thống | All authenticated accounts | Super Admin approves |

School Admin retains read oversight for documents belonging to their school;
Super Admin retains platform oversight. Shared recipients may view and select
sources when their role permits exam creation, but cannot modify/delete/share
someone else's file. Viewers remain read-only. Owner or Super Admin may withdraw
sharing. School sharing requires the owner to belong to the document's school;
transferring an account does not silently move old documents to a new school.

System publication is requested, pending, approved or rejected. Pending and
rejected documents are not published to recipients. Super Admin can inspect,
approve, reject or withdraw approval; the owner can cancel/resubmit. Stale
requests cannot overwrite a newer sharing decision. Decisions have audit rows.

The library offers all accessible documents, mine, school and approved system
collections; Super Admin also has a pending collection. Source selection in
CreateExam uses the same access rules. Revocation takes effect for new reads and
retrievals. It does not erase content already included in saved exams or copies
already viewed. A retrieval already started uses its authorized snapshot.

Library and detail views follow the latest selection. Late responses or errors
from older selections must not replace current content. Completing a sharing,
moderation, upload or delete action refreshes the currently selected library.

Supported filenames with empty, corrupt or unreadable document contents are
rejected with HTTP 400 before saving a file or row. Password-protected PDFs
require an unlocked copy. Unexpected internal failures retain their server-error
status rather than being presented as a problem with the user's document.

## Extraction and Retrieval

Upload supports PDF, DOCX, XLSX and PNG/JPEG. Native PDF extraction runs before
selective OCR; good text pages avoid OCR. Gemini Vision and local Tesseract are
optional providers; missing/failed OCR retains usable native text with per-page
warnings, while an entirely unreadable scan/image is rejected. The teacher can
select native-only or request OCR for difficult PDF layouts.

Structured blocks preserve real page/section locators and formulas/tables for
the same optional hybrid RAG flow. No additional document permissions or
public vector collection are introduced. See [authoring capabilities](authoring-capabilities.md).

## Audit revision: deletion and long-running access

Long-running AI requests recheck source access before provider calls and result persistence. A revoked source, changed actor school/role/session, account lock or subscription pause stops publication. Document deletion commits metadata removal with an identifier-only cleanup tombstone, then retries exact file/vector cleanup. Tombstones deny retrieval after restoration as well. Physical cleanup failure stays observable and retryable. Restoring a backup requires the current deletion journal before reopening; sharing/role revocations since the snapshot still require separate reconciliation. Retention durations are not implicitly selected by this implementation. See [runbook](../operations-runbook.md).
