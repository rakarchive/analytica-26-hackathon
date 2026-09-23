"""Win-Stay: keeps its move after a win; otherwise plays what beats the
opponent's last move."""

from protocol import BEATEN_BY, R, Bot, beat, run


class WinStay(Bot):
    def choose(self):
        if not self.my:
            return R
        won = BEATEN_BY[self.opp[-1]] == self.my[-1]
        return self.my[-1] if won else beat(self.opp[-1])


if __name__ == "__main__":
    run(WinStay())
