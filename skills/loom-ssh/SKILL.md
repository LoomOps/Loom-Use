---
name: loom-ssh
description: Read or transfer files and author Component, Tool or Profile drafts on a Loom host using local filesystem access or an existing personal SSH grant. Use Loom MCP for execution and result registration.
---

# Loom host access

Resolve this Skill's directory and run `python3 ../../loom_use.py ssh info` there. Use `--name NAME` for a named connection. Read `docs/ssh.md` in the client root for setup and failures.

- `mode: local`: use the current OS user and local tools. Do not SSH back into this host or create another account.
- Remote: reuse an already authorized user-supplied connection, or run `ssh doctor` for the managed personal account. If a grant is missing, report the Dashboard Admin → Tailscale → SSH requirement. An MCP token is not an SSH credential.
- Preserve host-key verification. Confirm an unknown key through the administrator or trusted host information before saving it.

Use the personal workspace and existing filesystem permissions. Missing access does not grant the service identity, sudo or Docker. Transfer only task-relevant files. For software drafts, load the server's `components` and `authoring` guides and use the configured dependency root. Register exact revisions through MCP and submit execution through the Loom queue. Mutable draft files do not change accepted Job pins.
