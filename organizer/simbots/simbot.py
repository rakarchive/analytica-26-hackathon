"""Simulated team submissions for dry runs:  python simbot.py <strategy> [param]

A spread of what 20 teams might plausibly submit in 90 minutes, from
Tier 0 (textbook, often noise-naive) through Tier 2 (opponent modelling).
All speak the real protocol, so they exercise the same plumbing as teams.
"""

import random
import sys

C, D = "C", "D"


class Bot:
    def __init__(self, param):
        self.param = param
        self.rng = random.Random()
        self.reset()

    def reset(self):
        self.my, self.opp, self.intent = [], [], []
        self.state = {}

    def move(self):
        m = self.choose()
        self.intent.append(m)
        return m

    # helpers
    def t(self):
        return len(self.my)

    def opp_d_rate(self, window=None):
        xs = self.opp[-window:] if window else self.opp
        return xs.count(D) / len(xs) if xs else 0.0


# ---------------- Tier 0 ----------------

class TFT(Bot):
    def choose(self):
        return self.opp[-1] if self.opp else C


class AllD(Bot):
    def choose(self):
        return D


class Grim(Bot):
    def choose(self):
        return D if D in self.opp else C


class Coin(Bot):
    def choose(self):
        return C if self.rng.random() < float(self.param or 0.8) else D


# ---------------- Tier 1 ----------------

class GTFT(Bot):
    def choose(self):
        if not self.opp or self.opp[-1] == C:
            return C
        return C if self.rng.random() < float(self.param) else D


class Pavlov(Bot):
    def choose(self):
        if not self.my:
            return C
        return self.my[-1] if self.opp[-1] == C else (D if self.my[-1] == C else C)


class ContriteTFT(Bot):
    """Doesn't echo retaliation for its own noise-flipped moves."""
    def choose(self):
        t = self.t()
        excused = self.state.setdefault("excused", set())
        if t and self.my[-1] == D and self.intent[-1] == C:
            excused.add(t)
        move = C
        if self.opp and self.opp[-1] == D and (t - 1) not in excused:
            move = D
        if self.param == "firm" and t >= 20 and self.opp_d_rate(20) >= 0.6:
            move = D
        return move


class TF2T(Bot):
    def choose(self):
        return D if self.opp[-2:] == [D, D] else C


class WindowGrudge(Bot):
    def choose(self):
        s = self.state
        if s.get("punish", 0):
            s["punish"] -= 1
            return D
        if self.opp[-10:].count(D) >= 3:
            s["punish"] = 4
            return D
        return C


class Majority(Bot):
    def choose(self):
        return C if self.opp.count(C) >= self.opp.count(D) else D


class Gradual(Bot):
    """Beaufils' Gradual: the n-th defection is answered with n defections
    then two cooperations. Escalates badly under noise."""
    def choose(self):
        s = self.state
        if s.get("queue"):
            return s["queue"].pop(0)
        if self.opp and self.opp[-1] == D:
            s["n"] = s.get("n", 0) + 1
            s["queue"] = [D] * (s["n"] - 1) + [C, C]
            return D
        return C


# ---------------- Tier 2 ----------------

class Joss(Bot):
    def choose(self):
        m = self.opp[-1] if self.opp else C
        return D if m == C and self.rng.random() < 0.1 else m


class Sneaky(Bot):
    def choose(self):
        if self.t() % 7 == 6:
            return D
        return self.opp[-1] if self.opp else C


class Detective(Bot):
    """C, D, C, C, then: if the opponent ever retaliated, TFT; else defect."""
    def choose(self):
        t = self.t()
        if t < 4:
            return [C, D, C, C][t]
        if "mode" not in self.state:
            self.state["mode"] = "tft" if D in self.opp[1:4] else "exploit"
        if self.state["mode"] == "exploit":
            return D
        return self.opp[-1]


class Prober(Bot):
    """D, C, C; if the opponent cooperated in rounds 2 and 3, defect forever."""
    def choose(self):
        t = self.t()
        if t < 3:
            return [D, C, C][t]
        if self.opp[1:3] == [C, C]:
            return D
        return self.opp[-1]


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


# ---------------- Tier 3 ----------------

class ZDExtort(Bot):
    """Press & Dyson extort-2: memory-one probabilities of cooperating after
    CC, CD, DC, DD (my move first)."""
    P = {(C, C): 8 / 9, (C, D): 1 / 2, (D, C): 1 / 3, (D, D): 0.0}

    def choose(self):
        if not self.my:
            return C
        return C if self.rng.random() < self.P[self.my[-1], self.opp[-1]] else D


STRATEGIES = {
    "tft": TFT, "alld": AllD, "grim": Grim, "coin": Coin, "gtft": GTFT, "pavlov": Pavlov,
    "ctft": ContriteTFT, "tf2t": TF2T, "wgrudge": WindowGrudge, "majority": Majority,
    "gradual": Gradual, "joss": Joss, "sneaky": Sneaky, "detective": Detective, "prober": Prober,
    "bayes": Bayes, "adaptive": Adaptive, "zd": ZDExtort,
}


def main():
    bot = STRATEGIES[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else None)
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


if __name__ == "__main__":
    main()
