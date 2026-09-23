# Dies partway through its 3rd match, every time it is started.
import sys
from _loop import run
run(lambda p: "C", on_round=lambda n: sys.exit(1) if n == 500 else None)
