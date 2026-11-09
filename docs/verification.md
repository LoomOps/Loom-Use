# Verification blocks

| Block | Contract | Regression scope |
|---|---|---|
| release | Trusted repository, exact version/checksum, immutable directories | Wrong hash, traversal, noncanonical ZIP aliases, duplicate, internal/ancestor symlink, injected source, cache tamper; generated Python bytecode allowed |
| profiles | Named endpoints, isolated credentials, atomic configuration | Repeated setup, collision, switch failure, foreign registration on disconnect/default switch, unrelated settings, concurrent writer preservation during credential writes and rollback |
| auth | Real Tailscale user or Admin-issued Loom Agent Token | Tagged client, rejected token, no leakage, exact-endpoint adoption, explicit Tailscale overriding saved headers |
| Codex | Existing process refresh; thread status AND live calls | Real Unix-socket HTTP Upgrade, masked frames, fragmented replies/ping, direct and symlink sockets, broken/loop/foreign-owner selectors, ambiguous fallback, refused connection, missing cwd/client/socket, optional thread refresh, timeout, cached catalog, actual tool error |
| update | Server declaration, per-profile release selection | No change, version change, download failure, preserved token |
| SSH | Local detection, personal remote account, strict host keys | Same host without account, wrong host/user, disabled access, live username check, optional Skill rollback |
| server contract | MCP initialize/list/status/guide, JSON/SSE response identity/envelope | Loom CI tests the released client against its actual HTTP server |

Unit tests cannot prove a particular desktop application's control socket is
available, nor remote TLS/Sharing or reboot behavior. Record those separately.
Configuration and standalone Python transport success never imply active-chat success.

Release workflow: test client, build deterministic ZIP, publish Loom Use first,
then update Loom's pinned client-release.json and run cross-repository tests before
publishing Loom. Source-only edits do not change an installed client automatically.

Codex control sockets use WebSocket-over-Unix, not JSONL. The integration fixture
performs the real HTTP Upgrade and rejects unmasked frames. No fake JSONL executable
stands in for the transport. Actual runtime verification still requires the chosen
thread to report connected and complete both system.status and system.guide.
Refreshing an existing control socket does not require a `codex` executable on PATH.

## Installation preflight and diagnostics

Preflight must report the first missing parent without creating it. Connect tests
actual Skill directory writes before network calls/config mutation. Permission
failures preserve existing configuration. Collector tests cover secret exclusion,
private files, rotation, duplicates, busy writers, concurrent writes and symlinks.
The JSONL envelope is `loom-diagnostic/v1`, shared with Loom; neither product uploads
records automatically. Runtime pending remains separate from installation failure.
The client collector reads the client VERSION and uses CODEX_HOME/loom-use, rather
than server `/loom` defaults. The legacy guide helper rejects symlink cache paths
and archive aliases and redacts exception text that could contain a credential.

Transport regression includes JSON/SSE error results with structured diagnostic
IDs and Loom revision metadata: these must pass through unchanged, not become a
successful result or lose their correlation fields. External integration runners
can pair current Loom and Loom Use source with their adapters; this is separate
from testing an immutable published client release.

## Research Tools and administrator migrations

The transport remains generic across the six groups: optional components Tool
registration/discovery and exact Tool pins pass through without rewriting source,
credentials or Job arguments. Server guides own these schemas. Administrator
migration plans/scripts are separate from client update/guide refresh: a client
never executes them, chooses rebuild, or registers operational research software
as a side effect of connection. Use immutable release checksums and the selected
server's declaration; no new client code is required for these additive actions.

**Extensions** is the Dashboard grouping for Components, Tools and Profiles. It is
not a replacement API group name. Client cache checks detect accidental or external
file changes under the current OS user's trust boundary; the local receipt is not
an independent signature against that same user rewriting the entire cache.
