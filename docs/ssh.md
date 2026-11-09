# Optional Loom SSH

`python3 loom_use.py ssh install` installs the additional loom-ssh Skill from the
selected, verified client release. It creates no server account or private key.
`ssh info` refreshes the selected server's personal connection descriptor and caches
it in that connection profile. `ssh doctor` verifies the remote Unix username without
changing the server. All commands accept `--name NAME`.

Same-host detection compares local Tailscale addresses with authenticated server
metadata. It never assumes that a hostname or the current Linux username establishes
identity. Same-host agents use local tools; MCP keeps its existing token authentication.
When detection cannot establish locality, do not infer it or bypass SSH authentication.

Existing manually configured SSH connections remain usable without provisioning.
Managed remote connections use the personal Tailscale identity and an Admin-enabled
Unix account. Tagged clients are not automatically mapped to a person. Strict host
key checking remains enabled; first-use trust is a separate check, not an auth error.

The personal components/profiles directories are editable drafts. Register them with
Loom MCP; do not change immutable runtime revisions. Shared storage permissions are
configured on the host separately. Disabling SSH retains the home and does not cancel
Jobs. Updating Loom Use preserves optional Skill selection and connection profiles.
