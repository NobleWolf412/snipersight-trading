"""The journal must not be able to call a loss a win.

Between 2026-04-21 and 2026-05-20, 306 of 460 rows recorded `exit_reason=target`
against a negative P&L. The cause — a target on the unfavourable side of the fill
registering as hit the instant the position opened — was fixed at source in
`position_manager._check_targets_hit` (9a9a7c9), and the 82 target exits recorded
since are all genuinely profitable.

These tests do not re-test that fix. They pin the property that makes the class
of failure unrepeatable: **a win is decided by money, never by a label**, at the
write layer, for every path including ones not written yet.
"""
import unittest

from bot.exit_classification import classify, enrich, EXIT_PATHS


def row(**kw):
    base = dict(symbol="BTC/USDT", direction="LONG", entry_price=100.0,
                exit_price=101.0, quantity=10.0, pnl=10.0, exit_reason="target")
    base.update(kw)
    return base


class ClassifyCase(unittest.TestCase):

    # ---------- the defect that actually happened ----------

    def test_a_target_that_lost_money_is_a_loss_and_a_conflict(self):
        """The literal shape of the 306 bad rows: XRP LONG, entry 1.4369215,
        exit 1.4366, exit_reason 'target', pnl -0.77."""
        c = classify(row(entry_price=1.4369215, exit_price=1.4366,
                         quantity=1595.03, pnl=-0.7692, exit_reason="target"))
        # -$0.77 on a $2,292 position is inside the round-trip fee, so the honest
        # outcome is SCRATCH rather than LOSS — and it is still a conflict, because
        # a target that price never travelled to was not hit. This exact row shape
        # is why scratches must flag: the 306 bad rows were near-zero moves, not
        # large losses, so a rule that only caught decided losses would catch none.
        self.assertEqual(c["outcome"], "SCRATCH")
        self.assertTrue(c["label_conflict"], "the contradiction must be recorded")
        self.assertIn("round-trip cost", c["conflict_note"])

    def test_the_conflict_note_names_both_sides(self):
        c = classify(row(pnl=-25.0, exit_reason="target", quantity=1.0, entry_price=100.0))
        self.assertIn("target", c["conflict_note"])
        self.assertIn("lost", c["conflict_note"])

    def test_a_stop_that_made_money_is_also_a_conflict(self):
        """The mirror case. A genuine trailed exit arrives labelled `trailing_stop`
        and is NOT a conflict — see the trail test below — so a plain `stop_loss`
        closing green means something is wrong."""
        c = classify(row(pnl=+40.0, exit_reason="stop_loss"))
        self.assertEqual(c["outcome"], "WIN")
        self.assertTrue(c["label_conflict"])

    # ---------- the honest cases must stay quiet ----------

    def test_a_real_target_is_not_flagged(self):
        c = classify(row(pnl=+18.0, exit_reason="target"))
        self.assertEqual(c["outcome"], "WIN")
        self.assertFalse(c["label_conflict"])

    def test_a_real_stop_is_not_flagged(self):
        c = classify(row(pnl=-12.0, exit_reason="stop_loss"))
        self.assertEqual(c["outcome"], "LOSS")
        self.assertFalse(c["label_conflict"])

    def test_a_trailed_stop_closing_green_is_not_a_conflict(self):
        """The trail doing its job. Flagging this would train the operator to
        ignore the flag, which is how a warning stops being one."""
        for reason in ("trailing_stop", "trail_stop", "breakeven_stop"):
            c = classify(row(pnl=+31.0, exit_reason=reason))
            self.assertFalse(c["label_conflict"], f"{reason} closing green is normal")

    def test_paths_with_no_expected_sign_are_never_flagged(self):
        """Stagnation, operator closes and direction flips can honestly land on
        either side. Asserting a sign for them would manufacture false alarms."""
        for reason in ("stagnation", "session_stopped", "direction_flip",
                       "max_hours_open", "emergency"):
            for pnl in (+9.0, -9.0):
                self.assertFalse(classify(row(pnl=pnl, exit_reason=reason))["label_conflict"],
                                 f"{reason} at pnl={pnl} must not be flagged")

    # ---------- scratches ----------

    def test_a_trade_inside_the_round_trip_fee_is_a_scratch(self):
        """$1000 notional, 0.1% a side = $2 round trip. A 40-cent 'win' paid the
        venue and went home; counting it as a win is most of how a 37% strategy
        displayed 50%."""
        c = classify(row(quantity=10.0, entry_price=100.0, pnl=+0.40))
        self.assertEqual(c["outcome"], "SCRATCH")

    def test_a_scratch_on_a_bracket_exit_IS_a_conflict(self):
        """A target or a stop names a price chosen in advance. Landing inside the
        fee band means the bracket sat on top of the fill — the historical defect
        exactly. Scratch on an unbracketed path stays quiet (see below)."""
        for reason in ("target", "stop_loss"):
            c = classify(row(quantity=10.0, entry_price=100.0, pnl=-0.40,
                             exit_reason=reason))
            self.assertEqual(c["outcome"], "SCRATCH")
            self.assertTrue(c["label_conflict"], f"{reason} scratch must flag")

    def test_a_scratch_on_a_path_with_no_expected_sign_is_quiet(self):
        c = classify(row(quantity=10.0, entry_price=100.0, pnl=-0.40,
                         exit_reason="stagnation"))
        self.assertEqual(c["outcome"], "SCRATCH")
        self.assertFalse(c["label_conflict"])

    def test_a_move_clearly_beyond_the_fee_is_decided(self):
        c = classify(row(quantity=10.0, entry_price=100.0, pnl=+8.0))
        self.assertEqual(c["outcome"], "WIN")

    # ---------- provenance and safety ----------

    def test_the_engines_own_reason_is_never_overwritten(self):
        """`exit_reason` is what made the later forensic possible. The honest
        fields are added beside it, never on top of it."""
        r = row(pnl=-5.0, exit_reason="target")
        out = enrich(r)
        self.assertEqual(out["exit_reason"], "target")
        self.assertEqual(out["outcome"], "LOSS")
        self.assertEqual(r.get("outcome"), None, "enrich must not mutate its input")

    def test_an_unknown_reason_is_classified_not_dropped(self):
        c = classify(row(pnl=-5.0, exit_reason="some_future_exit_path"))
        self.assertEqual(c["exit_path"], "UNKNOWN")
        self.assertEqual(c["outcome"], "LOSS", "money still decides")
        self.assertFalse(c["label_conflict"], "no expectation, so no contradiction")

    def test_a_missing_pnl_is_unknown_rather_than_zero(self):
        """A missing number must never default to a value that reads as a result."""
        c = classify(row(pnl=None))
        self.assertEqual(c["outcome"], "UNKNOWN")
        self.assertFalse(c["label_conflict"])

    def test_short_direction_is_handled(self):
        c = classify(row(direction="SHORT", entry_price=100.0, exit_price=99.0,
                         pnl=+10.0, exit_reason="target"))
        self.assertEqual(c["outcome"], "WIN")
        self.assertFalse(c["label_conflict"])

    def test_every_mapped_reason_resolves_to_a_family(self):
        for reason, family in EXIT_PATHS.items():
            self.assertEqual(classify(row(exit_reason=reason))["exit_path"], family)

    # ---------- realized R ----------

    def test_realized_r_is_none_when_the_stop_is_unknown(self):
        """An R derived from an assumed risk is worse than no R, because it looks
        like a measurement."""
        self.assertIsNone(classify(row())["realized_r"])

    def test_realized_r_is_computed_when_the_stop_is_present(self):
        # entry 100, stop 98 -> $2 risk/unit, 10 units -> $20 risk. +$40 = +2R
        c = classify(row(entry_price=100.0, stop_price=98.0, quantity=10.0, pnl=40.0))
        self.assertAlmostEqual(c["realized_r"], 2.0, places=6)


class JournalWriteCase(unittest.TestCase):
    """Both write paths must classify. A second writer that skipped it is exactly
    how the original defect stayed invisible for a month."""

    def setUp(self):
        import tempfile, pathlib
        from bot.trade_journal import TradeJournalService
        self.tmp = tempfile.TemporaryDirectory()
        self.j = TradeJournalService(pathlib.Path(self.tmp.name) / "j.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def _rows(self):
        import json
        with open(self.j._path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_append_stamps_the_honest_fields(self):
        self.j.append(row(pnl=-5.0, exit_reason="target"), "sess")
        r = self._rows()[0]
        self.assertEqual(r["outcome"], "LOSS")
        self.assertTrue(r["label_conflict"])

    def test_upsert_stamps_them_too(self):
        self.j.upsert(row(pnl=-5.0, exit_reason="target", trade_id="t1"), "sess")
        r = self._rows()[0]
        self.assertEqual(r["outcome"], "LOSS")
        self.assertTrue(r["label_conflict"])

    def test_a_contradictory_trade_is_kept_not_dropped(self):
        """It happened. Dropping it would swap an overstated win rate for a
        missing trade, which is worse."""
        self.j.append(row(pnl=-5.0, exit_reason="target"), "sess")
        self.assertEqual(len(self._rows()), 1)

    def test_aggregate_counts_wins_by_money_and_reports_the_damage(self):
        self.j.append(row(pnl=-5.0, exit_reason="target"), "s")     # conflict, loss
        self.j.append(row(pnl=+8.0, exit_reason="target"), "s")     # honest win
        self.j.append(row(pnl=-4.0, exit_reason="stop_loss"), "s")  # honest loss
        self.j.append(row(quantity=10.0, entry_price=100.0,
                          pnl=+0.30, exit_reason="stagnation"), "s")  # quiet scratch
        a = self.j.aggregate()
        self.assertEqual(a["winning_trades"], 1)
        self.assertEqual(a["losing_trades"], 2)
        self.assertEqual(a["scratches"], 1)
        self.assertEqual(a["label_conflicts"], 1)
        self.assertEqual(a["decided_trades"], 3)
        self.assertEqual(a["win_rate"], round(1 / 3 * 100, 1),
                         "scratches must leave the denominator, not pad it")

    def test_win_rate_excludes_scratches_from_the_denominator(self):
        for _ in range(9):
            self.j.append(row(quantity=10.0, entry_price=100.0, pnl=+0.10,
                              exit_reason="stagnation"), "s")
        self.j.append(row(quantity=10.0, entry_price=100.0, pnl=+8.0), "s")
        a = self.j.aggregate()
        self.assertEqual(a["win_rate"], 100.0,
                         "one real win and nine scratches is 100% of what was decided")
        self.assertEqual(a["total_trades"], 10)


if __name__ == "__main__":
    unittest.main()
