"""Bayes Watch."""

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


class Bayes(Bot):
    """Estimates P(opp C | my previous actual move) and picks the move with
    the better payoff now plus the opponent's expected response next round."""
    def choose(self):
        t = self.t()
        if t < 2:
            return C
        cc = cd = nc = nd = 1  # Laplace
        for k in range(1, t):
            if self.my[k - 1] == C:
                nc += 1
                cc += self.opp[k] == C
            else:
                nd += 1
                cd += self.opp[k] == C
        p_after_c, p_after_d = cc / (nc + 1), cd / (nd + 1)
        p_now = p_after_c if self.my[-1] == C else p_after_d
        v_c = 3 * p_now + 3 * p_after_c
        v_d = 5 * p_now + (1 - p_now) + 3 * p_after_d
        return D if v_d > v_c else C


if __name__ == "__main__":
    run(Bayes())
