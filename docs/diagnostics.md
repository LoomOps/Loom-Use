# Local client diagnostics

Failures and pending Codex refresh outcomes are collected under
`$CODEX_HOME/loom-use/diagnostics`, or `~/.codex/loom-use/diagnostics`.
`--home` selects another client root. The directory is private (0700), records 0600.
The output is `events.jsonl` plus up to fifteen rotated backups, 64 MiB per segment (about 1 GiB total).
Identical categories are suppressed for 30 seconds per process.

The `loom-diagnostic/v1` envelope matches Loom's local collector: incident UUID,
UTC epoch timestamp, component, operation, code, build, exception class/errno and
up to 12 basename/function/line frames. No exception messages, source lines,
locals, request bodies, credentials, URLs or user identities are stored.

There is no network sender or automatic upload. A future development-server
collector can consume this schema independently. Read-only/full disks, lock
contention and invalid paths do not change the original operation's result.
A pending refresh is not an installation failure; actual current-chat tool calls
remain the readiness check. Records are best-effort diagnostics, not an audit log.

Set `LOOM_DIAGNOSTICS_SEGMENT_MIB` and `LOOM_DIAGNOSTICS_BACKUPS` in the client
environment to adjust retention. Invalid values use defaults; no space is preallocated.
