"""What happened in a match, in words: the verdict, and the captions that
describe how it went. Both come from whichever game is in force, so the same
code reads a match of whichever game is being played."""

import harness

MAX_REPLAYS_PER_PAIR = 3  # first match plus up to two that end differently


def actual(ch):
    """The move as played, from an encoded move string. A forfeited round is
    read as the forfeit move, which is what the opponent faced."""
    return harness.GAME.forfeit if ch == "#" else ch.upper()


def word(move):
    return harness.GAME.verb.get(move, move)


def past(move):
    return harness.GAME.past.get(move, move)


def intent_of(move):
    """What a bot must have played for noise to produce `move` — knowable
    only when there are two moves to choose from."""
    others = harness.GAME.other_moves(move)
    return others[0] if len(others) == 1 else None


def verdict(a, b):
    return harness.GAME.verdict(a, b)


def match_story(ma, mb, na, nb):
    return harness.GAME.story(ma, mb, na, nb)


def headline(a, b, na, nb):
    kind, text = verdict(a, b)
    (W, w), (L, l) = ((na, a), (nb, b)) if a >= b else ((nb, b), (na, a))
    return text.format(A=na, B=nb, a=a, b=b, W=W, w=w, L=L, l=l)


def new_story(shown, a, b):
    """Is a match (points per round a, b) a new story for its pairing, given
    the (kind, a, b) of matches already shown? Its kind must be new AND its
    points clearly apart from every shown one, so noise nudging a match across
    a threshold doesn't count as something new."""
    if len(shown) >= MAX_REPLAYS_PER_PAIR:
        return None
    kind = verdict(a, b)[0]
    if any(k == kind or abs(a - x) + abs(b - y) < 0.6 for k, x, y in shown):
        return None
    return kind
