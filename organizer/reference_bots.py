"""Seeded reference bots for the practice game. ORGANIZER ONLY: do not ship
to teams.

A spread from trivially exploitable (a cycle, a rock habit) to unexploitable
(random), with two that adapt, so a practice run has some texture. Nothing
here matters for the real event; it's the same machinery, exercised.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "arena"))

from harness import Strategy
from rules import P, R, S
from sparring import Cycler, RandomBot

MOVES = (R, P, S)
BEATEN_BY = {R: P, P: S, S: R}   # what beats each move


class RockHeavy(Strategy):
    """Rock with probability p, otherwise random: a habit worth finding."""
    name = "rock_heavy"

    def __init__(self, p=0.6):
        self.p = p

    def choose(self):
        return R if self.rng.random() < self.p else self.rng.choice(MOVES)


class Markov(Strategy):
    """Predicts the opponent's next move from what it played after its last
    one, and beats it."""
    name = "markov"

    def choose(self):
        if len(self.opp) < 2:
            return self.rng.choice(MOVES)
        last = self.opp[-1]
        after = [self.opp[k + 1] for k in range(len(self.opp) - 1) if self.opp[k] == last]
        return BEATEN_BY[max(MOVES, key=after.count)]


class FrequencyHunter(Strategy):
    """Beats the opponent's favourite move over the last `window` rounds."""
    name = "frequency_hunter"

    def __init__(self, window=20):
        self.window = window

    def choose(self):
        recent = self.opp[-self.window:]
        if not recent:
            return P
        return BEATEN_BY[max(MOVES, key=recent.count)]


class Switcher(Strategy):
    """Win-stay, lose-shift: keeps a winning move, and after a loss or a draw
    plays what would have beaten the opponent's last move."""
    name = "switcher"

    def choose(self):
        if not self.my:
            return S
        if BEATEN_BY[self.opp[-1]] == self.my[-1]:
            return self.my[-1]
        return BEATEN_BY[self.opp[-1]]


REFERENCE_BOTS = [
    ("ref_cycler", Cycler, {}),
    ("ref_rock_heavy", RockHeavy, {"p": 0.6}),
    ("ref_switcher", Switcher, {}),
    ("ref_frequency_hunter", FrequencyHunter, {}),
    ("ref_markov", Markov, {}),
    ("ref_random", RandomBot, {}),
]


def reference_specs():
    return [{"name": name, "kind": "ref", "strategy": (cls.__module__, cls.__name__, kw)}
            for name, cls, kw in REFERENCE_BOTS]
