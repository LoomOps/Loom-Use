# Loom Use

Client setup tools and agent Skills for [Loom](https://github.com/LoomOps/Loom). Connect to a server, preserve named connections, configure authentication and refresh an existing Codex session. Python 3.11+; no third-party Python packages.

For requested setup, read [INSTALL.md](INSTALL.md) and use the exact client release declared by the server. Settings live under `$CODEX_HOME/loom-use` (default `~/.codex/loom-use`), outside this checkout. Tokens use a hidden prompt.

```sh
python3 loom_use.py connect https://loom-machine.example.ts.net
python3 loom_use.py connections list
python3 loom_use.py connect https://second.example.ts.net:8443 --name second
python3 loom_use.py connections use second
python3 loom_use.py doctor
```

| Task | Reference |
|---|---|
| Install or verify this client | [Installation](INSTALL.md) |
| Switch, repair or disconnect | [Connections](docs/connections.md) |
| Configure optional Codex roles and Job follow-ups | [Agent Workflows](docs/agent-workflows.md) |
| Apply a server-declared client release | [Updates](docs/updates.md) |
| Resolve/analyze host files, transfer selected files or author drafts | [Optional SSH](docs/ssh.md) |
| Interpret local diagnostics | [Diagnostics](docs/diagnostics.md) |
| Change the client | [Implementation](clients/README.md), [developer instructions](AGENTS.md), [verification](docs/verification.md) |
| Maintain these documents and Skills | [Documentation contract](docs/documentation.md), [inventory](docs/documentation-catalog.json) |

Server concepts, action schemas and task workflows come from `system.guide` and `system.describe`; see the [Loom reference](https://github.com/LoomOps/Loom/blob/main/docs/README.md) for the source documentation. This client has no alternate Job schema and does not install frameworks, compilers or server updates on connection.

License: GPL-3.0-only. See LICENSE and THIRD_PARTY_NOTICES.md.
