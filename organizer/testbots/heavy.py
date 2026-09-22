# Legal but slow: 30 ms every move. Tests worst-case tournament duration.
import time
from _loop import run
run(lambda p: "C", on_round=lambda n: time.sleep(0.03))
