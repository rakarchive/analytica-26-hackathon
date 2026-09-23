"""Second Guessers: assumes the opponent will try to beat its last move, and
beats that instead."""

from protocol import P, Bot, beat, run


class SecondGuess(Bot):
    def choose(self):
        return beat(beat(self.my[-1])) if self.my else P


if __name__ == "__main__":
    run(SecondGuess())
