"""Tit4Tat Fans."""

from protocol import C, D, Bot, run


class TFT(Bot):
    def choose(self):
        return self.opp[-1] if self.opp else C


if __name__ == "__main__":
    run(TFT())
