# Prints debug lines to stdout. Should still work, with junk_lines counted.
from _loop import MOVE, run
def out(m):
    print("thinking...", flush=True)
    print(m, flush=True)
run(lambda p: MOVE if p[2] == "-" else p[2], out=out)  # copies the opponent
