"""Command-line entry for the optional Loom Use workflow module."""
import json

from . import mcp
from .profiles import ROLES
from .workflow import CONDITIONS, Workflows


def register(parser):
    sub = parser.add_subparsers(dest="workflow_command", required=True)
    models = sub.add_parser("models", help="Compare installed role settings with available Codex models")
    models.add_argument("--socket")
    install = sub.add_parser("install-profiles", help="Install the recommended available Codex agent profiles")
    install.add_argument("--socket")
    sub.add_parser("install-mcp", help="Register local workflow tools for the attached Codex parent")
    sub.add_parser("mcp", help="Serve the local workflow tools over stdio")
    configure = sub.add_parser("configure-profile", help="Apply one chosen role model and reasoning effort")
    configure.add_argument("role", choices=ROLES)
    configure.add_argument("model")
    configure.add_argument("effort")
    configure.add_argument("--socket")
    attach = sub.add_parser("attach", help="Select an existing Codex parent for a Loom connection")
    attach.add_argument("--thread-id", required=True)
    attach.add_argument("--socket")
    attach.add_argument("--name")
    watch = sub.add_parser("watch", help="Register a bounded follow-up for exact Loom records")
    watch.add_argument("--name")
    watch.add_argument("--on", required=True, choices=CONDITIONS)
    watch.add_argument("--job", action="append", default=[])
    watch.add_argument("--unit", action="append", default=[])
    watch.add_argument("--then", required=True, dest="instruction")
    status = sub.add_parser("status", help="Show local watches, deliveries and selected agent profiles")
    status.add_argument("--name")
    status.add_argument("--verify-models", action="store_true")
    run = sub.add_parser("run", help="Run the selected user-level observer in the foreground")
    run.add_argument("--name")
    run.add_argument("--once", action="store_true")
    run.add_argument("--interval", type=int, default=10)
    run.add_argument("--recheck", type=int, default=60)
    for command in ("show", "acknowledge", "cancel"):
        action = sub.add_parser(command)
        action.add_argument("identifier")
        action.add_argument("--name")


def execute(client, args, script):
    workflow = Workflows(client)
    action = args.workflow_command
    if action == "models":
        return workflow.profile_check(args.socket)
    if action == "install-profiles":
        with client.lock():
            return workflow.profile_check(args.socket, install=True)
    if action == "install-mcp":
        with client.lock():
            return mcp.install(workflow, script)
    if action == "mcp":
        mcp.serve(workflow)
        return None
    if action == "configure-profile":
        with client.lock():
            return workflow.profile_check(args.socket, True, args.role, args.model, args.effort)
    if action == "attach":
        return workflow.attach(args.name, args.thread_id, args.socket)
    if action == "watch":
        return workflow.watch(args.name, args.on, args.job, args.unit, args.instruction)
    if action == "status":
        return workflow.status(args.name, verify_models=args.verify_models)
    if action == "run":
        try:
            return workflow.run(args.name, once=args.once, interval=args.interval, recheck=args.recheck)
        except KeyboardInterrupt:
            return {"status": "observer_stopped"}
    if action == "show":
        return workflow.read_signal(args.name, args.identifier)
    if action == "acknowledge":
        return workflow.acknowledge(args.name, args.identifier)
    return workflow.cancel(args.name, args.identifier)


def summary(client, name, verify_models=False):
    root = client.root / "agent-workflows"
    if not root.exists():
        return {"status": "not_enabled"}
    try:
        return Workflows(client).status(name, verify_models=verify_models)
    except (OSError, ValueError, KeyError) as error:
        return {"status": "workflow_diagnostics_unavailable", "kind": type(error).__name__}
