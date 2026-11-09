# Connections and authentication

Use `connect URL` for first setup. Default registration is loom-use. For another
server use `connect URL --name second`, then `connections use second`. Switching
verifies the target before replacing the default MCP entry; prior profiles remain.
Use the named MCP entries to work with several servers concurrently. An occupied
name pointing elsewhere is never silently overwritten.

A Gateway origin is queried without credentials for its private Dashboard origin;
a different hostname must be supplied explicitly. No operational calls go to the
public Gateway. HTTPS is required except loopback. No secret-bearing redirects.
Actual MCP initialize/status/guide responses establish server identity, not an open
TCP port or a successful HTML page. An unexpected server replacement is reported.

Personal Tailscale identity can authenticate without a token. A client machine's
Tailscale tags indicate a service identity, not a person. Resident/tagged clients
must use Dashboard > Tailscale > Agent Tokens. Users can explicitly select
`--authentication token` or `tailscale`. Never use installer or management tokens.
The token is stored privately and reused; updates do not reissue it.

`connections disconnect NAME` removes local registration/profile, not the server
credential. It retains the protected credential file for deliberate recovery.
Revoke unused credentials in Dashboard Admin. Never infer remote revocation from
local disconnection. `connections list` excludes secret values and credential paths.

Doctor separates network/TLS, authentication, configuration, project cwd and Codex
runtime failures. ENOENT during helper startup is not evidence of a bad token.
A failed refresh reports its stage and reason; it does not establish that the control
API is absent. Use an available agent-accessible MCP Restart action before asking
the user to restart it, then verify actual tool calls. A fresh standalone app-server is not the active user's session.


`--cwd` defaults to the process working directory, not an automatically discovered
Codex project. Use an existing project explicitly when invoking the script from
an installation directory. It supplies the Skills refresh context, not a directory
to create or a restriction on MCP use.

`--thread-id` is optional and defaults to CODEX_THREAD_ID. It is used only for
current-chat status and two real tool calls; it is not saved in Codex registration,
a connection profile or credentials. Without it, successful reload reports
`status: refreshed`, `verification: unverified`. Configuration and server transport
can still be verified. Do not invent/select another thread or ask the user for an ID
just to complete installation. Use the current agent's MCP tools when available.
