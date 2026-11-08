# Loom Use development

This repository owns client installation, connection profiles, authentication setup,
Codex refresh and the loom-use Skill. Server features and authoritative action
schemas belong to LoomOps/Loom. Use English for distributable documentation.

Never commit credentials, personal Codex configuration or machine identities.
Tests use temporary homes and mock external Codex/Tailscale boundaries. Run
`python3 -m unittest discover -s tests -v` and `python3 package.py --output /tmp/loom-use-package`.
Loom integration CI must exercise this pinned release against its real MCP server.
Read docs/verification.md when changing a feature and update matching tests.
No automatic daemon restart, token issuance, Job mutation or foreign-host access.
