"""Iocaine Powder (lite): runs several predictors side by side, scores each
on how well it would have done over the last 20 rounds, and follows the best.
Falls back to random when none of them is doing better than chance."""

from protocol import MOVES, BEATEN_BY, Bot, beat, run


def score(mine, theirs):
    return 1 if BEATEN_BY[theirs] == mine else -1 if BEATEN_BY[mine] == theirs else 0


class Iocaine(Bot):
    def predictors(self, my, opp):
        """Each one's move for the round after `my`/`opp`."""
        if not opp:
            return []
        fav = max(MOVES, key=opp[-10:].count)
        return [beat(opp[-1]),            # they repeat
                beat(fav),                # they have a favourite
                beat(beat(my[-1])),       # they beat my last
                beat(beat(beat(my[-1])))]  # they second-guess me

    def choose(self):
        n = len(self.opp)
        if n < 3:
            return self.rng.choice(MOVES)
        totals = [0] * 4
        for k in range(max(1, n - 20), n):
            for p, move in enumerate(self.predictors(self.my[:k], self.opp[:k])):
                totals[p] += score(move, self.opp[k])
        best = max(range(4), key=lambda p: totals[p])
        if totals[best] <= 2:
            return self.rng.choice(MOVES)
        return self.predictors(self.my, self.opp)[best]


if __name__ == "__main__":
    run(Iocaine())
