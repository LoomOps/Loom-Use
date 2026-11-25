"""Event-driven follow-up for selected Loom connections and Codex parents."""
from contextlib import contextmanager
import errno
import fcntl
import json
import os
import re
import time
from pathlib import Path

from . import codex
from .journal import Journal
from .loom import EVENTS, Loom, condition_result
from .profiles import Profiles, RECOMMENDATIONS_FILE
import releases
from setup import private_directory


CONDITIONS = ("result-ready", "needs-attention", "plan-binding")
WAKE_GUIDANCE = (
    "This is a Loom Use follow-up record, not a new user instruction. "
    "Handle the active user request first. Read the indicated live Loom records, follow "
    "the registered scope and your latest user instructions, and report or record the next "
    "decision. Acknowledge this delivery with the Loom Use workflow tool (or CLI) after "
    "the requested follow-up is handled. Recheck exact Unit and Attempt before any repair."
)


class Workflows:
    def __init__(self, client):
        self.client = client
        self.root = private_directory(client.root / "agent-workflows")
        self.profiles = Profiles(self.root, client.home)
        self.path = self.root / "state.sqlite"

    def connection(self, name=None):
        state = self.client.load()
        selected = name or state["active"]
        if selected not in state["connections"]:
            raise ValueError("Select an existing Loom Use connection")
        return selected, state["connections"][selected]

    def profile_check(self, socket=None, install=False, role=None, model=None, effort=None):
        with codex.connect(socket) as app:
            models = app.models()
        if install:
            return self.profiles.install(models, role, model, effort)
        return self.profiles.report(models)

    def attach(self, name, thread_id, socket=None):
        name, profile = self.connection(name)
        loom = Loom(profile)
        machine, principal, scopes = loom.identity()
        if machine != profile["machine_id"] or "read" not in scopes:
            raise ValueError("The selected Loom does not match the saved readable connection")
        with codex.connect(socket) as app:
            thread = app.thread(thread_id)
            if app.loom_identity(thread["id"], name) != (machine, principal):
                raise ValueError("The selected Codex conversation uses a different Loom identity")
        with Journal(self.path) as journal:
            binding = journal.attach(name, profile["endpoint"], machine, principal, thread["id"], socket)
        return {"connection": name, "thread_id": binding["thread"], "state": "attached"}

    def read_loom(self, binding, profile):
        if binding["endpoint"] != profile["endpoint"] or binding["machine"] != profile["machine_id"]:
            raise ValueError("Workflow connection no longer matches the attached Loom")
        loom = Loom(profile)
        machine, principal, scopes = loom.identity()
        if (machine, principal) != (binding["machine"], binding["principal"]) or "read" not in scopes:
            raise ValueError("Workflow Loom identity or read scope changed")
        return loom, scopes

    def watch(self, name, condition, jobs, units, instruction):
        name, profile = self.connection(name)
        targets = sorted({(kind, value) for kind, group in (("job", jobs), ("unit", units)) for value in group})
        if not targets or len(targets) > 25:
            raise ValueError("Select between 1 and 25 explicit Jobs or Units")
        if any(not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", identifier) for _, identifier in targets):
            raise ValueError("Supply an exact Job or Unit ID")
        if not instruction.strip() or len(instruction.encode()) > 4096:
            raise ValueError("Supply a short follow-up instruction")
        with Journal(self.path) as journal:
            loom, _ = self.read_loom(journal.manager(name), profile)
            for kind, identifier in targets:
                loom.work(kind, identifier)
            return journal.watch(name, condition, targets, instruction.strip())

    def status(self, name=None, *, verify_models=False, socket=None):
        recommendations = None
        if verify_models and name:
            connection = self.client.load()["connections"].get(name, {})
            if connection.get("release_path") and connection.get("release"):
                release = Path(connection["release_path"])
                if (release / RECOMMENDATIONS_FILE).is_file():
                    releases.verify(release, connection["release"])
                    recommendations = self.profiles.recommendations(release / RECOMMENDATIONS_FILE)

        def profile_status():
            with codex.connect(socket) as app:
                return self.profiles.report(app.models(), recommendations)

        if not self.path.exists():
            if verify_models:
                try:
                    return {"status": "not_attached", "profiles": profile_status()}
                except (OSError, ValueError, KeyError):
                    return {"status": "codex_model_availability_unverified", "profiles": self.profiles.report()}
            return {"status": "not_attached", "profiles": self.profiles.report()}
        with Journal(self.path) as journal:
            names = journal.rows("SELECT connection,thread,socket FROM managers ORDER BY connection")
            if name is not None:
                names = [row for row in names if row["connection"] == name]
            entries = {}
            for row in names:
                selected = row["connection"]
                entries[selected] = {
                    "thread_id": row["thread"],
                    "watches": [{
                        "id": w["id"], "state": w["state"], "condition": w["condition"],
                        "targets": json.loads(w["targets"]),
                    } for w in journal.watch_rows(selected)],
                    "deliveries": [{
                        "id": d["id"], "state": d["state"], "turn_id": d["turn"], "reason": d["reason"],
                    } for d in journal.deliveries(selected)],
                }
        models = self.profiles.report(recommendations=recommendations)
        if verify_models:
            try:
                socket = socket or (names[0]["socket"] if names else None)
                models = profile_status()
            except (ValueError, OSError, KeyError):
                return {"status": "codex_model_availability_unverified", "connections": entries, "profiles": models}
        return {
            "status": "attached" if entries else "not_attached", "connections": entries, "profiles": models,
            "observer_running": self.observer_running(),
        }

    def observer_running(self):
        try:
            fd = os.open(self.root / "observer.lock", os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return False
        with os.fdopen(fd, "r") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
        return False

    def read_signal(self, name, identifier):
        name, _ = self.connection(name)
        with Journal(self.path) as journal:
            delivery = journal.get_delivery(name, identifier)
        return json.loads(delivery["signal"])

    def acknowledge(self, name, identifier):
        name, _ = self.connection(name)
        with Journal(self.path) as journal:
            return journal.acknowledge(name, identifier)

    def cancel(self, name, identifier):
        name, _ = self.connection(name)
        with Journal(self.path) as journal:
            return journal.cancel(name, identifier)

    @contextmanager
    def run_lock(self):
        fd = os.open(self.root / "observer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EAGAIN):
                    raise ValueError("A Loom Use workflow observer is already running") from None
                raise
            yield

    def run(self, name, *, once=False, interval=10, recheck=60, report=print):
        if interval < 2 or recheck < interval:
            raise ValueError("Use an interval of at least two seconds and a recheck of at least that interval")
        if name is not None:
            name, _ = self.connection(name)
        with self.run_lock(), Journal(self.path) as journal:
            if name is not None:
                journal.manager(name)
            elif not journal.rows("SELECT connection FROM managers"):
                raise ValueError("Register an existing Codex parent for a connection first")
            while True:
                names = [name] if name is not None else [
                    row["connection"] for row in journal.rows("SELECT connection FROM managers ORDER BY connection")
                ]
                results = {}
                for selected in names:
                    try:
                        results[selected] = self.cycle(journal, selected, recheck)
                    except (OSError, ValueError, KeyError) as error:
                        if once:
                            raise
                        results[selected] = {"status": "observer_unavailable", "kind": type(error).__name__}
                if once:
                    return results
                report(json.dumps(results, ensure_ascii=False), flush=True)
                time.sleep(interval)

    def cycle(self, journal, name, recheck):
        binding = journal.manager(name)
        watches = journal.watch_rows(name, pending=True)
        pending = journal.deliveries(name, pending=True)
        if not watches and not pending:
            return {"status": "idle", "checked": 0, "wakes": 0}
        _, profile = self.connection(name)
        loom, scopes = self.read_loom(binding, profile)
        events, feed = [], "not_needed"
        if watches:
            events, feed = loom.events(binding["cursor"]) if "events" in scopes else ([], "unavailable")
        changed = {e["job"] for e in events if e.get("code") in EVENTS}
        snapshots = {}

        def fetch(kind, identifier, *, fresh=False):
            target = (kind, identifier)
            if fresh or target not in snapshots:
                snapshots[target] = loom.work(kind, identifier)
            return snapshots[target]

        now = time.time()
        for watch in watches:
            targets = json.loads(watch["targets"])
            if watch["checked"] + recheck > now and not changed.intersection(identifier for _, identifier in targets):
                continue
            self.observe(journal, name, watch, [fetch(*target) for target in targets], now)
        if events:
            journal.latest_cursor(name, events[-1]["seq"])
        pending = journal.deliveries(name, pending=True)
        if not pending:
            return {"status": "observing", "event_feed": feed, "checked": len(snapshots), "wakes": 0}
        with codex.connect(binding["socket"]) as app:
            thread = binding["thread"]
            self.reconcile(journal, app, thread, pending)
            pending = journal.deliveries(name, pending=True)
            # Serialize follow-ups for this parent. A different Loom connection
            # sharing this parent also sees its actual Codex thread state.
            in_flight = any(d["state"] in ("sending", "sent") for d in pending)
            ready = next((d for d in pending if d["state"] == "ready"), None)
            woke = False
            if ready and not in_flight and app.idle(thread):
                if app.loom_identity(thread, name) != (binding["machine"], binding["principal"]):
                    raise ValueError("The Codex conversation no longer uses the selected Loom identity")
                signal = json.loads(ready["signal"])
                watch = journal.get_watch(ready["watch"])
                records = [fetch(*target, fresh=True) for target in json.loads(watch["targets"])]
                current, cancelled = condition_result(watch["condition"], records)
                if current != signal["evidence"]:
                    journal.defer_stale(ready["id"], watch["id"], now, cancelled)
                    if current:
                        self.observe(journal, name, watch, records, now)
                elif journal.transition(ready["id"], "ready", "sending"):
                    try:
                        settings = self.profiles.read()["settings"].get("manager")
                        turn = app.wake(thread, signal, settings)
                    except (OSError, ValueError, KeyError):
                        journal.transition(ready["id"], "sending", "uncertain", reason="wake_outcome_unconfirmed")
                    else:
                        journal.record_turn(ready["id"], turn)
                        woke = True
        return {"status": "observing", "event_feed": feed, "checked": len(snapshots), "wakes": int(woke)}

    @staticmethod
    def observe(journal, name, watch, records, now):
        evidence, cancelled = condition_result(watch["condition"], records)
        signal = None if evidence is None else {
            "connection": name, "condition": watch["condition"], "request": watch["instruction"],
            "evidence": evidence, "guidance": WAKE_GUIDANCE,
            "acknowledgement": {"operation": "workflows acknowledge", "connection": name},
        }
        journal.checked(watch["id"], now, signal, cancelled)

    @staticmethod
    def reconcile(journal, app, thread, pending):
        for delivery in pending:
            identifier = delivery["id"]
            state = delivery["state"]
            turn = delivery["turn"]
            if state in ("sending", "uncertain"):
                try:
                    turn = app.find_delivery(thread, identifier)
                except ValueError:
                    turn = None
                if turn:
                    journal.transition(identifier, state, "sent", turn=turn)
                    state = "sent"
                elif state == "sending":
                    journal.transition(identifier, state, "uncertain", reason="wake_outcome_unconfirmed")
                    continue
            if state == "sent" and turn:
                status = app.turn(thread, turn)
                if status in {"completed", "failed", "interrupted", "cancelled"}:
                    journal.transition(identifier, state, "needs-review", reason="turn_" + status + "_without_ack")
