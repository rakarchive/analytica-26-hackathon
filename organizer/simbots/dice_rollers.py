"""Dice Rollers: uniformly random. Nobody can beat it on average, and it
beats nobody on average either."""

from protocol import MOVES, Bot, run


class Dice(Bot):
    def choose(self):
        return self.rng.choice(MOVES)


if __name__ == "__main__":
    run(Dice())
