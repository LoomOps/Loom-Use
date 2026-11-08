# Install Loom Use

This installs a client, not a Loom server. Use the current agent machine and current
OS user unless the user explicitly selects another target. Do not ask again for a
client, machine, profile or endpoint already known from the server handoff.
Python 3.11+ and Codex are required. Do not use sudo to configure the client.

1. Read this file and [connections](docs/connections.md). Confirm the actual project
   directory exists. If it does not, report the path mismatch; never hide it with
   an invented directory or symlink. Use the pinned release supplied by Loom.
2. Use the endpoint supplied by the installer/user. If absent, ask only which Loom
   address to connect to. A Gateway URL can resolve to its private Dashboard.
3. Run `python3 loom_use.py connect <address>` in this checkout. The script detects
   existing configuration, validates the server, obtains its exact required client
   release, installs the Skill and registers Streamable HTTP as `loom-use`.
   Resident/tagged clients use an Admin token. The hidden prompt explains where to
   obtain it. Do not issue it via sudo or copy a server owner credential.
4. The command attempts to refresh the **running** Codex app-server and Skills.
   Pass `--thread-id <current-thread>` if the client does not provide CODEX_THREAD_ID.
   If the control API is unavailable, use the client's supported MCP Restart action
   and verify real tool calls. Do not restart a daemon or claim that a separate
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
