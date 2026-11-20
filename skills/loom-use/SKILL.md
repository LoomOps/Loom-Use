---
name: loom-use
description: Use Loom MCP to discover software, create or inspect Jobs and results, author Components/Tools/Profiles, or reconcile selected assets. Also use for Loom Use client setup, connection repair and updates. Not general host administration.
---

# Loom Use

Confirm the destination and permissions with `system.status`. Use `system.guide` for task routes and `system.describe({group,action})` for exact inputs. Follow the connected server's advertised actions and guides.

| Task | Server guide |
|---|---|
| Submit a research outcome or supporting Unit | `jobs`, then the relevant `job-cases` or `job-intake-cases` example |
| Inspect, control or recover execution | `jobs`, `job-control-cases` or `recovery` for the operation |
| Reuse a Profile or author software | `components`; `authoring` for source or `runtimes` for environments |
| Register, publish or supplement scientific results | `catalog-cases`; `metadata` or `reporting` for the contract |
| Read files or repair their bindings | `items` for reads and `reconciliation` for selected assets |

Use exact reads for progress and completed-result comparisons. Before submitting, resolve required inputs from the request, exact prior records and current Profile defaults. Ask about required choices still unresolved. Use a stable key to replay an uncertain submission. Follow `workflows` for plans and `results` for publication, imported data and Dataset lineage. Before choosing an output format, inspect the closest comparable record and its exact template.

After reconnect or an installation change, refresh guides and schemas whose revision changed. Follow older servers' own guide index.

## Client tasks

Resolve the client root two directories above this Skill. Read `INSTALL.md` for requested setup, `docs/connections.md` for connection changes, or `docs/updates.md` for a server-declared client update. Verify active-chat readiness with calls through this chat's MCP tools.

For host file work, use the server's `items` guide and an existing local or SSH grant. The optional `loom-ssh` Skill covers File resolution and host probes.
