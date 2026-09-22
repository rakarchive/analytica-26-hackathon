"""Joss Stick."""

from protocol import C, D, Bot, run


class Joss(Bot):
    def choose(self):
        m = self.opp[-1] if self.opp else C
        return D if m == C and self.rng.random() < 0.1 else m


if __name__ == "__main__":
    run(Joss())
