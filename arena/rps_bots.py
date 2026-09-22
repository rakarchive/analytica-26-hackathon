"""Sparring partners for the practice game. Beating these teaches you nothing
about the real game, which is the point: they are here so you can check your
bot talks to the Arena properly."""

from harness import Strategy

R, P, S = "R", "P", "S"
BEATS = {R: S, P: R, S: P}          # key beats value
LOSES_TO = {v: k for k, v in BEATS.items()}


class AlwaysRock(Strategy):
    name = "always_rock"

    def choose(self):
        return R


class RandomBot(Strategy):
    name = "random"

    def choose(self):
        return self.rng.choice((R, P, S))


class Cycler(Strategy):
    """Rock, paper, scissors, rock, paper, scissors…"""
    name = "cycler"

    def choose(self):
        return (R, P, S)[len(self.my) % 3]


class Mirror(Strategy):
    """Plays whatever you played last."""
    name = "mirror"

    def choose(self):
        return self.opp[-1] if self.opp else R


class BeatLast(Strategy):
    """Plays whatever would have beaten your last move."""
    name = "beat_last"

    def choose(self):
        return LOSES_TO[self.opp[-1]] if self.opp else P


class Favourite(Strategy):
    """Counts what you play most and answers that."""
    name = "favourite"

    def choose(self):
        if not self.opp:
            return S
        top = max((R, P, S), key=self.opp.count)
        return LOSES_TO[top]


BASELINES = [AlwaysRock, RandomBot, Cycler, Mirror, BeatLast, Favourite]
