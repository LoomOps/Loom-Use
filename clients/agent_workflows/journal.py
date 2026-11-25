"""Private state for watches and Codex deliveries, independent of Loom storage."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid


SCHEMA = """
CREATE TABLE IF NOT EXISTS managers(
    connection TEXT PRIMARY KEY, endpoint TEXT NOT NULL, machine TEXT NOT NULL,
    principal TEXT NOT NULL, thread TEXT NOT NULL, socket TEXT,
    cursor INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS watches(
    id TEXT PRIMARY KEY, connection TEXT NOT NULL REFERENCES managers(connection),
    condition TEXT NOT NULL, targets TEXT NOT NULL, instruction TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'waiting', checked REAL NOT NULL DEFAULT 0,
    UNIQUE(connection, condition, targets, instruction)
);
CREATE INDEX IF NOT EXISTS watches_connection ON watches(connection, state);
CREATE TABLE IF NOT EXISTS deliveries(
    id TEXT PRIMARY KEY, watch TEXT NOT NULL UNIQUE REFERENCES watches(id),
    state TEXT NOT NULL DEFAULT 'ready', signal TEXT NOT NULL,
    turn TEXT, reason TEXT, updated REAL NOT NULL
);
"""


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Journal:
    def __init__(self, path):
        path = Path(path)
        fd = os.open(path, os.O_CREAT | os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise PermissionError("Workflow database must be a private user-owned regular file")
        finally:
            os.close(fd)
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def rows(self, query, *args):
        with closing(self.db.execute(query, args)) as cursor:
            return [dict(row) for row in cursor]

    def manager(self, name):
        rows = self.rows("SELECT * FROM managers WHERE connection=?", name)
        if not rows:
            raise ValueError("Register an existing Codex parent for this connection first")
        return rows[0]

    def attach(self, name, endpoint, machine, principal, thread, socket):
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO managers(connection,endpoint,machine,principal,thread,socket) VALUES(?,?,?,?,?,?)",
                (name, endpoint, machine, principal, thread, socket),
            )
            selected = self.manager(name)
            if (selected["endpoint"], selected["machine"], selected["principal"], selected["thread"]) != (
                endpoint, machine, principal, thread,
            ):
                raise ValueError("This connection has a different workflow binding")
            self.db.execute("UPDATE managers SET socket=? WHERE connection=?", (socket, name))
        return self.manager(name)

    def watch(self, name, condition, targets, instruction):
        self.manager(name)
        args = (name, condition, encode(targets), instruction)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO watches(id,connection,condition,targets,instruction) VALUES(?,?,?,?,?)",
                (str(uuid.uuid4()), *args),
            )
            return self.rows(
                "SELECT id,state FROM watches WHERE connection=? AND condition=? AND targets=? AND instruction=?", *args,
            )[0]

    def watch_rows(self, name, pending=False):
        return self.rows(
            "SELECT * FROM watches WHERE connection=? AND (?=0 OR state='waiting') ORDER BY rowid",
            name, int(pending),
        )

    def get_watch(self, identifier):
        return self.rows("SELECT * FROM watches WHERE id=?", identifier)[0]

    def get_delivery(self, name, identifier):
        rows = self.rows(
            "SELECT d.* FROM deliveries d JOIN watches w ON d.watch=w.id WHERE w.connection=? AND d.id=?",
            name, identifier,
        )
        if not rows:
            raise ValueError("Unknown workflow delivery")
        return rows[0]

    def deliveries(self, name, pending=False):
        return self.rows(
            "SELECT d.* FROM deliveries d JOIN watches w ON d.watch=w.id WHERE w.connection=? "
            "AND (?=0 OR d.state IN ('ready','sending','sent','uncertain')) ORDER BY d.rowid",
            name, int(pending),
        )

    def checked(self, watch, now, signal=None, cancelled=False):
        with self.db:
            current = self.db.execute(
                "UPDATE watches SET checked=? WHERE id=? AND state='waiting'", (now, watch),
            ).rowcount
            if not current:
                return
            if cancelled:
                self.db.execute("UPDATE watches SET state='cancelled' WHERE id=? AND state='waiting'", (watch,))
            if signal is not None:
                identifier = str(uuid.uuid4())
                self.db.execute(
                    "INSERT OR IGNORE INTO deliveries(id,watch,signal,updated) VALUES(?,?,?,?)",
                    (identifier, watch, encode({"id": identifier, **signal}), now),
                )
                self.db.execute("UPDATE watches SET state='ready' WHERE id=? AND state='waiting'", (watch,))

    def latest_cursor(self, name, after):
        with self.db:
            self.db.execute("UPDATE managers SET cursor=max(cursor,?) WHERE connection=?", (after, name))

    def transition(self, delivery, previous, state, *, turn=None, reason=None):
        with self.db:
            n = self.db.execute(
                "UPDATE deliveries SET state=?, turn=coalesce(?,turn), reason=?, updated=? WHERE id=? AND state=?",
                (state, turn, reason, time.time(), delivery, previous),
            ).rowcount
            if n:
                self.db.execute(
                    "UPDATE watches SET state=? WHERE id=(SELECT watch FROM deliveries WHERE id=?)",
                    (state, delivery),
                )
        return bool(n)

    def record_turn(self, delivery, turn):
        if not self.transition(delivery, "sending", "sent", turn=turn):
            # A very fast manager may acknowledge before turn/start returns.
            with self.db:
                self.db.execute(
                    "UPDATE deliveries SET turn=? WHERE id=? AND state='handled' AND turn IS NULL",
                    (turn, delivery),
                )

    def defer_stale(self, delivery, watch, checked, cancelled=False):
        # The signal was never sent. Drop it and let the current watch condition
        # become eligible again at a later observation.
        with self.db:
            n = self.db.execute("DELETE FROM deliveries WHERE id=? AND state='ready'", (delivery,)).rowcount
            if n:
                self.db.execute(
                    "UPDATE watches SET state=?, checked=? WHERE id=?",
                    ("cancelled" if cancelled else "waiting", checked, watch),
                )

    def acknowledge(self, name, delivery):
        with self.db:
            changed = self.db.execute(
                "UPDATE deliveries SET state='handled', reason=NULL, updated=? WHERE id=? "
                "AND state IN ('sending','sent','uncertain','needs-review') "
                "AND watch IN (SELECT id FROM watches WHERE connection=?)",
                (time.time(), delivery, name),
            ).rowcount
            if changed:
                self.db.execute(
                    "UPDATE watches SET state='handled' WHERE id=(SELECT watch FROM deliveries WHERE id=?)",
                    (delivery,),
                )
            elif self.get_delivery(name, delivery)["state"] != "handled":
                raise ValueError("Delivery is not eligible for acknowledgement")
        return {"id": delivery, "state": "handled"}

    def cancel(self, name, watch):
        with self.db:
            n = self.db.execute(
                "UPDATE watches SET state='cancelled' WHERE connection=? AND id=? AND state IN ('waiting','ready')",
                (name, watch),
            ).rowcount
            if not n:
                raise ValueError("Only a waiting or unsent watch can be cancelled")
            self.db.execute("UPDATE deliveries SET state='cancelled' WHERE watch=? AND state='ready'", (watch,))
        return {"id": watch, "state": "cancelled"}
