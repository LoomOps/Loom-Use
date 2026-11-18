---
name: loom-use
description: Use Loom MCP to discover software, create or inspect Jobs and results, author Components/Tools/Profiles, or reconcile selected assets. Also use for Loom Use client setup, connection repair and updates. Not general host administration.
---

# Loom Use

For a working connection, call `system.status` to confirm the destination and permissions. Read `system.guide` for the guide index, then load only the topic needed for the task. Use `system.describe({group})` for an action index and `{group,action}` for exact inputs. The connected server, not a cached Skill, defines available features.

| Task | Server guide |
|---|---|
| First Job | `quickstart` |
| Submit, inspect or control execution | `jobs` |
| One outcome with multiple stages or prior runs | `workflows` (or `jobs` on older servers) |
| Reuse or create software | `components`, then `authoring` when writing source |
| Choose or install an environment | `runtimes` |
| Publish or reconnect outputs | `results` (or `jobs`) |
| Choose or extend an output format | `metadata` (or `results` on older servers) |
| Plan scientific evidence or report a hypothesis | `reporting`; use `jobs.preview_outcome` when advertised |
| Reuse a Dataset or publish a derived variant | `results`, then the exact lineage action schema |
| Find files and logs | `items` |
| Analyze output bytes or large archives | `items`, then optional `loom-ssh` with an existing local/SSH grant |
| Reconcile selected existing assets | `reconciliation` (or `items`) |
| Recover an error | `recovery` |
| Pin task/protocol context | `scenarios` |

Keep the original accepted request and stable key after an uncertain response; retain the returned Job ID. One requested outcome normally maps to one logical Job with producer-reported Steps or independently scheduled workflow Nodes. When the server advertises `jobs.create`, reserve the outcome before Runtime installation, then bind the open slot on the same ID with `jobs.revise_plan`. See the connected workflows guide. Select a compatible Profile for each execution. Its Stage runners select the environments. Reuse compatible exact Profiles before creating new revisions. Client or guide updates never repin existing Jobs. Event ACK records receipt; `recovery.claim` acquires a repair lease.
For a follow-up serving the same outcome, preserve the existing Main Job and follow the server `workflows` guide. Presentation grouping is distinct from workflow execution membership; keep exact execution ownership and failure history.

Compare response `_meta.loom` / onboarding revisions after reconnect or a version change. Refresh changed guides and schemas. Missing guide IDs on older servers are a reason to use that server's index, not invent newer fields.

Before publishing an output, find the most comparable existing record and inspect its exact metadata/template revision. Reuse a compatible registered format, or extend it when field coverage is missing. Copy structure rather than values or acceptance claims; follow the connected server guide for robot-first labels and unknown fields.

Before creating a Dataset variant, find the existing parent and retain its exact reference. Follow the server guide to distinguish relocation, condition selection, partial reuse and new data generation. Shared Task membership and general input consumption do not establish derivation. Publish typed output facts; do not fill missing research fields or write generic Overview prose.

## Client tasks

The client root is two directories above this installed Skill. Read its `INSTALL.md` for requested initial setup, `docs/connections.md` for switching/repair, and `docs/updates.md` for a declared client-release change. A working Job task does not require reinstalling or running a full doctor. Preserve named connections and keep credentials private to their endpoint.

Report configuration, transport and this chat's MCP readiness separately. Use actual tool results; unavailable app refresh tools do not establish runtime readiness. File discovery stays in MCP; use local/SSH tools for large-file inspection and short CPU summaries. The optional `loom-ssh` Skill resolves registered File IDs and checks the chosen host Python. A missing client helper does not require repairing a working MCP connection: follow the server `items` guide and an existing authorized route. Server administration and global reconciliation require their own requested scope.
