# Optional Loom SSH

`python3 loom_use.py ssh install` installs the additional loom-ssh Skill from the
selected, verified client release. It creates no server account or private key.
`ssh info` refreshes the selected server's personal connection descriptor and caches
it in that connection profile. `ssh doctor` verifies the remote Unix username without
changing the server. All commands accept `--name NAME`.

Same-host detection compares local Tailscale addresses with authenticated server
metadata. It never assumes that a hostname or the current Linux username establishes
identity. Same-host agents use local tools with the current OS account. MCP keeps its configured authentication.
When detection cannot establish locality, do not infer it or bypass SSH authentication.

Existing manually configured SSH connections remain usable without provisioning.
Managed remote connections use the personal Tailscale identity and an Admin-enabled
Unix account. Tagged clients are not automatically mapped to a person. Strict host
key checking remains enabled; first-use trust is a separate check, not an auth error.

Personal Component/Tool/Profile sources are editable drafts. Register them with
Loom MCP; do not change immutable runtime revisions. Shared storage permissions are
configured on the host separately. Disabling SSH retains the home and does not cancel
Jobs. Updating Loom Use preserves optional Skill selection and connection profiles.

## Resolve a registered File

Discover the exact File ID through the selected server's `items` guide. Then run:

```sh
python3 loom_use.py ssh resolve "$file_id" --name science
python3 loom_use.py ssh resolve "$file_id" --name science --probe --python "$python_path"
python3 loom_use.py ssh resolve "$file_id" --name science --probe --verify --python "$python_path"
```

`science` is an existing named connection; omit `--name` to use the active one.
`python_path` is an existing absolute **host** Python path chosen from available
environment information or the user's configuration. Omitting it uses `python3`.
An interpreter path inside a container Runtime is not a host executable. Use a
compatible Loom Job for that Runtime; this client never installs packages or
invokes Docker to make an interpreter available.

The first command reads only `system.status`, `system.ssh` and `results.get_file`.
It checks the saved machine identity and joins a registered copy's storage ID to
the server's configured storage selector and host root. `locations` retains the
other copies. `--copy N` selects the zero-based index from that list. No file bytes
are returned through MCP. No connection, Skill, credential or server setting is
changed. The same-host result retains `data_paths` and uses the current OS user.

`state: resolved` means the metadata maps to a path, not that the account has
read it. `ssh_access_required` still includes that path but does not attempt a
login. A foreign-machine copy or unsupported source is reported without guessing
another server or forwarding credentials to it. Select its existing owning
connection explicitly. Historical machine IDs may retain their pre-migration
name; use the connected server's descriptor, not that name as a hostname.
An older File with unrecorded size or SHA-256 retains its metadata and location;
`content_identity_unrecorded` prevents this helper from claiming an identity check
or running a probe against an invented content identity.

`--probe` executes a fixed read-only script locally or over SSH. It checks the
remote Unix account when applicable, storage marker, regular file, size, actual
read permission and the chosen Python's `numpy`/`h5py`/`torch` availability. Missing
packages are reported, never installed. Symlinked roots or path components are
rejected. Failure states distinguish missing files, permission denial, changed
storage/size, interpreter/SSH failures and timeouts.

Only `--probe --verify` reads the whole selected file to compare its SHA-256; large
files may exceed the probe timeout. Treat `probe.verified` and
`content_verification` separately: a readability probe does not verify content.
This is a point-in-time client check, not a server verification receipt or a new
artifact registration. Recheck expected bytes when using mutable files later.

For an already authorized manual connection, add `--ssh-target USER@HOST` and,
if needed, `--ssh-port PORT`. This uses that existing route without creating an
account, key or Tailscale grant. Its hostname is explicitly user-selected; storage
and content checks do not independently authenticate a Loom installation there.
Known-host checking stays enabled. Same-host access remains local.

## Analyze files in place

Use the resolved location and an existing suitable interpreter for short file
inspection and CPU summaries. Keep large archives on the host. `--member PATH`
retains a relative archive-member hint; it does **not** read, verify or extract that
member. An agent can inspect the selected TAR/ZIP in place with its available
libraries. Write derived working files in the personal workspace, preserving
source bytes. Long-running or GPU work goes through Loom Jobs.

File inventory covers registered members. Archive contents and legacy working
files may require following the output manifest, current binding or preserved
reference index. A partial search or zero hits does not prove filesystem absence.
Resolve retired paths against current locations instead of repeating old paths on
another host. Do not run a whole-store reconciliation to answer one file question.

## Account permissions

Dashboard Enable creates the entered `loomu_…` Unix account and joins the
installation's dedicated data-sharing group. The Unix password stays locked;
Tailscale authenticates the permitted identity. An MCP token is not an SSH password.
The current shared data ACL permits read/write access, with directory defaults.
No `ax`, sudo or Docker membership is added. Reading still requires file read and
ancestor traversal permissions. Dependency/interpreter access is separate from
registered data-store access; a successful account login does not prove either.
