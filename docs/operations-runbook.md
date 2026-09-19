# Operations runbook

Use a restricted operator shell with the correct deployment environment. Commands below are templates; do not substitute the development environment or a production database for a rehearsal. No backup schedule, alert recipient or off-host storage has been activated by this implementation.

## Observe and stop admission

`/health` answers process liveness; `/ready` checks database, expected schema and deployment configuration. Probe readiness through the proxy as well as inside the network. Run `python -m app.services.operations_health` inside the backend image: exit 0 means its checks pass, 1 means expired leases, legacy unleased requests, cleanup backlog, unpriced attempts or low disk need attention, and 2 means the check failed. Alert on sustained 5xx/429, latency, memory, disk, DB health, unknown prices, pending cleanup and expired leases. Set an actual operator recipient before pilot.

Set `AI_ACCEPT_NEW_REQUESTS=false` and recreate the backend to close admission. A recreate interrupts workers; first drain existing requests when feasible, then recover only expired leases. Do not increase worker count to bypass capacity. Defaults: 4 operations total, 1 per account, 8 simultaneous SDK calls, 4 parsers, 8 buffered HTTP requests, 22 MiB request body, 20 MiB upload, 100 documents/512 MiB per owner. Daily admission limits are 500 requests and USD 20 of recorded known cost. Unknown or in-flight provider costs require separate provider-side spending caps.

## Recover request credit

Run `python -m app.services.ai.operator --actor-id ADMIN_ID --limit 100` in the backend environment. The default is dry-run. Inspect the expired request IDs; add `--apply` to perform audited conditional refunds. Repeat safely until no eligible rows remain. Heartbeat/owner checks fence old workers from saving results. A successful result and credit finalization are committed together, so a response lost after commit remains retrievable from `/api/me/requests/REQUEST_ID` and the user's usage history. Late provider attempts remain cost records.

Legacy requests without leases are reported separately and never automatically refunded. Inspect the ledger and saved results before an audited account adjustment; do not infer an exam match from timestamps. An unknown upstream outcome is not evidence of zero provider cost.

## Delete documents and clean caches

`python -m app.services.document_cleanup --limit 100` previews persistent cleanup records; add `--apply` after inspecting the batch. Use `--after-id` for subsequent batches. Completed tombstones remain available for rechecking late writes/restores. Cleanup removes only the owner's matching document chunks and file; failed cleanup stays pending with error type and attempt count. Tombstones immediately deny document retrieval even if physical cleanup is still pending.

Export the latest deletion journal regularly with `python -m app.services.deletion_journal export`. Keep this identifier-only file independently of old backups, encrypted and restricted. It is operational evidence, not a public download. Set retention for journals, uploads, audit, usage and backups before real-user pilot. Export current signed authority with the journal exporter below; deletion tombstones alone do not encode sharing or role changes.

## Backup and restore

From the repository root, preview `scripts/operations/backup.sh deploy/staging.env /restricted/backups/NEW_DIRECTORY`. Add `--apply` for a consistent pilot backup: the script stops backend writers, exports PostgreSQL, uploads and deletion evidence, writes checksums, then restarts the backend. All other writer processes must also be stopped. Chroma is a derived cache, rebuilt from authorized documents rather than restored as authoritative data. Copy backups and the continuously refreshed deletion journal to restricted encrypted off-host storage. The example `deploy/smart-exam-backup.timer.example` timer is a starting point; select retention and verify the schedule/notifications before installing it.

Restore only into a fresh project, empty database and empty uploads volume. Supply current deletion evidence outside the old backup directory:

```bash
scripts/operations/restore.sh deploy/restore.env /restricted/backups/SNAPSHOT /restricted/journals/current.json ADMIN_ID
CURRENT_AUTHORITY_JOURNAL=/restricted/journals/current/authority.json \
  scripts/operations/restore.sh deploy/restore.env /restricted/backups/SNAPSHOT /restricted/journals/current/deletions.json ADMIN_ID --apply
```

The script verifies checksums and safe archive paths, refuses a nonempty target, restores DB/uploads, migrates, reconciles deletions and retries cleanup. It leaves the backend stopped. Before reopening, verify current user locks/roles/token revocations and sharing revocations against post-backup evidence; compare ledger totals, saved exam links, file hashes and tombstones; confirm deleted material cannot be served from SQL/files/RAG. Record elapsed restore time (RTO) and actual backup/deletion-journal age/data-loss window (RPO). A successful dump is not restore proof.

## Account/provider incident

Close admission, preserve restricted audit evidence, revoke affected provider credentials at the provider and replace backend configuration. Revoke affected user sessions by incrementing token versions or locking accounts through supported administration; verify old JWTs fail. Rotate signing secrets with care: MFA uses independent `MFA_ENCRYPTION_KEY`; rotating `SECRET_KEY` revokes JWTs without changing MFA encryption. Legacy deployments must convert their MFA records before adopting the independent key. Recovery codes are one-use and hashed; never print their values in logs. OAuth-only super admins need a local password before MFA enrollment/step-up.

Test recovery in the isolated rehearsal first. Roll back to a tested compatible image; never restore over active writers or drop tables to resolve an incident. See [deployment](production-deployment.md) and [security evidence](security-validation.md).


## Current authority journals and key rotation

Preview `scripts/operations/export-journals.sh DEPLOYMENT_ENV /restricted/journals`; `--apply` exports a signed consistent authority snapshot and deletion IDs, validates JSON, writes checksums and atomically replaces a `current` symlink. Keep its directory mode 0700/files 0600. The example journal timer refreshes every five minutes; install only after setting alerting and encrypted off-host copying. Export and preserve a fresh journal after any MFA encryption-key rotation. Retain the old key securely for decrypting retained backups, but use the current journal/key pair for reconciliation.

Restore now requires `CURRENT_AUTHORITY_JOURNAL` pointing outside the old backup. It rejects evidence older than 24 hours, invalidates restored sessions, reapplies current roles/locks/status, resets changed passwords, quarantines changed identity/MFA mappings and resets all document shares to private. Owners must re-share deliberately. This can leave the restored operator quarantined when MFA changed after the backup; keep access closed and use supervised recovery. No automated bypass or backend start is provided.

To convert legacy MFA encryption or rotate its key: stop backend writers; take a verified backup; set `MFA_ROTATION_OLD_KEY` and `MFA_ROTATION_NEW_KEY` in a restricted operator environment (never CLI argument values); run `python -m app.services.mfa_rotation --actor-id ADMIN_ID` for dry-run, then `--apply`. For legacy conversion the old key is the former JWT signing secret. Only after successful conversion set `MFA_ENCRYPTION_KEY` to the new key, export new journals, restart and verify MFA/recovery in staging. All records change in one transaction; a decrypt failure rolls back. A rollback image must understand the same encryption-key contract, or the operator must reverse the conversion while writers remain stopped.

`python -m app.services.document_orphans --limit 100` lists referenced, cleanup-recorded, unknown and symlink entries with a continuation cursor. Unknown ownership is review-only; it never removes files automatically.

Retention is not silently imposed on existing teacher data. Before pilot, record approved durations for original/extracted documents, shared derived exams, account identity, audit/usage and encrypted backups, plus cleanup cadence and off-host destination. A practical pilot proposal is daily database/uploads backups, a five-minute authority/deletion journal, a daily cleanup review and 30-day backup retention; this is a proposal until the operator confirms requirements. Test restore before deleting any backup, preserve journals needed for all retained backups, and report provider/backup retention separately from local deletion.
