"""Grim Reapers."""

from protocol import C, D, Bot, run


class Grim(Bot):
    def choose(self):
        return D if D in self.opp else C


if __name__ == "__main__":
    run(Grim())
