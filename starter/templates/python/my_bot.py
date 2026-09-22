"""Starter bot (Python). Run with:  python3 my_bot.py

The protocol plumbing is done: edit Bot.choose() and leave main() alone
unless you know why. stdout is ONLY for moves; print debugging to stderr.
"""

import random
import sys

C, D = "C", "D"


class Bot:
    def __init__(self):
        self.rng = random.Random()
        self.reset()

    def reset(self):
        """New match. Clear everything that belongs to one opponent. Keeping
        state across matches is against the rules."""
        self.my = []   # your ACTUAL moves so far (after noise), oldest first
        self.opp = []  # opponent's actual moves so far

    def choose(self):
        """Return C or D for the next round. Default: generous tit-for-tat."""
        return self.generous_tft()

    # ---- the textbook floor; beat these ----

    def tit_for_tat(self):
        return self.opp[-1] if self.opp else C

    def generous_tft(self, p=1 / 3):
        if not self.opp or self.opp[-1] == C:
            return C
        return C if self.rng.random() < p else D

    def pavlov(self):
        if not self.my:
            return C
        won = self.opp[-1] == C
        return self.my[-1] if won else (D if self.my[-1] == C else C)


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
