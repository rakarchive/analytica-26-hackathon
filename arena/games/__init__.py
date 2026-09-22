"""The games the Arena can run.

A game says what the moves are, what they score, how noise mangles them, and
how a match is described afterwards. The engine, the board and the replay
viewer read all of that from here, so the same Arena runs the practice game
and the real one; only the game changes.

    games.use("rps")        # pick a game
    games.current()         # the one in use
"""

import os
import sys

_GAMES = {}
_CURRENT = None


def register(game):
    _GAMES[game.key] = game
    return game


def names():
    return sorted(_GAMES)


def use(key):
    """Switch games. Everything else reads current()."""
    global _CURRENT
    if key not in _GAMES:
        raise KeyError(f"no such game: {key} (have {', '.join(names())})")
    _CURRENT = _GAMES[key]
    return _CURRENT


def current():
    if _CURRENT is None:
        use(default_key())
    return _CURRENT


def default_key():
    """Which game to start in: a `game.txt` beside the app wins, then the
    IPD_GAME environment variable, then whichever game is bundled. The
    practice build ships a game.txt saying `rps`."""
    home = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                           else os.path.dirname(os.path.abspath(__file__)))
    marker = os.path.join(home, "game.txt")
    try:
        with open(marker) as f:
            key = f.read().strip().lower()
        if key in _GAMES:
            return key
    except OSError:
        pass
    return os.environ.get("IPD_GAME", "ipd" if "ipd" in _GAMES else names()[0])


# Each game registers itself. A build can leave one out (the practice build
# ships without the real game, so nothing in it can give the game away), so a
# missing module is not an error.
for _name in ("ipd", "rps"):
    try:
        __import__(f"games.{_name}")
    except ImportError:  # not bundled in this build
        pass
