"""Read the connected Loom authority without mutating its event or Job state."""
import json
from urllib.error import HTTPError

from stdio import OpsTransport


FAILURE = {"failed", "interrupted", "result_failed", "finalizing_failed"}
COMPLETE = {"complete", "completed"}
EVENTS = {"completed", "complete", "failed", "interrupted", "result_failed", "cancelled", "ready", "plan_binding_required"}


class Rejection(ValueError):
    def __init__(self, status=None):
        super().__init__("Loom rejected a workflow read")
        self.status = status


class Loom:
    def __init__(self, profile):
        self.transport = OpsTransport(profile=profile)
        self.request_id = 0
        self.rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "loom-use-agent-workflows", "version": "1"},
        })
        self.transport.rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def rpc(self, method, arguments):
        self.request_id += 1
        try:
            response = self.transport.rpc({
                "jsonrpc": "2.0", "id": self.request_id, "method": method, "params": arguments,
            })
        except HTTPError as error:
            raise Rejection(error.code) from None
        if "error" in response:
            data = response["error"].get("data") or {}
            raise Rejection(data.get("status") if isinstance(data, dict) else None)
        return response["result"]

    def call(self, group, action, arguments=None):
        payload = {"action": action}
        if arguments is not None:
            payload["arguments"] = arguments
        result = self.rpc("tools/call", {"name": group, "arguments": payload})
        if result.get("isError"):
            error = result.get("structuredContent") or {}
            raise Rejection(error.get("status") if isinstance(error, dict) else None)
        items = result.get("content")
        if not isinstance(items, list) or not items or items[0].get("type") != "text":
            raise ValueError("Unexpected Loom tool response")
        item = items[0]
        return json.loads(item["text"])

    def identity(self):
        status = self.call("system", "status")
        return status["machine_id"], status["principal"]["id"], status["principal"]["scopes"]

    def events(self, cursor):
        try:
            events = self.call("events", "list", {"kind": "all", "after": cursor})
        except Rejection as error:
            if error.status in (403, 404, 405):
                return [], "unavailable"
            raise
        if not isinstance(events, list):
            raise ValueError("Invalid Loom event feed")
        current = cursor
        for event in events:
            if type(event["seq"]) is not int or event["seq"] <= current:
                raise ValueError("Invalid Loom event sequence")
            current = event["seq"]
        return events, "available"

    def work(self, kind, identifier):
        record = self.call("jobs" if kind == "job" else "units", "get", {"id": identifier})
        if record.get("id") != identifier:
            raise ValueError("Loom returned a different Job or Unit")
        return record


def failure(record):
    recovery = record.get("recovery") or {}
    state = record.get("state")
    status = record.get("status")
    return (
        (state in FAILURE or status in FAILURE)
        and (record.get("recovery_state") or recovery.get("state")) not in {"claimed", "pending", "executing"}
    )


def compact(record):
    recovery = record.get("recovery") or {}
    return {
        k: v for k, v in {
            "id": record.get("id"),
            "job": record.get("job_id"),
            "state": record.get("state") or record.get("status"),
            "attempt": record.get("attempt"),
            "plan_revision": (record.get("spec") or {}).get("plan_revision"),
            "recovery": record.get("recovery_state") or recovery.get("state"),
        }.items() if v is not None
    }


def condition_result(condition, records):
    if any("cancelled" in (record.get("state"), record.get("status")) for record in records):
        return None, True
    if condition == "result-ready":
        if all(
            (record.get("state") in COMPLETE or record.get("status") in COMPLETE)
            and (record.get("result") or {}).get("artifact_ready") is True
            for record in records
        ):
            return [compact(record) for record in records], False
    elif condition == "needs-attention":
        findings = []
        for record in records:
            units = record.get("units") or ()
            # A research Job is context. A recovery action must target its physical Unit.
            if units:
                findings.extend(
                    compact({**unit, "job_id": record["id"]}) for unit in units if failure(unit)
                )
            elif failure(record):
                findings.append(compact(record))
        if findings:
            return findings, False
    elif condition == "plan-binding":
        findings = [
            {**compact(record), "next_action": record["next_action"]}
            for record in records if (record.get("next_action") or {}).get("kind") == "bind_plan_slot"
        ]
        if findings:
            return findings, False
    return None, False
