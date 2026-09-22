"""Organizer tournament runner.

    python tournament.py check  manifest.json     build + smoke-test every team bot
    python tournament.py run    manifest.json     full round robin + leaderboard

Manifest (paths relative to the manifest file):

    {"bots": [
      {"name": "team-alpha", "dir": "submissions/alpha",
       "build": "javac MyBot.java", "run": "java -XX:+UseSerialGC MyBot"},
      {"name": "team-beta",  "dir": "submissions/beta", "run": "python3 my_bot.py"}
    ]}
"""

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "arena"))

import harness  # noqa: E402
from reference_bots import reference_specs  # noqa: E402


def load_manifest(path):
    try:
        return harness.load_manifest(path)
    except ValueError as e:
        sys.exit(str(e))


def build(spec):
    if not spec.get("build"):
        return True, ""
    try:
        r = subprocess.run(spec["build"], cwd=spec["cwd"],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def cmd_check(args):
    specs = load_manifest(args.manifest)
    failed, think = [], {}
    for spec in specs:
        print(f"\n=== {spec['name']} ===")
        ok, log = build(spec)
        if not ok:
            print("FAIL  build failed:\n" + log)
            failed.append(spec["name"])
            continue
        report = harness.smoke_test(spec["cmd"], cwd=spec["cwd"])
        print("\n".join(report.lines()))
        if not report.ok:
            failed.append(spec["name"])
        else:
            think[spec["name"]] = report.stats.summary()["mean_ms"] / 1000
    print(f"\n{len(specs) - len(failed)}/{len(specs)} bots passed."
          + (f"  Failed: {', '.join(failed)}  (remove them from the manifest before the run)"
             if failed else ""))

    # Project run time from measured latency. Every move of a bot is a round
    # trip the worker waits on, so bot think time dominates once bots are slow.
    n = len(think) + len(reference_specs())
    moves_per_bot = (n - 1) * args.reps * (harness.MIN_ROUNDS + harness.MAX_ROUNDS) / 2
    print(f"\nProjected run time, {n} bots at {args.reps} reps on {args.workers} workers:")
    for reps in sorted({args.reps, 30}, reverse=True):
        total = harness.projected_seconds(think.values(), n, reps, args.workers)
        print(f"  {reps:>3} reps: ~{total / 60:.1f} min")
    slow = sorted(think.items(), key=lambda kv: -kv[1])[:5]
    for name, t in slow:
        cost = t * moves_per_bot / args.workers
        if cost > 30:
            print(f"  {name} alone adds ~{cost / 60:.1f} min (mean {t * 1000:.2f} ms/move)")
    return 1 if failed else 0


def prepare_specs(manifest, no_build=False, no_reference=False, log=print):
    specs = load_manifest(manifest)
    if not no_build:
        for spec in specs:
            ok, out = build(spec)
            if not ok:
                log(f"build failed for {spec['name']} (it will forfeit every round):\n{out}")
    for s in specs:
        s.pop("build", None)
    if not no_reference:
        specs += reference_specs()
    return specs


def cmd_run(args):
    specs = prepare_specs(args.manifest, args.no_build, args.no_reference)
    log_dir = os.path.join(args.out, "logs")
    os.makedirs(log_dir, exist_ok=True)

    n = len(specs)
    pairings = n * (n + 1) // 2 if args.self_play else n * (n - 1) // 2
    total = pairings * args.reps

    # Resume from <out>/matches.jsonl if it holds a run with the same field and settings.
    header, records = harness.Checkpoint.load(args.out)
    seed = args.seed
    if header and not args.fresh and harness.Checkpoint.compatible(header, specs, args.reps,
                                                                   args.self_play, args.seed):
        seed = header["seed"]
        checkpoint = harness.Checkpoint(args.out, header, resume=True)
        print(f"resuming: {len(records)}/{total} matches already played (seed {seed})")
    else:
        if header:
            backup = harness.Checkpoint.set_aside(args.out)
            print(f"starting over; previous record kept as {os.path.basename(backup)}")
        records = []
        if seed is None:
            seed = random.randrange(1 << 30)
        checkpoint = harness.Checkpoint(args.out, harness.Checkpoint.header(specs, args.reps, seed, args.self_play))
    args.seed = seed
    prev_points, prev_rounds, done = harness.restore_totals(records, n)

    print(f"{n} bots, {pairings} pairings x {args.reps} reps = {total} matches, "
          f"{args.workers} workers, seed {seed}")

    last = [0.0]

    def progress(done, total, elapsed):
        if elapsed - last[0] < 2 and done != total:
            return
        last[0] = elapsed
        eta = elapsed / done * (total - done)
        print(f"\r  {done}/{total} matches  {elapsed:6.0f}s elapsed  ETA {eta:6.0f}s ",
              end="", flush=True)

    t0 = time.perf_counter()
    try:
        points, rounds, stats = harness.run_round_robin(
            specs, args.reps, seed=seed, workers=args.workers,
            self_play=args.self_play, log_dir=log_dir, progress=progress, skip=done,
            on_match=lambda i, j, pa, pb, k, moves, r: checkpoint.add(i, j, r, pa, pb, k, moves))
    finally:
        checkpoint.close()
    print(f"\ndone in {time.perf_counter() - t0:.0f}s")
    points = [[a + b for a, b in zip(ra, rb)] for ra, rb in zip(points, prev_points)]
    rounds = [[a + b for a, b in zip(ra, rb)] for ra, rb in zip(rounds, prev_rounds)]

    rows = harness.score_rows(specs, points, rounds, stats, args.ref_weight)
    print(f"\n{'#':>3}  {'bot':<26} {'score':>6} {'vs team':>8} {'vs ref':>7}  "
          f"{'t/o':>5} {'crash':>5} {'mean ms':>8} {'max ms':>7}")
    rank = 0
    for r in rows:
        if r["kind"] == "team":
            rank += 1
        tag = f"{rank:>3}" if r["kind"] == "team" else "  -"
        flag = "  DISABLED" if r["disabled"] else ""
        print(f"{tag}  {r['name']:<26} {r['score']:6.3f} {r['vs_teams']:8.3f} {r['vs_refs']:7.3f}  "
              f"{r['timeouts']:5d} {r['crashes']:5d} {r['mean_ms']:8.3f} {r['max_ms']:7.1f}{flag}")

    harness.write_outputs(args.out, specs, points, rounds, rows, vars(args))
    print(f"\nwrote {args.out}/leaderboard.csv, pairwise.csv, run.json; bot stderr in {log_dir}/")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="build and smoke-test every bot")
    c.add_argument("manifest")
    c.add_argument("--reps", type=int, default=100)
    c.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    r = sub.add_parser("run", help="run the tournament")
    r.add_argument("manifest")
    r.add_argument("--reps", type=int, default=100, help="repetitions per pairing (fallback: 30)")
    r.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                   help="parallel workers; keep <= cores/2 so bots aren't starved into timeouts")
    r.add_argument("--seed", type=int, default=None, help="default: random (recorded in the results)")
    r.add_argument("--fresh", action="store_true",
                   help="ignore a saved run in --out and start over (the old record is kept)")
    r.add_argument("--ref-weight", type=float, default=1.0,
                   help="weight of rounds vs reference bots in the score (1 = plain mean per round)")
    r.add_argument("--self-play", action="store_true", help="each bot also plays a copy of itself")
    r.add_argument("--no-reference", action="store_true")
    r.add_argument("--no-build", action="store_true")
    r.add_argument("--out", default="results")
    args = ap.parse_args()
    sys.exit(cmd_check(args) if args.cmd == "check" else cmd_run(args))


if __name__ == "__main__":
    main()
