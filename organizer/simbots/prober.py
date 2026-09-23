"""Trust Issues."""

from protocol import C, D, Bot, run


class Prober(Bot):
    """D, C, C; if the opponent cooperated in rounds 2 and 3, defect forever."""
    def choose(self):
        t = self.t()
        if t < 3:
            return [D, C, C][t]
        if self.opp[1:3] == [C, C]:
            return D
        return self.opp[-1]


if __name__ == "__main__":
    run(Prober())
