"""Seeded reference bots. ORGANIZER ONLY: do not ship to teams.

Teams are told seeding exists, not what is in it. The set spans the
exploitability spectrum, from trivially exploitable to punishing probes hard.

Reconstructed from the design handoff. ForgivingThreshold's exact rule was not
recorded there; the one below is a fresh choice (see its docstring).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "arena"))

from baselines import AlwaysCooperate, AlwaysDefect, GenerousTFT, Pavlov, RandomBot, TitForTat
from harness import C, D, Strategy


class ForgivingThreshold(Strategy):
    """Tit-for-tat that ignores defections until they are frequent: it only
    answers a D with a D once the opponent has 3+ defections in the last 10
    rounds. Isolated noise flips are forgiven entirely, so an opponent can
    slip in about one deliberate defection per ten rounds for free. That makes
    it exploitable, but only by a bot that probes for the threshold carefully."""
    name = "forgiving_threshold"

    def __init__(self, window=10, threshold=3):
        self.window, self.threshold = window, threshold

    def choose(self):
        if not self.opp or self.opp[-1] == C:
            return C
        return D if self.opp[-self.window:].count(D) >= self.threshold else C


class SlowGrudge(Strategy):
    """Cooperates until the opponent has 4+ defections in the last 10 rounds,
    then defects for 20 rounds no matter what, then starts counting afresh.
    The window has to slide: a cumulative grim trigger goes off from noise
    alone (~10 flips per 200-round match) and turns into always-defect."""
    name = "slow_grudge"

    def __init__(self, window=10, threshold=4, grudge=20):
        self.window, self.threshold, self.grudge = window, threshold, grudge

    def reset(self, rng):
        super().reset(rng)
        self.punish_left = 0
        self.count_from = 0  # ignore history from before the last grudge ended

    def choose(self):
        if self.punish_left:
            self.punish_left -= 1
            if not self.punish_left:
                self.count_from = len(self.opp) + 1
            return D
        recent = self.opp[max(self.count_from, len(self.opp) - self.window):]
        if recent.count(D) >= self.threshold:
            self.punish_left = self.grudge - 1
            return D
        return C


# (name, class, kwargs). GenerousTFT uses p=0.4 here, not the p=1/3 that ships
# in the starter pack, so the shipped baseline doesn't reveal the seeded one.
REFERENCE_BOTS = [
    ("ref_always_cooperate", AlwaysCooperate, {}),
    ("ref_generous_tft", GenerousTFT, {"p": 0.4}),
    ("ref_forgiving_threshold", ForgivingThreshold, {}),
    ("ref_tit_for_tat", TitForTat, {}),
    ("ref_pavlov", Pavlov, {}),
    ("ref_random", RandomBot, {}),
    ("ref_slow_grudge", SlowGrudge, {}),
    ("ref_always_defect", AlwaysDefect, {}),
]


def reference_specs():
    return [{"name": name, "kind": "ref", "strategy": (cls.__module__, cls.__name__, kw)}
            for name, cls, kw in REFERENCE_BOTS]
