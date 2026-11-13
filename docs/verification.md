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
Guide-cache reuse verifies the complete file set and recorded hashes. Older caches
without a receipt are compared with a fresh server bundle before adoption; changed,
missing, extra or linked files are rejected and retained without overwrite. These
receipts detect cache changes within the current OS user's trust boundary.

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

The **Runtimes** workspace contains **Profiles**, **Components**, **Tools** and **Runtimes**. **Profiles**
is the default view for execution combinations. These labels do not replace
API group names. Client cache checks detect accidental or external
file changes under the current OS user's trust boundary; the local receipt is not
an independent signature against that same user rewriting the entire cache.

Runtime extension actions use the same generic transport and live server schemas.
The Runtime administrator workflow is separate from client installation: the Skill
reads the server runtimes guide, preserves exact Profile/Job pins and uses the
configured dependency directory. Client tests do not prove framework/GPU readiness.

Execution Profile combinations and optional usage declarations are server-owned
contracts. Multiple categories/modes are descriptive, not new client gates.
`components.assign_owner` changes display attribution while preserving namespace
and exact pins. Built-in denotes Loom-supplied software; all software remains
shared. The client never relabels research code, rewrites Profile revisions or
infers declared purpose from a name or observed Job.

The Skill directs discovery and exact-kind reuse before registration, separates parameter changes from source/contract changes, and keeps category annotations outside execution permissions. Actual agent behavior requires call-history and distinct logical-Job analysis; guide text alone is not proof of adherence.

Server-owned guides define components.curate, inspect_profile and compare_profiles. Existing clients fetch their schemas at connection; guide-only changes do not replace installed client code. Dependency representatives are references to installed metadata, and read-only inspection never submits Jobs or installs packages.
