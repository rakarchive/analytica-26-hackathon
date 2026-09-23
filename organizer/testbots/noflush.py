# Forgets to flush: stdout to a pipe is block-buffered, so nothing arrives.
from _loop import MOVE, run
run(lambda p: MOVE, out=lambda m: print(m))
