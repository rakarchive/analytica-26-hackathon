# A bot in Python. Run it with:  python my_bot.py
# Print only your moves. For debugging, print to stderr instead:
#     print("hello", file=sys.stderr)

import sys

my = ""   # your moves so far this match, like "RPPS" (as they came out, after noise)
opp = ""  # your opponent's moves so far this match

BEATS = {"R": "P", "P": "S", "S": "R"}  # what beats each move: paper beats rock, ...


def choose():
    """Return "R", "P" or "S". This plays rock first, then whatever beats
    the opponent's last move."""
    if not opp:
        return "R"
    return BEATS[opp[-1]]


for line in sys.stdin:
    words = line.split()
    if not words:
        continue
    if words[0] == "RESET":          # a new match: forget the last one
        my = ""
        opp = ""
    elif words[0] == "ROUND":
        if words[1] != "-":          # "-" means the first round: nothing to record
            my += words[1]
            opp += words[2]
        print(choose(), flush=True)  # flush=True is required
    elif words[0] == "END":
        break
