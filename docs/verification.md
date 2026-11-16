# Verification blocks

| Block | Contract | Regression scope | Executable modules |
|---|---|---|---|
| release | Trusted repository, exact version/checksum, immutable directories | Wrong hash, traversal, noncanonical ZIP aliases, duplicate, internal/ancestor symlink, injected source, cache tamper; generated Python bytecode allowed | `test_client.py` |
| profiles | Named endpoints, isolated credentials, atomic configuration | Repeated setup, collision, switch failure, foreign registration on disconnect/default switch, unrelated settings, concurrent writer preservation during credential writes and rollback | `test_client.py` |
| auth | Real Tailscale user or Admin-issued Loom Agent Token | Tagged client, rejected token, no leakage, exact-endpoint adoption, explicit Tailscale overriding saved headers | `test_client.py`, `test_transport.py` |
| Codex | Existing process refresh; thread status AND live calls | Real Unix-socket HTTP Upgrade, masked frames, fragmented replies/ping, direct and symlink sockets, broken/loop/foreign-owner selectors, ambiguous fallback, refused connection, missing cwd/client/socket, optional thread refresh, timeout, cached catalog, actual tool error | `test_codex_websocket.py`, `test_client.py` |
| update | Server declaration, per-profile release selection | No change, version change, download failure, preserved token | `test_client.py` |
| SSH | Local detection, personal remote account, strict host keys | Same host without account, wrong host/user, disabled access, live username check, optional Skill rollback | `test_ssh.py`, `test_client.py` |
| transport | MCP JSON/SSE response identity/envelope | Preserve errors, revision metadata and exact Tool/Runtime arguments; external server contract acceptance remains separate | `test_transport.py` |
| guide cache | Version-scoped complete guide files | Unchanged reuse, verified legacy adoption, aliases, changed/missing/extra files and symlinks | `test_transport.py` |
| diagnostics | Private bounded fail-open collection | Secret exclusion, rotation, concurrency, symlink and busy writer rejection | `test_diagnostics.py` |
| verification | Current matrix matches executable modules | Missing/new/obsolete module references are rejected | `test_verification.py` |
| documentation | Complete document inventory, local navigation and portable Skill metadata | Added unclassified file, broken reference and invalid Skill name | `test_documentation.py` |

Run `python3 -m unittest discover -s tests -v` for these mapped regressions and
`python3 package.py --output <temporary-directory>` for packaging. Record actual
case outcomes and source hashes per block; skipped or failed cases are not passes.
The separate Loom CI server contract exercises initialize/list/status/guide through
the real fixture HTTP server. It is not implied by the client-only unit result.

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

## Evidence boundaries

The tests exercise private temporary homes, real Unix WebSocket framing and mock external service boundaries. Server schemas, Rust producer behavior, Runtime/GPU acceptance and actual agent Profile reuse are verified in Loom or call-history review, not inferred from these client tests.

The generic transport preserves large decimal-string IDs, exact revision selectors, opaque cursors, errors and revision metadata. Setup/update does not execute Cargo, migrations, Jobs or server installation. The local cache receipt detects changes within the current OS user's trust boundary; it is not a signature against that user rewriting the entire cache.

Review [documentation](documentation.md) separately: check local links, Skill metadata, task routing and the guide's ownership of server contracts. A wording check is not proof that an agent followed the instructions.
