"""Order-flow (CVD) forward-capture — observational only, no decision-path coupling.

decisions/2026-06-30__cvd-experiment. Phase A captures Cumulative-Volume-Delta features at entry into
the journal so they can be tested against the noise floor BEFORE any of it touches a trading decision.
"""
from backend.bot.cvd.cvd_tracker import CvdTracker

__all__ = ["CvdTracker"]
