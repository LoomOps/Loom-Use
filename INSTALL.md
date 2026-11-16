# Install Loom Use

Use this procedure for requested client setup on the selected agent machine and OS account. It configures a client, not a Loom server. Prerequisites: Python 3.11+, Codex, an existing project directory, the Loom address and the server-declared exact client release. Reuse information already supplied in the handoff.

## Install and connect

1. Use the checksum-verified release package supplied by Loom, or check out its exact tag. Do not silently install `main` or GitHub latest.
2. Run `python3 loom_use.py preflight`. It reports required write roots and missing parents without creating them. If the environment denies a write, resolve that specific access failure using the available permission mechanism; do not use sudo for personal client configuration.
3. From the existing project directory, run:

   ```sh
   python3 /path/to/Loom-Use/loom_use.py connect https://loom-machine.example.ts.net
   ```

   Alternatively pass `--cwd /existing/project`. This supplies Skill-refresh context; it does not limit MCP scope or create a project. Add `--name NAME` for another connection.
4. Use the configured authentication method. A verified user-owned Tailscale device can use `--authentication tailscale`. Resident/tagged clients need an Admin-issued Loom Agent Token entered in the hidden prompt. Do not infer a person's identity from an OS username or reuse server management credentials.
5. The command verifies the server, selects its exact client release, installs the Skill, registers Streamable HTTP and attempts to refresh the existing Codex app-server. Run `doctor` for the resulting configuration, then call `system.status` and `system.guide` through this chat's actual MCP tools when available.

Report three results separately: local configuration, server transport and active-chat MCP calls. A standalone transport or cached tool catalog does not prove active-chat readiness. Installation and refresh do not require a thread ID. Optional `--thread-id` defaults to `CODEX_THREAD_ID` and verifies that chat only; it is never saved in a profile. Do not invent another thread to complete verification.

## Failures and subsequent changes

Inspect the reported refresh stage/reason. If an MCP Restart tool is actually available, use it for the selected connection and verify real calls afterward. Otherwise report refresh pending and the specific user action needed. A failed/refused socket is not proof that the API is absent. Do not start another daemon as a substitute for the existing session.

Existing credentials and other connections are preserved. Explicit `--authentication tailscale` removes the selected Bearer header but retains its protected credential file. Rejected explicit tokens do not fall back silently. A different server identity at the same endpoint requires an explicit disconnect before replacement. Rollback preserves concurrent edits that no longer match this operation's writes.

See [connections](docs/connections.md) for switching/repair, [updates](docs/updates.md) for release changes, and [diagnostics](docs/diagnostics.md) for private failure records. Optional [Loom SSH](docs/ssh.md) is a separate choice for host file work; normal MCP usage does not need it.
