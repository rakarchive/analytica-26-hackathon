"""Noise Cancellers."""

from protocol import C, D, Bot, run


class ContriteTFT(Bot):
    """Doesn't echo retaliation for its own noise-flipped moves."""
    def choose(self):
        t = self.t()
        excused = self.state.setdefault("excused", set())
        if t and self.my[-1] == D and self.intent[-1] == C:
            excused.add(t)
        move = C
        if self.opp and self.opp[-1] == D and (t - 1) not in excused:
            move = D
        return move


if __name__ == "__main__":
    run(ContriteTFT())
