# Legal but slow: 30 ms every move. Tests worst-case tournament duration.
import time
from _loop import MOVE, run
run(lambda p: MOVE, on_round=lambda n: time.sleep(0.03))
