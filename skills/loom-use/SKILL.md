---
name: loom-use
description: Connect to Loom, install or update Loom Use, and submit or inspect Jobs, components, profiles and results through Loom MCP. Not general host administration.
---

# Loom Use

Resolve this Skill's installed path; the client root is two directories above it.
For initial setup read that root's INSTALL.md. For a different Loom address or
connection problems read docs/connections.md, then run the documented client command.
Never hand-edit client configuration or infer identity from the Linux user.

Start a new session/reconnection with system.status and system.guide. The server
manifest declares client_release, contract_revision and guide_revision. Compare
with the selected connection profile using the client `doctor`. If client_release
changed, follow docs/updates.md and run `update` under the authorized client-update
scope. This is an agent-driven check, not a resident watcher. If local execution is
unavailable, report the required update instead of claiming it happened.

Use connections list/use to switch servers; keep old profiles. Never forward a saved
token to another endpoint. Ask only for missing information. Check that the actual
project directory exists before registration/reconnection.

Fetch action arguments from system.describe and relevant operational guides from
system.guide. Compare Loom response markers; refresh changed guides/schemas only.
A cached catalog or standalone transport does not establish this chat's readiness.
Report config, transport and actual Codex runtime independently.

Submit with a stable idempotency key, retain Job IDs and use events.list(kind=all)
for completion/errors. Ack is receipt; recovery.claim owns a repair lease. Loom runs
Jobs independently. Agent supervision/recovery policy belongs to the caller.
Do not spawn supervisors, rewrite databases, issue tokens, or install server software
as an entry step. Existing Job/profile pins remain unchanged by client updates.
