"""Detectives."""

from protocol import C, D, Bot, run


class Detective(Bot):
    """C, D, C, C, then: if the opponent ever retaliated, TFT; else defect."""
    def choose(self):
        t = self.t()
        if t < 4:
            return [C, D, C, C][t]
        if "mode" not in self.state:
            self.state["mode"] = "tft" if D in self.opp[1:4] else "exploit"
        if self.state["mode"] == "exploit":
            return D
        return self.opp[-1]


if __name__ == "__main__":
    run(Detective())
