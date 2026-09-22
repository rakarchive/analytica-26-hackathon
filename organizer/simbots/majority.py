"""Majority Rule."""

from protocol import C, D, Bot, run


class Majority(Bot):
    def choose(self):
        return C if self.opp.count(C) >= self.opp.count(D) else D


if __name__ == "__main__":
    run(Majority())
