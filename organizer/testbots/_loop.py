"""Plumbing test bots: each misbehaves in one way. They play any legal move,
since the move doesn't matter, only how they deliver it."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "arena"))
from rules import GAME  # noqa: E402

MOVE = GAME.moves[0]


def run(choose, out=lambda m: print(m, flush=True), on_round=None):
    n = 0
    for line in sys.stdin:
        p = line.split()
        if not p: continue
        if p[0] == "ROUND":
            n += 1
            if on_round: on_round(n)
            out(choose(p))
        elif p[0] == "END":
            break
