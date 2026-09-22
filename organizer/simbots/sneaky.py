"""Sneaky Snakes."""

from protocol import C, D, Bot, run


class Sneaky(Bot):
    def choose(self):
        if self.t() % 7 == 6:
            return D
        return self.opp[-1] if self.opp else C


if __name__ == "__main__":
    run(Sneaky())
