"""Cooperative Kernel."""

from protocol import C, D, Bot, run


class ContriteFirm(Bot):
    """Contrite tit-for-tat that also gives up on opponents which
    defect most of the time."""
    def choose(self):
        t = self.t()
        excused = self.state.setdefault("excused", set())
        if t and self.my[-1] == D and self.intent[-1] == C:
            excused.add(t)
        move = C
        if self.opp and self.opp[-1] == D and (t - 1) not in excused:
            move = D
        if t >= 20 and self.opp_d_rate(20) >= 0.6:
            move = D
        return move


if __name__ == "__main__":
    run(ContriteFirm())
