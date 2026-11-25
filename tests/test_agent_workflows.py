"""Job follow-up, Codex role configuration, and crash/retry boundaries."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
import tomllib
import unittest
from contextlib import contextmanager
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loom_use
from agent_workflows import codex
from agent_workflows import mcp
from agent_workflows.journal import Journal
from agent_workflows.profiles import MODEL
from agent_workflows.workflow import Workflows


class FakeLoom:
    machine = "loom-workflow-fixture"
    principal = "fixture-principal"
    work_id = "fixture-job"
    attempt = "attempt-fixture"

    def __init__(self):
        self.scopes = ["read", "events"]
        self.feed = []
        self.calls = []
        self.fixture_actions = {}
        self.records = {self.work_id: {
            "id": self.work_id, "state": "running", "status": "running",
            "spec": {"plan_revision": 1}, "result": {"artifact_ready": False},
        }}

    def complete(self):
        self.records[self.work_id]["state"] = "complete"
        self.records[self.work_id]["status"] = "completed"
        self.records[self.work_id]["result"] = {"artifact_ready": True, "outputs": {
            "experiment": {"id": "fixture-exp", "revision": 1},
        }}
        self.feed.append({"seq": len(self.feed) + 1, "code": "complete", "job": self.work_id})

    @contextmanager
    def serve(self):
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_):
                pass

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                method = req["method"]
                if method == "notifications/initialized":
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if method == "initialize":
                    result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                              "serverInfo": {"name": "loom-fixture", "version": "1"}}
                elif method == "tools/list":
                    schema = {"type": "object", "properties": {"action": {"type": "string"}, "arguments": {"type": "object"}}, "required": ["action"]}
                    names = ["system", "jobs", "units", "events"]
                    if fixture.fixture_actions:
                        names.append("fixture")
                    result = {"tools": [{"name": name, "description":
                                        ("Synthetic read_evaluation and save_plan operations" if name == "fixture"
                                         else "Read synthetic Loom records"), "inputSchema": schema}
                                        for name in names]}
                else:
                    params = req["params"]
                    name = params["name"]
                    outer = params["arguments"]
                    action = outer["action"]
                    args = outer.get("arguments", {})
                    fixture.calls.append((name, action, args))
                    error = None
                    if (name, action) == ("system", "status"):
                        body = {"machine_id": fixture.machine, "principal": {
                            "id": fixture.principal, "scopes": fixture.scopes,
                        }}
                    elif (name, action) == ("events", "list") and "events" in fixture.scopes:
                        body = [e for e in fixture.feed if e["seq"] > args["after"]][:100]
                    elif (name, action) in (("jobs", "get"), ("units", "get")) and args["id"] in fixture.records:
                        body = fixture.records[args["id"]]
                    elif name == "fixture" and action in fixture.fixture_actions:
                        try:
                            body = fixture.fixture_actions[action](args)
                        except ValueError as error_value:
                            body = str(error_value)
                            error = {"error": "fixture_rejected", "status": 400}
                    else:
                        body = "Synthetic Loom only accepts fixture reads"
                        error = {"error": "fixture_rejected", "status": 403}
                    result = {"content": [{"type": "text", "text": json.dumps(body)}]}
                    if error:
                        result.update(isError=True, structuredContent=error)
                body = json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield f"http://127.0.0.1:{server.server_port}/mcp"
            finally:
                server.shutdown()
                thread.join()


class FakeCodex:
    def __init__(self, fixture):
        self.fixture = fixture
        self.ready = True
        self.known = {}
        self.wakes = []
        self.lose_reply = False
        self.subagent = False

    def models(self):
        return {MODEL: {"low", "medium", "high"}, "other-model": {"high"}}

    def thread(self, identifier):
        if self.subagent:
            raise ValueError("Select a persistent, unarchived Codex parent conversation")
        return {"id": identifier}

    def loom_identity(self, thread, name):
        return self.fixture.machine, self.fixture.principal

    def idle(self, thread):
        return self.ready

    def wake(self, thread, signal, settings):
        self.wakes.append((thread, signal, settings))
        self.known[signal["id"]] = f"turn-{len(self.wakes)}"
        if self.lose_reply:
            raise TimeoutError()
        return self.known[signal["id"]]

    def find_delivery(self, thread, identifier):
        return self.known.get(identifier)

    def turn(self, thread, turn):
        return "completed"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.client = loom_use.Client(Path(directory) / "codex")
        self.loom = FakeLoom()
        endpoint = self.enterContext(self.loom.serve())
        self.client.save({"schema": 1, "active": "fixture", "connections": {"fixture": {
            "endpoint": endpoint, "machine_id": self.loom.machine, "authentication": "tailscale",
        }}})
        self.app = FakeCodex(self.loom)
        self.enterContext(patch.object(codex, "connect", side_effect=lambda *_: self.fake_connection()))
        self.workflow = Workflows(self.client)
        self.workflow.attach(None, "fixture-parent")

    @contextmanager
    def fake_connection(self):
        yield self.app

    def tick(self):
        return self.workflow.run(None, once=True)["fixture"]

    def register(self, condition="result-ready"):
        return self.workflow.watch(None, condition, [self.loom.work_id], [], "Interpret the fixture result")

    def test_one_followup_and_explicit_acknowledgement(self):
        self.workflow.profile_check(install=True)
        watch = self.register()
        self.assertEqual(self.register()["id"], watch["id"])
        self.assertEqual(self.tick()["wakes"], 0)
        self.loom.complete()
        self.assertEqual(self.tick()["wakes"], 1)
        self.assertEqual(self.tick()["wakes"], 0)
        _, signal, model = self.app.wakes[0]
        self.assertEqual(model, {"model": MODEL, "effort": "low"})
        self.assertEqual(signal["evidence"][0]["id"], self.loom.work_id)
        self.assertEqual(self.workflow.status()["connections"]["fixture"]["deliveries"][0]["state"], "needs-review")
        self.assertEqual(self.workflow.acknowledge(None, signal["id"])["state"], "handled")
        self.assertEqual(self.tick()["status"], "idle")
        self.assertNotIn(("events", "ack"), [(n, a) for n, a, _ in self.loom.calls])

    def test_busy_parent_and_stale_failure(self):
        self.app.ready = False
        self.register("needs-attention")
        self.loom.records[self.loom.work_id]["units"] = [{
            "id": "unit-fixture", "state": "result_failed", "attempt": self.loom.attempt,
        }]
        self.loom.feed = [{"seq": 1, "code": "result_failed", "job": self.loom.work_id}]
        self.assertEqual(self.tick()["wakes"], 0)
        self.app.ready = True
        self.loom.records[self.loom.work_id]["units"][0]["state"] = "complete"
        self.assertEqual(self.tick()["wakes"], 0)
        self.assertEqual(self.workflow.status()["connections"]["fixture"]["watches"][0]["state"], "waiting")

    def test_lost_reply_reconciles_without_duplicate_start(self):
        self.app.lose_reply = True
        self.register()
        self.loom.complete()
        self.assertEqual(self.tick()["wakes"], 0)
        workflow_after_restart = Workflows(self.client)
        self.assertEqual(workflow_after_restart.run(None, once=True)["fixture"]["wakes"], 0)
        self.assertEqual(len(self.app.wakes), 1)
        self.assertEqual(self.workflow.status()["connections"]["fixture"]["deliveries"][0]["turn_id"], "turn-1")

    def test_recovery_claim_during_identity_check_prevents_stale_wake(self):
        self.register("needs-attention")
        record = self.loom.records[self.loom.work_id]
        record["units"] = [{"id": "unit-fixture", "state": "failed", "attempt": self.loom.attempt}]

        def claim_during_check(*_):
            record["units"][0]["recovery_state"] = "claimed"
            return self.loom.machine, self.loom.principal

        with patch.object(self.app, "loom_identity", side_effect=claim_during_check):
            self.assertEqual(self.tick()["wakes"], 0)
        self.assertEqual(self.app.wakes, [])
        self.assertEqual(self.workflow.status()["connections"]["fixture"]["watches"][0]["state"], "waiting")

    def test_unknown_reply_is_not_replayed_without_evidence(self):
        self.app.lose_reply = True
        self.register()
        self.loom.complete()
        self.tick()
        self.app.known.clear()
        self.assertEqual(self.tick()["wakes"], 0)
        self.assertEqual(len(self.app.wakes), 1)

    def test_no_events_uses_bounded_active_record_reconcile(self):
        self.loom.scopes = ["read"]
        self.register()
        self.assertEqual(self.tick()["event_feed"], "unavailable")
        self.loom.calls.clear()
        self.loom.complete()
        self.assertEqual(self.tick()["checked"], 0)
        self.assertNotIn(("jobs", "get"), [(n, a) for n, a, _ in self.loom.calls])
        with Journal(self.workflow.path) as journal, journal.db:
            journal.db.execute("UPDATE watches SET checked=?", (time.time() - 70,))
        self.assertEqual(self.tick()["wakes"], 1)

    def test_multiple_inputs_require_all_ready_and_batch_duplicate_events(self):
        self.loom.records["second-job"] = {"id": "second-job", "status": "queued"}
        self.workflow.watch(None, "result-ready", [self.loom.work_id, "second-job"], [], "Analyze both")
        self.loom.complete()
        self.assertEqual(self.tick()["wakes"], 0)
        self.loom.records["second-job"].update(state="complete", result={"artifact_ready": True})
        self.loom.feed.extend([{"seq": n, "job": "second-job", "code": "complete"} for n in (2, 3)])
        self.assertEqual(self.tick()["wakes"], 1)
        self.assertEqual({x["id"] for x in self.app.wakes[0][1]["evidence"]}, {self.loom.work_id, "second-job"})

    def test_foreign_connection_refused_before_wake(self):
        self.register()
        self.loom.complete()
        self.loom.principal = "replaced-principal"
        with self.assertRaisesRegex(ValueError, "identity"):
            self.tick()
        self.assertEqual(self.app.wakes, [])

    def test_profiles_are_explicit_and_preserve_operator_edit(self):
        profiles = self.workflow.profile_check(install=True)
        path = self.client.home / "agents/loom-job-entry.toml"
        self.assertEqual(tomllib.loads(path.read_text())["model_reasoning_effort"], "high")
        self.assertEqual(profiles["manager"]["current"]["effort"], "low")
        self.workflow.profile_check(install=True, role="job-entry", model="other-model", effort="high")
        self.workflow.profile_check(install=True)
        self.assertEqual(tomllib.loads(path.read_text())["model"], "other-model")
        before = path.read_text() + "# operator note\n"
        path.write_text(before)
        with self.assertRaisesRegex(ValueError, "outside Loom Use"):
            self.workflow.profile_check(install=True)
        self.assertEqual(path.read_text(), before)

    def test_stdio_workflow_ack_requires_attached_parent(self):
        self.register()
        self.loom.complete()
        self.tick()
        delivery = self.app.wakes[0][1]["id"]
        params = {
            "name": "acknowledge", "arguments": {"connection": "fixture", "delivery_id": delivery},
            "_meta": {"threadId": "detached-subagent"},
        }
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
        self.assertTrue(mcp.reply(self.workflow, request)["result"]["isError"])
        params["_meta"]["threadId"] = "fixture-parent"
        value = mcp.reply(self.workflow, request)["result"]["content"][0]["text"]
        self.assertEqual(json.loads(value)["state"], "handled")

    def test_mcp_registration_preserves_other_servers_and_refuses_foreign_replacement(self):
        self.client.config.write_text('[mcp_servers.other]\nurl = "https://other.test/mcp"\n')
        mcp.install(self.workflow, loom_use.ROOT / "loom_use.py")
        config = tomllib.loads(self.client.config.read_text())
        self.assertEqual(config["mcp_servers"]["other"]["url"], "https://other.test/mcp")
        self.assertIn("agent-workflows", str(self.workflow.path))
        altered = self.client.config.read_text().replace('"workflows", "mcp"', '"workflows", "status"')
        self.client.config.write_text(altered)
        with self.assertRaisesRegex(ValueError, "managed outside"):
            mcp.install(self.workflow, loom_use.ROOT / "loom_use.py")

    def test_fast_ack_retains_turn_identity(self):
        self.register()
        self.loom.complete()
        wake = self.app.wake

        def fast_ack(thread, signal, settings):
            accepted = wake(thread, signal, settings)
            self.workflow.acknowledge("fixture", signal["id"])
            return accepted

        self.app.wake = fast_ack
        self.assertEqual(self.tick()["wakes"], 1)
        delivery = self.workflow.status()["connections"]["fixture"]["deliveries"][0]
        self.assertEqual((delivery["state"], delivery["turn_id"]), ("handled", "turn-1"))

    def test_open_plan_slot_is_distinct_from_execution_failure(self):
        self.register("plan-binding")
        self.loom.records[self.loom.work_id].update(
            state="blocked", next_action={"kind": "bind_plan_slot", "slots": ["evaluate"], "plan_revision": 2},
        )
        self.assertEqual(self.tick()["wakes"], 1)
        evidence = self.app.wakes[0][1]["evidence"][0]
        self.assertEqual(evidence["next_action"]["slots"], ["evaluate"])
