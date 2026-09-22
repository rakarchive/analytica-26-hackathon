"""Pavlov's Dogs."""

from protocol import C, D, Bot, run


class Pavlov(Bot):
    def choose(self):
        if not self.my:
            return C
        return self.my[-1] if self.opp[-1] == C else (D if self.my[-1] == C else C)


if __name__ == "__main__":
    run(Pavlov())
