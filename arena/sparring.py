"""Textbook strategies. These are the floor, not the goal: your bot should
beat them. Each sees only what your bot sees: the previous round's ACTUAL
(post-noise) moves, accumulated in self.my / self.opp."""

from rules import C, D
from harness import Strategy


class AlwaysCooperate(Strategy):
    name = "always_cooperate"

    def choose(self):
        return C


class AlwaysDefect(Strategy):
    name = "always_defect"

    def choose(self):
        return D


class RandomBot(Strategy):
    name = "random"

    def choose(self):
        return self.rng.choice((C, D))


class TitForTat(Strategy):
    """Copy the opponent's last move. Under noise, one flipped move starts an
    echo of alternating retaliation that lasts until the next flip."""
    name = "tit_for_tat"

    def choose(self):
        return self.opp[-1] if self.opp else C


class GenerousTFT(Strategy):
    """Tit-for-tat that forgives a defection with probability p, which breaks
    the retaliation echo that noise starts."""
    name = "generous_tft"

    def __init__(self, p=1 / 3):
        self.p = p

    def choose(self):
        if not self.opp or self.opp[-1] == C:
            return C
        return C if self.rng.random() < self.p else D


class Pavlov(Strategy):
    """Win-stay, lose-shift: repeat your last move if it scored 3 or 5,
    otherwise switch. Recovers from a single flip within two rounds."""
    name = "pavlov"

    def choose(self):
        if not self.my:
            return C
        won = self.opp[-1] == C  # CC -> 3, DC -> 5; anything against D is a loss
        return self.my[-1] if won else (D if self.my[-1] == C else C)


class Grudger(Strategy):
    """Cooperates until the opponent has defected twice, then defects for the
    rest of the match. Under noise it usually snaps within the first fifty
    rounds even against a nice opponent: grudges and noise don't mix."""
    name = "grudger"

    def choose(self):
        return D if self.opp.count(D) >= 2 else C


class TitForTwoTats(Strategy):
    """Only retaliates after two defections in a row, so a single flip is
    forgiven. Hard to provoke, which also makes it easier to exploit."""
    name = "tit_for_two_tats"

    def choose(self):
        return D if self.opp[-2:] == [D, D] else C


class SuspiciousTFT(Strategy):
    """Tit-for-tat that opens with a defection. Against another reciprocator
    that first D can start an echo of retaliation that runs until noise
    breaks it."""
    name = "suspicious_tft"

    def choose(self):
        return self.opp[-1] if self.opp else D


BASELINES = [AlwaysCooperate, AlwaysDefect, RandomBot, TitForTat, GenerousTFT, Pavlov,
             Grudger, TitForTwoTats, SuspiciousTFT]
