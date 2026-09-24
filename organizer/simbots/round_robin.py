"""Round Robin: rock, paper, scissors, rock, paper, scissors..."""

# ---- the protocol, and a little bookkeeping (the same in every bot here) ----

import random
import sys

R, P, S = "R", "P", "S"
MOVES = (R, P, S)
BEATEN_BY = {R: P, P: S, S: R}   # what beats each move


def beat(move):
    return BEATEN_BY[move]


class Bot:
    """Keeps the match history so strategies can stay short. Subclasses
    implement choose(); self.my and self.opp are the ACTUAL moves so far
    (after noise), oldest first."""

    def __init__(self):
        self.rng = random.Random()
        self.reset()

    def reset(self):
        """New match: forget everything about the last opponent."""
        self.my, self.opp = [], []
        self.state = {}

    def t(self):
        """The round about to be played, counting from 0."""
        return len(self.my)

    def favourite(self, window=None):
        """The opponent's most played move, over the last `window` rounds."""
        xs = self.opp[-window:] if window else self.opp
        return max(MOVES, key=xs.count) if xs else None


def run(bot):
    """Talk to the tournament: RESET, ROUND, END. stdout is moves only."""
    for line in sys.stdin:
        p = line.split()
        if not p:
            continue
        if p[0] == "RESET":
            bot.reset()
        elif p[0] == "ROUND":
            if p[1] != "-":
                bot.my.append(p[1])
                bot.opp.append(p[2])
            print(bot.choose(), flush=True)
        elif p[0] == "END":
            break

# ---- the strategy ----


class Cycle(Bot):
    def choose(self):
        return MOVES[self.t() % 3]


if __name__ == "__main__":
    run(Cycle())
