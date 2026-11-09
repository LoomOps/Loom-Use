# Verification blocks

| Block | Contract | Regression scope |
|---|---|---|
| release | Trusted repository, exact version/checksum, immutable directories | Wrong hash, traversal, duplicate, symlink, cache tamper |
| profiles | Named endpoints, isolated credentials, atomic configuration | Repeated setup, collision, switch failure, unrelated settings |
| auth | Real Tailscale user or Admin token | Tagged client, rejected token, no leakage, exact-endpoint adoption |
| Codex | Existing process refresh; thread status AND live calls | Missing cwd/client/socket, timeout, cached catalog, actual tool error |
| update | Server declaration, per-profile release selection | No change, version change, download failure, preserved token |
| SSH | Local detection, personal remote account, strict host keys | Same host without account, wrong host/user, disabled access, live username check, optional Skill rollback |
| server contract | MCP initialize/list/status/guide | Loom CI tests the released client against its actual HTTP server |

Unit tests cannot prove a particular desktop application's control socket is
available, nor remote TLS/Sharing or reboot behavior. Record those separately.
Configuration and standalone Python transport success never imply active-chat success.

Release workflow: test client, build deterministic ZIP, publish Loom Use first,
then update Loom's pinned client-release.json and run cross-repository tests before
publishing Loom. Source-only edits do not change an installed client automatically.
