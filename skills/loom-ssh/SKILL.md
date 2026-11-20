---
name: loom-ssh
description: Resolve and inspect Loom output files, analyze archives in place, transfer selected files or author software drafts through local access or an existing SSH grant. Use Loom Jobs for long-running or GPU work.
---

# Loom host access

Resolve the client root two directories above this Skill. Run `python3 <client-root>/loom_use.py ssh resolve FILE_ID` with `--name NAME` for a named connection. Read [the SSH how-to](../../docs/ssh.md) for probe options and errors. If the helper is unavailable, use the connected server's `items` guide.

- `mode: local`: use the current OS user and local tools. Do not SSH back into this host or create another account.
- Remote: reuse an already authorized user-supplied connection (`--ssh-target USER@HOST`), or use the managed personal account. If a grant is missing, report the Dashboard Admin → Tailscale → SSH requirement. An MCP token is not an SSH credential.
- Preserve host-key verification. Confirm an unknown key through the administrator or trusted host information before saving it.

Resolution returns metadata, not proof of file access. Request `--probe` for account/file/Python checks and add `--verify` only when a whole-file SHA-256 read is needed. Supply an existing host interpreter with `--python`; a container Runtime path is not a host executable. Missing readers call for another suitable environment or an authorized Runtime setup, not automatic package installation by this helper.

Keep large files on the host and inspect archive members in place. `--member` is an unverified relative hint, not an extraction request. Follow current copy locators and explicit manifests instead of retired paths; partial search results do not establish file absence.

Use the personal workspace and existing filesystem permissions. Missing access does not grant the service identity, sudo or Docker. Transfer only task-relevant files. For software drafts, load the server's `components` and `authoring` guides and use the configured dependency root. Register exact revisions through MCP. Short file inspection and CPU summaries may use local/SSH tools; submit long-running or GPU work through the Loom queue. Mutable draft files do not change accepted Job pins.
