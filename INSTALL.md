# Install Loom Use

This installs a client, not a Loom server. Use the current agent machine and current
OS user unless the user explicitly selects another target. Do not ask again for a
client, machine, profile or endpoint already known from the server handoff.
Python 3.11+ and Codex are required. Do not use sudo to configure the client.

1. Read this file and [connections](docs/connections.md). Confirm the actual project
   directory exists. If it does not, report the path mismatch; never hide it with
   an invented directory or symlink. Use the pinned release supplied by Loom.
2. Before requesting filesystem grants, run `python3 loom_use.py preflight`. Grant
   the reported write scopes, including a missing `~/.agents` parent. This command
   does not install or claim sandbox permissions; connect tests actual Skill writes
   before network/token/configuration work.
   Use the endpoint supplied by the installer/user. If absent, ask only which Loom
   address to connect to. A Gateway URL can resolve to its private Dashboard.
3. Run `python3 /path/to/loom-use/loom_use.py connect <address>` from the existing
   project directory, or add `--cwd /existing/project` when running in this checkout.
   `--cwd` defaults to the shell working directory; no project is auto-discovered or
   created. It controls project-scoped Skill refresh, not MCP registration scope. The script detects
   existing configuration, validates the server, obtains its exact required client
   release, installs the Skill and registers Streamable HTTP as `loom-use`.
   Resident/tagged clients use an Admin-issued Loom Agent Token. The hidden prompt explains where to
   obtain it. Do not issue it via sudo or copy a server owner credential.
4. The command attempts to refresh the **running** Codex app-server and Skills.
   Installation, user-scoped MCP registration and refresh do **not** require a thread ID.
   The optional `--thread-id` defaults to CODEX_THREAD_ID and only verifies actual
   tool calls in that chat; it is never stored in the MCP registration or profile.
   Do not ask the user for a thread ID when it is unavailable. Report refresh and
   chat verification separately, then verify with the agent's actual MCP tools.
   Normal user-owned control-socket symlinks are resolved and peer ownership checked.
   If refresh fails, inspect its reason/stage. Do not call a rejected or inaccessible
   socket an absent API. Discover and use an available agent-accessible MCP Restart
   tool before asking the user to click Restart. Verify real tool calls afterward. Do not restart a daemon or claim that a separate
   app-server proves this chat works. Newly installed Skills may only become visible
   on a subsequent turn, depending on the client.
5. Reread this checklist. Run `python3 loom_use.py doctor`, then call `system.status`
   and `system.guide` through the actual configured MCP. Report server identity,
   authentication method, client release, Skill/registration and actual runtime
   verification separately. No token values in output.

Current valid credentials are reused, including the former CODEX_HOME/loom helper
layout when the exact endpoint and configured helper match. Configuration for
other servers is preserved. Without a token, report client authentication pending;
a previously completed Loom server installation remains complete.

For a Git checkout use `git clone https://github.com/LoomOps/Loom-Use.git` and
checkout the tag specified by Loom. A checksum-verified release ZIP is the equivalent
source package; it contains this same INSTALL.md. Never silently follow main.

6. Offer optional Loom SSH for file analysis and Component/Tool/Profile authoring. If selected,
   run `python3 loom_use.py ssh install`, then `ssh info`. Same-host mode needs no
   SSH account; otherwise reuse existing authorized SSH or direct the user to Admin
   enablement. Run `ssh doctor` only for the intended remote connection. Read
   [SSH](docs/ssh.md). Never request an MCP token as an SSH credential.

Explicit `--authentication tailscale` removes the profile’s Bearer header without deleting its saved credential file. It never silently falls back after a rejected token. Reconnecting an existing profile also checks the server machine identity; disconnect that profile explicitly before binding a replacement server. Failed changes roll back only files/links still matching this operation’s writes, preserving concurrent edits by other tools.

Diagnostics are private local JSONL under `$CODEX_HOME/loom-use/diagnostics` (or
`~/.codex/loom-use/diagnostics`). Only allowlisted exception categories and code
locations are recorded; never token values or request bodies. Rotation is bounded
and no automatic upload occurs. See [diagnostics](docs/diagnostics.md).
