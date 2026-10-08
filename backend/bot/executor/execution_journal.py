"""Local execution ownership and durable request identity (not a position ledger).

One store per exchange environment, never per session or credential. No secrets
are persisted. Missing/corrupt expected storage requires operator recovery; this
module never deletes or repairs it. Use a local filesystem, not a network share.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from threading import RLock
import uuid


class JournalError(RuntimeError):
    """Execution must remain blocked until durable state can be reconciled."""


_owners = set()
_owners_lock = RLock()
SCHEMA_VERSION = 1
MARKER_VERSION = 1
ACCOUNTING_SCHEMA_VERSION = 2
RUNTIME_SCHEMA_VERSION = 3
TERMINAL = {"FILLED", "CANCELLED", "REJECTED"}


def credential_binding(testnet: bool, api_key: str) -> str:
    if type(testnet) is not bool or not isinstance(api_key, str) or not api_key:
        raise JournalError("Execution store requires an explicit environment and credential binding")
    return hashlib.sha256(f"phemex:swap:USDT:{testnet}:{api_key}".encode()).hexdigest()


def default_store(testnet: bool) -> Path:
    return Path(__file__).resolve().parents[3] / ".live_trading" / (
        "execution-testnet.sqlite3" if testnet else "execution-production.sqlite3")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _number(value, positive=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def validate_record(intent, state, *, runtime=False):
    """Reject unusable records before they can authorize any exchange mutation."""
    try:
        for key in ("order_id", "symbol", "owner", "generation"):
            if not isinstance(intent[key], str) or not intent[key].strip():
                raise ValueError(key)
        if intent["side"] not in ("BUY", "SELL") or intent["order_type"] not in (
                "MARKET", "LIMIT", "STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP"):
            raise ValueError("order enums")
        if intent["purpose"] not in ("entry", "exit", "protection") or type(intent["reduce_only"]) is not bool:
            raise ValueError("purpose")
        if intent["reduce_only"] != (intent["purpose"] != "entry"):
            raise ValueError("reduce-only purpose")
        parent = intent.get('parent_entry_order_id')
        if parent is not None and (not isinstance(parent, str) or not parent.strip()
                or parent == intent['order_id'] or intent['purpose'] == 'entry'):
            raise ValueError('parent entry identity')
        if not _number(intent["quantity"], positive=True):
            raise ValueError("quantity")
        for key in ("price", "stop_price"):
            if intent[key] is not None and not _number(intent[key], positive=True):
                raise ValueError(key)
        wire = intent["wire"]
        if (not isinstance(wire, dict) or wire["symbol"] != intent["symbol"]
                or wire["side"] != intent["side"].lower() or wire["amount"] != intent["quantity"]
                or wire["params"]["clientOrderId"] != intent["order_id"]):
            raise ValueError("wire identity")
        if state["status"] not in TERMINAL | {"OPEN", "PENDING", "PARTIALLY_FILLED"}:
            raise ValueError("status")
        if not _number(state["filled_quantity"]) or state["filled_quantity"] > intent["quantity"] + 1e-9:
            raise ValueError("fill watermark")
        if ((state["status"] == "FILLED" and state["filled_quantity"] <= 0)
                or (state["status"] in ("CANCELLED", "REJECTED") and state["filled_quantity"] != 0)
                or (state["status"] in TERMINAL and (state["unknown_reason"] or state["cancel_requested"]))):
            raise ValueError("contradictory terminal state")
        if not (runtime and state["average_fill_price"] is None):
            if not _number(state["average_fill_price"]) or (state["filled_quantity"] > 0 and state["average_fill_price"] <= 0):
                raise ValueError("fill price")
        if type(state["cancel_requested"]) is not bool:
            raise ValueError("cancel intent")
        if state["exchange_id"] is not None and (not isinstance(state["exchange_id"], str) or not state["exchange_id"]):
            raise ValueError("exchange identity")
        for key in ("unknown_reason", "rejection_reason"):
            if state[key] is not None and not isinstance(state[key], str):
                raise ValueError(key)
        for key in ("created_at", "updated_at"):
            if datetime.fromisoformat(state[key]).tzinfo is None:
                raise ValueError(key)
        _json(intent)
        _json(state)
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise JournalError(f"Invalid execution journal record: {exc}") from exc


class ExecutionJournal:
    """Short FULL-synchronous SQLite transactions plus an OS lifetime lock.

    The marker is written and flushed BEFORE first database creation. Interrupted
    bootstrap therefore blocks instead of silently recreating an empty journal.
    Deleting both marker and database cannot be detected locally.
    """
    def __init__(self, path: Path, binding: str, *, runtime=False, environment=None):
        self._initialize_handle(path, binding)
        if type(runtime) is not bool or (runtime and environment not in ("testnet", "production")):
            raise JournalError("Explicit runtime environment required")
        self._requested_runtime, self._requested_environment = runtime, environment
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._open_service_store()

    def _initialize_handle(self, path, binding):
        self.path = Path(path).resolve()
        self.binding = binding
        self._mutex = RLock()
        self._connection = None
        self._lock_file = None
        self._owned = False
        self._pid = os.getpid()
        self.failed = None
        self._key = os.path.normcase(str(self.path))
        self.schema_version = None
        self._validated_stamp = None

    def _open_service_store(self):
        binding = self.binding
        try:
            self._acquire()
            marker = self.path.with_suffix(".initialized")
            existed, marked = self.path.exists(), marker.exists()
            if existed != marked:
                raise JournalError("Execution database/initialized marker missing; recovery required")
            if not existed:
                store_id = uuid.uuid4().hex
                with marker.open("x", encoding="utf-8") as stream:
                    stream.write(_json({"version": MARKER_VERSION, "store_id": store_id, "binding": binding}))
                    stream.flush()
                    os.fsync(stream.fileno())
                if os.name != "nt":
                    descriptor = os.open(str(marker.parent), os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
            marker_data = json.loads(marker.read_text(encoding="utf-8"))
            if marker_data.get("version") != MARKER_VERSION or marker_data.get("binding") != binding:
                raise JournalError("Execution marker schema/binding mismatch; credential rotation needs reconciliation")
            self._connection = sqlite3.connect(str(self.path), timeout=2, check_same_thread=False)
            self._connection.execute("PRAGMA journal_mode=DELETE")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            if self._connection.execute("PRAGMA synchronous").fetchone() != (2,):
                raise JournalError("SQLite FULL synchronization unavailable")
            if self._connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise JournalError("Execution database integrity check failed")
            if not existed:
                with self._accounting_transaction():
                    self._connection.execute("CREATE TABLE metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL, store_id TEXT NOT NULL, binding TEXT NOT NULL, clean INTEGER NOT NULL)")
                    self._connection.execute("CREATE TABLE requests (order_id TEXT PRIMARY KEY, intent TEXT NOT NULL, state TEXT NOT NULL)")
                    self._connection.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, order_id TEXT, kind TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL)")
                    self._connection.execute("INSERT INTO metadata VALUES (1, ?, ?, ?, 1)", (SCHEMA_VERSION, store_id, binding))
                    if self._requested_runtime:
                        self._create_financial_tables()
                        self._event(None, "accounting_migration", "bootstrap", {
                            "schema": ACCOUNTING_SCHEMA_VERSION, "environment": self._requested_environment,
                            "backup": None, "backup_sha256": None})
                        self._event(None, "runtime_migration", "bootstrap", {"schema": RUNTIME_SCHEMA_VERSION})
                        self._connection.execute("CREATE INDEX execution_facts_order ON execution_facts(order_id)")
                        self._create_runtime_indexes()
                        self._connection.execute("UPDATE metadata SET version=?", (RUNTIME_SCHEMA_VERSION,))
            meta = self._connection.execute("SELECT version,store_id,binding,clean FROM metadata WHERE singleton=1").fetchone()
            if (not meta or meta[0] not in (SCHEMA_VERSION, ACCOUNTING_SCHEMA_VERSION, RUNTIME_SCHEMA_VERSION)
                    or meta[1:3] != (marker_data.get("store_id"), binding)
                    or meta[3] not in (0, 1)):
                raise JournalError("Execution database schema/identity mismatch")
            self.schema_version = meta[0]
            self._store_id = meta[1]
            if self._requested_runtime and self.schema_version != RUNTIME_SCHEMA_VERSION:
                raise JournalError("Explicit offline runtime accounting upgrade required")
            self.was_clean = bool(meta[3])
            self.records()  # Validate the whole restore set before marking ownership active.
            if self.schema_version >= ACCOUNTING_SCHEMA_VERSION:
                environment = self._validate_accounting(self._connection, binding)
                if self._requested_runtime and environment != self._requested_environment:
                    raise JournalError("Runtime accounting environment mismatch")
            with self._transaction():
                self._connection.execute("UPDATE metadata SET clean=0 WHERE singleton=1")
                self._event(None, "owner_acquired", "local", {})
        except Exception as exc:
            self.close()
            if isinstance(exc, JournalError):
                raise
            raise JournalError(f"Execution storage unavailable: {exc}") from exc

    def _acquire(self):
        with _owners_lock:
            if self._key in _owners:
                raise JournalError("Execution store already owned by another local service")
            handle = self.path.with_suffix(".lock").open("a+b")
            try:
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except Exception as exc:
                handle.close()
                raise JournalError("Execution store already owned or lock unavailable") from exc
            self._lock_file = handle
            self._owned = True
            _owners.add(self._key)

    def assert_writable(self):
        if not self._owned or self._pid != os.getpid() or self.failed:
            raise JournalError(self.failed or "Execution store has no mutation ownership")

    @contextmanager
    def _transaction(self):
        with self._mutex:
            self.assert_writable()
            try:
                with self._connection:
                    if self.schema_version == RUNTIME_SCHEMA_VERSION:
                        self._connection.execute('BEGIN IMMEDIATE')
                        self._validate_before_runtime()
                    yield
                self._validated_stamp = self._database_stamp()
            except Exception as exc:
                self.failed = f"Execution persistence failed; recovery required: {exc}"
                raise JournalError(self.failed) from exc

    def _event(self, order_id, kind, source, payload):
        self._connection.execute("INSERT INTO events(order_id,kind,source,observed_at,payload) VALUES(?,?,?,?,?)",
                                 (order_id, kind, source, datetime.now(timezone.utc).isoformat(), _json(payload)))

    def _create_financial_tables(self):
        self._connection.execute("CREATE TABLE financial_orders (order_id TEXT PRIMARY KEY REFERENCES requests(order_id), payload TEXT NOT NULL, event_sequence INTEGER NOT NULL REFERENCES events(sequence))")
        self._connection.execute("CREATE TABLE execution_facts (symbol TEXT NOT NULL, execution_id TEXT NOT NULL, order_id TEXT REFERENCES requests(order_id), payload TEXT NOT NULL, event_sequence INTEGER NOT NULL REFERENCES events(sequence), PRIMARY KEY(symbol,execution_id))")

    def _create_runtime_indexes(self):
        self._connection.execute("CREATE INDEX events_kind ON events(kind)")
        self._connection.execute("CREATE INDEX events_request_kind ON events(order_id,kind)")
        self._connection.execute("CREATE UNIQUE INDEX requests_exchange_identity ON requests(json_extract(state,'$.exchange_id')) WHERE json_extract(state,'$.exchange_id') IS NOT NULL")

    def _database_stamp(self):
        return (self._connection.execute('PRAGMA data_version').fetchone()[0], self._connection.total_changes)

    def _validate_before_runtime(self):
        """Replay after opening or unexpected writes; own transactions validate their changed order."""
        if self._validated_stamp != self._database_stamp():
            meta = self._connection.execute('SELECT version,store_id,binding,clean FROM metadata WHERE singleton=1').fetchone()
            if (not meta or meta[:3] != (RUNTIME_SCHEMA_VERSION, self._store_id, self.binding) or meta[3] not in (0, 1)):
                raise JournalError('Runtime storage identity changed')
            self._validate_accounting(self._connection, self.binding)
            self._validated_stamp = self._database_stamp()

    def _seed_runtime_order(self, intent, legacy):
        from backend.bot.executor.accounting_models import to_payload
        state = _seed_financial(intent, legacy, self.binding, self._accounting_environment(self._connection))
        self._event(intent["order_id"], "financial_seed", "legacy_unverified", {"projection": to_payload(state)})
        seq = self._connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        self._connection.execute("INSERT INTO financial_orders VALUES(?,?,?)", (intent["order_id"], _json(to_payload(state)), seq))

    def records(self):
        with self._mutex:
            rows = self._connection.execute("SELECT order_id,intent,state FROM requests ORDER BY rowid").fetchall()
            records = []
            for oid, raw_intent, raw_state in rows:
                intent, state = json.loads(raw_intent), json.loads(raw_state)
                validate_record(intent, state, runtime=self.schema_version == RUNTIME_SCHEMA_VERSION)
                self._validate_parent(self._connection, intent, require_evidence=True)
                if oid != intent["order_id"]:
                    raise JournalError("Execution record identity mismatch")
                records.append((intent, state))
            return records

    @staticmethod
    def inspect(path):
        """Read-only inspection without credentials, ownership or store creation."""
        path = Path(path).resolve()
        marker = path.with_suffix(".initialized")
        if not path.exists() and not marker.exists():
            return {"exists": False, "recovery_required": False, "requests": []}
        connection = None
        try:
            if not path.exists() or not marker.exists():
                raise JournalError("Execution database/initialized marker missing")
            mark = json.loads(marker.read_text(encoding="utf-8"))
            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.2)
            if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise JournalError("Execution database integrity check failed")
            meta = connection.execute("SELECT version,store_id,binding,clean FROM metadata WHERE singleton=1").fetchone()
            if (not meta or meta[0] not in (SCHEMA_VERSION, ACCOUNTING_SCHEMA_VERSION, RUNTIME_SCHEMA_VERSION)
                    or meta[1:3] != (mark.get("store_id"), mark.get("binding"))
                    or mark.get("version") != MARKER_VERSION or meta[3] not in (0, 1)):
                raise JournalError("Execution database schema/identity mismatch")
            if meta[0] >= ACCOUNTING_SCHEMA_VERSION:
                ExecutionJournal._validate_accounting(connection, mark.get("binding"))
            requests = []
            for oid, raw_intent, raw_state in connection.execute("SELECT order_id,intent,state FROM requests"):
                intent, state = json.loads(raw_intent), json.loads(raw_state)
                validate_record(intent, state, runtime=meta[0] == RUNTIME_SCHEMA_VERSION)
                ExecutionJournal._validate_parent(connection, intent, require_evidence=True)
                if oid != intent["order_id"]:
                    raise JournalError("Execution record identity mismatch")
                if state["status"] not in TERMINAL or state["unknown_reason"] or state["cancel_requested"]:
                    requests.append({"order_id": oid, "exchange_id": state["exchange_id"],
                                     "symbol": intent["symbol"], "purpose": intent["purpose"],
                                     "status": state["status"], "quantity": intent["quantity"],
                                     "filled_quantity": state["filled_quantity"],
                                     "reason": state["unknown_reason"] or "Persisted request requires recovery"})
            return {"exists": True, "recovery_required": not bool(meta[3]) or bool(requests), "requests": requests}
        except Exception as exc:
            return {"exists": True, "recovery_required": True, "requests": [], "error": str(exc)}
        finally:
            if connection:
                connection.close()

    @staticmethod
    def _validate_parent(connection, intent, *, require_evidence=False):
        if require_evidence:
            event = connection.execute("SELECT payload FROM events WHERE order_id=? AND kind='submit_intent' ORDER BY sequence DESC LIMIT 1",
                                       (intent['order_id'],)).fetchone()
            if not event or json.loads(event[0]).get('parent_entry_order_id') != intent.get('parent_entry_order_id'):
                raise JournalError('Parent entry evidence mismatch')
            if json.loads(event[0]).get('report_version') != intent.get('report_version'):
                raise JournalError('Report version evidence mismatch')
            if json.loads(event[0]).get('reduction_root_order_id') != intent.get('reduction_root_order_id'):
                raise JournalError('Reduction root evidence mismatch')
        if 'report_version' in intent and (type(intent['report_version']) is not int
                or intent['report_version'] != 1 or intent['purpose'] != 'entry'):
            raise JournalError('Report version intent invalid')
        root_id = intent.get('reduction_root_order_id')
        if root_id is not None:
            if (not isinstance(root_id, str) or not root_id.strip() or root_id == intent['order_id']
                    or intent['purpose'] != 'exit' or intent['order_type'] != 'MARKET'
                    or not intent.get('parent_entry_order_id')):
                raise JournalError('Reduction root identity invalid')
            root_row = connection.execute('SELECT intent FROM requests WHERE order_id=?', (root_id,)).fetchone()
            if root_row is None:
                raise JournalError('Reduction root missing')
            root = json.loads(root_row[0])
            if (root.get('reduction_root_order_id') is not None or root['purpose'] != 'exit'
                    or root['order_type'] != 'MARKET'
                    or any(root.get(k) != intent.get(k) for k in
                           ('parent_entry_order_id', 'symbol', 'side', 'owner', 'generation'))
                    or intent['quantity'] > root['quantity']):
                raise JournalError('Reduction root scope conflict')
        parent_id = intent.get('parent_entry_order_id')
        if parent_id is None:
            return
        row = connection.execute('SELECT intent FROM requests WHERE order_id=?', (parent_id,)).fetchone()
        if row is None:
            raise JournalError('Parent entry identity missing')
        parent = json.loads(row[0])
        if (parent['purpose'] != 'entry' or parent['side'] == intent['side']
                or any(parent[k] != intent[k] for k in ('symbol', 'owner', 'generation'))):
            raise JournalError('Parent entry scope conflict')

    def submit_intent(self, intent, state):
        validate_record(intent, state, runtime=self.schema_version == RUNTIME_SCHEMA_VERSION)
        with self._transaction():
            self._validate_parent(self._connection, intent)
            previous = self._connection.execute("SELECT intent FROM requests WHERE order_id=?", (intent["order_id"],)).fetchone()
            if previous:
                # A protocol rejection retry may add posSide, but identity/purpose
                # and quantities cannot change. Every wire attempt gets an event.
                old = json.loads(previous[0])
                if {k: v for k, v in old.items() if k != "wire"} != {k: v for k, v in intent.items() if k != "wire"}:
                    raise JournalError("Execution request identity reused with different intent")
                self._connection.execute("UPDATE requests SET intent=?,state=? WHERE order_id=?", (_json(intent), _json(state), intent["order_id"]))
            else:
                self._connection.execute("INSERT INTO requests VALUES(?,?,?)", (intent["order_id"], _json(intent), _json(state)))
                if self.schema_version == RUNTIME_SCHEMA_VERSION:
                    self._seed_runtime_order(intent, state)
            self._connection.execute("UPDATE metadata SET clean=0 WHERE singleton=1")
            self._event(intent["order_id"], "submit_intent", "local", intent)
            if self.schema_version == RUNTIME_SCHEMA_VERSION:
                self._validate_accounting(self._connection, self.binding, intent['order_id'])

    def observe(self, order_id, state, source="rest", kind="observation"):
        with self._transaction():
            row = self._connection.execute("SELECT intent,state FROM requests WHERE order_id=?", (order_id,)).fetchone()
            if not row:
                raise JournalError("Observation has no durable submission intent")
            validate_record(json.loads(row[0]), state, runtime=self.schema_version == RUNTIME_SCHEMA_VERSION)
            if state["filled_quantity"] < json.loads(row[1])["filled_quantity"] - 1e-9:
                raise JournalError("Durable fill watermark cannot regress")
            self._connection.execute("UPDATE requests SET state=? WHERE order_id=?", (_json(state), order_id))
            self._event(order_id, kind, source, state)
            if self.schema_version == RUNTIME_SCHEMA_VERSION:
                self._validate_accounting(self._connection, self.binding, order_id)

    def report_events(self, order_id=None):
        from .execution_reports import validate_report_events
        with self._mutex:
            self._require_accounting()
            return validate_report_events(self._connection, self.binding,
                                          self._accounting_environment(self._connection), order_id)

    def record_report_event(self, order_id, kind, payload):
        from .execution_reports import REPORT_KINDS
        if self.schema_version != RUNTIME_SCHEMA_VERSION or kind not in REPORT_KINDS:
            raise JournalError('Invalid execution report event')
        with self._transaction():
            previous = self.report_events(order_id).get(order_id, {}).get(kind)
            if previous is not None:
                if previous != payload:
                    raise JournalError('EXECUTION_REPORT_EVENT_CONFLICT')
                return
            self._event(order_id, kind, 'execution_report', payload)
            self.report_events(order_id)

    def mark_flat(self, observed_at):
        with self._transaction():
            if any(state["status"] not in TERMINAL or state["unknown_reason"] or state["cancel_requested"]
                   for _, state in self.records()):
                raise JournalError("Unresolved execution requests prevent clean shutdown")
            self._connection.execute("UPDATE metadata SET clean=1 WHERE singleton=1")
            self._event(None, "account_flat", "account_snapshot", {"observed_at": observed_at})

    @contextmanager
    def _accounting_transaction(self):
        """Explicit transaction includes DDL and publishes no candidate state."""
        with self._mutex:
            self.assert_writable()
            try:
                if self._connection.in_transaction:
                    raise JournalError("Nested accounting transaction")
                self._connection.execute("BEGIN IMMEDIATE")
                if self.schema_version == RUNTIME_SCHEMA_VERSION:
                    self._validate_before_runtime()
                yield
                self._connection.commit()
                self._validated_stamp = self._database_stamp()
            except BaseException as exc:
                self._connection.rollback()
                self.failed = f"Accounting persistence failed; recovery required: {exc}"
                if not isinstance(exc, Exception):
                    raise
                raise JournalError(self.failed) from exc

    @staticmethod
    def _accounting_environment(connection):
        rows = connection.execute("SELECT payload FROM events WHERE kind='accounting_migration'").fetchall()
        if len(rows) != 1:
            raise JournalError("Accounting migration identity missing or duplicated")
        payload = json.loads(rows[0][0])
        if payload.get("schema") != ACCOUNTING_SCHEMA_VERSION or payload.get("environment") not in ("testnet", "production"):
            raise JournalError("Accounting environment invalid")
        return payload["environment"]

    @staticmethod
    def _validate_accounting(connection, binding, order_id=None):
        from backend.bot.executor.accounting_models import ExecutionFact, OrderExecutionState, from_payload, to_payload
        from backend.bot.executor.accounting_reducer import check_link, project
        environment = ExecutionJournal._accounting_environment(connection)
        if order_id is None and connection.execute("PRAGMA foreign_key_check").fetchall():
            raise JournalError("Accounting foreign-key integrity failed")
        states, facts = {}, {}
        where, params = (' WHERE order_id=?', (order_id,)) if order_id is not None else ('', ())
        for oid, raw, seq in connection.execute("SELECT order_id,payload,event_sequence FROM financial_orders" + where, params):
            state = from_payload(json.loads(raw))
            if (type(state) is not OrderExecutionState or state.order_id != oid
                    or state.binding != binding or state.environment != environment):
                raise JournalError("Financial projection identity invalid")
            intent_row = connection.execute("SELECT intent FROM requests WHERE order_id=?", (oid,)).fetchone()
            if not intent_row:
                raise JournalError("Financial projection has no request")
            intent = json.loads(intent_row[0])
            if state.symbol != intent["symbol"] or state.side != intent["side"] or state.requested_quantity != _legacy_amount(intent["quantity"]):
                raise JournalError("Financial projection contradicts request")
            event = connection.execute("SELECT payload FROM events WHERE sequence=?", (seq,)).fetchone()
            if not event or json.loads(event[0]).get("projection") != to_payload(state):
                raise JournalError("Financial projection event mismatch")
            states[oid], facts[oid] = state, []
        for symbol, eid, oid, raw, seq in connection.execute("SELECT symbol,execution_id,order_id,payload,event_sequence FROM execution_facts" + where, params):
            fact = from_payload(json.loads(raw))
            if (type(fact) is not ExecutionFact or (fact.symbol, fact.execution_id) != (symbol, eid)
                    or fact.context.binding != binding or fact.context.environment != environment):
                raise JournalError("Execution fact identity invalid")
            event = connection.execute("SELECT payload FROM events WHERE sequence=?", (seq,)).fetchone()
            if not event or json.loads(event[0]).get("fact") != to_payload(fact):
                raise JournalError("Execution fact event mismatch")
            if oid is not None:
                if oid not in states:
                    raise JournalError("Execution fact has no financial projection")
                check_link(states[oid], fact)
                facts[oid].append(fact)
        for oid, state in states.items():
            if project(state, facts[oid]) != state:
                raise JournalError("Financial projection cannot be replayed")
        version = connection.execute("SELECT version FROM metadata WHERE singleton=1").fetchone()[0]
        if version == RUNTIME_SCHEMA_VERSION:
            migrations = connection.execute("SELECT payload FROM events WHERE kind='runtime_migration'").fetchall()
            if len(migrations) != 1 or json.loads(migrations[0][0]).get("schema") != RUNTIME_SCHEMA_VERSION:
                raise JournalError("Runtime migration evidence missing or duplicated")
            for oid, raw_intent, raw_legacy in connection.execute("SELECT order_id,intent,state FROM requests" + where, params):
                intent, legacy = json.loads(raw_intent), json.loads(raw_legacy)
                validate_record(intent, legacy, runtime=True)
                ExecutionJournal._validate_parent(connection, intent, require_evidence=True)
                if oid not in states:
                    raise JournalError("Runtime request has no financial projection")
                expected = ExecutionJournal._runtime_lifecycle(intent, legacy, states[oid])
                if any(legacy[k] != expected[k] for k in ("filled_quantity", "average_fill_price")):
                    raise JournalError("Runtime lifecycle and financial projection disagree")
        from .execution_reports import validate_report_events
        validate_report_events(connection, binding, environment, order_id)
        return environment

    def _require_accounting(self):
        if self.schema_version not in (ACCOUNTING_SCHEMA_VERSION, RUNTIME_SCHEMA_VERSION):
            raise JournalError("Explicit offline accounting upgrade required")

    def financial_state(self, order_id):
        from backend.bot.executor.accounting_models import from_payload
        with self._mutex:
            self._require_accounting()
            if self.schema_version == RUNTIME_SCHEMA_VERSION:
                self._validate_before_runtime()
            else:
                self._validate_accounting(self._connection, self.binding)
            row = self._connection.execute("SELECT payload FROM financial_orders WHERE order_id=?", (order_id,)).fetchone()
            return from_payload(json.loads(row[0])) if row else None

    def record_accounting(self, evidence):
        """Atomically retain one financial observation (FV1 compatibility API)."""
        if self.schema_version == RUNTIME_SCHEMA_VERSION:
            raise JournalError("Runtime observations require atomic record_execution")
        self._require_accounting()
        with self._accounting_transaction():
            environment = self._validate_accounting(self._connection, self.binding)
            result = self._record_accounting_locked(evidence, environment)
            self._validate_accounting(self._connection, self.binding)
        return result

    def record_execution(self, order_id, evidence=(), *, exchange_id=None, acknowledged=False):
        """Commit lifecycle and financial facts together; no caller candidate is published.

        Empty evidence is permitted only for a positive identity acknowledgment.
        Unowned evidence uses order_id=None and cannot alter a local lifecycle.
        """
        from backend.bot.executor.accounting_models import AccountingError, from_payload
        if self.schema_version != RUNTIME_SCHEMA_VERSION:
            raise JournalError("Runtime accounting schema required")
        evidence = tuple(evidence)
        if not evidence and not acknowledged:
            raise AccountingError("EXECUTION_EVIDENCE_REQUIRED")
        with self._accounting_transaction():
            environment = self._validate_accounting(self._connection, self.binding, order_id)
            intent = previous = None
            if order_id is not None:
                row = self._connection.execute("SELECT intent,state FROM requests WHERE order_id=?", (order_id,)).fetchone()
                if row is None:
                    raise JournalError("Execution update has no durable request")
                intent, previous = map(json.loads, row)
                if acknowledged and not (exchange_id or previous['exchange_id']):
                    raise JournalError('Acknowledgment requires an exchange identity')
                if exchange_id is not None:
                    if not isinstance(exchange_id, str) or not exchange_id.strip():
                        raise JournalError("Invalid exchange identity")
                    if previous["exchange_id"] not in (None, exchange_id):
                        raise JournalError("Exchange identity conflict")
                    if self._connection.execute("SELECT order_id FROM requests WHERE json_extract(state,'$.exchange_id')=? AND order_id<>?", (exchange_id, order_id)).fetchone():
                        raise JournalError("Exchange identity already owned")
                    previous = dict(previous, exchange_id=exchange_id)
                    self._connection.execute("UPDATE requests SET state=? WHERE order_id=?", (_json(previous), order_id))
            results = [self._record_accounting_locked(item, environment) for item in evidence]
            if any(r["state"] is not None and r["state"].order_id != order_id for r in results):
                raise JournalError("Evidence belongs to a different execution request")
            state = legacy = None
            if intent is not None:
                raw = self._connection.execute("SELECT payload FROM financial_orders WHERE order_id=?", (order_id,)).fetchone()
                if raw is None:
                    raise JournalError("Runtime request has no financial projection")
                state = from_payload(json.loads(raw[0]))
                legacy = (self._runtime_lifecycle(intent, previous, state, acknowledged)
                          if acknowledged or any(r['state'] is not None for r in results) else previous)
                validate_record(intent, legacy, runtime=True)
                self._connection.execute("UPDATE requests SET state=? WHERE order_id=?", (_json(legacy), order_id))
                self._event(order_id, "execution_publication", "committed_evidence", {
                    "lifecycle": legacy, "financial_revision": state.revision})
            self._validate_accounting(self._connection, self.binding, order_id)
            result = {"state": state, "lifecycle": legacy, "results": tuple(results)}
        return result

    @staticmethod
    def _runtime_lifecycle(intent, previous, financial, acknowledged=False):
        from decimal import localcontext
        quantity = max(financial.filled_quantity, financial.legacy_quantity)
        price = None
        if (financial.cost is not None and financial.cost_quantity == quantity and quantity > 0
                and not financial.reasons):
            with localcontext() as ctx:
                ctx.prec = 80
                price = float(financial.cost / quantity)
        elif quantity == 0:
            price = 0.0
        status = previous["status"]
        cancel, unknown = previous["cancel_requested"], previous["unknown_reason"]
        if financial.status != "UNOBSERVED":
            status = ("FILLED" if financial.status in TERMINAL and quantity > 0 else
                      "PARTIALLY_FILLED" if financial.status == "OPEN" and quantity > 0 else financial.status)
            unknown = None
            if status in TERMINAL:
                cancel = False
        elif acknowledged and status not in TERMINAL:
            status, unknown = ("PARTIALLY_FILLED" if quantity > 0 else "OPEN"), None
        return dict(previous, status=status, filled_quantity=float(quantity), average_fill_price=price,
                    cancel_requested=cancel, unknown_reason=unknown,
                    updated_at=datetime.now(timezone.utc).isoformat())

    def _record_accounting_locked(self, evidence, environment):
        """Opt-in only. Atomically retain evidence, merge result and projection."""
        from dataclasses import replace
        from backend.bot.executor.accounting_models import (
            AccountingError, ExecutionFact, OrderExecutionObservation, from_payload, to_payload,
        )
        from backend.bot.executor.accounting_reducer import check_link, merge_fact, merge_order, project
        if type(evidence) not in (ExecutionFact, OrderExecutionObservation):
            raise AccountingError("EXECUTION_EVIDENCE_REQUIRED")
        # Round-trip validates nested payloads before touching storage.
        evidence = from_payload(to_payload(evidence))
        self._require_accounting()
        result = None
        state = fact = None
        oid = None
        disposition, reasons = "quarantined", []
        if evidence.context.binding != self.binding or evidence.context.environment != environment:
            reasons = ["EVIDENCE_SCOPE_MISMATCH"]
        else:
            matches = []
            if self.schema_version == RUNTIME_SCHEMA_VERSION:
                rows = self._connection.execute("SELECT intent,state FROM requests WHERE order_id=? OR json_extract(state,'$.exchange_id')=?",
                    (evidence.client_order_id, evidence.exchange_order_id)).fetchall()
                records = [(json.loads(i), json.loads(s)) for i, s in rows]
            else:
                records = self.records()
            for intent, legacy in records:
                current = self._connection.execute("SELECT payload FROM financial_orders WHERE order_id=?", (intent["order_id"],)).fetchone()
                candidate = (from_payload(json.loads(current[0])) if current else
                             _seed_financial(intent, legacy, self.binding, environment))
                if candidate.exchange_order_id is None and legacy["exchange_id"] is not None:
                    candidate = replace(candidate, exchange_order_id=legacy["exchange_id"])
                if evidence.client_order_id == candidate.order_id or (
                        evidence.exchange_order_id is not None
                        and evidence.exchange_order_id in (candidate.exchange_order_id, legacy["exchange_id"])):
                    matches.append(candidate)
            if len(matches) == 1:
                state, oid = matches[0], matches[0].order_id
                try:
                    check_link(state, evidence)
                except AccountingError as exc:
                    state, oid, reasons = None, None, [str(exc)]
            else:
                reasons = ["ORDER_LINK_AMBIGUOUS" if matches else "UNOWNED_EVIDENCE"]
            if type(evidence) is OrderExecutionObservation and state is not None:
                facts = [from_payload(json.loads(r[0])) for r in self._connection.execute(
                    "SELECT payload FROM execution_facts WHERE order_id=?", (oid,))]
                merged = merge_order(state, evidence, facts)
                state, disposition, reasons = merged.state, merged.disposition, list(merged.reasons)
            elif type(evidence) is ExecutionFact and evidence.execution_id is not None:
                existing = self._connection.execute("SELECT order_id,payload FROM execution_facts WHERE symbol=? AND execution_id=?",
                                                   (evidence.symbol, evidence.execution_id)).fetchone()
                previous = from_payload(json.loads(existing[1])) if existing else None
                fact, disposition = merge_fact(previous, evidence)
                # Never transfer an execution already owned by a different request.
                if existing and existing[0] is not None:
                    oid = existing[0]
                    state = from_payload(json.loads(self._connection.execute(
                        "SELECT payload FROM financial_orders WHERE order_id=?", (oid,)).fetchone()[0]))
                if state is not None:
                    try:
                        check_link(state, fact)
                    except AccountingError:
                        fact = replace(previous, conflicts=tuple(sorted(set(previous.conflicts) | {"EXECUTION_OWNER_CONFLICT"}))) if previous else fact
                        state, oid = (state, oid) if existing and existing[0] is not None else (None, None)
                if state is not None and fact.kind != "FUNDING":
                    others = [from_payload(json.loads(r[0])) for r in self._connection.execute(
                        "SELECT payload FROM execution_facts WHERE order_id=? AND NOT (symbol=? AND execution_id=?)",
                        (oid, fact.symbol, fact.execution_id))]
                    state = project(state, others + [fact])
                    state = replace(state, revision=state.revision + (disposition != "duplicate"))
                    reasons = list(state.reasons)
                else:
                    state, oid = None, None
                    reasons = ["FUNDING_NOT_TRADE" if fact.kind == "FUNDING" else "UNOWNED_EVIDENCE"]
                    reasons.extend(fact.conflicts)
                    disposition = "conflict" if fact.conflicts else "quarantined"
            elif type(evidence) is ExecutionFact:
                reasons, state, oid = ["EXECUTION_ID_REQUIRED"], None, None
        payload = {"evidence": to_payload(evidence), "disposition": disposition, "reasons": reasons,
                   "projection": to_payload(state), "fact": to_payload(fact)}
        self._event(oid, "financial_observation", evidence.context.source, payload)
        seq = self._connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        if state is not None:
            self._connection.execute("INSERT INTO financial_orders VALUES(?,?,?) ON CONFLICT(order_id) DO UPDATE SET payload=excluded.payload,event_sequence=excluded.event_sequence",
                                     (oid, _json(to_payload(state)), seq))
        if fact is not None:
            self._connection.execute("INSERT INTO execution_facts VALUES(?,?,?,?,?) ON CONFLICT(symbol,execution_id) DO UPDATE SET order_id=excluded.order_id,payload=excluded.payload,event_sequence=excluded.event_sequence",
                                     (fact.symbol, fact.execution_id, oid, _json(to_payload(fact)), seq))
        result = {"disposition": disposition, "reasons": tuple(reasons), "state": state}
        return result

    def close(self):
        """Release ownership, never infer flatness and never erase recovery state."""
        with self._mutex:
            if self._connection:
                self._connection.close()
                self._connection = None
            if self._lock_file:
                self._lock_file.close()  # OS releases the lock even on process death.
                self._lock_file = None
            if self._owned:
                with _owners_lock:
                    _owners.discard(self._key)
                self._owned = False


def _legacy_amount(value):
    from backend.bot.executor.accounting_models import amount
    return amount(str(value))  # Historical float claim, never raw exchange evidence.


def _seed_financial(intent, state, binding, environment):
    from backend.bot.executor.accounting_models import OrderExecutionState
    qty = _legacy_amount(state["filled_quantity"])
    return OrderExecutionState(intent["order_id"], intent["symbol"], intent["side"], binding, environment,
                               _legacy_amount(intent["quantity"]), state["exchange_id"], legacy_quantity=qty,
                               reasons=("LEGACY_QUANTITY_UNVERIFIED",) if qty else ())


def upgrade_accounting_schema(path, binding, *, environment, target_version=ACCOUNTING_SCHEMA_VERSION):
    """Offline, explicit migration. Never called by service construction.

    An exclusive lease excludes even an executor currently waiting on transport.
    The stable marker and all legacy row values are preserved. Keep the returned
    backup after success; it must not overwrite newer execution evidence.
    """
    from backend.bot.executor.accounting_models import to_payload
    if environment not in ("testnet", "production"):
        raise JournalError("Explicit accounting environment required")
    if target_version not in (ACCOUNTING_SCHEMA_VERSION, RUNTIME_SCHEMA_VERSION):
        raise JournalError("Unsupported accounting migration target")
    owner = object.__new__(ExecutionJournal)
    owner._initialize_handle(path, binding)
    if not owner.path.is_file() or not owner.path.with_suffix(".initialized").is_file():
        raise JournalError("Migration requires an existing initialized store")
    try:
        owner._acquire()
        inspection = ExecutionJournal.inspect(owner.path)
        if inspection.get("error"):
            raise JournalError(inspection["error"])
        marker = json.loads(owner.path.with_suffix(".initialized").read_text(encoding="utf-8"))
        if marker.get("binding") != binding:
            raise JournalError("Migration binding mismatch")
        owner._connection = sqlite3.connect(owner.path.as_uri() + "?mode=rw", uri=True, timeout=2)
        owner._connection.execute("PRAGMA synchronous=FULL")
        owner._connection.execute("PRAGMA foreign_keys=ON")
        version = owner._connection.execute("SELECT version FROM metadata WHERE singleton=1").fetchone()[0]
        owner.schema_version = version
        if version >= target_version:
            if owner._validate_accounting(owner._connection, binding) != environment:
                raise JournalError("Migration environment mismatch")
            return {"schema": version, "already_upgraded": True, "backup": None}
        records = owner.records()
        backup = owner.path.with_name(owner.path.name + f".pre-accounting-v{target_version}-" + uuid.uuid4().hex + ".sqlite3")
        with backup.open("xb"):
            pass
        target = sqlite3.connect(str(backup))
        try:
            owner._connection.backup(target)
            if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise JournalError("Migration backup integrity failure")
            tables = ("metadata", "requests", "events") + (("financial_orders", "execution_facts") if version >= 2 else ())
            for table in tables:
                if target.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() != owner._connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall():
                    raise JournalError("Migration backup contents mismatch")
        finally:
            target.close()
        with backup.open("r+b") as stream:
            os.fsync(stream.fileno())
        if os.name != "nt":
            fd = os.open(str(backup.parent), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        checksum = hashlib.sha256(backup.read_bytes()).hexdigest()
        with owner._accounting_transaction():
            if version < ACCOUNTING_SCHEMA_VERSION:
                owner._create_financial_tables()
                owner._event(None, "accounting_migration", "offline", {"schema": ACCOUNTING_SCHEMA_VERSION,
                             "environment": environment, "backup": str(backup), "backup_sha256": checksum})
            elif owner._accounting_environment(owner._connection) != environment:
                raise JournalError("Migration environment mismatch")
            for intent, legacy in records:
                oid = intent["order_id"]
                current = owner._connection.execute("SELECT payload FROM financial_orders WHERE order_id=?", (oid,)).fetchone()
                if current is None:
                    owner._seed_runtime_order(intent, legacy)
                if target_version == RUNTIME_SCHEMA_VERSION:
                    from backend.bot.executor.accounting_models import from_payload
                    current = owner._connection.execute("SELECT payload FROM financial_orders WHERE order_id=?", (oid,)).fetchone()
                    state = owner._runtime_lifecycle(intent, legacy, from_payload(json.loads(current[0])))
                    owner._event(oid, "runtime_seed", "offline", {"previous_lifecycle": legacy, "lifecycle": state})
                    owner._connection.execute("UPDATE requests SET state=? WHERE order_id=?", (_json(state), oid))
            if target_version == RUNTIME_SCHEMA_VERSION:
                owner._connection.execute("CREATE INDEX execution_facts_order ON execution_facts(order_id)")
                owner._create_runtime_indexes()
                owner._event(None, "runtime_migration", "offline", {"schema": RUNTIME_SCHEMA_VERSION,
                             "backup": str(backup), "backup_sha256": checksum})
            owner._connection.execute("UPDATE metadata SET version=? WHERE singleton=1", (target_version,))
            owner._validate_accounting(owner._connection, binding)
        return {"schema": target_version, "already_upgraded": False,
                "backup": str(backup), "backup_sha256": checksum}
    except Exception as exc:
        if isinstance(exc, JournalError):
            raise
        raise JournalError(f"Accounting migration failed: {exc}") from exc
    finally:
        owner.close()
