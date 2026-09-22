"""Test your bot locally.

    python run_local.py --smoke "python3 my_bot.py"       protocol check (do this first)
    python run_local.py "python3 my_bot.py"                your bot vs the baselines
    python run_local.py "java MyBot" "python3 other.py"    several bots + baselines

Each argument is the command that starts one bot (run from the current
directory). The real tournament field is different: it contains the other
teams plus some undisclosed opponents.
"""

import argparse
import os
import sys

import harness
from baselines import BASELINES


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bots", nargs="+", help="command line for each bot, quoted")
    ap.add_argument("--smoke", action="store_true", help="only check the bot speaks the protocol")
    ap.add_argument("--reps", type=int, default=20, help="matches per pairing")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    if args.smoke:
        all_ok = True
        for cmd in args.bots:
            print(f"=== {cmd} ===")
            report = harness.smoke_test(cmd)
            print("\n".join(report.lines()))
            all_ok &= report.ok
        print("\nPASS" if all_ok else "\nFAIL")
        sys.exit(0 if all_ok else 1)

    specs = [{"name": f"bot{k}" if len(args.bots) > 1 else "your_bot", "kind": "yours",
              "cmd": cmd, "cwd": os.getcwd()}
             for k, cmd in enumerate(args.bots, 1)]
    specs += [{"name": cls.name, "kind": "baseline", "strategy": ("baselines", cls.__name__, {})}
              for cls in BASELINES]

    points, rounds, stats = harness.run_round_robin(
        specs, args.reps, seed=args.seed, workers=args.workers,
        progress=lambda d, t, e: print(f"\r  {d}/{t} matches", end="", flush=True))
    print()

    names = [s["name"] for s in specs]
    width = max(map(len, names)) + 2
    print("\nPoints per round, row against column:\n")
    print(" " * width + "".join(f"{n[:9]:>10}" for n in names) + "     mean")
    for i, n in enumerate(names):
        cells = [points[i][j] / rounds[i][j] if rounds[i][j] else None for j in range(len(names))]
        mean = sum(points[i]) / sum(rounds[i])
        print(f"{n:<{width}}" + "".join(f"{c:10.3f}" if c is not None else f"{'':>10}" for c in cells)
              + f"{mean:9.3f}")

    for i, s in enumerate(specs):
        if "cmd" in s:
            st = stats[i].summary()
            print(f"\n{s['name']}: {s['cmd']}")
            print(f"  latency mean {st['mean_ms']:.2f} ms, p99 {st['p99_ms']:.2f} ms, max {st['max_ms']:.1f} ms")
            for k in ("timeouts", "crashes", "forfeits", "junk_lines"):
                if st[k]:
                    print(f"  {k}: {st[k]}")


if __name__ == "__main__":
    main()
