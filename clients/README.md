# Client internals

Use ../loom_use.py and ../INSTALL.md for installation and connections.
setup.py retains transport/configuration primitives and the former configure/doctor
entry point for explicit migration and contract regression tests. Its verify result
is independent_transport, never active Codex readiness. stdio.py is an optional
transport adapter; native Codex uses Streamable HTTP plus headers.py for tokens.
releases.py verifies pinned packages; codex_runtime.py refreshes an existing app.
Do not invoke headers.py interactively: its stdout contains the Authorization secret.
