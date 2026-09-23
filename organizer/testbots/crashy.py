# Dies partway through its 3rd match, every time it is started.
import sys
from _loop import MOVE, run
run(lambda p: MOVE, on_round=lambda n: sys.exit(1) if n == 500 else None)
