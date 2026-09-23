# Forgets to flush: stdout to a pipe is block-buffered, so nothing arrives.
from _loop import run
run(lambda p: "C", out=lambda m: print(m))
