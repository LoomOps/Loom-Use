---
name: loom-ssh
description: Analyze files, transfer data, or author Component, Tool and Profile drafts on a connected Loom host using local filesystem access or an existing personal SSH account. Use Loom MCP for Job execution and result registration.
---

# Loom SSH

Use the installed Loom Use client beside this Skill: resolve this file's directory,
then run `python3 ../../loom_use.py ssh info` from it. A named connection accepts
`--name NAME`. Read the selected connection, not a remembered machine address.

If the result says `mode: local`, work as the current OS user with local tools.
Do not SSH back into this machine or request another account. Missing file permissions
remain real; do not borrow the `loom` service identity or sudo implicitly.

For a remote host, use `ssh doctor` to verify the personal account. Reuse an existing
user-supplied SSH connection when it is already authorized for that host; no managed
account is required in that case. Otherwise, if access is not enabled, direct the user
to Dashboard → Tailscale → SSH (Admin). An MCP token never authenticates SSH.
A tagged source device does not prove the person's Tailscale identity; report that
boundary rather than inventing a key-issuance or account-creation workaround.

Use the returned SSH argv/username and preserve host key verification. For a first
connection, verify an unknown host key through the machine administrator or trusted
Tailscale information before saving it. Keep connection and credential caches local.

Write analyses and Component/Tool/Profile drafts in the personal home/workspaces. Read
registered data paths with the current filesystem permissions. Register drafts via
Loom MCP; running Jobs use frozen revisions, not mutable drafts. Submit GPU work
through the Loom queue. Never edit the platform DB, secrets, or execution receipts
to register a result or repair a Job. Transfer only the files needed for the task.

The Dashboard calls their shared inventory Extensions. Registration does not prove
runtime readiness, and renaming a UI section never rewrites existing Job pins.
