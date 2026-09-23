# Prints debug lines to stdout. Should still work, with junk_lines counted.
from _loop import run
def out(m):
    print("thinking...", flush=True)
    print(m, flush=True)
run(lambda p: "D" if p[2:] == ["D"] else "C", out=out)
