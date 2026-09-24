"""Shared pieces of the Arena (teams' toolkit) and the event app: the
board, the replay stage, check report cards, the engine thread, verdicts
and captions. Not run directly.

Originally:
The Arena: test your bot, run tournaments, watch matches.

Double-click this file, or run:  python arena.py

  + Add bot     pick your bots' main files (.py .java .cpp .c .js .jar .exe);
                select several at once to add them all
  Check         protocol check for the selected bot (do this first)
  Run           round robin: your bots vs the baselines, with live replays
  Watch         click two rows on the board, then Watch to replay that match

Right-click one of your bots to edit its run command or remove it. Click a
row after a run to see its scores against each opponent.

Advanced (collapsed by default) is for running an event: load the house
bots, check every bot at once, set tournament options and a results folder,
and switch to presentation mode for the projector. Start with --dev to also
load a team manifest there (development testing with simulated fields).
"""

import argparse
import collections
import colorsys
import multiprocessing
import os
import queue
import random
import importlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import traceback
from tkinter import filedialog, simpledialog
from tkinter import font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness  # noqa: E402
from game import (MAX_REPLAYS_PER_PAIR, actual, headline, intent_of,  # noqa: E402,F401
                  match_story, new_story, past, verdict, word)


BG, PANEL, PANEL2, LINE = "#0e1218", "#161c26", "#1b2230", "#2a3344"
SELECT = "#26344d"
FG, DIM, FAINT = "#eef1f6", "#8d97a8", "#4b5566"
FORFEIT_COL = "#596274"
MEDALS = {1: "#f5c542", 2: "#c9d1dc"}         # only the top two are winners
MEDAL_BG = {1: "#3b321a", 2: "#2c3444"}       # their rows on the board
UP, DOWN, GLOW, WARN, ACCENT = "#4fd18b", "#ff6b61", "#ffd34d", "#ffb35c", "#5b8def"


def bot_colors(n):
    out, h = [], random.Random(7).random()
    for _ in range(n):
        h = (h + 0.618034) % 1
        r, g, b = colorsys.hsv_to_rgb(h, 0.55, 0.98)
        out.append(f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}")
    return out


def pick_family(root):
    have = set(tkfont.families(root))
    for f in ("Segoe UI", "Helvetica Neue", "Helvetica", "Arial"):
        if f in have:
            return f
    return "TkDefaultFont"


FROZEN = getattr(sys, "frozen", False)  # running as the packaged Arena.exe

# Bots' stderr (their debug prints) goes to files here. A windowed exe has no
# console, and a bot writing to a missing stderr would crash.
BOT_LOG_DIR = os.path.join(tempfile.gettempdir(), "arena-logs")


PORTABLE_PYTHON = None   # set when a kit's Python is adopted from tools/

# Run a bot with its own folder importable. The kit's embeddable Python
# restricts sys.path, which would break a bot split across several files.
PY_BOOTSTRAP = ("import os, runpy, sys; p = sys.argv[1]; "
                "sys.path.insert(0, os.path.dirname(os.path.abspath(p))); sys.argv = [p]; "
                "runpy.run_path(p, run_name='__main__')")


def adopt_portable_tools():
    """Put a `tools` folder sitting next to the app on PATH, so a copy of the
    kit on a flash drive brings its own Python, JDK and g++ with it: nothing
    installed, nothing changed outside this process."""
    home = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
    tools = os.path.join(home, "tools")
    if not os.path.isdir(tools):
        return []
    global PORTABLE_PYTHON
    added = []
    for rel in ("python", os.path.join("jdk", "bin"), os.path.join("mingw", "bin")):
        d = os.path.join(tools, rel)
        if os.path.isdir(d):
            added.append(d)
            if rel == "python":
                PORTABLE_PYTHON = d
    jdk = os.path.join(tools, "jdk")
    if os.path.isdir(jdk):
        os.environ["JAVA_HOME"] = jdk
    if added:
        os.environ["PATH"] = os.pathsep.join(added + [os.environ.get("PATH", "")])
    return added


def python_cmd(script):
    """How to run a Python bot: the machine's Python if it has one, otherwise
    the interpreter inside this exe (--run-bot), so teams writing Python need
    nothing installed."""
    if FROZEN:
        # Prefer the py launcher: "python" may be the Microsoft Store stub.
        for name in ("py", "python", "python3"):
            found = shutil.which(name)
            if found:
                if PORTABLE_PYTHON and os.path.dirname(found) == PORTABLE_PYTHON:
                    return [found, "-c", PY_BOOTSTRAP, script]
                return [found, script]
        return [sys.executable, "--run-bot", script]
    return [python_exe(), script]


def python_exe():
    if FROZEN:
        return sys.executable
    # Double-clicked scripts may run under pythonw.exe; bots need python.exe
    # so their stdin/stdout are real pipes.
    exe = sys.executable
    head, tail = os.path.split(exe)
    if tail.lower() == "pythonw.exe" and os.path.exists(os.path.join(head, "python.exe")):
        exe = os.path.join(head, "python.exe")
    return exe


def detect(path):
    """(build argv or None, run argv) for a bot's main file."""
    folder, fname = os.path.split(os.path.abspath(path))
    stem, ext = os.path.splitext(fname)
    ext = ext.lower()
    exe = stem + (".exe" if harness.WINDOWS else "")
    if ext in (".py", ".pyw"):
        return None, python_cmd(fname)
    if ext == ".java":
        return ["javac", fname], ["java", "-cp", ".", stem]
    if ext == ".class":
        return None, ["java", "-cp", ".", stem]
    if ext == ".jar":
        return None, ["java", "-jar", fname]
    # Static on Windows, so a compiled bot never depends on finding MinGW's
    # runtime DLLs on the PATH of whatever machine ends up running it.
    static = ["-static"] if harness.WINDOWS else []
    if ext in (".cpp", ".cc", ".cxx"):
        return ["g++", "-O2", "-std=c++17", *static, "-o", exe, fname], [os.path.join(folder, exe)]
    if ext == ".c":
        return ["gcc", "-O2", *static, "-o", exe, fname, "-lm"], [os.path.join(folder, exe)]
    if ext == ".js":
        return None, ["node", fname]
    return None, [os.path.abspath(path)]


def user_bot_spec(path, name):
    build, run = detect(path)
    return {"name": name, "kind": "team", "cmd": run, "cwd": os.path.dirname(os.path.abspath(path)),
            "build": build, "source": os.path.abspath(path)}


def baseline_specs():
    """The sparring partners of whichever game is in force."""
    import importlib
    out = []
    for module, cls_name in harness.GAME.baselines:
        cls = getattr(importlib.import_module(module), cls_name)
        out.append({"name": cls.name, "kind": "baseline", "strategy": (module, cls_name, {})})
    return out


def build(spec):
    """Compile a bot if it needs it. Returns (ok, compiler output or error)."""
    if not spec.get("build"):
        return True, ""
    try:
        r = subprocess.run(spec["build"], cwd=spec["cwd"], capture_output=True, text=True,
                           timeout=120, creationflags=harness.POPEN_FLAGS)
    except FileNotFoundError:
        return False, f"Could not find '{spec['build'][0]}'. Is it installed and on your PATH?"
    except subprocess.TimeoutExpired:
        return False, "Build took over 2 minutes; gave up."
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def default_workers():
    return max(1, min(4, (os.cpu_count() or 2) // 2))


# --------------------------------------------------------------------------
# Background tournament engine
# --------------------------------------------------------------------------

class Engine(threading.Thread):
    def __init__(self, specs, reps, seed, workers, self_play, log_dir, out_q, skip=(), checkpoint=None,
                 priority=None):
        super().__init__(daemon=True)
        self.priority = priority
        self.specs, self.reps, self.seed, self.workers = specs, reps, seed, workers
        self.self_play, self.log_dir, self.q = self_play, log_dir, out_q
        self.skip, self.checkpoint = skip, checkpoint
        self.stop = threading.Event()

    def _on_match(self, i, j, pa, pb, n, moves, rep):
        if self.checkpoint:
            self.checkpoint.add(i, j, rep, pa, pb, n, moves)  # saved before it is shown
        self.q.put(("match", (i, j, pa, pb, n, moves, rep)))

    def run(self):
        try:
            points, rounds, stats = harness.run_round_robin(
                self.specs, self.reps, seed=self.seed, workers=self.workers,
                self_play=self.self_play, log_dir=self.log_dir, stop=self.stop,
                on_match=self._on_match, skip=self.skip, priority=self.priority)
            if not self.stop.is_set():
                self.q.put(("done", (points, rounds, stats)))
        except Exception:
            self.q.put(("error", traceback.format_exc()))
        finally:
            if self.checkpoint:
                self.checkpoint.close()


# --------------------------------------------------------------------------
# A stage that replays one match round by round
# --------------------------------------------------------------------------

class Stage:
    PER_BAND = 50

    def __init__(self, app, tag):
        self.app, self.tag = app, tag
        self.match = None
        self.pinned = False
        self.title = ""
        self.labels = self.captions = self.focus = None
        self.hold = 0.0
        self.hold_time = 2.8
        self.owes = False  # presentation: this match still has to reach the board
        self.quota = self.fed = 0
        self.cellmap = {}

    @property
    def cv(self):
        return self.app.cv

    def layout(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.cv.delete(self.tag)
        self.cv.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=LINE, tags=self.tag)
        s = self.app.scale
        self.head_h = (116 if self.labels else 96) * s
        grid_h = h - self.head_h - 14 * s
        # Pick how many rounds go on a row so the squares come out as large as
        # the stage allows (a tall single viewer fits fewer, bigger squares).
        best = None
        for per in (20, 25, 30, 40, 50):
            bands = -(-harness.GAME.rounds[1] // per)
            cell = min((w - 44 * s) / per, (grid_h - 120 * s) / (bands * 2.7))
            if best is None or cell > best[0]:
                best = (cell, per)
        self.cell, self.PER_BAND = max(4.0, best[0]), best[1]
        if self.match:
            done = self.drawn
            self._draw_static()
            self.cellmap = {}
            for t in range(done):
                self._draw_cell(t)
            if self.hold or self.pinned and done >= self.match[4]:
                self._ring_focus()
                self._draw_verdict()
            self._update_text()
        else:
            self._draw_waiting()

    def playing(self):
        return {self.match[0], self.match[1]} if self.match else set()

    def busy(self):
        return self.match is not None

    def clear(self):
        self.match, self.pinned, self.hold = None, False, 0.0
        self._draw_waiting()

    def start(self, match, pinned=False, title="", labels=None, captions=None, focus=None):
        """`labels` puts a line under each bot's name (what it plays),
        `captions` replaces the generated ones, and `focus` is a (first, last)
        round range to ring once the replay finishes."""
        self.match, self.pinned = match, pinned  # (i, j, pa, pb, n, (ma, mb))
        self.title = title
        self.labels, self.captions, self.focus = labels, captions, focus
        self.owes, self.quota, self.fed = False, 0, 0
        self.pos, self.drawn = 0.0, 0
        self.run_a = self.run_b = 0
        self.flips = 0
        self.glows = []
        self.hold = 0.0
        self._draw_static()

    def _draw_waiting(self):
        self.cv.delete(self.tag + "dyn")
        self.cellmap = {}
        text = self.app.stage_hint()
        self.wait_item = self.cv.create_text(self.x + self.w / 2, self.y + self.h / 2, text=text, justify="center",
                            fill=FAINT, font=self.app.f_small, width=self.w * 0.8,
                            tags=(self.tag, self.tag + "dyn"))

    def _draw_static(self):
        app, cv, t = self.app, self.cv, (self.tag, self.tag + "dyn")
        cv.delete(self.tag + "dyn")
        self.cellmap = {}
        i, j = self.match[0], self.match[1]
        x, y, w, s = self.x, self.y, self.w, app.scale
        pad = 18 * s
        cv.create_rectangle(x + pad, y + 18 * s, x + pad + 6 * s, y + 58 * s, fill=app.color(i), width=0, tags=t)
        cv.create_text(x + pad + 16 * s, y + 16 * s, text=app.display_name(i), anchor="nw",
                       fill=FG, font=app.f_stage_name, tags=t)
        cv.create_rectangle(x + w - pad - 6 * s, y + 18 * s, x + w - pad, y + 58 * s, fill=app.color(j),
                            width=0, tags=t)
        cv.create_text(x + w - pad - 16 * s, y + 16 * s, text=app.display_name(j), anchor="ne",
                       fill=FG, font=app.f_stage_name, tags=t)
        if self.labels:
            cv.create_text(x + pad + 16 * s, y + 52 * s, text=self.labels[0] or "", anchor="nw",
                           fill=DIM, font=app.f_card_detail, width=w * 0.3, tags=t)
            cv.create_text(x + w - pad - 16 * s, y + 52 * s, text=self.labels[1] or "", anchor="ne",
                           fill=DIM, font=app.f_card_detail, width=w * 0.3, tags=t)
        sy = y + (72 if self.labels else 50) * s
        self.score_a = cv.create_text(x + pad + 16 * s, sy, text="0.00", anchor="nw",
                                      fill=DIM, font=app.f_stage_score, tags=t)
        self.score_b = cv.create_text(x + w - pad - 16 * s, sy, text="0.00", anchor="ne",
                                      fill=DIM, font=app.f_stage_score, tags=t)
        self.round_txt = cv.create_text(x + w / 2, y + 22 * s, text="", fill=DIM,
                                        font=app.f_small, tags=t)
        self.flip_txt = cv.create_text(x + w / 2, y + 56 * s, text="", fill=GLOW, width=w * 0.5,
                                       justify="center", font=app.f_small, tags=t)

    def _cell_xy(self, t):
        band, k = divmod(t, self.PER_BAND)
        c = self.cell
        gx = self.x + (self.w - c * self.PER_BAND) / 2
        gy = self.y + self.head_h + band * 2.7 * c
        return gx + k * c, gy, gy + c + 1

    def _draw_cell(self, t, glow=False):
        ma, mb = self.match[5]
        x, ya, yb = self._cell_xy(t)
        c = self.cell
        tags = (self.tag, self.tag + "dyn")
        for ch, y in ((ma[t], ya), (mb[t], yb)):
            color = FORFEIT_COL if ch == "#" else harness.GAME.colour[actual(ch)]
            r = self.cv.create_rectangle(x + 1, y, x + c - 1, y + c - 1, fill=color, width=0, tags=tags)
            self.cellmap[r] = t
            if ch.islower():
                rr = c * 0.22
                dot = self.cv.create_oval(x + c / 2 - rr, y + c / 2 - rr, x + c / 2 + rr, y + c / 2 + rr,
                                          fill="#111", width=0, tags=tags)
                self.cellmap[dot] = t
                if glow:
                    self.cv.itemconfig(dot, fill=GLOW, outline=GLOW, width=max(2, c * 0.18))
                    self.glows.append((dot, 0.7))

    def _update_text(self):
        cv, n = self.cv, self.match[4]
        k = max(1, self.drawn)
        a, b = self.run_a / k, self.run_b / k
        cv.itemconfig(self.score_a, text=f"{a:.2f}", fill=FG if a >= b else DIM)
        cv.itemconfig(self.score_b, text=f"{b:.2f}", fill=FG if b >= a else DIM)
        cv.itemconfig(self.round_txt, text=(f"{self.title}  ·  " if self.title else "")
                      + f"round {self.drawn} / {n}")
        cv.itemconfig(self.flip_txt, text=f"⚡ {self.flips} flipped by noise" if self.flips else "")

    def reveal(self):
        """Show the whole match at once instead of replaying it."""
        if self.match:
            self.pos = self.match[4]
            self.step(0.0, 0.0)

    def step(self, dt, rps):
        if not self.match:
            return
        cv, n = self.cv, self.match[4]
        if self.hold:
            self.hold -= dt
            if self.hold <= 0:
                self.clear()
            return
        if self.drawn >= n:
            return  # pinned and finished: stays up for inspection
        self.pos = min(n, self.pos + rps * dt)
        ma, mb = self.match[5]
        while self.drawn < int(self.pos):
            t = self.drawn
            self._draw_cell(t, glow=True)
            sa, sb = harness.GAME.payoff[actual(ma[t]), actual(mb[t])]
            self.run_a += 0 if ma[t] == "#" else sa
            self.run_b += 0 if mb[t] == "#" else sb
            self.flips += ma[t].islower() + mb[t].islower()
            self.drawn += 1
        still = []
        for dot, left in self.glows:
            left -= dt
            if left > 0:
                still.append((dot, left))
            else:
                cv.itemconfig(dot, fill="#111", outline="", width=0)
        self.glows = still
        self._update_text()
        if self.drawn >= n:
            for dot, _ in self.glows:
                cv.itemconfig(dot, fill="#111", outline="", width=0)
            self.glows = []
            self._ring_focus()
            self._draw_verdict()
            if self.pinned:
                cv.itemconfig(self.flip_txt, text="hover over a round for details")
            else:
                self.hold = self.hold_time

    def _ring_focus(self):
        """Ring the rounds worth looking at, once the replay has finished."""
        if not self.focus:
            return
        first, last = max(1, self.focus[0]), min(self.match[4], self.focus[1])
        for t in range(first - 1, last):
            x, ya, yb = self._cell_xy(t)
            c = self.cell
            for y in (ya, yb):
                self.cv.create_rectangle(x + 1, y, x + c - 1, y + c - 1, outline=GLOW, width=2,
                                         tags=(self.tag, self.tag + "dyn"))

    def describe(self, t):
        ma, mb = self.match[5]
        parts = []
        for i, ch in ((self.match[0], ma[t]), (self.match[1], mb[t])):
            name = self.app.display_name(i)
            if ch == "#":
                parts.append(f"{name} forfeited")
            elif ch.islower():
                meant = intent_of(ch.upper())
                parts.append(f"{name} tried to {word(meant)}; noise made it {past(ch.upper())}"
                             if meant else f"noise made {name} {past(ch.upper())}")
            else:
                parts.append(f"{name} {past(ch)}")
        return f"Round {t + 1}: " + "  ·  ".join(parts)

    def _draw_verdict(self):
        i, j, pa, pb, n = self.match[:5]
        a, b = pa / n, pb / n
        na, nb = self.app.display_name(i), self.app.display_name(j)
        # Captions for replays someone chose (highlights, Watch); auto-played
        # matches in presentation just get the smaller headline.
        detailed = self.pinned
        captions = self.captions or (match_story(*self.match[5], na, nb)[0] if detailed else [])
        s = self.app.scale
        t = (self.tag, self.tag + "dyn")
        cx = self.x + self.w / 2
        head = self.cv.create_text(cx, 0, text=headline(a, b, na, nb), fill=FG, anchor="n",
                                   font=self.app.f_verdict if detailed else self.app.f_card_label,
                                   width=self.w - 60 * s, justify="center", tags=t)
        cap = self.cv.create_text(cx, 0, text="\n".join(captions), fill=GLOW, anchor="n", justify="center",
                                  font=self.app.f_card_detail, width=self.w - 60 * s, tags=t)
        hh = self.cv.bbox(head)[3] - self.cv.bbox(head)[1]
        ch = (self.cv.bbox(cap)[3] - self.cv.bbox(cap)[1] + 6 * s) if captions else 0
        # Below the grid if there is room, otherwise pinned to the stage's bottom edge.
        last_y = self._cell_xy(n - 1)[2] + self.cell
        top = min(last_y + 24 * s, self.y + self.h - hh - ch - 30 * s)
        self.cv.coords(head, cx, top)
        self.cv.coords(cap, cx, top + hh + 6 * s)
        if not captions:
            self.cv.delete(cap)
        boxes = [self.cv.bbox(head)] + ([self.cv.bbox(cap)] if captions else [])
        x0, x1 = min(b[0] for b in boxes), max(b[2] for b in boxes)
        box = self.cv.create_rectangle(x0 - 20 * s, top - 10 * s, x1 + 20 * s, top + hh + ch + 10 * s,
                                       fill=PANEL2, outline=LINE, width=2, tags=t)
        self.cv.tag_lower(box, head)


# --------------------------------------------------------------------------
# Flat buttons (tk.Button ignores colours on macOS)
# --------------------------------------------------------------------------

class FlatButton(tk.Label):
    def __init__(self, parent, text, command, primary=False):
        self.bg = ACCENT if primary else PANEL2
        self.hover_bg = "#6f9cf2" if primary else LINE
        super().__init__(parent, text=text, bg=self.bg, fg=FG, padx=14, pady=6, cursor="hand2")
        self.command, self.enabled = command, True
        self.bind("<Enter>", lambda e: self.enabled and self.config(bg=self.hover_bg))
        self.bind("<Leave>", lambda e: self.config(bg=self.bg if self.enabled else PANEL))
        self.bind("<Button-1>", lambda e: self.enabled and self.command())

    def set_enabled(self, on):
        self.enabled = on
        self.config(bg=self.bg if on else PANEL, fg=FG if on else FAINT)


# --------------------------------------------------------------------------
# The app shell shared by the toolkit and the event app
# --------------------------------------------------------------------------

class BaseApp:
    """Board, stages, check cards, runs. Subclasses add their toolbar and,
    for the event app, the presentation."""

    TITLE = "ANALYTICA - INTEGRATE AND CONQUER"

    def __init__(self, root):
        self.root = root
        self.team_specs = []     # your bots, or the teams from a manifest
        self.house_specs = []    # house (reference) bots
        self.check_status = {}   # bot name -> "ok" | "warn" | "fail"
        self.card = None         # report card over the stages (check results)
        self.ui_q = queue.Queue()
        self.engine = None
        self.selected = []
        self.rows = {}
        self.buttons = {}
        self.working = False
        self.presenting = False
        self.hide_house = False
        self.menu_target = None
        self.rps = 30.0
        self.run_info = {}
        self.closing = False
        self.reps_var = tk.StringVar(value="20")
        self._build_vars()
        self._compose_field()
        self._reset_standings()

        root.title(self.TITLE)
        root.configure(background=BG)
        root.geometry("1440x880")
        root.minsize(1000, 660)
        self.cv = tk.Canvas(root, background=BG, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.family = pick_family(root)
        self.stages = [Stage(self, "stage0"), Stage(self, "stage1")]
        self.toolbar = tk.Frame(self.cv, bg=BG)
        self._build_toolbar(self.toolbar)
        self.logbox = tk.Text(self.cv, bg=PANEL, fg=FG, relief="flat", wrap="word",
                              highlightthickness=1, highlightbackground=LINE, padx=14, pady=10,
                              insertbackground=FG, cursor="arrow")
        self.logbox.bind("<Key>", lambda e: "break" if e.keysym not in ("c", "C") else None)
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Keep this version", command=lambda: self.keep_version(self.menu_target))
        self.menu.add_command(label="Check protocol", command=lambda: self.check(self.menu_target))
        self.menu.add_command(label="Edit run command…", command=lambda: self.edit_cmd(self.menu_target))
        self.menu.add_command(label="Remove", command=lambda: self.remove_bot(self.menu_target))
        self._refresh_buttons()
        self._layout_pending = None
        self._laid_out = False
        self.cv.bind("<Configure>", self._on_resize)
        self.cv.bind("<Motion>", self._on_motion)
        root.bind("<F11>", lambda e: root.attributes("-fullscreen", not root.attributes("-fullscreen")))
        root.bind("<Escape>", lambda e: self._escape())
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.last_tick = time.perf_counter()
        self._tick_id = root.after(30, self.tick)

    # ---------------- hooks (overridden by the apps) ----------------

    def _build_vars(self):
        pass

    def _compose_field(self):
        self.specs = self.team_specs + baseline_specs()

    def _build_toolbar(self, tb):
        raise NotImplementedError

    def _reset_extra(self):
        pass

    def settings(self):
        """Run options. The toolkit uses these defaults; the event app reads its panel."""
        return {"seed": None, "workers": default_workers(), "self_play": False, "ref_weight": 1.0,
                "out": "", "show_minutes": 0.0, "stage_speed": 30.0}

    def _on_run_start(self, reps, self_play, records, minutes):
        pass

    def _priority(self, specs):
        return None

    def _escape(self):
        self.root.attributes("-fullscreen", False)

    def note(self, text, color, toast=False):
        """Something worth telling the room; the event app also pops it up."""
        self._append_log(text, color)

    def _arrive(self, m):
        i, j, pa, pb, n, moves, rep = m
        self.matches.append({"i": i, "j": j, "r": rep, "n": n, "pa": pa, "pb": pb,
                             "a": moves[0], "b": moves[1]})
        self.pending.append(m)

    def _advance(self, dt):
        """Apply results and feed the stages. The toolkit shows everything at
        once and replays random recent matches."""
        if self.state == "running":
            while self.pending:
                self.apply(self.pending.popleft())
            if self.final_stats and self.applied >= self.played:
                self.finish()
        if self.state in ("running", "final"):
            busy = set()
            for st in self.stages:
                busy |= st.playing()
            for st in self.stages:
                if not st.busy():
                    m = self.pick_match(busy)
                    if m:
                        st.start(m)
                        busy |= st.playing()
        for st in self.stages:
            st.step(dt, self.rps)

    def _layout_content(self, W, H, top, m):
        """Fill the area under the toolbar. The default is the board on the
        left, replay stages and the log on the right."""
        bw = W * 0.5
        self.board = (m, top, bw - m / 2, H - m)
        rx = bw + m / 2
        rw = W - m - rx
        avail = H - top - m
        log_h = avail * 0.28
        st_h = (avail - log_h - m) / 2
        self.card_box = (rx, top, rw, 2 * st_h + m / 2)
        self.stages[0].layout(rx, top, rw, st_h)
        self.stages[1].layout(rx, top + st_h + m / 2, rw, st_h)
        self.log_box = (rx, top + 2 * (st_h + m / 2), rw, log_h)
        self.log_win = self.cv.create_window(rx, self.log_box[1], window=self.logbox, anchor="nw",
                                             width=rw, height=log_h)
        self._layout_board()

    def _draw_overlays(self):
        self._draw_card()

    def _ranks_changed(self, ranks, now):
        pass

    def _finished(self, ranks, stats):
        self._append_log(f"Finished. Standings are final ({self.total:,} matches). "
                         "Click any row for its scores against each opponent.", UP)
        for i, s in enumerate(self.specs):
            if not s.get("added"):
                continue
            st = stats[i].summary()
            self._append_log(f"{s['name']}: #{ranks[i]} of {len(ranks)}, {self.score(i):.3f} pts/round, "
                             f"latency mean {st['mean_ms']:.2f} ms, max {st['max_ms']:.1f} ms", FG)
            for k, msg in (("timeouts", "moves over the 50 ms limit (forfeited)"),
                           ("crashes", "crashes"), ("forfeits", "rounds forfeited while crashed"),
                           ("junk_lines", "non-move lines on stdout (print debug to stderr)")):
                if st[k]:
                    self._append_log(f"  {st[k]} {msg}", DOWN if k != "junk_lines" else WARN)
        self._append_log(f"Bots' stderr (debug prints) is in {self.run_info['log_dir']}", DIM)

    def _status_text(self):
        s = self.state
        if s == "ready" or (s == "final" and not self.applied):
            return f"{self.n} players on the board"
        if s == "final":
            return f"FINAL · {self.applied:,} matches"
        return f"{'PAUSED · ' if s == 'paused' else ''}match {self.applied:,} / {self.total:,}"

    def _progress(self):
        """(played, shown) fractions for the two layers of the progress bar."""
        t = max(1, self.total)
        return self.played / t, self.applied / t

    def show_badges(self):
        """Whether to mark bots with their protocol-check result."""
        return not self.presenting

    def show_scores(self):
        """Whether the board has scores to show yet."""
        return True

    def stage_hint(self):
        return "Click two rows on the board, then Watch.\nDuring a run, fresh matches replay here."

    def _refresh_buttons(self):
        idle = not self.working and self.state in ("ready", "final")
        has_team = any(s["kind"] == "team" for s in self.specs)
        b = self.buttons
        if not b:
            return
        b["add"].set_enabled(idle)
        b["check"].set_enabled(idle and has_team)
        b["run"].set_enabled(not self.working or self.state in ("running", "paused"))
        b["run"].config(text="Stop" if self.state in ("running", "paused") else "Run tournament")
        b["watch"].set_enabled(idle and len(self.selected) == 2)
        if len(self.selected) == 2:
            self.hint.config(text=f"{self.display_name(self.selected[0])} vs "
                                  f"{self.display_name(self.selected[1])}: press Watch")
        elif len(self.selected) == 1:
            self.hint.config(text="click a second row to pick an opponent")
        else:
            self.hint.config(text="click two rows to watch them play")

    @staticmethod
    def num(var, cast, default):
        try:
            return cast(var.get())
        except (ValueError, tk.TclError):
            return default

    def _field_changed(self):
        if self.working:
            return
        self.selected = []
        for st in self.stages:
            st.match = None
        self._compose_field()
        self._reset_standings()
        if self.rows or hasattr(self, "cv"):
            self.layout()
            self._refresh_buttons()

    def _reset_standings(self):
        n = self.n = len(self.specs)
        self.colors = bot_colors(n)
        refs = [i for i, s in enumerate(self.specs) if s["kind"] == "ref"]
        self.house_label = {i: f"House bot {chr(65 + k)}" for k, i in enumerate(refs)}
        self.rank_all = not refs
        self.state = "ready"  # ready, running, paused, final
        self.total = 0
        self.pending = collections.deque()
        self.recent = collections.deque(maxlen=400)
        self.played = self.applied = 0
        self.budget = 0.0
        self.rate = float("inf")
        self.final_stats = None
        self.pts = [[0.0, 0.0] for _ in range(n)]   # [vs teams, vs everyone else]
        self.rnds = [[0, 0] for _ in range(n)]
        self.pair_pts = [[0] * n for _ in range(n)]
        self.pair_rnds = [[0] * n for _ in range(n)]
        self.coop = [0] * n
        self.moves = [0] * n
        self.shown = [0] * n
        self.forfeit_reported, self.exploit_reported = set(), set()
        self.rank_prev, self.arrows = {}, {}
        self.champion = None
        self.champion_index = None
        self.run_presenting = False
        self.pair_kinds = {}                    # (i, j) -> [(kind, a, b)] already told
        self.applied_at_start = 0
        self.matches = []                       # every match played, with its moves
        self.tour = None                        # harness.Tournament once a run finishes
        self._reset_extra()

    def display_name(self, i):
        if self.specs[i]["kind"] == "ref" and self.hide_house:
            return self.house_label[i]
        return self.specs[i]["name"]

    def color(self, i):
        return self.colors[i] if self.specs[i]["kind"] == "team" else "#7b8496"

    def score(self, i):
        w = self.run_info.get("ref_weight", 1.0)
        p = self.pts[i][0] + w * self.pts[i][1]
        r = self.rnds[i][0] + w * self.rnds[i][1]
        return p / r if r else 0.0

    def order(self):
        if not self.applied:
            return sorted(range(self.n), key=lambda i: (self.specs[i]["kind"] != "team", i))
        return sorted(range(self.n), key=lambda i: -self.score(i))

    def ranks(self, order):
        ranks, k = {}, 0
        for i in order:
            if self.rank_all or self.specs[i]["kind"] == "team":
                k += 1
                ranks[i] = k
        return ranks

    def _label(self, parent, text, fg=DIM):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=fg)

    def _spin(self, parent, var, lo, hi, inc=1, width=5):
        value = var.get()
        sb = tk.Spinbox(parent, from_=lo, to=hi, increment=inc, width=width, textvariable=var,
                        bg=PANEL2, fg=FG, buttonbackground=PANEL2, insertbackground=FG,
                        relief="flat", highlightthickness=0)
        var.set(value)  # Tk resets the variable to from_ on creation
        return sb

    def _entry(self, parent, var, width):
        return tk.Entry(parent, textvariable=var, width=width, bg=PANEL2, fg=FG, insertbackground=FG,
                        relief="flat", highlightthickness=0)

    def _checkbox(self, parent, text, var):
        return tk.Checkbutton(parent, text=text, variable=var, bg=parent["bg"], fg=FG,
                              selectcolor=PANEL2, activebackground=parent["bg"], activeforeground=FG,
                              highlightthickness=0, bd=0)

    def _all_widgets(self, w):
        yield w
        for c in w.winfo_children():
            yield from self._all_widgets(c)

    def _on_resize(self, _):
        if self.closing:
            return
        if self._layout_pending:
            self.root.after_cancel(self._layout_pending)
        self._layout_pending = self.root.after(80, self.layout)

    def layout(self):
        self._laid_out = True
        if self._layout_pending:  # called directly: drop the queued re-layout
            self.root.after_cancel(self._layout_pending)
            self._layout_pending = None
        W, H = self.cv.winfo_width(), self.cv.winfo_height()
        if W < 50:
            return
        s = self.scale = max(0.55, min(W / 1920, H / 1080))
        fam = self.family
        mk = lambda size, weight="normal": tkfont.Font(family=fam, size=-max(10, int(size * s)), weight=weight)
        self.f_title = mk(40, "bold")
        self.f_status = mk(22)
        self.f_small = mk(20)
        self.f_head = mk(17, "bold")
        self.f_stage_name = mk(28, "bold")
        self.f_stage_score = mk(34, "bold")
        self.f_verdict = mk(28, "bold")
        self.f_champ = mk(48, "bold")
        self.f_card_label = mk(22, "bold")
        self.f_card_detail = mk(18)
        self.f_mono = tkfont.Font(family="Consolas" if harness.WINDOWS else "Menlo",
                                  size=-max(9, int(16 * s)))
        f_ui = mk(19)
        self.logbox.config(font=mk(24 if self.presenting else 19), tabs=(int(300 * s), int(400 * s)))
        for color in (FG, DIM, FAINT, DOWN, UP, WARN, MEDALS[1]):
            self.logbox.tag_configure(color, foreground=color)
        for w in self._all_widgets(self.toolbar):
            if isinstance(w, (tk.Label, tk.Spinbox, tk.Entry, tk.Checkbutton)):
                w.config(font=f_ui)

        cv = self.cv
        cv.delete("all")
        self.rows = {}
        m = 28 * s
        self.m = m
        cv.create_text(m, 20 * s, text=harness.GAME.title, anchor="nw", fill=FG, font=self.f_title)
        self.status = cv.create_text(W - m, 30 * s, text="", anchor="ne", fill=DIM, font=self.f_status)
        self.bar_box = (m, 82 * s, W - m, 92 * s)
        cv.create_rectangle(*self.bar_box, fill=PANEL2, width=0)
        self.bar_played = cv.create_rectangle(m, 82 * s, m, 92 * s, fill=LINE, width=0)
        self.bar_shown = cv.create_rectangle(m, 82 * s, m, 92 * s, fill=ACCENT, width=0)
        top = 108 * s
        if not self.presenting:
            cv.create_window(m, top, window=self.toolbar, anchor="nw", width=W - 2 * m)
            self.root.update_idletasks()
            top += self.toolbar.winfo_reqheight() + 16 * s

        self._layout_content(W, H, top, m)
        self._draw_overlays()
        self._update_header()

    def on_board(self, i):
        return True

    def _layout_board(self):
        cv, s = self.cv, self.scale
        x, y, x1, y1 = self.board
        w = x1 - x
        cols = self.cols = {
            "rank": x + 44 * s, "arrow": x + 70 * s, "name": x + 90 * s,
            "bar0": x + w * 0.48, "bar1": x + w * 0.80, "score": x + w * 0.82, "coop": x1 - 12 * s}
        scored = self.show_scores()
        stat_name = harness.GAME.stat[0] if harness.GAME.stat else ""
        for text, cx, anchor, only_scored in (("#", cols["rank"], "ne", True),
                                              ("BOT", cols["name"], "nw", False),
                                              ("POINTS / ROUND", cols["bar0"], "nw", True),
                                              (stat_name, cols["coop"], "ne", True)):
            if only_scored and not scored:
                continue
            cv.create_text(cx, y + 4 * s, text=text, anchor=anchor, fill=FAINT, font=self.f_head)
        top = y + 34 * s
        visible = [i for i in self.order() if self.on_board(i)]
        self.row_h = rh = min((84 if self.presenting else 52) * s, (y1 - top) / max(1, len(visible)))
        self.row_top = top
        # Fonts follow the row height, but only up to what the columns have room for.
        self.f_row = tkfont.Font(family=self.family, size=-max(10, int(min(rh * 0.5, 30 * s))), weight="bold")
        self.f_row_small = tkfont.Font(family=self.family, size=-max(9, int(min(rh * 0.42, 24 * s))))
        self.f_badge = tkfont.Font(family=self.family, size=-max(8, int(min(rh * 0.34, 18 * s))), weight="bold")
        for pos, i in enumerate(visible):
            ry = top + pos * rh
            tg = f"row{i}"
            team = self.specs[i]["kind"] == "team"
            r = {"y": ry, "cache": {}}
            r["bg"] = cv.create_rectangle(x, ry, x1, ry + rh - 3 * s, fill=PANEL, width=0, tags=tg)
            r["rank"] = cv.create_text(cols["rank"], ry + rh / 2, anchor="e", fill=FG, font=self.f_row, tags=tg)
            r["arrow"] = cv.create_text(cols["arrow"], ry + rh / 2, fill=UP, font=self.f_row_small, tags=tg)
            r["name"] = cv.create_text(cols["name"], ry + rh / 2, anchor="w", fill=FG,
                                       font=self.f_row if team else self.f_row_small, tags=tg)
            r["badge"] = cv.create_text(cols["coop"], ry + rh / 2, anchor="e", fill=FAINT,
                                        font=self.f_badge, tags=tg)
            bh = rh * 0.34
            r["barbg"] = cv.create_rectangle(cols["bar0"], ry + rh / 2 - bh / 2, cols["bar1"],
                                             ry + rh / 2 + bh / 2, fill=PANEL2, width=0, tags=tg)
            r["bar"] = cv.create_rectangle(cols["bar0"], ry + rh / 2 - bh / 2, cols["bar0"],
                                           ry + rh / 2 + bh / 2, fill=self.color(i), width=0, tags=tg)
            r["score"] = cv.create_text(cols["score"], ry + rh / 2, anchor="w", fill=FG, font=self.f_row, tags=tg)
            r["coop"] = cv.create_text(cols["coop"], ry + rh / 2, anchor="e", fill=DIM,
                                       font=self.f_row_small, tags=tg)
            cv.tag_bind(tg, "<Button-1>", lambda e, i=i: self.click_row(i))
            for seq in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
                cv.tag_bind(tg, seq, lambda e, i=i: self.row_menu(e, i))
            cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
            cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))
            self.rows[i] = r
        self._refresh_board(0, snap=True)

    STATUS_STYLE = {"ok": (UP, "✓"), "warn": (WARN, "!"), "fail": (DOWN, "✗"), "wait": (FAINT, "·")}

    def close_card(self):
        if self.card and self.card.get("state") == "done":
            self.card = None
            self.cv.delete("card")

    def _pill(self, x, y, text, color, anchor="ne"):
        cv, s = self.cv, self.scale
        t = cv.create_text(x - 16 * s, y + 8 * s, text=text, anchor=anchor, fill=BG,
                           font=self.f_card_label, tags="card")
        x0, y0, x1, y1 = cv.bbox(t)
        box = cv.create_rectangle(x0 - 14 * s, y0 - 6 * s, x1 + 14 * s, y1 + 6 * s, fill=color,
                                  width=0, tags="card")
        cv.tag_raise(t, box)

    def _status_dot(self, x, y, status, r):
        color, sym = self.STATUS_STYLE[status]
        self.cv.create_oval(x - r, y - r, x + r, y + r, fill=color, width=0, tags="card")
        self.cv.create_text(x, y, text=sym, fill=BG, font=self.f_card_label, tags="card")

    def _draw_card(self):
        cv = self.cv
        cv.delete("card")
        if not self.card or self.presenting:
            return
        x, y, w, h = self.card_box
        s = self.scale
        cv.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=LINE, width=2, tags="card")
        if self.card["kind"] == "check":
            self._draw_check_card(x, y, w, h, s)
        else:
            self._draw_summary_card(x, y, w, h, s)
        if self.card.get("state") == "done":
            cv.create_text(x + w - 18 * s, y + h - 12 * s, text="click the card to close", anchor="se",
                           fill=FAINT, font=self.f_card_detail, tags="card")
        cv.tag_bind("card", "<Button-1>", lambda e: self.close_card())

    def _draw_check_card(self, x, y, w, h, s):
        cv, c = self.cv, self.card
        pad = 28 * s
        cv.create_text(x + pad, y + 20 * s, text="PROTOCOL CHECK", anchor="nw", fill=FAINT,
                       font=self.f_head, tags="card")
        cv.create_text(x + pad, y + 44 * s, text=c["name"], anchor="nw", fill=FG,
                       font=self.f_stage_name, tags="card")
        rep = c.get("report")
        if c["state"] == "building":
            self._pill(x + w, y + 24 * s, "BUILDING…", ACCENT)
        elif c["state"] == "running":
            self._pill(x + w, y + 24 * s, "CHECKING…", ACCENT)
        elif c.get("build_error") is not None:
            self._pill(x + w, y + 24 * s, "BUILD FAILED", DOWN)
        else:
            worst = rep.worst
            self._pill(x + w, y + 24 * s, {"ok": "PASS", "warn": "PASS WITH WARNINGS", "fail": "FAIL"}[worst],
                       {"ok": UP, "warn": WARN, "fail": DOWN}[worst])

        rows = []
        if c.get("build_error") is not None:
            tail = "\n".join(c["build_error"].strip().splitlines()[-10:])
            rows.append(("fail", "Compiles", tail or "the build command failed"))
        elif rep is not None:
            rows = [(k.status, k.label, k.detail) for k in rep.checks if k.label != "Speed"]
        elif c["state"] == "running":
            rows = [("wait", "Playing it against the sparring partners…", "")]

        cy = y + 104 * s
        r = 13 * s
        text_x = x + pad + 2 * r + 14 * s
        limit_y = y + h - (150 * s if rep and rep.stats.latencies else 40 * s)
        for status, label, detail in rows:
            if cy > limit_y:
                break
            self._status_dot(x + pad + r, cy + r, status, r)
            t = cv.create_text(text_x, cy + r, text=label, anchor="w", fill=FG,
                               font=self.f_card_label, tags="card")
            cy = cv.bbox(t)[3] + 2 * s
            if detail:
                mono = "\n" in detail
                d = cv.create_text(text_x, cy, text=detail, anchor="nw", width=w - (text_x - x) - pad,
                                   fill=DIM, font=self.f_mono if mono else self.f_card_detail, tags="card")
                cy = cv.bbox(d)[3]
            cy += 12 * s
        if rep is not None and rep.stderr_tail and cy < limit_y:
            t = cv.create_text(text_x, cy, text="Last lines your bot wrote to stderr:", anchor="nw",
                               fill=WARN, font=self.f_card_detail, tags="card")
            cy = cv.bbox(t)[3] + 4 * s
            cv.create_text(text_x, cy, text="\n".join(rep.stderr_tail[-8:]), anchor="nw", fill=DIM,
                           width=w - (text_x - x) - pad, font=self.f_mono, tags="card")
        if rep is not None and rep.stats.latencies:
            speed = next((k for k in rep.checks if k.label == "Speed"), None)
            self._draw_speed_gauge(x + pad, y + h - 128 * s, w - 2 * pad, rep.stats.summary(), speed)

    def _draw_speed_gauge(self, x, y, w, st, speed):
        """Time per move on a log scale from 0.01 ms to 100 ms."""
        cv, s = self.cv, self.scale
        import math
        lo, hi = math.log10(0.01), math.log10(100)
        px = lambda ms: x + w * (min(max(math.log10(max(ms, 0.01)), lo), hi) - lo) / (hi - lo)
        status = speed.status if speed else "ok"
        self._status_dot(x + 13 * s, y + 13 * s, status, 13 * s)
        cv.create_text(x + 40 * s, y + 13 * s, text="Time per move", anchor="w", fill=FG,
                       font=self.f_card_label, tags="card")
        by = y + 58 * s
        bh = 14 * s
        for a, b, color in ((0.01, 1, "#1f5c3a"), (1, harness.MOVE_TIMEOUT * 1000, "#6b5321"),
                            (harness.MOVE_TIMEOUT * 1000, 100, "#6b2724")):
            cv.create_rectangle(px(a), by, px(b), by + bh, fill=color, width=0, tags="card")
        limit = px(harness.MOVE_TIMEOUT * 1000)
        cv.create_line(limit, by - 6 * s, limit, by + bh + 6 * s, fill=DOWN, width=2, tags="card")
        for ms, label in ((0.01, "0.01"), (0.1, "0.1"), (1, "1"), (10, "10"), (50, "50 ms limit")):
            cv.create_text(px(ms), by + bh + 8 * s, text=label, anchor="n",
                           fill=DOWN if ms == 50 else FAINT, font=self.f_card_detail, tags="card")
        # Values go in a legend: on a fast bot the three markers sit on top of each other.
        lx = x + 250 * s
        for key, label, color in (("mean_ms", "mean", UP), ("p99_ms", "p99", WARN), ("max_ms", "max", FG)):
            mx = px(st[key])
            cv.create_polygon(mx - 7 * s, by - 14 * s, mx + 7 * s, by - 14 * s, mx, by - 2 * s,
                              fill=color, outline=BG, width=1, tags="card")
            cv.create_polygon(lx, y + 7 * s, lx + 14 * s, y + 7 * s, lx + 7 * s, y + 19 * s,
                              fill=color, width=0, tags="card")
            t = cv.create_text(lx + 20 * s, y + 13 * s, text=f"{label} {st[key]:.2f} ms", anchor="w",
                               fill=color, font=self.f_card_detail, tags="card")
            lx = cv.bbox(t)[2] + 22 * s

    def _draw_summary_card(self, x, y, w, h, s):
        cv, c = self.cv, self.card
        pad = 28 * s
        results = c["results"]
        n_total = c["total"]
        passed = sum(1 for r in results if r["status"] != "fail")
        cv.create_text(x + pad, y + 20 * s, text="CHECK ALL TEAMS", anchor="nw", fill=FAINT,
                       font=self.f_head, tags="card")
        cv.create_text(x + pad, y + 44 * s, text=f"{passed} of {n_total} ready", anchor="nw", fill=FG,
                       font=self.f_stage_name, tags="card")
        if c["state"] != "done":
            self._pill(x + w, y + 24 * s, f"CHECKING {len(results) + 1}/{n_total}…", ACCENT)
        else:
            failed = n_total - passed
            self._pill(x + w, y + 24 * s, "ALL READY" if not failed else f"{failed} FAILING",
                       UP if not failed else DOWN)
        top = y + 104 * s
        bottom = y + h - 70 * s
        rh = min(34 * s, (bottom - top) / max(1, n_total))
        f_name = tkfont.Font(family=self.family, size=-max(9, int(rh * 0.5)), weight="bold")
        f_det = tkfont.Font(family=self.family, size=-max(8, int(rh * 0.44)))
        for k, r in enumerate(results):
            ry = top + k * rh + rh / 2
            color, sym = self.STATUS_STYLE[r["status"]]
            d = rh * 0.3
            cv.create_oval(x + pad, ry - d, x + pad + 2 * d, ry + d, fill=color, width=0, tags="card")
            cv.create_text(x + pad + 2 * d + 12 * s, ry, text=r["name"], anchor="w", fill=FG,
                           font=f_name, tags="card")
            cv.create_text(x + w * 0.42, ry, text=r["reason"], anchor="w", fill=color if r["status"] != "ok"
                           else DIM, font=f_det, tags="card", width=w * 0.42)
            if r.get("mean_ms") is not None:
                cv.create_text(x + w - pad, ry, text=f"{r['mean_ms']:.2f} ms", anchor="e", fill=DIM,
                               font=f_det, tags="card")
        if c.get("projection"):
            cv.create_text(x + pad, y + h - 40 * s, text=c["projection"], anchor="w", fill=FG,
                           font=self.f_card_detail, tags="card")

    def log(self, text, color=FG):
        """Thread-safe."""
        self.ui_q.put(("log", (text, color)))

    def _append_log(self, text, color):
        self.logbox.insert("end", text.rstrip("\n") + "\n", color)
        self.logbox.see("end")

    def add_bot(self):
        paths = filedialog.askopenfilenames(
            title="Choose your bots' main files (select several to add them all)",
            filetypes=[("Bot source", "*.py *.java *.cpp *.cc *.c *.js *.jar *.class *.exe"),
                       ("All files", "*.*")])
        if paths:
            self.add_bots(paths)

    def add_bots(self, paths):
        taken = {s["name"] for s in self.specs}
        stems = [os.path.splitext(os.path.basename(p))[0] for p in paths]
        for path, stem in zip(paths, stems):
            folder = os.path.basename(os.path.dirname(os.path.abspath(path)))
            # Several teams' files are often all called my_bot.py: name them
            # after their folders, and only number as a last resort.
            clash = stem in taken or stems.count(stem) > 1
            base = f"{folder}-{stem}" if clash else stem
            name, k = base, 2
            while name in taken:
                name, k = f"{base}_{k}", k + 1
            taken.add(name)
            spec = user_bot_spec(path, name)
            spec["added"] = True
            self.team_specs.append(spec)
            self.log(f"Added {name} ({os.path.basename(path)})"
                     + ("  ·  compiled first" if spec["build"] else ""), DIM)
        self._field_changed()
        self.log("Right-click a bot on the board to change its command. Next: Check.", DIM)

    def can_keep(self, i):
        spec = self.specs[i]
        return (spec["kind"] == "team" and not spec.get("kept_from")
                and bool(spec.get("source")) and os.path.isfile(spec["source"]))

    def keep_version(self, i):
        """Freeze a bot's code as it is now: a copy joins the field as a fixed
        opponent, "my_bot (v1)", so every run shows whether the version being
        worked on beats the last one kept. The copy goes in versions/ beside
        the bot's file under the same file name (Java needs the class and the
        file to match), and stays there for next time."""
        if not self.can_keep(i):
            return
        spec = self.specs[i]
        src = spec["source"]
        stem = os.path.splitext(os.path.basename(src))[0]
        root = os.path.join(os.path.dirname(src), "versions")
        taken = [s.get("version", 0) for s in self.team_specs if s.get("kept_from") == spec["name"]]
        k = max(taken, default=0) + 1
        while os.path.exists(os.path.join(root, f"{stem}-v{k}")):
            k += 1                      # versions kept in an earlier session
        folder = os.path.join(root, f"{stem}-v{k}")
        try:
            os.makedirs(folder)
            shutil.copy2(src, folder)
        except OSError as e:
            self.log(f"Could not keep a copy of {os.path.basename(src)}: {e}", DOWN)
            return
        kept = user_bot_spec(os.path.join(folder, os.path.basename(src)), f"{spec['name']} (v{k})")
        self.keeps = getattr(self, "keeps", 0) + 1
        kept.update(added=True, kept_from=spec["name"], version=k, kept_order=self.keeps)
        if spec["name"] in self.check_status:
            self.check_status[kept["name"]] = self.check_status[spec["name"]]  # the same code
        # Next to the bot it came from, newest first.
        at = self.team_specs.index(spec) + 1 if spec in self.team_specs else len(self.team_specs)
        self.team_specs.insert(at, kept)
        self._field_changed()
        self.log(f"Kept {spec['name']} as it is now: {kept['name']} will stay exactly like this. "
                 f"Keep editing {os.path.basename(src)}; after each run, the two are compared beside the board.", UP)

    def remove_bot(self, i):
        spec = self.specs[i]
        if spec in self.team_specs:
            self.team_specs.remove(spec)
            self._field_changed()

    def edit_cmd(self, i):
        spec = self.specs[i]
        new = simpledialog.askstring("Run command", f"Command that starts {spec['name']}:",
                                     initialvalue=harness.join_cmd(spec["cmd"]), parent=self.root)
        if new and new.strip():
            spec["cmd"] = harness.split_cmd(new.strip())
            self.check_status.pop(spec["name"], None)
            self.log(f"{spec['name']} will run: {harness.join_cmd(spec['cmd'])}", DIM)

    def click_row(self, i):
        if self.presenting:
            return
        if i in self.selected:
            self.selected.remove(i)
        else:
            self.selected = (self.selected + [i])[-2:]
        self._refresh_buttons()
        if self.applied and self.selected == [i]:
            self._log_breakdown(i)

    def row_menu(self, event, i):
        if self.presenting or self.specs[i]["kind"] != "team" or self.working:
            return
        self.menu_target = i
        self.menu.entryconfigure("Keep this version",
                                 state="normal" if self.can_keep(i) else "disabled")
        self.menu.tk_popup(event.x_root, event.y_root)

    def _log_breakdown(self, i):
        parts = []
        for j in sorted(range(self.n), key=lambda j: -self.pair_rnds[i][j]):
            if self.pair_rnds[i][j]:
                mine = self.pair_pts[i][j] / self.pair_rnds[i][j]
                theirs = self.pair_pts[j][i] / self.pair_rnds[j][i]
                parts.append(f"   vs {self.display_name(j)}\t{mine:.3f}\tthey got {theirs:.3f}")
        if parts:
            self._append_log(f"{self.display_name(i)}, points per round against each opponent:", FG)
            for p in parts:
                self._append_log(p, DIM)

    def _work(self, fn):
        self.working = True
        self._refresh_buttons()

        def target():
            try:
                fn()
            except Exception:
                self.log(traceback.format_exc(), DOWN)
            finally:
                self.ui_q.put(("idle", None))
        threading.Thread(target=target, daemon=True).start()

    def _build_logged(self, spec):
        if spec.get("build"):
            self.log(f"Building {spec['name']}: {harness.join_cmd(spec['build'])}", DIM)
        ok, out = build(spec)
        if not ok:
            self.log(f"{spec['name']}: build failed\n{out}", DOWN)
        elif out:
            self.log(out, WARN)
        return ok

    def check(self, i=None):
        if i is None:
            teams = [k for k in range(self.n) if self.specs[k]["kind"] == "team"]
            picked = [k for k in self.selected if self.specs[k]["kind"] == "team"]
            if picked:
                i = picked[-1]
            elif len(teams) == 1:
                i = teams[0]
            else:
                self.log("Click one of your bots on the board first, then Check.", WARN)
                return
        spec = dict(self.specs[i])
        name = spec["name"]

        def card(**kw):
            self.ui_q.put(("card", dict({"kind": "check", "name": name}, **kw)))

        def work():
            card(state="building" if spec.get("build") else "running")
            ok, out = build(spec)
            if not ok:
                card(state="done", build_error=out)
                self.ui_q.put(("status", (name, "fail")))
                self.log(f"{name}: build failed", DOWN)
                return
            card(state="running")
            rep = harness.smoke_test(spec["cmd"], cwd=spec["cwd"])
            card(state="done", report=rep)
            self.ui_q.put(("status", (name, rep.worst)))
            self.log(f"{name}: " + {"ok": "PASS. Now run a tournament.", "warn": "passed with warnings",
                                    "fail": "FAIL; see the report card"}[rep.worst],
                     {"ok": UP, "warn": WARN, "fail": DOWN}[rep.worst])
        self._work(work)

    def watch(self):
        i, j = self.selected
        specs = [dict(self.specs[i]), dict(self.specs[j])]

        def work():
            for spec in specs:
                if not self._build_logged(spec):
                    return
            os.makedirs(BOT_LOG_DIR, exist_ok=True)
            players = [harness.make_player(specs[0], 0, BOT_LOG_DIR),
                       harness.make_player(specs[1], 1, BOT_LOG_DIR)]
            seed = random.randrange(1 << 30)
            _, flips = harness.match_plan(seed, 0)
            record = []
            try:
                pa, pb, n = harness.play_match(players[0], players[1], flips, seed, seed + 1, record)
            finally:
                for p in players:
                    p.close()
            for p, spec in zip(players, specs):
                if p.stats.crashes or p.stats.timeouts:
                    self.log(f"{spec['name']}: {p.stats.timeouts} timeouts, {p.stats.crashes} crashes"
                             + (f" ({p.last_error})" if getattr(p, "last_error", None) else ""), DOWN)
            self.ui_q.put(("watch", (i, j, pa, pb, n, harness.encode_record(record))))
        self._work(work)

    def run_or_stop(self):
        if self.state in ("running", "paused"):
            self.engine.stop.set()
            self.log("Stopped.", WARN)
            self.state = "final"
            self.working = False
            self._refresh_buttons()
            return
        reps = max(1, self.num(self.reps_var, int, 20))
        specs = [dict(s) for s in self.specs]

        def work():
            for s in specs:
                if not self._build_logged(s):
                    return
                s.pop("build", None)
            self.ui_q.put(("start", (specs, reps)))
        self._work(work)

    def start_run(self, specs, reps):
        self._reset_standings()
        self.card = None
        for st in self.stages:
            if not st.pinned:
                st.match = None
        n = self.n
        opts = self.settings()
        self_play = opts["self_play"]
        pairings = n * (n + 1) // 2 if self_play else n * (n - 1) // 2
        self.total = pairings * reps
        minutes = opts["show_minutes"] if self.presenting else 0
        self.run_presenting = self.presenting
        self.rps = opts["stage_speed"]
        out = opts["out"]
        log_dir = os.path.join(os.path.dirname(out), "logs") if out else BOT_LOG_DIR
        os.makedirs(log_dir, exist_ok=True)
        seed = opts["seed"]

        # Carry on with the tournament in the file when the app says to (see
        # settings()["resume"]); otherwise the file is a new one. Nobody is
        # asked: an existing file is moved aside, never overwritten.
        records, tfile = [], None
        if out:
            old = harness.TournamentFile.load(out) if opts.get("resume") else None
            if old and harness.TournamentFile.compatible(old.header, specs, reps, self_play, seed) \
                    and len(old) < self.total:
                seed, records = old.seed, old.matches
                tfile = harness.TournamentFile(out, old.header, resume=True)
            else:
                backup = harness.TournamentFile.set_aside(out)
                if backup:
                    self._append_log(f"Previous file kept as {os.path.basename(backup)}", DIM)
        if seed is None:
            seed = random.randrange(1 << 30)
        if out and tfile is None:
            tfile = harness.TournamentFile(out, harness.TournamentFile.header(specs, reps, seed, self_play))

        self.run_info = {"reps": reps, "seed": seed, "workers": opts["workers"], "self_play": self_play,
                         "ref_weight": opts["ref_weight"], "log_dir": log_dir, "out": out,
                         "header": harness.TournamentFile.header(specs, reps, seed, self_play)}
        skip = self._restore(records)
        self.applied_at_start = self.applied  # restored matches don't count as arrivals
        self._on_run_start(reps, self_play, records, minutes)
        priority = self._priority(specs)
        self.engine = Engine(specs, reps, seed, self.run_info["workers"], self_play, log_dir, self.ui_q,
                             skip, tfile, priority)
        self.engine.start()
        self.state = "running"
        self.working = True
        self.layout()
        if records:
            self._append_log(f"Resumed: {len(records):,} of {self.total:,} matches restored "
                             f"(seed {seed}).", UP)
        else:
            self._append_log(f"The tournament begins: {n} players, {self.total:,} matches, seed {seed}."
                             + ("  Saving as it goes." if out else ""), FG)
        self._refresh_buttons()

    def _restore(self, records):
        """Fold saved matches into the standings. Returns the (i, j, rep) set."""
        done = set()
        self.matches = list(records)
        for r in records:
            i, j, pa, pb, n = r["i"], r["j"], r["pa"], r["pb"], r["n"]
            for me, other, p, c in ((i, j, pa, r.get("ca")), (j, i, pb, r.get("cb"))):
                k = 0 if self.specs[other]["kind"] == "team" else 1
                self.pts[me][k] += p
                self.rnds[me][k] += n
                if c is not None:
                    self.coop[me] += c
                    self.moves[me] += n
            self.pair_pts[i][j] += pa
            self.pair_pts[j][i] += pb
            self.pair_rnds[i][j] += n
            self.pair_rnds[j][i] += n
            done.add((i, j, r["r"]))
            shown = self.pair_kinds.setdefault((i, j), [])
            kind = new_story(shown, pa / n, pb / n)
            if kind is not None:
                shown.append((kind, pa / n, pb / n))  # already told; don't replay it
        self.applied = self.played = len(records)
        return done

    def close(self):
        self.closing = True  # destroying widgets still fires resize events
        if self.engine:
            self.engine.stop.set()
        self.root.after_cancel(self._tick_id)
        if self._layout_pending:
            self.root.after_cancel(self._layout_pending)
        self.root.destroy()

    def apply(self, m):
        i, j, pa, pb, n, (ma, mb) = m[:6]
        for me, other, p, mv in ((i, j, pa, ma), (j, i, pb, mb)):
            k = 0 if self.specs[other]["kind"] == "team" else 1
            self.pts[me][k] += p
            self.rnds[me][k] += n
            if harness.GAME.stat:
                counted = harness.GAME.stat[1]
                self.coop[me] += sum(1 for ch in mv if ch.upper() in counted)
            self.moves[me] += n
            if "#" in mv and self.specs[me]["kind"] == "team" and me not in self.forfeit_reported:
                self.forfeit_reported.add(me)
                self.note(f"{self.display_name(me)} is forfeiting rounds (timeout or crash)", DOWN, toast=True)
        self.pair_pts[i][j] += pa
        self.pair_pts[j][i] += pb
        self.pair_rnds[i][j] += n
        self.pair_rnds[j][i] += n
        self.applied += 1
        self.recent.append(m)
        a, b = pa / n, pb / n
        for x, y, sx, sy in ((i, j, a, b), (j, i, b, a)):
            if sx >= 4.0 and sy <= 0.75 and (x, y) not in self.exploit_reported \
                    and self.specs[x]["kind"] == "team":
                self.exploit_reported.add((x, y))
                self.note(f"{self.display_name(x)} extracts {sx:.2f} a round from {self.display_name(y)}"
                          f" (who gets {sy:.2f})", WARN)

    def pick_match(self, busy):
        best, best_key = None, None
        has_team = any(s["kind"] == "team" for s in self.specs)
        for idx in range(len(self.recent) - 1, max(-1, len(self.recent) - 150), -1):
            i, j = self.recent[idx][0], self.recent[idx][1]
            if i in busy or j in busy:
                continue
            teams = (self.specs[i]["kind"] == "team") + (self.specs[j]["kind"] == "team")
            if has_team and not teams:
                continue
            key = self.shown[i] + self.shown[j] + (0 if teams == 2 else 3) + random.random()
            if best_key is None or key < best_key:
                best, best_key = idx, key
        if best is None:
            return None
        m = self.recent[best]
        del self.recent[best]
        self.shown[m[0]] += 1
        self.shown[m[1]] += 1
        return m

    def tick(self):
        now = time.perf_counter()
        # Real elapsed time (big replays can make frames slow); capped so a
        # stall (dragging the window, a dialog) doesn't cause a jump.
        dt, self.last_tick = min(0.5, now - self.last_tick), now
        if not self._laid_out:
            self.layout()
        redraw_card = False
        try:
            while True:
                kind, payload = self.ui_q.get_nowait()
                if kind == "match":
                    self._arrive(payload)
                    self.played += 1
                elif kind == "done":
                    self.final_stats = payload
                elif kind == "error":
                    self._append_log("Engine error:\n" + payload, DOWN)
                    self.state, self.working = "final", False
                    self._refresh_buttons()
                elif kind == "log":
                    self._append_log(*payload)
                elif kind == "idle":
                    if self.state not in ("running", "paused"):
                        self.working = False
                    self._refresh_buttons()
                elif kind == "start":
                    self.start_run(*payload)
                elif kind == "watch":
                    self.card = None
                    self.cv.delete("card")
                    self.stages[0].start(payload, pinned=True)
                elif kind == "card":
                    self.card = payload
                    redraw_card = True
                elif kind == "status":
                    name, status = payload
                    self.check_status[name] = status
        except queue.Empty:
            pass
        if redraw_card:
            self._draw_card()

        self._advance(dt)
        if self.card:
            self.cv.tag_raise("card")

        self._refresh_board(dt)
        self._update_header()
        self._tick_id = self.root.after(33, self.tick)

    def finish(self):
        self.state = "final"
        self.working = False
        _, _, stats = self.final_stats
        ranks = self.ranks(self.order())
        # Every match is already in the tournament file; CSVs are Export CSV's job.
        self.champion_index = min(ranks, key=ranks.get) if ranks else None
        header = self.run_info.get("header") or harness.TournamentFile.header(
            self.specs, self.run_info.get("reps", 0), self.run_info.get("seed"), False)
        self.tour = harness.Tournament(self.run_info.get("out", ""), header, self.matches,
                                       {s["name"]: stats[i].summary() for i, s in enumerate(self.specs)
                                        if i in stats})
        self._finished(ranks, stats)
        self._refresh_buttons()

    BADGES = {"ok": ("✓ checked", UP), "warn": ("! warnings", WARN), "fail": ("✗ failing", DOWN)}

    def _refresh_board(self, dt, snap=False):
        if not self.rows:
            return
        cv = self.cv
        order = self.order()
        ranks = self.ranks(order)
        now = time.perf_counter()

        self._ranks_changed(ranks, now)
        for i, rk in ranks.items():
            prev = self.rank_prev.get(i)
            if prev is not None and rk != prev and self.applied:
                self.arrows[i] = (now, rk < prev)
            self.rank_prev[i] = rk

        order = [i for i in order if i in self.rows]
        top = max([self.score(i) for i in order] + [3.0])
        on_stage = set()
        for st in self.stages:
            on_stage |= st.playing()
        for pos, i in enumerate(order):
            r = self.rows[i]
            target = self.row_top + pos * self.row_h
            dy = (target - r["y"]) if snap else (target - r["y"]) * min(1.0, dt * 7)
            if abs(dy) > 0.25:
                cv.move(f"row{i}", 0, dy)
                r["y"] += dy
            spec = self.specs[i]
            team = spec["kind"] == "team"
            rk = ranks.get(i)
            sc = self.score(i)
            arrow = self.arrows.get(i)
            arrow_txt, arrow_col = "", UP
            if arrow and now - arrow[0] < 2.5:
                arrow_txt, arrow_col = ("▲", UP) if arrow[1] else ("▼", DOWN)
            medal = MEDALS.get(rk) if self.applied and team else None
            badge = ("", FAINT)
            if team and self.show_badges():
                status = self.check_status.get(spec["name"])
                badge = self.BADGES[status] if status else (("not checked", FAINT) if spec.get("added") else badge)
            scored = self.show_scores() and self.applied
            vals = {
                "rank": (str(rk) if rk and scored else ("·" if scored else ""),
                         medal or (FG if team else DIM)),
                "arrow": (arrow_txt if scored else "", arrow_col),
                "score": (f"{sc:.3f}" if scored else "", FG if team else DIM),
                "coop": (f"{self.coop[i] / self.moves[i]:.0%}" if scored and self.moves[i] else "", DIM),
                "name": (self.display_name(i), FG if team else DIM),
                "badge": badge,
            }
            for key, (text, col) in vals.items():
                if r["cache"].get(key) != (text, col):
                    cv.itemconfig(r[key], text=text, fill=col)
                    r["cache"][key] = (text, col)
            b0, b1 = self.cols["bar0"], self.cols["bar1"]
            bx = b0 + (b1 - b0) * (sc / (top * 1.02)) if scored else b0
            if r["cache"].get("barbg") != scored:
                state = "normal" if scored else "hidden"
                cv.itemconfig(r["barbg"], state=state)
                cv.itemconfig(r["bar"], state=state)
                r["cache"]["barbg"] = scored
            if r["cache"].get("bar") != int(bx):
                c = cv.coords(r["bar"])
                cv.coords(r["bar"], b0, c[1], bx, c[3])
                r["cache"]["bar"] = int(bx)
            bg = MEDAL_BG[rk] if medal else PANEL
            outline = ""
            if i in self.selected:
                bg, outline = SELECT, FG
            elif i in on_stage:
                bg, outline = (bg if medal else PANEL2), self.color(i)  # the two bots playing now
            if r["cache"].get("bg") != (bg, outline):
                cv.itemconfig(r["bg"], fill=bg, outline=outline, width=3 if outline else 0)
                r["cache"]["bg"] = (bg, outline)

    def _update_header(self):
        if not self.rows:
            return
        self.cv.itemconfig(self.status, text=self._status_text())
        x0, y0, x1, y1 = self.bar_box
        f = lambda frac: x0 + (x1 - x0) * max(0.0, min(1.0, frac))
        played, shown = self._progress()
        self.cv.coords(self.bar_played, x0, y0, f(played), y1)
        self.cv.coords(self.bar_shown, x0, y0, f(shown), y1)

    def load_teams(self, path):
        try:
            specs = harness.load_manifest(path)
        except (OSError, ValueError, KeyError) as e:
            self.log(f"Could not load {path}: {e}", DOWN)
            return False
        self.team_specs = specs
        self.check_status = {}
        self._field_changed()
        self.log(f"Loaded {len(specs)} team bots from {os.path.basename(path)}.", UP)
        return True

    def load_teams_dialog(self):
        path = filedialog.askopenfilename(title="Team manifest", filetypes=[("Manifest", "*.json")])
        if path:
            self.load_teams(path)

    def load_house(self, path):
        """House bots come from a file outside the app (the organizer's
        reference_bots.py), so the app never contains them."""
        folder, fname = os.path.split(os.path.abspath(path))
        if folder not in sys.path:
            sys.path.insert(0, folder)  # worker processes inherit sys.path
        try:
            mod = importlib.import_module(os.path.splitext(fname)[0])
            specs = [dict(s, kind="ref", path=folder) for s in mod.reference_specs()]
        except Exception as e:
            self.log(f"Could not load house bots from {path}: {e}", DOWN)
            return False
        self.house_specs = specs
        self.log(f"Loaded {len(specs)} house bots. Sparring partners switched off.", UP)
        if self.baselines_var.get():
            self.baselines_var.set(False)  # triggers _field_changed
        else:
            self._field_changed()
        return True

    def load_house_dialog(self):
        path = filedialog.askopenfilename(title="House bots (Python file with reference_specs())",
                                          filetypes=[("Python", "*.py")])
        if path:
            self.load_house(path)

    def check_all(self):
        teams = [dict(s) for s in self.specs if s["kind"] == "team"]
        if not teams:
            self.log("No team bots to check. Load a manifest or add bots first.", WARN)
            return
        reps = self.num(self.reps_var, int, 100)
        workers = self.num(self.workers_var, int, default_workers())
        n_field = self.n

        def work():
            results = []
            self.ui_q.put(("card", {"kind": "summary", "state": "running", "results": [], "total": len(teams)}))
            for spec in teams:
                ok, out = build(spec)
                if not ok:
                    r = {"name": spec["name"], "status": "fail",
                         "reason": "build failed: " + (out.strip().splitlines() or ["?"])[-1]}
                else:
                    rep = harness.smoke_test(spec["cmd"], cwd=spec["cwd"])
                    bad = next((k for k in rep.checks if k.status == rep.worst and k.status != "ok"), None)
                    reason = f"{bad.label}: {bad.detail.splitlines()[0]}" if bad and bad.detail else \
                        (bad.label if bad else "all checks passed")
                    st = rep.stats.summary()
                    r = {"name": spec["name"], "status": rep.worst, "reason": reason,
                         "mean_ms": st["mean_ms"] if rep.stats.latencies else None}
                results.append(r)
                self.ui_q.put(("status", (r["name"], r["status"])))
                self.ui_q.put(("card", {"kind": "summary", "state": "running", "results": list(results),
                                        "total": len(teams)}))
            means = [r["mean_ms"] / 1000 for r in results if r.get("mean_ms") is not None]
            secs = harness.projected_seconds(means, n_field, reps, workers)
            secs30 = harness.projected_seconds(means, n_field, 30, workers)
            projection = (f"Projected run: ~{secs / 60:.1f} min at {reps} matches per pairing on {workers} "
                          f"workers  ·  ~{secs30 / 60:.1f} min at 30")
            self.ui_q.put(("card", {"kind": "summary", "state": "done", "results": results,
                                    "total": len(teams), "projection": projection}))
            failing = [r["name"] for r in results if r["status"] == "fail"]
            self.log(f"Checked {len(teams)} bots: " + (f"{len(failing)} failing ({', '.join(failing)})"
                                                       if failing else "all ready."),
                     DOWN if failing else UP)
        self._work(work)

    def _on_motion(self, event):
        x, y = self.cv.canvasx(event.x), self.cv.canvasy(event.y)
        for st in self.stages:
            if not st.match or not st.pinned or st.drawn < st.match[4]:
                continue
            for item in self.cv.find_overlapping(x, y, x, y):
                if item in st.cellmap:
                    self.cv.itemconfig(st.flip_txt, text=st.describe(st.cellmap[item]))
                    return

