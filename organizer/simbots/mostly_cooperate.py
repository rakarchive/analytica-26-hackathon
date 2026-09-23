"""Stochastic Squad."""

from protocol import C, D, Bot, run


class Coin(Bot):
    def choose(self):
        return C if self.rng.random() < float(0.8 or 0.8) else D


if __name__ == "__main__":
    run(Coin())
