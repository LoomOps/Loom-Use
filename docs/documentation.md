# Documentation and Skill maintenance

Client setup, authentication, named connections, update linkage and Codex refresh belong here. Server schemas, research workflows and implementation policies belong to Loom's running `system.guide` / `system.describe`. Link to them rather than maintaining another copy.

| Surface | Purpose |
|---|---|
| README | Human entry and task navigation |
| INSTALL / docs how-to | Concrete prerequisites, commands, observable outcomes and failure handling |
| clients/README | Maintainer implementation map |
| Skills | Trigger and short routing, plus non-obvious constraints needed for that task |
| verification | Tested boundaries and limits |

Keep Skill frontmatter specific and the body short. Load optional references only for the task at hand. Do not make connection repair, doctor, SSH enrollment or installation a prerequisite for an already working Job task. Assume programming/tool competence; explain only client-specific behavior. Distinguish local configuration, server transport and active-chat readiness. Use exact command names and preserve the user's scope.

Inventory every Markdown file in `documentation-catalog.json`; classify new documents and check local links with `python3 docs/documentation.py check`. Run the client test suite and deterministic packaging after instruction changes. Use the server fixture for actual schema/workflow acceptance. Never claim agent behavior from prose or string-matching tests alone.

These conventions follow the audience separation in [Diátaxis](https://diataxis.fr/start-here/), [OpenAI skill guidance](https://learn.chatgpt.com/docs/build-skills), [OpenAI skill-creator](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md) and the [Agent Skills specification](https://agentskills.io/specification). See [Loom's documentation contract](https://github.com/LoomOps/Loom/blob/main/docs/DOCUMENTATION.md) for the shared standard.
