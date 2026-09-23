"""Last Word: plays whatever beats the opponent's last move."""

from protocol import R, Bot, beat, run


class LastWord(Bot):
    def choose(self):
        return beat(self.opp[-1]) if self.opp else R


if __name__ == "__main__":
    run(LastWord())
