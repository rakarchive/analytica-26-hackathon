"""Cooperative Kernel."""

# ---- the protocol, and a little bookkeeping (the same in every bot here) ----

import random
import sys

C, D = "C", "D"


class Bot:
    """Keeps the match history so strategies can stay short. Subclasses
    implement choose(); self.my and self.opp are the ACTUAL moves so far
    (after noise), oldest first, and self.intent is what this bot meant
    to play, which noise may have changed."""

    def __init__(self):
        self.rng = random.Random()
        self.reset()

    def reset(self):
        """New match: forget everything about the last opponent."""
        self.my, self.opp, self.intent = [], [], []
        self.state = {}

    def move(self):
        m = self.choose()
        self.intent.append(m)
        return m

    def t(self):
        """The round about to be played, counting from 0."""
        return len(self.my)

    def opp_d_rate(self, window=None):
        xs = self.opp[-window:] if window else self.opp
        return xs.count(D) / len(xs) if xs else 0.0


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
            print(bot.move(), flush=True)
        elif p[0] == "END":
            break

# ---- the strategy ----


class ContriteFirm(Bot):
    """Contrite tit-for-tat that also gives up on opponents which
    defect most of the time."""
    def choose(self):
        t = self.t()
        excused = self.state.setdefault("excused", set())
        if t and self.my[-1] == D and self.intent[-1] == C:
            excused.add(t)
        move = C
        if self.opp and self.opp[-1] == D and (t - 1) not in excused:
            move = D
        if t >= 20 and self.opp_d_rate(20) >= 0.6:
            move = D
        return move


if __name__ == "__main__":
    run(ContriteFirm())
