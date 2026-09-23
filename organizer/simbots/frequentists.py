"""Frequentists: beats whatever the opponent has played most, all match."""

from protocol import P, Bot, beat, run


class Frequentist(Bot):
    def choose(self):
        top = self.favourite()
        return beat(top) if top else P


if __name__ == "__main__":
    run(Frequentist())
