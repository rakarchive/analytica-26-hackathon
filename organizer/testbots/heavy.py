# Legal but slow: 30 ms every move. Tests worst-case tournament duration.
import time
import sys

MOVE = "R"   # any legal move: this bot only tests the plumbing


def run(choose, out=lambda m: print(m, flush=True), on_round=None):
    n = 0
    for line in sys.stdin:
        p = line.split()
        if not p: continue
        if p[0] == "ROUND":
            n += 1
            if on_round: on_round(n)
            out(choose(p))
        elif p[0] == "END":
            break

run(lambda p: MOVE, on_round=lambda n: time.sleep(0.03))
