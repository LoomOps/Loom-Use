"""Codex transport for a single selected parent conversation."""
from contextlib import contextmanager
import json

from codex_runtime import discover_socket
from websocket_unix import Connection


@contextmanager
def connect(socket=None):
    connection = Connection(discover_socket(socket), 8)
    try:
        client = Codex(connection)
        client.call("initialize", {
            "clientInfo": {"name": "loom-use-agent-workflows", "version": "1"},
            "capabilities": {"experimentalApi": True},
        })
        connection.send({"method": "initialized", "params": {}})
        yield client
    finally:
        connection.close()


class Codex:
    def __init__(self, connection):
        self.connection = connection
        self.request_id = 0

    def call(self, method, arguments):
        self.request_id += 1
        return self.connection.rpc(self.request_id, method, arguments)

    def models(self):
        models = {}
        cursor = None
        for _ in range(20):
            args = {"limit": 100, "includeHidden": False}
            if cursor is not None:
                args["cursor"] = cursor
            page = self.call("model/list", args)
            for model in page["data"]:
                models[model["model"]] = {
                    item["reasoningEffort"] for item in model["supportedReasoningEfforts"]
                }
            cursor = page.get("nextCursor")
            if cursor is None:
                return models
        raise ValueError("Codex model list did not finish")

    def thread(self, thread_id):
        thread = self.call("thread/read", {"threadId": thread_id, "includeTurns": False})["thread"]
        source = thread.get("source")
        subagent = isinstance(source, dict) and bool({"subAgent", "subagent"} & source.keys())
        if (
            thread["id"] != thread_id or thread.get("ephemeral") or thread.get("parentThreadId")
            or subagent or "archived_sessions" in str(thread.get("path") or "").split("/")
        ):
            raise ValueError("Select a persistent, unarchived Codex parent conversation")
        return thread

    def idle(self, thread_id):
        status = self.thread(thread_id)["status"]["type"]
        if status == "notLoaded":
            self.call("thread/resume", {"threadId": thread_id, "excludeTurns": True})
            status = self.thread(thread_id)["status"]["type"]
        return status == "idle"

    def loom_identity(self, thread_id, server):
        reply = self.call("mcpServer/tool/call", {
            "threadId": thread_id,
            "server": server,
            "tool": "system",
            "arguments": {"action": "status"},
        })
        if reply.get("isError") or not reply.get("content"):
            raise ValueError("The selected Codex conversation cannot read the Loom connection")
        status = json.loads(reply["content"][0]["text"])
        return status["machine_id"], status["principal"]["id"]

    def wake(self, thread_id, signal, settings=None):
        model = {"model": settings["model"], "effort": settings["effort"]} if settings else {}
        turn = self.call("turn/start", {
            "threadId": thread_id,
            "clientUserMessageId": signal["id"],
            **model,
            "input": [],
            "toolOutput": {
                "name": "loom_use_job_followup",
                "namespace": None,
                "output": json.dumps(signal, ensure_ascii=False, separators=(",", ":")),
                "retain": True,
            },
        })["turn"]
        return turn["id"]

    def turn(self, thread_id, turn_id):
        cursor = None
        for _ in range(4):
            args = {"threadId": thread_id, "limit": 50, "itemsView": "notLoaded"}
            if cursor is not None:
                args["cursor"] = cursor
            page = self.call("thread/turns/list", args)
            for turn in page["data"]:
                if turn["id"] == turn_id:
                    return turn["status"]
            cursor = page.get("nextCursor")
            if cursor is None:
                break
        return None

    def find_delivery(self, thread_id, identifier):
        cursor = None
        for _ in range(4):
            args = {"threadId": thread_id, "limit": 50, "sortDirection": "desc"}
            if cursor is not None:
                args["cursor"] = cursor
            page = self.call("thread/items/list", args)
            for entry in page["data"]:
                item = entry["item"]
                if item.get("type") != "functionCallOutput" or item.get("name") != "loom_use_job_followup":
                    continue
                output = item.get("output")
                if isinstance(output, str):
                    try:
                        signal = json.loads(output)
                    except ValueError:
                        continue
                    if isinstance(signal, dict) and signal.get("id") == identifier:
                        return entry["turnId"]
            cursor = page.get("nextCursor")
            if cursor is None:
                break
        return None
