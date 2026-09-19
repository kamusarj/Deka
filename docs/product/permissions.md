# Permissions

## Role Hierarchy

The application exposes the stored roles directly. Higher roles inherit the
capabilities of lower roles, but retain strict platform and school boundaries.

| Role | Scope | Purpose |
| --- | --- | --- |
| `super_admin` | Entire platform | Manage all schools and all non-super-admin accounts. |
| `school_admin` | Assigned school | Manage only Teacher accounts in that school. |
| `teacher` | Own workspace | Create exams with the platform-configured AI provider. |
| `viewer` | Legacy basic access | Use basic authenticated workspace without management permissions. |

Unknown role strings fail closed.

For local role testing, the explicit demo provisioning command creates one
account for each of these four roles. School Admin, Teacher and Viewer share
`Trường THCS Demo`; Super Admin retains platform scope. Demo accounts use the
same backend authorization checks as other accounts. See the opt-in login
workflow in [Account Profile](account-profile.md#demo-login).

## Permission Matrix

| Capability | Super admin | School admin | Teacher | Viewer |
| --- | --- | --- | --- |
| Use authenticated workspace | Yes | Yes | Yes | Yes |
| View safe AI provider/model metadata | Yes | No | No | No |
| View fixed AI provider priority | Yes | No | No | No |
| Change global AI model / run admin tests | Yes | No | No | No |
| List/edit every school | Yes | No | No | No |
| List/manage all non-super-admin accounts | Yes | No | No | No |
| Create/attach/lock/remove teachers | Yes, through platform scope | Own school only | No | No |
| Promote/demote a school admin | Yes | No | No | No |

## Assignment Rules

- Email/password registration and OAuth always create `teacher` users.
- Only a super admin may create or edit schools.
- Only a `super_admin` may change another account between `school_admin` and
  `teacher`/`viewer`, change school membership, or activate/deactivate it.
- A promoted `school_admin` must be assigned to an existing school. The account
  editor submits its selected school with role changes; a teacher who stays a
  teacher uses the explicit school-transfer operation.
- A `super_admin` role cannot be assigned, removed, or modified through the
  application role-management endpoint.
- A super admin cannot change their own role through that endpoint.
- Role checks use the current database row, so revocation is effective even
  when an older JWT still contains the previous role claim.

## UI Contract

- Authenticated workspace navigation, including Documents and Question Bank,
  is visible to every recognized role. Read and write operations remain scoped
  by backend authorization and the role-specific capabilities below.
- Platform administration is visible only to super admins.
- School teacher management is visible only to school and super admins, with
  backend scope checks for the assigned school.
- AI provider metadata, the OpenAI → Gemini → DeepSeek order, model mutation,
  and administrative tests are visible only to super admins. School admins and
  teachers create exams through the server-configured chain without seeing or
  requesting provider metadata.
- `ai_provider_metadata` and `ai_provider_mutation` are Super-Admin-only.
  `content_write` remains independent for super admins, school admins, and
  teachers.
- The account page displays the server role as read-only information.
- Client-side checks improve UX only; backend dependencies remain the security
  boundary.

## Shared Documents

Document reads additionally allow same-school shared files and approved system
files; see [Document Sharing](document-sharing.md). Recipients get no mutation
rights. Super Admin alone moderates global publication. Existing school and
platform oversight continues. Default uploads and historical rows remain private.

## Community Questions

All recognized signed-in roles can publish community topics and comments, including
Viewer. Only authors or Super Admin can remove these contributions. Personal-bank
writes retain content_write. See [Community Questions](community-questions.md).

## Authoring Extensions

Question edits and bank template reuse require exam mutation ownership (or
Super Admin), current version and existing writer role. Semantic search and
duplicate candidates resolve existing bank read scope before embeddings.
Uploaded documents resolve current sharing scope before retrieval; cached
vectors never grant access. Student preview continues hiding edits, answers,
rubrics and private provenance while rendering learner-facing rich content.

## Subscription Reporting

Every known role can read personal AI-account statistics. School Admin can also
report on teachers in their assigned school, following the existing teacher
management boundary. Super Admin can view all nondeleted accounts and aggregate
by current role, date and account. Report queries enforce this scope before
applying client filters; unknown roles are denied.

Super Admin alone can customize any individual subscription (including their
own): plan, recurring allowance, active/paused status and explicit credit delta.
This endpoint cannot change roles or global provider settings. Version checks,
ledger and audit are atomic. See ADR-0048 and `docs/ai-architecture.md` for API
and accounting semantics.
