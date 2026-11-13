---
name: loom-use
description: Connect to Loom, install or update Loom Use, and submit or inspect Jobs, Components, Tools, Profiles and results through Loom MCP. Not general host administration.
---

# Loom Use

The Runtimes workspace groups Profiles, Components, Tools and Runtimes. Components define Job lifecycles;
Tools implement research software used within Jobs; Profiles freeze software and
environment revisions. Keep these concepts distinct. The six MCP groups retain
their existing names, including `components` for Component/Tool/Profile actions.

Resolve this Skill's installed path; the client root is two directories above it.
For initial setup read that root's INSTALL.md. For a different Loom address or
connection problems read docs/connections.md, then run the documented client command.
Never hand-edit client configuration or infer identity from the Linux user.

Start a new session/reconnection with system.status and system.guide. The server
manifest declares client_release, contract_revision and guide_revision. Compare
with the selected connection profile using the client `doctor`. If client_release
changed, follow docs/updates.md and run `update` under the authorized client-update
scope. This is an agent-driven check, not a resident watcher. If local execution is
unavailable, report the required update instead of claiming it happened.

Use connections list/use to switch servers; keep old profiles. Never forward a saved
token to another endpoint. Ask only for missing information. Check that the actual
project directory exists before registration/reconnection.

Fetch action arguments from system.describe and relevant operational guides from
system.guide. Compare Loom response markers; refresh changed guides/schemas only.
A cached catalog or standalone transport does not establish this chat's readiness.
Report config, transport and actual Codex runtime independently.

Submit with a stable idempotency key, retain Job IDs and use events.list(kind=all)
for completion/errors. Ack is receipt; recovery.claim owns a repair lease. Loom runs
Jobs independently. Agent supervision/recovery policy belongs to the caller.
Do not spawn supervisors, rewrite databases, issue tokens, or install server software
as an entry step. Existing Job/profile pins remain unchanged by client updates.


## Job unit and internal batching

Treat one requested generation/training/evaluation outcome as one logical Job.
Batching, vectorization, parallel workers and per-case checkpoints are internal
execution units. For multiple Profiles or resource stages, discover
`jobs.submit_workflow` and submit one pinned execution graph when advertised.
Each node retains its actual Attempts, resource ownership and verified outputs;
link/report the returned main Job once. Use a stable request reference when
available, including Pale's `loom_context.request_ref`, without requiring Pale.
Use `presentation.scope=operations` for platform installation/runtime acceptance
and keep technical receipts as supporting outputs. Explicitly requested research
diagnostics remain research; names such as smoke do not decide their purpose.
On older servers, follow the advertised jobs guide rather than inventing fields.

Preserve existing fragmented execution and exact output provenance. With explicit
authorization, one continuation Job may verify and reuse completed inputs; never
regenerate completed scientific conditions just to clean up a Job list. Queue
holds, operator dispatch pause, running-process return and Job completion are
distinct. Only resume an operator pause when the requested correction is ready.

## Execution environments

When the server advertises Runtime discovery, read system.guide runtimes and
components.runtimes/get_runtime through the live schemas. Profiles select exact
Runtime revisions; dependencies belong to that environment, not the Loom client.
For explicitly requested installation, a host-capable administrator agent follows
the server Runtime workflow using the dependency directory configured for that
installation. Never assume /dependencies, change existing Job pins or claim a
declared inventory proves GPU/Sim compatibility. Without host authority, report
the concrete installation plan; MCP/client refresh cannot grant that authority.

Before registering a Component/Profile, discover existing kinds with
components.profiles and inspect suitable candidates with components.get_profile.
Reuse a compatible exact kind for new Jobs; vary params/inputs for cases, seeds and
run settings. Do not register task-named copies just to change a Job ID or output
path. New source, interfaces, stage commands or Runtime pins require a new revision;
state that concrete reason and reuse unchanged Tool revisions. Category tags are
display metadata, never execution permissions. Read the connected server's current
components guide and annotate schema before changing classification metadata.
