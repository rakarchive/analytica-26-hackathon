"""Iocaine Powder (lite): runs several predictors side by side, scores each
on how well it would have done over the last 20 rounds, and follows the best.
Falls back to random when none of them is doing better than chance."""

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


def score(mine, theirs):
    return 1 if BEATEN_BY[theirs] == mine else -1 if BEATEN_BY[mine] == theirs else 0


class Iocaine(Bot):
    def predictors(self, my, opp):
        """Each one's move for the round after `my`/`opp`."""
        if not opp:
            return []
        fav = max(MOVES, key=opp[-10:].count)
        return [beat(opp[-1]),            # they repeat
                beat(fav),                # they have a favourite
                beat(beat(my[-1])),       # they beat my last
                beat(beat(beat(my[-1])))]  # they second-guess me

    def choose(self):
        n = len(self.opp)
        if n < 3:
            return self.rng.choice(MOVES)
        totals = [0] * 4
        for k in range(max(1, n - 20), n):
            for p, move in enumerate(self.predictors(self.my[:k], self.opp[:k])):
                totals[p] += score(move, self.opp[k])
        best = max(range(4), key=lambda p: totals[p])
        if totals[best] <= 2:
            return self.rng.choice(MOVES)
        return self.predictors(self.my, self.opp)[best]


if __name__ == "__main__":
    run(Iocaine())
