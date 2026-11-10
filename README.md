# Loom Use

User-side tools and Codex Skills for [Loom](https://github.com/LoomOps/Loom).
Connect to a Loom server, preserve named connections, configure authentication,
refresh Codex MCP, and follow the client release declared by that server.

Give an agent this repository and the Loom address, then have it read [INSTALL.md](INSTALL.md).
Server installation is separate. Python 3.11+; no Python package dependencies.

```sh
python3 loom_use.py connect https://loom-machine.example.ts.net
python3 loom_use.py connections list
python3 loom_use.py connect https://second.example.ts.net:8443 --name second
python3 loom_use.py connections use second
python3 loom_use.py doctor
python3 loom_use.py update
python3 loom_use.py reconnect --thread-id CURRENT_THREAD_ID
```

Tokens are entered only in a hidden interactive prompt. Settings live under
`$CODEX_HOME/loom-use` (default `~/.codex/loom-use`), not in this checkout.
See [connections](docs/connections.md), [updates](docs/updates.md),
[verification](docs/verification.md), and [developer guide](AGENTS.md).
Server action schemas and operational guides come from `system.describe` and
`system.guide`; this package is not a second source of server contracts.

License: GPL-3.0. See LICENSE and THIRD_PARTY_NOTICES.md.

Optional host file analysis and component authoring use [Loom SSH](docs/ssh.md).
Install it with `python3 loom_use.py ssh install`, inspect with `ssh info`, and
verify remote access with `ssh doctor`. Same-host mode uses local files without SSH.

The Dashboard groups software under **Extensions**, with separate Components and
Tools filters. A Component owns a Job lifecycle, a Tool is research software called
inside a Job, and a Profile pins their versions and execution environment. The MCP
group is still named `components`; discover its Tool/Profile actions from the server.

A Job represents one requested outcome. Physical batches and vectorized work
belong inside that Job by default. The connected server's Job guide specifies
internal progress and explicit consolidation of preserved prior execution.
