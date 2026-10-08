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


def validate_record(intent, state):
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
    def __init__(self, path: Path, binding: str):
        self._initialize_handle(path, binding)
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
                with self._connection:
                    self._connection.execute("CREATE TABLE metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL, store_id TEXT NOT NULL, binding TEXT NOT NULL, clean INTEGER NOT NULL)")
                    self._connection.execute("CREATE TABLE requests (order_id TEXT PRIMARY KEY, intent TEXT NOT NULL, state TEXT NOT NULL)")
                    self._connection.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, order_id TEXT, kind TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL)")
                    self._connection.execute("INSERT INTO metadata VALUES (1, ?, ?, ?, 1)", (SCHEMA_VERSION, store_id, binding))
            meta = self._connection.execute("SELECT version,store_id,binding,clean FROM metadata WHERE singleton=1").fetchone()
            if (not meta or meta[0] not in (SCHEMA_VERSION, ACCOUNTING_SCHEMA_VERSION)
                    or meta[1:3] != (marker_data.get("store_id"), binding)
                    or meta[3] not in (0, 1)):
                raise JournalError("Execution database schema/identity mismatch")
            self.schema_version = meta[0]
            self.was_clean = bool(meta[3])
            self.records()  # Validate the whole restore set before marking ownership active.
            if self.schema_version == ACCOUNTING_SCHEMA_VERSION:
                self._validate_accounting(self._connection, binding)
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
                    yield
            except Exception as exc:
                self.failed = f"Execution persistence failed; recovery required: {exc}"
                raise JournalError(self.failed) from exc

    def _event(self, order_id, kind, source, payload):
        self._connection.execute("INSERT INTO events(order_id,kind,source,observed_at,payload) VALUES(?,?,?,?,?)",
                                 (order_id, kind, source, datetime.now(timezone.utc).isoformat(), _json(payload)))

    def records(self):
        with self._mutex:
            rows = self._connection.execute("SELECT order_id,intent,state FROM requests ORDER BY rowid").fetchall()
            records = []
            for oid, raw_intent, raw_state in rows:
                intent, state = json.loads(raw_intent), json.loads(raw_state)
                validate_record(intent, state)
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
            if (not meta or meta[0] not in (SCHEMA_VERSION, ACCOUNTING_SCHEMA_VERSION)
                    or meta[1:3] != (mark.get("store_id"), mark.get("binding"))
                    or mark.get("version") != MARKER_VERSION or meta[3] not in (0, 1)):
                raise JournalError("Execution database schema/identity mismatch")
            if meta[0] == ACCOUNTING_SCHEMA_VERSION:
                ExecutionJournal._validate_accounting(connection, mark.get("binding"))
            requests = []
            for oid, raw_intent, raw_state in connection.execute("SELECT order_id,intent,state FROM requests"):
                intent, state = json.loads(raw_intent), json.loads(raw_state)
                validate_record(intent, state)
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

    def submit_intent(self, intent, state):
        validate_record(intent, state)
        with self._transaction():
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
            self._connection.execute("UPDATE metadata SET clean=0 WHERE singleton=1")
            self._event(intent["order_id"], "submit_intent", "local", intent)

    def observe(self, order_id, state, source="rest", kind="observation"):
        with self._transaction():
            row = self._connection.execute("SELECT intent,state FROM requests WHERE order_id=?", (order_id,)).fetchone()
            if not row:
                raise JournalError("Observation has no durable submission intent")
            validate_record(json.loads(row[0]), state)
            if state["filled_quantity"] < json.loads(row[1])["filled_quantity"] - 1e-9:
                raise JournalError("Durable fill watermark cannot regress")
            self._connection.execute("UPDATE requests SET state=? WHERE order_id=?", (_json(state), order_id))
            self._event(order_id, kind, source, state)

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
                yield
                self._connection.commit()
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
    def _validate_accounting(connection, binding):
        from backend.bot.executor.accounting_models import ExecutionFact, OrderExecutionState, from_payload, to_payload
        from backend.bot.executor.accounting_reducer import check_link, project
        environment = ExecutionJournal._accounting_environment(connection)
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise JournalError("Accounting foreign-key integrity failed")
        states, facts = {}, {}
        for oid, raw, seq in connection.execute("SELECT order_id,payload,event_sequence FROM financial_orders"):
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
        for symbol, eid, oid, raw, seq in connection.execute("SELECT symbol,execution_id,order_id,payload,event_sequence FROM execution_facts"):
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
        return environment

    def _require_accounting(self):
        if self.schema_version != ACCOUNTING_SCHEMA_VERSION:
            raise JournalError("Explicit offline accounting upgrade required")

    def financial_state(self, order_id):
        from backend.bot.executor.accounting_models import from_payload
        with self._mutex:
            self._require_accounting()
            self._validate_accounting(self._connection, self.binding)
            row = self._connection.execute("SELECT payload FROM financial_orders WHERE order_id=?", (order_id,)).fetchone()
            return from_payload(json.loads(row[0])) if row else None

    def record_accounting(self, evidence):
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
        with self._accounting_transaction():
            environment = self._validate_accounting(self._connection, self.binding)
            state = fact = None
            oid = None
            disposition, reasons = "quarantined", []
            if evidence.context.binding != self.binding or evidence.context.environment != environment:
                reasons = ["EVIDENCE_SCOPE_MISMATCH"]
            else:
                matches = []
                for intent, legacy in self.records():
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
            self._validate_accounting(self._connection, self.binding)
            result = {"disposition": disposition, "reasons": tuple(reasons), "state": state}
        return result  # The transaction has committed; no financial state cache exists.

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


def upgrade_accounting_schema(path, binding, *, environment):
    """Offline, explicit migration. Never called by service construction.

    An exclusive lease excludes even an executor currently waiting on transport.
    The stable marker and all legacy row values are preserved. Keep the returned
    backup after success; it must not overwrite newer execution evidence.
    """
    from backend.bot.executor.accounting_models import to_payload
    if environment not in ("testnet", "production"):
        raise JournalError("Explicit accounting environment required")
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
        if version == ACCOUNTING_SCHEMA_VERSION:
            if owner._validate_accounting(owner._connection, binding) != environment:
                raise JournalError("Migration environment mismatch")
            return {"schema": version, "already_upgraded": True, "backup": None}
        records = owner.records()
        backup = owner.path.with_name(owner.path.name + ".pre-accounting-v2-" + uuid.uuid4().hex + ".sqlite3")
        with backup.open("xb"):
            pass
        target = sqlite3.connect(str(backup))
        try:
            owner._connection.backup(target)
            if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise JournalError("Migration backup integrity failure")
            for table in ("metadata", "requests", "events"):
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
            owner._connection.execute("CREATE TABLE financial_orders (order_id TEXT PRIMARY KEY REFERENCES requests(order_id), payload TEXT NOT NULL, event_sequence INTEGER NOT NULL REFERENCES events(sequence))")
            owner._connection.execute("CREATE TABLE execution_facts (symbol TEXT NOT NULL, execution_id TEXT NOT NULL, order_id TEXT REFERENCES requests(order_id), payload TEXT NOT NULL, event_sequence INTEGER NOT NULL REFERENCES events(sequence), PRIMARY KEY(symbol,execution_id))")
            owner._event(None, "accounting_migration", "offline", {"schema": ACCOUNTING_SCHEMA_VERSION,
                         "environment": environment, "backup": str(backup), "backup_sha256": checksum})
            for intent, legacy in records:
                state = _seed_financial(intent, legacy, binding, environment)
                owner._event(intent["order_id"], "financial_seed", "legacy_unverified", {"projection": to_payload(state)})
                seq = owner._connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                owner._connection.execute("INSERT INTO financial_orders VALUES(?,?,?)", (intent["order_id"], _json(to_payload(state)), seq))
            owner._validate_accounting(owner._connection, binding)
            owner._connection.execute("UPDATE metadata SET version=? WHERE singleton=1", (ACCOUNTING_SCHEMA_VERSION,))
        return {"schema": ACCOUNTING_SCHEMA_VERSION, "already_upgraded": False,
                "backup": str(backup), "backup_sha256": checksum}
    except Exception as exc:
        if isinstance(exc, JournalError):
            raise
        raise JournalError(f"Accounting migration failed: {exc}") from exc
    finally:
        owner.close()
