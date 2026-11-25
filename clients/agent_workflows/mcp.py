"""A small stdio MCP surface for an attached workflow parent."""
import json
from pathlib import Path
import sys
import tomllib

from setup import atomic_private, check_config, config_text
from .journal import Journal
from .workflow import CONDITIONS


NAME = "loom-use-workflows"
LIMIT = 64 * 1024
ID = {"type": "string", "minLength": 1, "maxLength": 128}
TARGETS = {"type": "array", "items": ID, "maxItems": 25}


def tool(name, description, properties, required):
    return {
        "name": name, "description": description,
        "inputSchema": {
            "type": "object", "properties": {"connection": ID, **properties},
            "required": ["connection", *required], "additionalProperties": False,
        },
    }


TOOLS = [
    tool("watch", "Register a follow-up on already accepted Loom Jobs or Units for this attached parent.",
         {"on": {"enum": list(CONDITIONS)}, "jobs": TARGETS, "units": TARGETS,
          "then": {"type": "string", "minLength": 1, "maxLength": 4096}}, ["on", "then"]),
    tool("followup", "Read an exact follow-up signal delivered to this parent.",
         {"delivery_id": ID}, ["delivery_id"]),
    tool("acknowledge", "Record that you handled a delivered follow-up after completing the requested work.",
         {"delivery_id": ID}, ["delivery_id"]),
]


def install(workflows, script):
    client = workflows.client
    config = client.config
    check_config(config)
    before = config.read_text() if config.exists() else ""
    desired = {"command": sys.executable, "args": [str(Path(script).resolve()), "--home", str(client.home), "workflows", "mcp"]}
    previous = workflows.root / "mcp-registration.json"
    if previous.is_symlink():
        raise PermissionError("Refusing a symlink workflow registration receipt")
    saved = json.loads(previous.read_text()) if previous.is_file() else None
    current = tomllib.loads(before).get("mcp_servers", {}).get(NAME)
    if current is not None and current not in (saved, desired):
        raise ValueError("An existing workflow MCP registration is managed outside Loom Use")
    amended = config_text(before, NAME, desired)
    if (config.read_text() if config.exists() else "") != before:
        raise ValueError("Codex configuration changed concurrently")
    if amended != before:
        atomic_private(config, amended)
    try:
        atomic_private(previous, json.dumps(desired) + "\n")
    except BaseException:
        if not config.is_symlink() and config.read_text() == amended:
            if before:
                atomic_private(config, before)
            else:
                config.unlink()
        raise
    return {"server": NAME, "configured": True, "refresh_required": amended != before}


def reply(workflows, request):
    method = request.get("method")
    if "id" not in request:
        return None
    envelope = {"jsonrpc": "2.0", "id": request["id"]}
    parameters = request.get("params") or {}
    if method == "initialize":
        return {**envelope, "result": {
            "protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
            "serverInfo": {"name": NAME, "version": "1"},
        }}
    if method == "ping":
        return {**envelope, "result": {}}
    if method == "tools/list":
        return {**envelope, "result": {"tools": TOOLS}}
    if method != "tools/call":
        return {**envelope, "error": {"code": -32601, "message": "Unknown method"}}
    try:
        value = call(workflows, parameters)
        result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
    except (OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if type(error) is ValueError else "Workflow request rejected: " + type(error).__name__
        result = {"isError": True, "content": [{"type": "text", "text": message}]}
    return {**envelope, "result": result}


def call(workflows, parameters):
    name = parameters["name"]
    args = parameters["arguments"]
    connection = args["connection"]
    meta = parameters.get("_meta")
    thread = meta.get("threadId") if isinstance(meta, dict) else None
    if not isinstance(thread, str) or not workflows.path.is_file():
        raise ValueError("The attached Codex parent is required")
    with Journal(workflows.path) as journal:
        if journal.manager(connection)["thread"] != thread:
            raise ValueError("The attached Codex parent is required")
    if name == "watch":
        jobs, units = args.get("jobs", []), args.get("units", [])
        if not isinstance(jobs, list) or not isinstance(units, list) or args["on"] not in CONDITIONS:
            raise ValueError("Watch expects explicit Job/Unit lists and a supported condition")
        return workflows.watch(connection, args["on"], jobs, units, args["then"])
    if name == "acknowledge":
        return workflows.acknowledge(connection, args["delivery_id"])
    if name == "followup":
        return workflows.read_signal(connection, args["delivery_id"])
    raise ValueError("Unknown workflow tool")


def serve(workflows):
    while line := sys.stdin.buffer.readline(LIMIT + 1):
        if len(line) > LIMIT:
            raise ValueError("Workflow MCP request exceeds the input bound")
        try:
            request = json.loads(line)
        except ValueError:
            continue
        if not isinstance(request, dict):
            continue
        result = reply(workflows, request)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False), flush=True)
