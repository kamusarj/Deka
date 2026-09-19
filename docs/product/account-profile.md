# Account Profile

## Purpose

Every authenticated user has one self-service account surface for identity,
teaching-school context, and credential security.

## Profile Contract

- Users may edit their own display name.
- Email, stored role, active state, and school membership are server-derived.
- The account surface displays the assigned school's name, address, and phone
  when available; an unassigned user sees a clear empty state.
- School membership remains administrator-controlled under
  `docs/product/permissions.md`. Self-service profile updates never accept a
  school id or school name.

## Password Contract

- Accounts with a local password may change it by supplying the correct current
  password and a new password that satisfies the existing password rules.
- OAuth-only accounts cannot set or change a local password through this flow;
  the UI directs them to their identity provider.
- The authenticated user response exposes only the derived boolean
  `can_change_password`; it never exposes a password hash or provider secret.
- Changing a password does not change role, school membership, or other profile
  data.
- A new password must differ from the verified current password; the browser
  provides immediate feedback and the server remains authoritative.
- Changing a password increments the account token version, invalidates every
  previously issued JWT, and returns one rotated token for the current browser.

## School Read Contract

- An account with no assigned school receives an explicit empty result and sees
  the unassigned-school state.
- Authorization, network, and server failures are displayed as load errors and
  are never presented as an unassigned-school state.

## Account Links

Email verification and password-reset links are single-use even under concurrent
requests. Consuming a link and changing the account commit together; a failed
account transaction leaves the link available for a legitimate retry.

## Logout Contract

- Authenticated logout increments the account token version and invalidates all
  JWTs issued before that logout, including tokens on other devices.
- The browser attempts server revocation before discarding its bearer token and
  always clears local authentication even if the server is unreachable.
- Per-device selective logout is not currently supported.
- Revocation captures the outgoing bearer and has a ten-second browser timeout.
  Local state and navigation clear as soon as that request starts; late logout or
  password-change responses cannot restore or erase a subsequent browser login.

## Login Persistence Contract

- Email/password login offers an unchecked `Ghi nhớ đăng nhập` option.
- Without the option, the bearer token is scoped to the current browser session
  and is removed when that session ends.
- With the option, the bearer token may survive a browser restart until the
  server-defined token expiry or a revocation event.
- The browser never stores the submitted email or password for this feature.
- Explicit logout and authentication invalidation clear both session-scoped and
  persistent token storage.
- On reopening the app, a saved token is verified before private content is
  shown. Network, timeout, and server errors retain that token and display a
  retry action; recovery retries after five seconds or when connectivity returns.
- Identity verification has a ten-second timeout. A current-session 401 clears
  the token; a delayed 401 from an older session cannot erase a newer login.
- The same 401 rule applies to streamed exam generation. Token changes in other
  tabs hide the previous identity and verify the effective replacement token;
  session-scoped tokens retain precedence over another tab's persistent token.
- A newer login or logout supersedes any pending login response. OAuth callbacks
  restore identity before navigating to private content.
- Visiting login with a verified session returns to the intended destination.
  The landing page offers `Vào ứng dụng` when authentication has been restored.
- Remembered login remains limited to server expiry (24 hours by default);
  restarting a computer does not extend it.

## Demo Login

- The optional `VITE_ENABLE_DEMO_LOGIN=true` build setting adds four demo role
  buttons, email addresses and a public demo password to login. It defaults off.
- Accounts are provisioned explicitly with
  `python -m app.services.demo_accounts --allow-demo-accounts`; startup never seeds
  them. Conflicting existing accounts are not reset or promoted.
- Each button uses ordinary password login and the current remember-login choice;
  login errors and session verification follow the existing contract.
- In demo mode, logout returns to login for the next role selection.
- Hiding shortcuts does not deactivate accounts; demo retirement is a separate
  operator action. These accounts have the real permissions of their roles.

## Brand Contract

- The shared interface uses paper/olive colors, Newsreader headings and locally
  served Be Vietnam Pro controls. See [Interface Design](interface-design.md).
- The login page separates the introduction and optional demo shortcuts from
  the credential form on desktop and stacks them on mobile. Authentication and
  remembered-login semantics remain unchanged.
- Native cursors replace the former pointer-following ornament. Motion is brief,
  honors reduced-motion preference and never gates access to content.

- Section links use router-aware fragments so landing/footer links and the skip
  link never replace the workspace route. The skip link moves keyboard focus to
  main content; section navigation respects reduced-motion preferences.
- Dashboard statistics and recent exams report failures independently and offer
  retry. Unavailable statistics show placeholders and a failed list is not shown
  as an empty account.

- On desktop above 1024px, Dashboard and workspace links appear in a left
  sidebar beside page content. The brand, theme toggle and account menu remain
  in the top bar. The sidebar stays visible while the workspace scrolls.
- At 1024px and below, navigation uses the menu button and drawer; the drawer
  fits below the header and scrolls on short screens. Route highlighting and
  existing role-based visibility apply to both navigation layouts.

- The Smart Exam mark is one reusable, code-native SVG representing a verified
  exam sheet.
- Landing, application navigation, authentication, and footer surfaces use the
  same mark and inherit the active light/dark theme.

## Subscription and Credit Visibility

The account page shows the current plan, status, available integer credits, monthly
allowance and current period using the existing paper/olive theme. Carried-over
credits may exceed the allowance, so no misleading percentage meter is shown.
The credit ledger is a collapsed disclosure showing up to ten recent transactions.
AI request history and charge/reservation statuses are available through the
existing usage-report link. Teachers
do not need raw tokens or provider pricing. Plan changes and credit grants remain
operator-controlled; there is no purchase button or payment flow.

Loading, empty history, zero balance and failed reads are explicit; retry fetches
fresh server data. Identity changes unmount the account panel and abort pending
requests; responses from older sessions are ignored. Forced password change keeps
its existing gate and does not load subscription APIs.


## Account Information Hierarchy

The account page opens with a compact identity header: avatar, full name/email,
read-only role and join date. It does not repeat email or school in quick-info
cards. Desktop places the personal profile and school details in the main
column with the current plan/credit summary alongside; mobile stacks them.

Profile updates retain existing APIs; an unchanged name disables saving. A
shared success toast survives the identity refresh that remounts the page.
School information is shown once, with distinct loading, missing and error
states. Email remains read-only in the identity header.

Security is a native disclosure, initially closed except when a temporary
password must be replaced. Existing password validation, token rotation and
OAuth guidance remain intact. The subscription panel retains real balance,
allowance, period, active/paused state, zero-balance warning and retry. No fake
percentage or payment CTA is introduced. Credit history expands on demand and
AI history moves to the existing statistics route.

## Audit revision: subscription reads and administrator proof

The account page may show an unactivated subscription (`null`); opening the page grants no credits. An authorized operation enrolls or renews once when due. Accumulated balances remain, missed periods do not multiply grants, paused subscriptions block AI, and held reservations retain refund headroom. The UI distinguishes renewal due from a completed grant. Raw provider/token/cost fields are absent for ordinary users. Super admins enroll TOTP with their password and obtain a ten-minute elevated token; production APIs enforce this proof, including direct calls. Recovery codes are shown once. See [ADR 0049](../decisions/0049-production-audit-boundaries.md).
