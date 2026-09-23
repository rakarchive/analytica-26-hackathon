"""Markov Chains: learns what the opponent tends to play after each of its
own moves, predicts the next one and beats it."""

from protocol import MOVES, Bot, beat, run


class Markov(Bot):
    def choose(self):
        if len(self.opp) < 2:
            return self.rng.choice(MOVES)
        last = self.opp[-1]
        after = [self.opp[k + 1] for k in range(len(self.opp) - 1) if self.opp[k] == last]
        return beat(max(MOVES, key=after.count))


if __name__ == "__main__":
    run(Markov())
