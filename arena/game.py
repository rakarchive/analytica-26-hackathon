"""What happened in a match, in words: the verdict, and the captions that
describe how it went. No UI, no engine; the Arena, the explorer and the show
all read matches through this."""

import harness

WORD = {"C": "cooperate", "D": "defect"}
PAST = {"C": "cooperated", "D": "defected"}


def actual(ch):
    return "D" if ch == "#" else ch.upper()


# --------------------------------------------------------------------------
# Your bots: how to build and run them
# --------------------------------------------------------------------------

def verdict(a, b):
    """What a match was like, from each side's points per round: (kind,
    headline template). The score is the points you extract for yourself,
    not beating the other bot, so the kinds are about how much each side
    took. Presentation mode replays a pairing again only when the kind changes."""
    if a >= 2.5 and b >= 2.5:
        return ("coop",), "Cooperation held: {A} {a:.2f}, {B} {b:.2f} of a possible 3"
    if a <= 1.5 and b <= 1.5:
        return ("lock",), "Mutual defection: both stuck near 1 a round"
    if abs(a - b) >= 1.0:
        return ("take", a > b), "{W} extracted {w:.2f} a round, {L} only {l:.2f}"
    if a + b >= 4.4:
        return ("unstable",), "Cooperation kept breaking down: {A} {a:.2f}, {B} {b:.2f}"
    return ("grind",), "Mostly defection: {A} {a:.2f}, {B} {b:.2f}"


def new_story(shown, a, b):
    """Is a match (points per round a, b) a new story for its pairing, given
    the (kind, a, b) of matches already shown? Its kind must be new AND its
    points clearly apart from every shown one, so noise nudging a match across
    a threshold (2.49 vs 2.51) doesn't count as something new."""
    if len(shown) >= MAX_REPLAYS_PER_PAIR:
        return None
    kind = verdict(a, b)[0]
    if any(k == kind or abs(a - x) + abs(b - y) < 0.6 for k, x, y in shown):
        return None
    return kind


def headline(a, b, na, nb):
    kind, text = verdict(a, b)
    (W, w), (L, l) = ((na, a), (nb, b)) if a >= b else ((nb, b), (na, a))
    return text.format(A=na, B=nb, a=a, b=b, W=W, w=w, L=L, l=l)


def match_story(ma, mb, na, nb):
    """What happened inside a match, from its move strings (see
    harness.encode_record). Returns (caption lines, metrics); the metrics
    also pick the presentation's highlights."""
    A = [actual(c) for c in ma]
    B = [actual(c) for c in mb]
    n = len(A)
    flips = sum(c.islower() for c in ma) + sum(c.islower() for c in mb)
    forfeits = (ma.count("#"), mb.count("#"))
    # Unprovoked defections: a deliberate D (not noise) right after a CC round.
    unprov = [[], []]
    for t in range(1, n):
        if A[t - 1] == B[t - 1] == "C":
            for side, s in ((0, ma), (1, mb)):
                if s[t] == "D":
                    unprov[side].append(t + 1)
    # Longest mutual-defection lock.
    lock = lock_start = run = 0
    for t in range(n):
        run = run + 1 if A[t] == B[t] == "D" else 0
        if run > lock:
            lock, lock_start = run, t - run + 2
    # Longest retaliation spiral set off by noise: from a flip that broke a
    # CC round to the next CC round (or the end of the match).
    echo = echo_at = 0
    echo_recovered = True
    for t in range(1, n):
        if A[t - 1] == B[t - 1] == "C" and (ma[t] == "d" or mb[t] == "d"):
            k = t + 1
            while k < n and not (A[k] == B[k] == "C"):
                k += 1
            if k - t > echo:
                echo, echo_at, echo_recovered = k - t, t + 1, k < n
    lines = []
    for side, name in ((0, na), (1, nb)):
        if forfeits[side]:
            lines.append((100, f"{name} forfeited {forfeits[side]} rounds (too slow, or crashed)"))
    if lock >= 8:
        lines.append((lock, f"Locked in mutual defection for {lock} rounds from round {lock_start}"))
    if echo >= 4:
        lines.append((echo * 1.2, f"A noise flip in round {echo_at} broke cooperation for {echo} rounds"
                      + ("" if echo_recovered else ", and it never came back")))
    for side, name in ((0, na), (1, nb)):
        if unprov[side]:
            k = len(unprov[side])
            lines.append((min(30, 4 * k), f"{name} defected unprovoked {k} time{'s' if k > 1 else ''}"
                          f", first in round {unprov[side][0]}"))
    if not lines and flips:
        lines.append((3, f"{flips} noise flips, each forgiven within a round or two"))
    if not lines:
        lines.append((1, "Steady from start to finish"))
    lines.sort(key=lambda x: -x[0])
    metrics = {"flips": flips, "lock": lock, "echo": echo, "unprovoked": len(unprov[0]) + len(unprov[1]),
               "forfeits": sum(forfeits)}
    return [text for _, text in lines[:2]], metrics


MAX_REPLAYS_PER_PAIR = 3  # first match plus up to two that end differently


