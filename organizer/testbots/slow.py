# Blows the 50 ms limit on every 40th move.
import time
from _loop import MOVE, run
run(lambda p: MOVE, on_round=lambda n: time.sleep(0.08) if n % 40 == 0 else None)
