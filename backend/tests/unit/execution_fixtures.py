"""Explicit temporary durable storage for pre-existing isolated executor fixtures."""
from backend.bot.executor.execution_journal import ExecutionJournal


def attach_journal(ex, path):
    ex._journal = ExecutionJournal(path, "offline-fixture")
    ex._journaled_ids = set()
    ex._restored_ids = set()
    ex._recovery_only = False
    ex._journal_error = None
    ex._inflight_mutations = 0
    ex._execution_owner = "fixture"
    ex._execution_generation = "fixture-generation"


def seed_order(ex, order):
    purpose = ("exit" if order.order_id in ex._reduce_only_order_ids else
               "entry" if order.order_type.value in ("LIMIT", "MARKET") else "protection")
    intent = {"order_id": order.order_id, "symbol": order.symbol, "side": order.side.value,
              "order_type": order.order_type.value, "quantity": order.quantity,
              "price": order.price, "stop_price": order.stop_price, "purpose": purpose,
              "reduce_only": purpose != "entry", "owner": "fixture", "generation": "fixture-generation",
              "wire": {"symbol": order.symbol, "side": order.side.value.lower(), "amount": order.quantity,
                       "order_type": "limit", "price": order.price, "params": {"clientOrderId": order.order_id}}}
    ex._journal.submit_intent(intent, ex._durable_state(order))
    ex._journaled_ids.add(order.order_id)
