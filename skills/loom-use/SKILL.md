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
| Reuse a Dataset or publish a derived variant | `results`, then the exact lineage action schema |
| Find files and logs | `items` |
| Reconcile selected existing assets | `reconciliation` (or `items`) |
| Recover an error | `recovery` |
| Pin task/protocol context | `scenarios` |

Keep the original accepted request and stable key after an uncertain response; retain the returned Job ID. One requested outcome normally maps to one logical Job with internal batches or a workflow. Reuse compatible exact Profiles before creating new revisions. Client or guide updates never repin existing Jobs. Event ACK records receipt; `recovery.claim` acquires a repair lease.

Compare response `_meta.loom` / onboarding revisions after reconnect or a version change. Refresh changed guides and schemas. Missing guide IDs on older servers are a reason to use that server's index, not invent newer fields.

Before creating a Dataset variant, find the existing parent and retain its exact reference. Follow the server guide to distinguish relocation, condition selection, partial reuse and new data generation. Shared Task membership and general input consumption do not establish derivation. Publish typed output facts; do not fill missing research fields or write generic Overview prose.

## Client tasks

The client root is two directories above this installed Skill. Read its `INSTALL.md` for requested initial setup, `docs/connections.md` for switching/repair, and `docs/updates.md` for a declared client-release change. A working Job task does not require reinstalling or running a full doctor. Preserve named connections and keep credentials private to their endpoint.

Report configuration, transport and this chat's MCP readiness separately. Use actual tool results; unavailable app refresh tools do not establish runtime readiness. Optional host authoring/file work uses `loom-ssh` and an existing grant. Server administration and global reconciliation require their own requested scope.
