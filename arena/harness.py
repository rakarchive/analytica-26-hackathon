"""The match engine and bot plumbing.

Two kinds of player share one interface:

* LocalPlayer   wraps an in-process Python Strategy (baselines, reference bots).
* ProcessPlayer talks to a long-lived subprocess over the line protocol:

      -> RESET                 new match, clear per-match state
      -> ROUND - -             first round of a match, no history yet
      -> ROUND <mine> <theirs> previous round's ACTUAL (post-noise) moves
      <- C | D                 your move for this round
      -> END                   tournament over, exit

Timeout, crash and junk-output handling lives in ProcessPlayer so that
the Arena's checks, its runs and the saved tournament all behave identically.
"""

import os
import queue
import random
import shlex
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

import games

GAME = games.current()   # the rules in force; see games/ and set_game()


def set_game(key):
    """Switch games. Worker processes are told which game to play, so this is
    the only thing that has to travel with a run."""
    global GAME
    GAME = games.use(key)
    return GAME
MOVE_TIMEOUT = 0.050     # hard per-move limit; overrun forfeits the round (see play_match)
STARTUP_TIMEOUT = 10.0   # allowance for the first reply after (re)start: JVM etc.
WINDOWS = sys.platform == "win32"
# Stop each bot opening its own console window when launched from the GUI.
POPEN_FLAGS = subprocess.CREATE_NO_WINDOW if WINDOWS else 0
LATE_GRACE = 1.0         # how long to wait for a late reply before killing the bot
MAX_FAILED_STARTS = 3    # consecutive startup failures before a bot is disabled


def split_cmd(cmd):
    """Command string -> argv. Windows paths (C:\\Users\\...) survive, which
    shlex's POSIX mode does not allow for."""
    if not isinstance(cmd, str):
        return list(cmd)
    if not WINDOWS:
        return shlex.split(cmd)
    return [t[1:-1] if len(t) > 1 and t[0] == t[-1] == '"' else t
            for t in shlex.split(cmd, posix=False)]


def join_cmd(argv):
    return subprocess.list2cmdline(argv) if WINDOWS else shlex.join(argv)


# --------------------------------------------------------------------------
# In-process strategies
# --------------------------------------------------------------------------

class Strategy:
    """Base class for in-process bots. Mirrors the protocol exactly: the
    strategy only ever sees the previous round's actual moves and keeps its
    own history. Subclasses implement choose() using self.my / self.opp."""

    name = None

    def reset(self, rng):
        self.rng = rng
        self.my, self.opp = [], []

    def move(self, my_last, opp_last):
        if my_last is not None:
            self.my.append(my_last)
            self.opp.append(opp_last)
        return self.choose()

    def choose(self):
        raise NotImplementedError


@dataclass
class BotStats:
    moves: int = 0
    timeouts: int = 0
    junk_lines: int = 0   # non-move lines on stdout (debug prints etc.)
    crashes: int = 0
    forfeits: int = 0     # rounds it was dead for, played as the forfeit move
    disabled: bool = False
    latencies: list = field(default_factory=list)
    loaded: dict = None          # set when read back from a tournament file

    def merge(self, other):
        for k in ("moves", "timeouts", "junk_lines", "crashes", "forfeits"):
            setattr(self, k, getattr(self, k) + getattr(other, k))
        self.disabled = self.disabled or other.disabled
        self.latencies.extend(other.latencies)

    def summary(self):
        if getattr(self, "loaded", None):
            return self.loaded          # read back from a tournament file
        lat = sorted(self.latencies)
        pick = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))] * 1000 if lat else 0.0
        return {
            "moves": self.moves, "timeouts": self.timeouts,
            "junk_lines": self.junk_lines, "crashes": self.crashes,
            "forfeits": self.forfeits, "disabled": self.disabled,
            "mean_ms": statistics.fmean(lat) * 1000 if lat else 0.0,
            "p99_ms": pick(0.99), "max_ms": lat[-1] * 1000 if lat else 0.0,
        }


class LocalPlayer:
    def __init__(self, name, strategy):
        self.name, self.strategy = name, strategy
        self.stats = BotStats()
        self._pending = None

    def reset(self, seed=None):
        self.strategy.reset(random.Random(seed))

    def request(self, my_last, opp_last):
        self._pending = self.strategy.move(my_last, opp_last)

    def response(self):
        self.stats.moves += 1
        return self._pending, "ok"

    def close(self):
        pass


# --------------------------------------------------------------------------
# Subprocess bots
# --------------------------------------------------------------------------

def _pump(stream, q):
    # A reader thread (rather than select) keeps this working on Windows,
    # which teams may be running the Arena on.
    try:
        for raw in iter(stream.readline, b""):
            q.put((time.perf_counter(), raw.decode("utf-8", "replace")))
    except (OSError, ValueError):
        pass
    q.put((time.perf_counter(), None))


class ProcessPlayer:
    def __init__(self, name, cmd, cwd=None, stderr=None,
                 move_timeout=MOVE_TIMEOUT, startup_timeout=STARTUP_TIMEOUT):
        self.name = name
        self.cmd = split_cmd(cmd)
        self.cwd, self.stderr = cwd, stderr
        self.move_timeout, self.startup_timeout = move_timeout, startup_timeout
        self.stats = BotStats()
        self.proc = None
        self.last_error = None
        self._lines = None
        self._fresh = False      # next reply gets the startup allowance
        self._late = False       # a timed-out reply is still owed
        self._dead = False       # forfeit the rest of the current match
        self._failed_starts = 0

    # ---- process lifecycle ----

    def _start(self):
        self._kill()
        try:
            self.proc = subprocess.Popen(
                self.cmd, cwd=self.cwd, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self.stderr, creationflags=POPEN_FLAGS)
        except OSError as e:
            self.last_error = f"could not start {self.cmd!r}: {e}"
            self.proc = None
            return False
        self._lines = queue.SimpleQueue()
        threading.Thread(target=_pump, args=(self.proc.stdout, self._lines),
                         daemon=True).start()
        self._fresh, self._late = True, False
        return True

    def _kill(self):
        if self.proc is None:
            return
        try:
            self.proc.kill()
            self.proc.wait(timeout=2)
        except Exception:
            pass
        for s in (self.proc.stdin, self.proc.stdout):
            try:
                s.close()
            except Exception:
                pass
        self.proc = None

    def _crash(self, why):
        self.stats.crashes += 1
        self.last_error = why
        if self.proc is not None and self.proc.poll() is not None:
            self.last_error += f" (exit code {self.proc.returncode})"
        if self._fresh:
            self._failed_starts += 1
            if self._failed_starts >= MAX_FAILED_STARTS:
                self.stats.disabled = True
        self._kill()
        self._dead = True

    def _send(self, text):
        try:
            self.proc.stdin.write(text.encode() + b"\n")
            self.proc.stdin.flush()
            return True
        except (OSError, ValueError, AttributeError):
            return False

    def _read_move(self, deadline):
        """Next move line that ARRIVED before the deadline (arrival is stamped by
        the reader thread, so time spent waiting on the other bot doesn't count).
        Returns (move | "timeout" | "eof", arrival time). Non-move lines, such
        as debug prints on stdout, are skipped."""
        while True:
            try:
                at, line = self._lines.get(timeout=max(0.0, deadline - time.perf_counter()))
            except queue.Empty:
                return "timeout", None
            if line is None:
                return "eof", at
            m = line.strip().upper()
            if m in GAME.moves:
                if at > deadline:
                    # Arrived late, and we have now consumed it: nothing is owed.
                    self.stats.latencies.append(at - self._sent_at)
                    return "late", at
                return m, at
            if m:
                self.stats.junk_lines += 1

    def _settle_late(self):
        """Swallow the reply we gave up on, so the stream stays in sync."""
        got, at = self._read_move(time.perf_counter() + LATE_GRACE)
        if got in GAME.moves or got == "late":
            if got != "late":
                self.stats.latencies.append(at - self._sent_at)
            self._late = False
            return True
        self._crash("stopped responding" if got == "timeout" else "exited")
        return False

    # ---- player interface ----

    def reset(self, seed=None):
        self._dead = False
        if self.stats.disabled:
            self._dead = True
            return
        if self._late:
            self._settle_late()
            self._dead = False
        if self.proc is None or self.proc.poll() is not None:
            if not self._start():
                self._fresh = True  # count it as a failed start
                self._crash(self.last_error)
                return
        if not self._send("RESET"):
            self._crash("stdin closed on RESET")

    def request(self, my_last, opp_last):
        if self._dead:
            return
        if self._late and not self._settle_late():
            return
        # Drop anything printed after the previous reply (e.g. "C\nC").
        while True:
            try:
                _, extra = self._lines.get_nowait()
            except queue.Empty:
                break
            if extra is None:
                self._crash("exited")
                return
            if extra.strip():
                self.stats.junk_lines += 1
        msg = "ROUND - -" if my_last is None else f"ROUND {my_last} {opp_last}"
        if not self._send(msg):
            self._crash("stdin closed")
            return
        self._sent_at = time.perf_counter()

    def response(self):
        self.stats.moves += 1
        if self._dead:
            self.stats.forfeits += 1
            return GAME.forfeit, "dead"
        limit = self.startup_timeout if self._fresh else self.move_timeout
        got, at = self._read_move(self._sent_at + limit)
        if got in ("timeout", "late"):
            self.stats.timeouts += 1
            self._late = got == "timeout"
            return GAME.forfeit, "timeout"
        if got == "eof":
            self._crash("exited mid-match")
            return GAME.forfeit, "crash"
        if self._fresh:
            self._fresh, self._failed_starts = False, 0
        else:
            self.stats.latencies.append(at - self._sent_at)
        return got, "ok"

    def close(self):
        if self.proc is not None and self.proc.poll() is None:
            self._send("END")
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        self._kill()


# --------------------------------------------------------------------------
# Matches
# --------------------------------------------------------------------------

def match_plan(seed, rep):
    """Length and noise for repetition `rep`: per round and side, either None
    or a draw in [0, 1) that picks which *other* move it comes out as (see
    noisy). Every pairing uses the same plan for a given rep (common random
    numbers), so differences between bots come from strategy, not from who
    drew the unlucky noise."""
    rng = random.Random(f"plan:{seed}:{rep}")
    lo, hi = GAME.rounds
    rounds = rng.randint(lo, hi)
    flips = []
    for _ in range(rounds):
        flips.append(tuple(rng.random() if rng.random() < GAME.noise else None
                           for _ in range(2)))
    return rounds, flips


def noisy(move, draw):
    """What `move` comes out as when noise strikes with `draw`: always a
    different move, so the noise rate is the rate at which moves change."""
    others = GAME.other_moves(move)
    return others[int(draw * len(others))]


def bot_seed(seed, rep, name, side):
    return random.Random(f"bot:{seed}:{rep}:{name}:{side}").getrandbits(64)


def play_match(a, b, flips, seed_a=None, seed_b=None, record=None):
    """Play one match; returns (points_a, points_b, rounds). If `record` is a
    list, one (intent_a, intent_b, flip_a, flip_b, status_a, status_b) tuple
    is appended per round."""
    a.reset(seed_a)
    b.reset(seed_b)
    last_a = last_b = None
    pa = pb = 0
    for alt_a, alt_b in flips:
        # Ask both before waiting on either, so their think time overlaps.
        a.request(last_a, last_b)
        b.request(last_b, last_a)
        ma, status_a = a.response()
        mb, status_b = b.response()
        if alt_a is not None:
            ma = noisy(ma, alt_a)   # noise: it comes out as something else
        if alt_b is not None:
            mb = noisy(mb, alt_b)
        if record is not None:
            record.append((ma, mb, alt_a is not None, alt_b is not None, status_a, status_b))
        sa, sb = GAME.payoff[ma, mb]
        # A forfeited round (timeout, crash, dead bot) still gives the opponent
        # a real move to play against, but scores 0 for the forfeiter. Otherwise
        # a broken bot is just a bot that always plays the forfeit move.
        pa += sa if status_a == "ok" else 0
        pb += sb if status_b == "ok" else 0
        last_a, last_b = ma, mb
    return pa, pb, len(flips)


def encode_record(record):
    """Compact per-side move strings for replaying a match: the move as it
    came out, lowercase if noise changed it, '#' if the bot forfeited."""
    def side(k):
        out = []
        for r in record:
            move, changed, status = r[k], r[2 + k], r[4 + k]
            out.append("#" if status != "ok" else (move.lower() if changed else move))
        return "".join(out)
    return side(0), side(1)


# --------------------------------------------------------------------------
# Smoke test
# --------------------------------------------------------------------------

FLUSH_HINTS = """\
  Python : print(move, flush=True)
  Java   : System.out.println(move); System.out.flush();
  C++    : std::cout << move << std::endl;     (endl flushes; "\\n" does not)
  C      : printf("%c\\n", move); fflush(stdout);
  Rust   : println!(..); std::io::stdout().flush().unwrap();
  Go     : use fmt.Println on os.Stdout directly, or w.Flush() after each move
  Node   : process.stdout.write(move + "\\n")   (read input with readline)"""


@dataclass
class Check:
    status: str        # "ok", "warn" or "fail"
    label: str
    detail: str = ""


@dataclass
class SmokeReport:
    ok: bool
    checks: list
    stats: BotStats
    stderr_tail: list = field(default_factory=list)

    @property
    def worst(self):
        s = {c.status for c in self.checks}
        return "fail" if "fail" in s or not self.ok else "warn" if "warn" in s else "ok"

    def lines(self):
        tag = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL"}
        out = []
        for c in self.checks:
            first, *rest = c.detail.split("\n") if c.detail else [""]
            out.append(f"{tag[c.status]}  {c.label}" + (f": {first}" if first else ""))
            out += ["      " + r for r in rest]
        if self.stderr_tail:
            out += ["      --- last lines of the bot's stderr ---"] + ["      " + l for l in self.stderr_tail]
        return out


def smoke_test(cmd, cwd=None, rounds=200):
    """Check a bot speaks the protocol. Returns a SmokeReport."""
    import tempfile
    with tempfile.TemporaryFile() as err:
        checks, ok, stats = _smoke(cmd, cwd, rounds, err)
        tail = []
        if not ok:
            err.seek(0)
            tail = err.read().decode("utf-8", "replace").strip().splitlines()[-15:]
    return SmokeReport(ok, checks, stats, tail)


def _smoke(cmd, cwd, rounds, stderr):
    import importlib

    checks = []
    bot = ProcessPlayer("bot", cmd, cwd=cwd, stderr=stderr)

    # 1. First reply: this is where unflushed output shows up.
    bot.reset()
    if bot._dead:
        checks.append(Check("fail", "Starts", bot.last_error))
        return checks, False, bot.stats
    t0 = time.perf_counter()
    bot.request(None, None)
    move, status = bot.response()
    if status == "timeout":
        checks.append(Check("fail", "Replies to its first move",
                            f"No reply within {STARTUP_TIMEOUT:.0f} s. Almost always this means stdout "
                            "is not flushed after each move:\n" + FLUSH_HINTS +
                            "\nAlso check it reads one line per message and doesn't wait for EOF."))
        bot._kill()
        return checks, False, bot.stats
    if status == "crash":
        checks.append(Check("fail", "Replies to its first move", f"crashed: {bot.last_error}"))
        return checks, False, bot.stats
    checks.append(Check("ok", "Starts and replies",
                        f"first move: {GAME.past[move]}, "
                        f"after {(time.perf_counter() - t0) * 1000:.0f} ms"))

    # 2. A few real matches, each preceded by RESET.
    ok = True
    for k, (module, cls_name) in enumerate(GAME.smoke):
        opp_cls = getattr(importlib.import_module(module), cls_name)
        opp = LocalPlayer(opp_cls.name, opp_cls())
        before = BotStats()
        before.merge(bot.stats)
        pa, _, n = play_match(bot, opp, match_plan(0, k)[1][:rounds], seed_b=1)
        problems = [f"{getattr(bot.stats, x) - getattr(before, x)} {x}"
                    for x in ("timeouts", "crashes", "forfeits")
                    if getattr(bot.stats, x) - getattr(before, x)]
        detail = f"{pa / n:.3f} points/round"
        if problems:
            ok = False
            detail += "  ·  " + ", ".join(problems) + (f" ({bot.last_error})" if bot.last_error else "")
        checks.append(Check("fail" if problems else "ok", f"Plays {opp_cls.name}", detail))

    if bot.stats.junk_lines:
        checks.append(Check("warn", "Keeps stdout for moves only",
                            f"{bot.stats.junk_lines} other lines were ignored. Print debug output to "
                            "stderr instead; it costs you time."))
    else:
        checks.append(Check("ok", "Keeps stdout for moves only"))

    # 3. Clean shutdown on END.
    if bot.proc is not None:
        bot._send("END")
        try:
            bot.proc.wait(timeout=2)
            checks.append(Check("ok", "Exits on END"))
        except subprocess.TimeoutExpired:
            checks.append(Check("warn", "Exits on END", "still running 2 s after END; it will be killed"))
    bot._kill()

    s = bot.stats.summary()
    speed = "fail" if s["timeouts"] else "warn" if s["max_ms"] > 25 or s["mean_ms"] > 1 else "ok"
    checks.append(Check(speed, "Speed", f"mean {s['mean_ms']:.2f} ms  ·  p99 {s['p99_ms']:.2f} ms  ·  "
                                        f"max {s['max_ms']:.1f} ms  (limit {MOVE_TIMEOUT * 1000:.0f} ms)"))
    return checks, ok, bot.stats


# --------------------------------------------------------------------------
# Manifests and results
# --------------------------------------------------------------------------

def load_manifest(path):
    """Team bots from a manifest (paths relative to the manifest file):
    {"bots": [{"name": ..., "dir": ..., "run": "...", "build": "..."}, ...]}"""
    import json
    base = os.path.dirname(os.path.abspath(path))
    with open(path) as f:
        entries = json.load(f)["bots"]
    specs = [{"name": e["name"], "kind": "team", "cmd": split_cmd(e["run"]),
              "cwd": os.path.join(base, e.get("dir", ".")),
              "build": split_cmd(e["build"]) if e.get("build") else None}
             for e in entries]
    names = [s["name"] for s in specs]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"duplicate bot names in manifest: {dupes}")
    return specs


def score_rows(specs, points, rounds, stats, ref_weight=1.0):
    """Leaderboard rows, best first. Score is mean points per round, with
    rounds against house (reference) bots weighted by ref_weight."""
    n = len(specs)
    rows = []
    for i, s in enumerate(specs):
        acc = {"team": [0, 0], "other": [0, 0]}
        for j in range(n):
            if rounds[i][j]:
                a = acc["team" if specs[j]["kind"] == "team" else "other"]
                a[0] += points[i][j]
                a[1] += rounds[i][j]
        tot_p = acc["team"][0] + ref_weight * acc["other"][0]
        tot_r = acc["team"][1] + ref_weight * acc["other"][1]
        per = lambda a: a[0] / a[1] if a[1] else float("nan")
        rows.append({"name": s["name"], "kind": s["kind"],
                     "score": tot_p / tot_r if tot_r else 0.0,
                     "vs_teams": per(acc["team"]), "vs_refs": per(acc["other"]),
                     **stats[i].summary()})
    rows.sort(key=lambda r: -r["score"])
    return rows


def write_outputs(out, specs, points, rounds, rows, run_args):
    import csv
    import json
    os.makedirs(out, exist_ok=True)
    n = len(specs)
    with open(os.path.join(out, "leaderboard.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    with open(os.path.join(out, "pairwise.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["row vs col (row's pts/round)"] + [s["name"] for s in specs])
        for i, s in enumerate(specs):
            wr.writerow([s["name"]] + [f"{points[i][j] / rounds[i][j]:.3f}" if rounds[i][j] else ""
                                       for j in range(n)])
    with open(os.path.join(out, "run.json"), "w") as f:
        json.dump({"args": run_args, "bots": [s["name"] for s in specs],
                   "points": points, "rounds": rounds}, f)


class TournamentFile:
    """The record of a whole tournament, written as it is played: one JSON
    object per line, flushed as it goes, so a crash costs at most the last
    match and a run can be resumed. It holds every move of every match, which
    is what the show replays and what the explorer digs through.

        line 1      header: the field, reps, seed, noise, payoff
        lines 2..n  one match: who, which repetition, the score, the moves
        last line   per-bot stats: timeouts, crashes, latency

    Reading a .gz file works too (see `load`)."""

    VERSION = 2

    def __init__(self, path, header, resume=False):
        folder = os.path.dirname(os.path.abspath(path))
        if folder:
            os.makedirs(folder, exist_ok=True)
        self.path = path
        self.f = open(path, "a" if resume else "w", encoding="utf-8")
        if not resume:
            self._write(header)

    @staticmethod
    def header(specs, reps, seed, self_play):
        return {"type": "header", "version": TournamentFile.VERSION, "game": GAME.key,
                "bots": [{"name": s["name"], "kind": s["kind"]} for s in specs],
                "reps": reps, "seed": seed, "self_play": bool(self_play),
                "noise": GAME.noise,
                "payoff": {f"{a}{b}": list(v) for (a, b), v in GAME.payoff.items()},
                "rounds": list(GAME.rounds),
                "started": time.strftime("%Y-%m-%d %H:%M:%S")}

    @classmethod
    def load(cls, path):
        """A Tournament, or None if the file isn't one. A torn last line
        (a crash mid-write) is ignored."""
        import gzip
        import json
        if not path or not os.path.exists(path):
            return None
        opener = gzip.open if path.endswith(".gz") else open
        header, matches, stats = None, [], {}
        with opener(path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                kind = obj.get("type")
                if kind == "header":
                    header = obj
                elif kind == "stats":
                    stats = obj.get("bots", {})
                elif header is not None:
                    matches.append(obj)
        if header is None:
            return None
        return Tournament(path, header, matches, stats)

    @staticmethod
    def compatible(header, specs, reps, self_play, seed=None):
        return (header is not None and header.get("version") == TournamentFile.VERSION
                and [b["name"] for b in header["bots"]] == [s["name"] for s in specs]
                and [b["kind"] for b in header["bots"]] == [s["kind"] for s in specs]
                and header["reps"] == reps and header["self_play"] == bool(self_play)
                and (seed is None or header["seed"] == seed))

    @staticmethod
    def set_aside(path):
        """Move an old record out of the way instead of deleting it."""
        if path and os.path.exists(path):
            stamp = time.strftime("%Y%m%d-%H%M%S")
            base = path[:-6] if path.endswith(".jsonl") else path
            new = f"{base}.{stamp}.jsonl"
            os.replace(path, new)
            return new
        return None

    def add(self, i, j, rep, pa, pb, n, moves=None):
        rec = {"i": i, "j": j, "r": rep, "n": n, "pa": pa, "pb": pb}
        if moves:
            rec["a"], rec["b"] = moves
        self._write(rec)

    def write_stats(self, stats):
        self._write({"type": "stats",
                     "bots": {name: s.summary() for name, s in stats.items()}})

    def _write(self, obj):
        import json
        self.f.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self.f.flush()

    def close(self):
        self.f.close()


class Tournament:
    """A tournament read back from a file: the field, every match, the stats."""

    def __init__(self, path, header, matches, stats):
        self.path, self.header, self.matches, self.bot_stats = path, header, matches, stats
        self.bots = header["bots"]
        self.names = [b["name"] for b in self.bots]
        self.kinds = [b["kind"] for b in self.bots]
        self.reps = header["reps"]
        self.seed = header["seed"]
        self.self_play = header["self_play"]
        self.noise = header.get("noise", GAME.noise)

    def __len__(self):
        return len(self.matches)

    @property
    def n(self):
        return len(self.bots)

    def duel(self, m):
        """A team-against-team match (not one involving a house bot)."""
        return self.kinds[m["i"]] == self.kinds[m["j"]] == "team"

    def expected(self):
        """How many matches a complete run of this field holds."""
        n = self.n
        pairings = n * (n + 1) // 2 if self.self_play else n * (n - 1) // 2
        return pairings * self.reps

    def complete(self):
        return len(self.matches) >= self.expected()

    def has_moves(self):
        return bool(self.matches) and "a" in self.matches[0]

    def in_cycles(self):
        """The matches in playback order: cycle by cycle (one cycle is every
        pairing once), and within a cycle the house matches first."""
        return sorted(self.matches, key=lambda m: (m["r"], 1 if self.duel(m) else 0))

    def totals(self):
        """points[i][j], rounds[i][j] over every match in the file."""
        n = self.n
        points = [[0] * n for _ in range(n)]
        rounds = [[0] * n for _ in range(n)]
        for m in self.matches:
            i, j = m["i"], m["j"]
            points[i][j] += m["pa"]
            points[j][i] += m["pb"]
            rounds[i][j] += m["n"]
            rounds[j][i] += m["n"]
        return points, rounds

    def played(self):
        """The (i, j, rep) already in the file, for resuming a run."""
        return {(m["i"], m["j"], m["r"]) for m in self.matches}

    def stats_objects(self):
        """Per-bot stats by index, as saved with the file."""
        out = {}
        for i, name in enumerate(self.names):
            s = BotStats()
            s.loaded = self.bot_stats.get(name) or None
            if s.loaded:
                for k in ("moves", "timeouts", "junk_lines", "crashes", "forfeits"):
                    setattr(s, k, s.loaded.get(k, 0))
                s.disabled = s.loaded.get("disabled", False)
            out[i] = s
        return out


def projected_seconds(mean_latencies, n_bots, reps, workers):
    """Rough run time from measured per-move latency (seconds): every move
    is a round trip a worker waits on, plus ~20 us/round of plumbing."""
    moves_per_bot = (n_bots - 1) * reps * sum(GAME.rounds) / 2
    base = n_bots * (n_bots - 1) / 2 * reps * 200 * 20e-6
    return (base + sum(mean_latencies) * moves_per_bot) / max(1, workers)


# --------------------------------------------------------------------------
# Round robin
# --------------------------------------------------------------------------
#
# A bot spec is a picklable dict:
#   {"name": ..., "kind": "team"|"ref"|..., "cmd": "...", "cwd": "..."}        subprocess
#   {"name": ..., "kind": ..., "strategy": ("module", "Class", {kwargs})}      in-process
#
# Each worker process keeps its own long-lived instance of every bot it has
# met (two for self-play) and reuses them across matches via RESET.

def make_player(spec, slot=0, log_dir=None, worker=0):
    import importlib
    if "strategy" in spec:
        mod, cls, kwargs = spec["strategy"]
        return LocalPlayer(spec["name"], getattr(importlib.import_module(mod), cls)(**kwargs))
    stderr = None
    if log_dir is not None:
        stderr = open(os.path.join(log_dir, f"{spec['name']}.w{worker}.s{slot}.log"), "ab")
    elif spec.get("quiet"):
        stderr = subprocess.DEVNULL
    return ProcessPlayer(spec["name"], spec["cmd"], cwd=spec.get("cwd"), stderr=stderr,
                         move_timeout=spec.get("move_timeout", MOVE_TIMEOUT))


def _worker(specs, seed, tasks, results, log_dir, worker, stream_moves, game_key):
    set_game(game_key)          # a spawned worker starts with the default game
    players = {}

    def get(i, slot):
        if (i, slot) not in players:
            players[i, slot] = make_player(specs[i], slot, log_dir, worker)
        return players[i, slot]

    try:
        while True:
            chunk = tasks.get()
            if chunk is None:
                break
            for i, j, rep in chunk:
                _, flips = match_plan(seed, rep)
                a, b = get(i, 0), get(j, 1 if i == j else 0)
                record = [] if stream_moves else None
                pa, pb, n = play_match(a, b, flips,
                                       bot_seed(seed, rep, specs[i]["name"], 0),
                                       bot_seed(seed, rep, specs[j]["name"], 1), record)
                moves = encode_record(record) if stream_moves else None
                results.put(("match", i, j, rep, pa, pb, n, moves))
    finally:
        stats = {}
        for (i, _), p in players.items():
            p.close()
            stats.setdefault(i, BotStats()).merge(p.stats)
        results.put(("stats", stats))


def run_round_robin(specs, reps, seed=0, workers=1, self_play=False,
                    log_dir=None, progress=None, on_match=None, stop=None, skip=(), priority=None):
    """Play every pairing `reps` times. Returns (points, rounds, stats) where
    points[i][j] / rounds[i][j] is bot i's mean payoff per round against j.

    on_match(i, j, points_i, points_j, rounds, (moves_i, moves_j), rep) is
    called for every finished match (see encode_record). `stop` is a
    threading.Event that aborts the run early. `skip` is a set of (i, j, rep)
    already played (resuming from a Checkpoint); those matches are not played
    and are not counted in the returned totals. `priority(i, j, rep)` orders
    the work: lower values are played first (e.g. each cycle's house matches
    before its team matches)."""
    import multiprocessing as mp

    n = len(specs)
    pairs = [(i, j) for i in range(n) for j in range(i if self_play else i + 1, n)]
    skip = set(skip)
    tasks_list = [(i, j, r) for r in range(reps) for i, j in pairs if (i, j, r) not in skip]
    random.Random(seed).shuffle(tasks_list)  # spread slow bots across workers
    if priority:
        tasks_list.sort(key=lambda t: priority(*t))  # stable: still shuffled within a group

    # Tasks go out in chunks: on macOS a multiprocessing.Queue holds at most
    # 32767 items, and a full tournament has more matches than that.
    size = max(1, len(tasks_list) // (workers * 100))
    chunks = [tasks_list[k:k + size] for k in range(0, len(tasks_list), size)]
    ctx = mp.get_context("spawn")
    tasks, results = ctx.Queue(), ctx.Queue()
    procs = [ctx.Process(target=_worker,
                         args=(specs, seed, tasks, results, log_dir, w, on_match is not None, GAME.key),
                         daemon=False) for w in range(workers)]
    for p in procs:
        p.start()
    for c in chunks:
        tasks.put(c)
    for _ in range(workers):
        tasks.put(None)

    points = [[0] * n for _ in range(n)]
    rounds = [[0] * n for _ in range(n)]
    stats = {i: BotStats() for i in range(n)}
    done, pending_stats, total = 0, workers, len(tasks_list)
    t0 = time.perf_counter()
    try:
        while pending_stats:
            if stop is not None and stop.is_set():
                break
            try:
                msg = results.get(timeout=0.25)
            except queue.Empty:
                if not any(p.is_alive() for p in procs):
                    raise RuntimeError("all tournament workers exited without finishing; "
                                       "see the console for their errors")
                continue
            if msg[0] == "match":
                _, i, j, r, pa, pb, k, moves = msg
                if on_match:
                    on_match(i, j, pa, pb, k, moves, r)
                points[i][j] += pa
                points[j][i] += pb
                rounds[i][j] += k
                rounds[j][i] += k
                done += 1
                if progress:
                    progress(done, total, time.perf_counter() - t0)
            else:
                for i, s in msg[1].items():
                    stats[i].merge(s)
                pending_stats -= 1
    finally:
        for p in procs:
            p.join(timeout=0 if stop is not None and stop.is_set() else 5)
            if p.is_alive():
                p.terminate()
    return points, rounds, stats
