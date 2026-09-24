# Dies partway through its 3rd match, every time it is started.
import sys

MOVE = "C"   # any legal move: this bot only tests the plumbing


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

run(lambda p: MOVE, on_round=lambda n: sys.exit(1) if n == 500 else None)
