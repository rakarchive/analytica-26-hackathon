"""Gradual Escalation."""

from protocol import C, D, Bot, run


class Gradual(Bot):
    """Beaufils' Gradual: the n-th defection is answered with n defections
    then two cooperations. Escalates badly under noise."""
    def choose(self):
        s = self.state
        if s.get("queue"):
            return s["queue"].pop(0)
        if self.opp and self.opp[-1] == D:
            s["n"] = s.get("n", 0) + 1
            s["queue"] = [D] * (s["n"] - 1) + [C, C]
            return D
        return C


if __name__ == "__main__":
    run(Gradual())
