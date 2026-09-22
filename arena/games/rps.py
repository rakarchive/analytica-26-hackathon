"""Rock, paper, scissors: the practice game.

Same plumbing as the real thing, deliberately nothing else. It is zero-sum
and there is no hidden depth to it: what you learn here is how to talk to the
Arena: one move per line, flushed, on time. Noise scrambles some moves on the
way out, exactly as it will in the real game, which is why each round tells
you what your own move actually came out as.
"""

from games import register
from games.base import Game

R, P, S = "R", "P", "S"
BEATS = {R: S, P: R, S: P}          # key beats value


def actual(ch):
    return "R" if ch == "#" else ch.upper()


def result(mine, theirs):
    if mine == theirs:
        return 1                     # a draw
    return 2 if BEATS[mine] == theirs else 0


class RPS(Game):
    key = "rps"
    title = "ROCK PAPER SCISSORS"
    moves = (R, P, S)
    payoff = {(a, b): (result(a, b), result(b, a)) for a in (R, P, S) for b in (R, P, S)}
    best = 2
    noise = 0.07
    rounds = (150, 250)
    colour = {R: "#6f8cf2", P: "#3fbf72", S: "#e0a23a"}
    verb = {R: "play rock", P: "play paper", S: "play scissors"}
    past = {R: "played rock", P: "played paper", S: "played scissors"}
    forfeit = R             # a bot that times out or crashes is treated as playing rock
    stat = None                      # nothing worth a column here
    baselines = (("rps_bots", "AlwaysRock"), ("rps_bots", "RandomBot"), ("rps_bots", "Cycler"),
                 ("rps_bots", "Mirror"), ("rps_bots", "BeatLast"), ("rps_bots", "Favourite"))
    smoke = (("rps_bots", "RandomBot"), ("rps_bots", "AlwaysRock"), ("rps_bots", "Cycler"))
    kind_colour = {"win": "up", "even": "dim"}

    def verdict(self, a, b):
        """Points per round, where a win is 2 and a draw is 1."""
        if abs(a - b) < 0.1:
            return ("even",), "Nothing in it: {A} {a:.2f}, {B} {b:.2f}"
        if abs(a - b) >= 0.6:
            return ("win", a > b), "{W} read {L} well: {w:.2f} to {l:.2f}"
        return ("win", a > b), "{W} edged it: {w:.2f} to {l:.2f}"

    def story(self, ma, mb, na, nb):
        """What happened inside a match: streaks, favourite moves, noise."""
        A = [actual(c) for c in ma]
        B = [actual(c) for c in mb]
        n = len(A)
        flips = sum(c.islower() for c in ma) + sum(c.islower() for c in mb)
        forfeits = (ma.count("#"), mb.count("#"))
        wins = [sum(1 for k in range(n) if result(A[k], B[k]) == 2),
                sum(1 for k in range(n) if result(B[k], A[k]) == 2)]
        draws = sum(1 for k in range(n) if A[k] == B[k])
        streak = best = 0
        streak_side = 0
        for k in range(n):
            if result(A[k], B[k]) == 2:
                streak = streak + 1 if streak > 0 else 1
            elif result(B[k], A[k]) == 2:
                streak = streak - 1 if streak < 0 else -1
            else:
                streak = 0
            if abs(streak) > best:
                best, streak_side = abs(streak), 0 if streak > 0 else 1
        lines = []
        for side, name in ((0, na), (1, nb)):
            if forfeits[side]:
                lines.append((100, f"{name} forfeited {forfeits[side]} rounds (too slow, or crashed)"))
        if best >= 5:
            lines.append((best, f"{(na, nb)[streak_side]} won {best} rounds in a row"))
        for side, moves, name in ((0, A, na), (1, B, nb)):
            top = max(self.moves, key=moves.count)
            share = moves.count(top) / max(1, n)
            if share > 0.45:
                lines.append((share * 10, f"{name} {self.past[top]} {share:.0%} of the time"))
        if draws > n * 0.45:
            lines.append((4, f"{draws} of {n} rounds were draws"))
        if not lines and flips:
            lines.append((3, f"{flips} moves came out scrambled by noise"))
        if not lines:
            lines.append((1, "Nothing either could predict"))
        lines.sort(key=lambda x: -x[0])
        metrics = {"flips": flips, "streak": best, "draws": draws,
                   "wins": wins, "forfeits": sum(forfeits)}
        return [text for _, text in lines[:2]], metrics


register(RPS())
