"""Barely Generous."""

from protocol import C, D, Bot, run


class GTFT(Bot):
    def choose(self):
        if not self.opp or self.opp[-1] == C:
            return C
        return C if self.rng.random() < float(0.1) else D


if __name__ == "__main__":
    run(GTFT())
