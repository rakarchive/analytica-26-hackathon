"""Two Strikes."""

from protocol import C, D, Bot, run


class TF2T(Bot):
    def choose(self):
        return D if self.opp[-2:] == [D, D] else C


if __name__ == "__main__":
    run(TF2T())
