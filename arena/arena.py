"""The Arena: test your bot, run tournaments, watch matches.

Double-click this file, or run:  python arena.py

  + Add bot     pick your bots' main files (.py .java .cpp .c .js .jar .exe);
                select several at once to add them all
  Check         protocol check for the selected bot (do this first)
  Run           round robin: your bots vs the baselines, with live replays
  Watch         click two rows on the board, then Watch to replay that match

Right-click one of your bots to edit its run command or remove it. Click a
row after a run to see its scores against each opponent.
"""

import argparse
import multiprocessing
import runpy
import os
import sys
import tempfile
import traceback
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness  # noqa: E402
from ui import *  # noqa: E402,F401,F403
from ui import (BG, FAINT, FG, BaseApp, FlatButton, adopt_portable_tools, baseline_specs,  # noqa: E402
                user_bot_spec)


class Arena(BaseApp):
    """The teams' toolkit."""

    def __init__(self, root):
        super().__init__(root)
        self.log("Welcome to the Arena. Click '+ Add bot' and pick your bot's main file, "
                 "then 'Check' it.", FG)

    def _build_toolbar(self, tb):
        row = tk.Frame(tb, bg=BG)
        row.pack(fill="x")
        for key, text, cmd, primary in (("add", "+ Add bot", self.add_bot, False),
                                        ("check", "Check", self.check, False),
                                        ("run", "Run tournament", self.run_or_stop, True),
                                        ("watch", "Watch", self.watch, False)):
            b = FlatButton(row, text, cmd, primary)
            b.pack(side="left", padx=(0, 8))
            self.buttons[key] = b
        self._label(row, "matches per pairing").pack(side="left", padx=(12, 6))
        self._spin(row, self.reps_var, 1, 1000).pack(side="left")
        self.hint = self._label(row, "", FAINT)
        self.hint.pack(side="left", padx=12)


SELFTEST_BOT = """import sys
for line in sys.stdin:
    p = line.split()
    if p and p[0] == "ROUND":
        print("C" if p[1] == "-" else p[2], flush=True)
    elif p and p[0] == "END":
        break
"""


def selftest(report_path):
    """Headless check of a packaged build: a small round robin with a real
    subprocess bot, exercising worker processes and bot plumbing. Used by CI,
    where a windowed exe has no console, so the result goes to a file."""
    lines, ok = [], False
    try:
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, "selftest_bot.py"), "w") as f:
            f.write(SELFTEST_BOT)
        bot = user_bot_spec(os.path.join(folder, "selftest_bot.py"), "selftest_bot")
        lines.append(f"python: {bot['cmd'][0]}")
        specs = [bot] + baseline_specs()
        points, rounds, stats = harness.run_round_robin(specs, 2, seed=1, workers=2, log_dir=folder)
        st = stats[0].summary()
        per_round = sum(points[0]) / max(1, sum(rounds[0]))
        lines.append(f"selftest_bot: {per_round:.3f} pts/round, {st['moves']} moves, "
                     f"{st['timeouts']} timeouts, {st['crashes']} crashes")
        ok = st["moves"] > 0 and not st["crashes"] and not st["timeouts"] and per_round > 1
    except Exception:
        lines.append(traceback.format_exc())
    lines.append("PASS" if ok else "FAIL")
    with open(report_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", metavar="REPORT", help=argparse.SUPPRESS)
    ap.add_argument("--run-bot", metavar="SCRIPT", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.run_bot:
        # The interpreter inside this exe, running a team's Python bot: no
        # Python installation needed. Keep this process clean for the bot.
        sys.argv = [args.run_bot]
        sys.path.insert(0, os.path.dirname(os.path.abspath(args.run_bot)))
        runpy.run_path(args.run_bot, run_name="__main__")
        return
    if args.selftest:
        sys.exit(selftest(args.selftest))
    adopt_portable_tools()
    root = tk.Tk()
    Arena(root)
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
