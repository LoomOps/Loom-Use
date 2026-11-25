# Agent Workflows

Agent Workflows connects an existing Codex parent conversation to accepted Loom Jobs or Units. Loom executes Jobs and owns their state and outputs. The optional Loom Use observer records follow-up conditions and opens a Codex turn when a condition is met. Long waits do not require a Codex turn to remain active.

## Set up the selected conversation

Use a working named Loom Use connection first. These commands use the active connection unless `--name` is supplied.

```sh
python3 loom_use.py workflows models
python3 loom_use.py workflows install-profiles
python3 loom_use.py workflows attach --name research --thread-id EXISTING_PARENT_ID
```

Select an existing persistent parent. Attachment checks the exact connection and verifies `system.status` through the chosen conversation. The same named server must be available in that conversation. Only attach a Loom and Codex conversation you intend to use together. Attachments are bound to the endpoint, machine identity, principal and parent ID.

The profile installer reads the models and supported reasoning efforts from this Codex. It installs the supported defaults under the current Codex home's `agents/` directory. It preserves saved choices and refuses to overwrite an edited profile. `configure-profile ROLE MODEL EFFORT` applies a verified explicit choice. The manager setting applies to automatic follow-up turns. Use the usual Codex controls for interactive turns. A model recommendation in `doctor` or `update` is informational.

Run `python3 loom_use.py workflows install-mcp` to give the selected parent local tools for watch registration and acknowledgement, then reload the MCP server using the existing Codex workflow. It uses Codex thread metadata and the attachment before reading or writing the journal. Codex's configured tool approval policy applies. The CLI remains available for manual operation.

## Register a follow-up

Use actual IDs returned by Loom. A result follow-up on more than one record waits for every result.

```sh
python3 loom_use.py workflows watch --name research --job ACCEPTED_JOB_ID \
  --on result-ready --then 'Compare the accepted results with the pinned baseline.'
python3 loom_use.py workflows watch --name research --job ACCEPTED_JOB_ID \
  --on needs-attention --then 'Diagnose the failed Unit and report the recovery options.'
python3 loom_use.py workflows run --name research
```

`result-ready` requires completed state and accepted artifact availability. `needs-attention` follows failed execution or publication and targets the failed member Unit when Loom reports it. It waits while recovery is claimed, pending, or executing. `plan-binding` follows the connected server's explicit `bind_plan_slot` next action. Use `--unit` for standalone or specific Unit follow-ups. Adding the same watch a second time returns its original local ID.

Run explicitly in the foreground or under an existing user service manager. `run --once` performs one cycle. Without `--name` one observer covers the registered connections. `workflows status` shows its lock, watches, and deliveries. `workflows cancel WATCH_ID` cancels a waiting or unsent local follow-up. Loom's normal controls handle Job or Unit cancellation independently.

## Handle the follow-up

Use the structured `loom_use_job_followup` record in the parent conversation. It carries the registered request, evidence IDs, and delivery ID. Read the exact live records before taking any action. Prioritize active user requests. After reporting the requested outcome or recording the next decision, call the local `acknowledge` tool or run:

```sh
python3 loom_use.py workflows acknowledge DELIVERY_ID --name research
```

Check `workflows show DELIVERY_ID` for the exact saved record. `needs-review` indicates the returned turn ended before acknowledgement. `uncertain` indicates that the observer cannot prove whether a start was accepted. It looks for the exact delivery in Codex history and retains the record without starting a duplicate turn. User-directed investigation and acknowledgement can resolve outstanding decisions.

The observer checks recipient events first and rechecks only watched records. It also refreshes active watches at a bounded interval to cover events consumed elsewhere or omitted by the server. It never ACKs Loom events, changes a Job, claims a lease, or installs a daemon. The local journal lives under `$CODEX_HOME/loom-use/agent-workflows`. It contains follow-up instructions and references. Use a private user directory for these records.

## Route work in Codex

Use one parent as manager. Handle simple lookups and submissions with an existing Profile and established inputs directly. Before writing or verifying new producer code, a new or changed Profile, or a new or changed Unit plan, delegate preparation to `loom-job-entry`. Give it the outcome, exact input pins and constraints. It reuses compatible software and returns the prepared submission and evidence to the parent.

Delegate independent evidence checks early in substantive analysis, once each role has a clear question. For example, delegate comparison of saved predictions and traces to `loom-experiment-analysis` and independent investigation of an evaluation failure to `loom-runtime-diagnosis`. `loom-history` finds prior evidence and `loom-output-review` checks publication evidence. `loom-performance-analysis`, `loom-experiment-design`, and `loom-simulation-diagnosis` cover more specific questions. Give each role a separate scope and ask for concise findings with exact references. If delegation is unavailable, state the limitation and continue within the authorized scope. The parent combines the evidence and makes the final decisions.

The parent applies the server's Job submission, authorization and recovery contracts. It preserves the accepted Job, Unit, Attempt and output storage and writes once per requested operation. Use existing Unit dependencies for known compute transitions. A conditional loop, such as stopping training based on successive validation scores, belongs in the accepted Loom execution workflow. Local follow-ups are for decisions or result interpretation.
