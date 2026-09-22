"""Practice bot (Python). Run with:  python3 my_bot.py

The protocol plumbing is done: edit Bot.choose() and leave main() alone
unless you know why. stdout is ONLY for moves; print debugging to stderr.
"""

import random
import sys

ROCK, PAPER, SCISSORS = "R", "P", "S"
BEATEN_BY = {ROCK: PAPER, PAPER: SCISSORS, SCISSORS: ROCK}   # what beats a move


class Bot:
    def __init__(self):
        self.rng = random.Random()
        self.reset()

    def reset(self):
        """New match. Clear everything that belongs to one opponent. Keeping
        state across matches is against the rules."""
        self.my = []   # your ACTUAL moves so far (after noise), oldest first
        self.opp = []  # the opponent's actual moves so far

    def choose(self):
        """Return R, P or S for the next round."""
        return self.beat_their_last()

    # ---- a few to start from ----

    def random_move(self):
        return self.rng.choice((ROCK, PAPER, SCISSORS))

    def beat_their_last(self):
        return BEATEN_BY[self.opp[-1]] if self.opp else ROCK

    def beat_their_favourite(self):
        if not self.opp:
            return ROCK
        favourite = max((ROCK, PAPER, SCISSORS), key=self.opp.count)
        return BEATEN_BY[favourite]


def main():
    bot = Bot()
    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "RESET":
            bot.reset()
        elif parts[0] == "ROUND":
            if parts[1] != "-":
                bot.my.append(parts[1])
                bot.opp.append(parts[2])
            print(bot.choose(), flush=True)  # flush=True is NOT optional
        elif parts[0] == "END":
            break


if __name__ == "__main__":
    main()
