"""Zero Determinants."""

from protocol import C, D, Bot, run


class ZDExtort(Bot):
    """Press & Dyson extort-2: memory-one probabilities of cooperating after
    CC, CD, DC, DD (my move first)."""
    P = {(C, C): 8 / 9, (C, D): 1 / 2, (D, C): 1 / 3, (D, D): 0.0}

    def choose(self):
        if not self.my:
            return C
        return C if self.rng.random() < self.P[self.my[-1], self.opp[-1]] else D


if __name__ == "__main__":
    run(ZDExtort())
