# A bot in Python. Run it with:  python my_bot.py
# Print only your moves. For debugging, print to stderr instead:
#     print("hello", file=sys.stderr)

import sys

my = ""   # your moves so far this match, like "CCDC" (as they came out, after noise)
opp = ""  # your opponent's moves so far this match


def choose():
    """Return "C" or "D". This plays tit-for-tat: cooperate first, then
    copy whatever the opponent did last round."""
    if not opp:
        return "C"
    return opp[-1]


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
