"""Forgive & Forget."""

from protocol import C, D, Bot, run


class WindowGrudge(Bot):
    def choose(self):
        s = self.state
        if s.get("punish", 0):
            s["punish"] -= 1
            return D
        if self.opp[-10:].count(D) >= 3:
            s["punish"] = 4
            return D
        return C


if __name__ == "__main__":
    run(WindowGrudge())
