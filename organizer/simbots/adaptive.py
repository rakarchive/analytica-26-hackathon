"""Axelrod Acolytes."""

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


class Adaptive(Bot):
    """Probe once, then classify from how the opponent reacts to my (intended
    and noise-flipped) defections: exploit pushovers, defect against
    defectors and randoms, otherwise play contrite TFT."""
    def choose(self):
        t = self.t()
        if t < 2:
            return C
        if t == 2:
            return D  # probe
        provoked = retal = unprov_n = unprov_d = 0
        for k in range(1, t):
            if self.my[k - 1] == D:
                provoked += 1
                retal += self.opp[k] == D
            else:
                unprov_n += 1
                unprov_d += self.opp[k] == D
        retal_rate = retal / provoked if provoked else 1.0
        unprov_rate = unprov_d / unprov_n if unprov_n else 0.0
        if t >= 20 and self.opp_d_rate(20) > 0.7:
            return D
        if t >= 12 and unprov_rate > 0.35:
            return D
        if provoked >= 3 and retal_rate < 0.15 and unprov_rate < 0.2:
            return D  # never punishes: take everything
        if provoked >= 2 and retal_rate < 0.3 and unprov_rate < 0.2:
            return C if self.intent[-1] == D else D  # punishes only doubles: alternate
        excused = self.state.setdefault("excused", set())
        if self.my[-1] == D and self.intent[-1] == C:
            excused.add(t)
        if self.opp[-1] == D and (t - 1) not in excused:
            return D
        return C


if __name__ == "__main__":
    run(Adaptive())
