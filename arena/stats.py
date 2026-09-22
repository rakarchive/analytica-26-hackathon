"""Is one bot actually better than another?

Scores here are points per round, a continuous number, not win/draw/loss, so
the usual engine-testing formulas need adapting. Everything below works on
per-match means, and comparisons are paired: two bots are compared on the
opponents they both faced in the same repetition, which cancels most of the
noise (both met the same opponents under the same noise draws).
"""

import math
import statistics


def z(confidence):
    return statistics.NormalDist().inv_cdf(0.5 + confidence / 2)


def mean_ci(values, confidence=0.95):
    """(mean, half-width). The half-width is infinite below two samples."""
    n = len(values)
    if n == 0:
        return 0.0, float("inf")
    mean = statistics.fmean(values)
    if n < 2:
        return mean, float("inf")
    se = statistics.stdev(values) / math.sqrt(n)
    return mean, z(confidence) * se


def match_scores(tour, i, opponent=None):
    """Bot i's points per round, one number per match it played."""
    out = []
    for m in tour.matches:
        if m["i"] == i and (opponent is None or m["j"] == opponent):
            out.append(m["pa"] / m["n"])
        elif m["j"] == i and (opponent is None or m["i"] == opponent):
            out.append(m["pb"] / m["n"])
    return out


def score_ci(tour, i, confidence=0.95):
    """A bot's mean points per round, with a confidence interval."""
    return mean_ci(match_scores(tour, i), confidence)


def paired_differences(tour, i, j):
    """Per (opponent, repetition), how much more bot i scored than bot j.

    Only opponents both faced count, and their matches against each other are
    left out: those say who beats whom, not who extracts more overall."""
    def table(me):
        out = {}
        for m in tour.matches:
            if m["i"] == me and m["j"] not in (i, j):
                out[m["j"], m["r"]] = m["pa"] / m["n"]
            elif m["j"] == me and m["i"] not in (i, j):
                out[m["i"], m["r"]] = m["pb"] / m["n"]
        return out
    a, b = table(i), table(j)
    return [a[k] - b[k] for k in sorted(a.keys() & b.keys())]


def head_to_head(tour, i, j):
    """(points per round for i, for j) over their own matches."""
    mine, theirs = [], []
    for m in tour.matches:
        if m["i"] == i and m["j"] == j:
            mine.append(m["pa"] / m["n"])
            theirs.append(m["pb"] / m["n"])
        elif m["i"] == j and m["j"] == i:
            mine.append(m["pb"] / m["n"])
            theirs.append(m["pa"] / m["n"])
    return mine, theirs


def sprt(diffs, delta=0.02, alpha=0.05, beta=0.05):
    """Sequential probability ratio test on paired differences.

    H0: the two bots score the same.  H1: the first scores `delta` more per
    round. Returns the log-likelihood ratio, the two bounds and a verdict of
    "H1" (better), "H0" (no better) or "continue" (not enough matches yet).
    With an unknown spread, the sample variance stands in for it, which is
    the usual practical compromise."""
    n = len(diffs)
    lower, upper = math.log(beta / (1 - alpha)), math.log((1 - beta) / alpha)
    if n < 2:
        return {"n": n, "llr": 0.0, "lower": lower, "upper": upper, "verdict": "continue",
                "mean": statistics.fmean(diffs) if diffs else 0.0}
    mean = statistics.fmean(diffs)
    var = statistics.variance(diffs)
    if var <= 0:
        var = 1e-12
    llr = n * delta * (mean - delta / 2) / var
    verdict = "H1" if llr >= upper else "H0" if llr <= lower else "continue"
    return {"n": n, "llr": llr, "lower": lower, "upper": upper, "verdict": verdict, "mean": mean}


def samples_needed(diffs, delta=0.02, alpha=0.05, power=0.9):
    """How many paired matches it would take to resolve a `delta` difference,
    given the spread seen so far."""
    if len(diffs) < 2:
        return None
    var = statistics.variance(diffs)
    n = (z(1 - alpha) + z(2 * power - 1)) ** 2 * var / (delta ** 2)
    return int(math.ceil(n))


def compare(tour, i, j, delta=0.02, alpha=0.05, beta=0.05, confidence=0.95):
    """Everything about "is i better than j": the paired difference with its
    interval, the SPRT verdict, how many matches that would need, and how
    they did against each other."""
    diffs = paired_differences(tour, i, j)
    mean, half = mean_ci(diffs, confidence)
    mine, theirs = head_to_head(tour, i, j)
    return {
        "pairs": len(diffs),
        "diff": mean, "ci": half,
        "sprt": sprt(diffs, delta, alpha, beta),
        "needed": samples_needed(diffs, delta, alpha),
        "h2h": (statistics.fmean(mine) if mine else float("nan"),
                statistics.fmean(theirs) if theirs else float("nan"), len(mine)),
    }


def tied(rows, confidence=0.95):
    """Group leaderboard rows whose intervals overlap: those places are not
    decided by the tournament, only by luck."""
    groups, current = [], []
    for r in rows:
        if current and r["score"] + r.get("ci", 0) < current[-1]["score"] - current[-1].get("ci", 0):
            groups.append(current)
            current = []
        current.append(r)
    if current:
        groups.append(current)
    return groups
