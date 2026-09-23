"""Round Robin: rock, paper, scissors, rock, paper, scissors..."""

from protocol import MOVES, Bot, run


class Cycle(Bot):
    def choose(self):
        return MOVES[self.t() % 3]


if __name__ == "__main__":
    run(Cycle())
