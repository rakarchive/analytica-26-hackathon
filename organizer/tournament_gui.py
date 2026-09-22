"""The event app: set up the tournament, check every bot, then present it.

    python tournament_gui.py [manifest.json] [--reps 100] [--show-minutes 6] [--present]

Setup: load the teams (manifest) and house bots, check every bot, choose
repetitions, seed, workers, house weight and a results folder. Then Present:

  1. House round: cycle 1's matches against the house bots as a grid, then a summary.
  2. Team against team, one match at a time in a large viewer: each pairing's
     first match and any later one that tells a new story. Every other result
     ticks onto the board between replays, cycle by cycle.
  3. Highlights, stepped through by hand with →; then the champion and runner-up.

Keys in presentation:  SPACE start/pause · → next highlight · H house names ·
L log · + − speed · Esc leave presentation · F11 fullscreen
"""

import argparse
import collections
import importlib
import multiprocessing
import os
import random
import sys
import time
import tkinter as tk
from tkinter import filedialog
from tkinter import font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "arena"))

import harness  # noqa: E402
from ui import *  # noqa: E402,F401,F403
from ui import (BG, DIM, DOWN, FAINT, FG, GLOW, LINE, MEDALS, PANEL, PANEL2, UP, WARN,  # noqa: E402
                MAX_REPLAYS_PER_PAIR, BaseApp, FlatButton, Stage, baseline_specs, default_workers,
                match_story, new_story, verdict)


def mix(c1, c2, t):
    """Blend two #rrggbb colours: t=0 gives c1, t=1 gives c2."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[k:k + 2], 16) for k in (1, 3, 5)]
    b = [int(c2[k:k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


class Show(BaseApp):
    """The organizer's app: setup view, then presentation mode."""

    TITLE = "IPD Tournament"

    def __init__(self, root):
        self.show_log = False       # presentation: the log is behind a disclosure (L)
        self.toasts = []            # [text, color, kind, shown_at]
        super().__init__(root)
        for key, fn in (("<space>", lambda: self.space()), ("<Right>", self.advance_key),
                        ("<Return>", self.advance_key),
                        ("<Key-h>", lambda: self.hide_house_var.set(not self.hide_house_var.get())),
                        ("<Key-l>", self.toggle_log),
                        ("<plus>", lambda: self.speed(1.5)), ("<equal>", lambda: self.speed(1.5)),
                        ("<minus>", lambda: self.speed(1 / 1.5))):
            root.bind(key, lambda e, fn=fn: self.presenting and fn())
        self.log("Load the teams, load the house bots, then Check all teams and Present.", FG)

    # ---------------- setup view ----------------

    def _build_toolbar(self, tb):
        def row(title):
            f = tk.Frame(tb, bg=BG)
            f.pack(fill="x", pady=3)
            self._label(f, title, FAINT).pack(side="left", padx=(0, 12))
            return f

        f = row("FIELD      ")
        for key, text, cmd in (("teams", "Load teams…", self.load_teams_dialog),
                               ("add", "+ Add bot", self.add_bot),
                               ("house", "Load house bots…", self.load_house_dialog),
                               ("check", "Check", self.check),
                               ("checkall", "Check all teams", self.check_all)):
            b = FlatButton(f, text, cmd)
            b.pack(side="left", padx=(0, 8))
            self.buttons[key] = b
        self._checkbox(f, "Sparring partners", self.baselines_var).pack(side="left", padx=(8, 12))
        self._checkbox(f, "Hide house names", self.hide_house_var).pack(side="left")

        f = row("TOURNAMENT ")
        self._label(f, "Matches per pairing").pack(side="left")
        self._spin(f, self.reps_var, 1, 1000, width=4).pack(side="left", padx=(6, 14))
        self._label(f, "Seed").pack(side="left")
        self._entry(f, self.seed_var, 8).pack(side="left", padx=(6, 14))
        self._label(f, "Workers").pack(side="left")
        self._spin(f, self.workers_var, 1, 64, width=3).pack(side="left", padx=(6, 14))
        self._label(f, "House weight").pack(side="left")
        self._spin(f, self.weight_var, 0.5, 5, inc=0.5, width=4).pack(side="left", padx=(6, 14))
        self._checkbox(f, "Self-play", self.self_play_var).pack(side="left", padx=(0, 14))
        self._label(f, "Save results to").pack(side="left")
        self._entry(f, self.out_var, 22).pack(side="left", padx=(6, 6))
        FlatButton(f, "Choose…", self.choose_out).pack(side="left")

        f = row("SHOW       ")
        self._label(f, "Length (min)").pack(side="left")
        self._spin(f, self.show_min_var, 0, 60, width=3).pack(side="left", padx=(6, 14))
        b = FlatButton(f, "▶  Present", lambda: self.present(True), primary=True)
        b.pack(side="left", padx=(0, 8))
        b = FlatButton(f, "Run without presenting", self.run_or_stop)
        b.pack(side="left", padx=(0, 8))
        self.buttons["run"] = b
        FlatButton(f, "Watch", self.watch).pack(side="left", padx=(0, 12))
        self.buttons["watch"] = f.winfo_children()[-1]
        self.hint = self._label(f, "", FAINT)
        self.hint.pack(side="left")

    def _refresh_buttons(self):
        idle = not self.working and self.state in ("ready", "final")
        has_team = any(s["kind"] == "team" for s in self.specs)
        b = self.buttons
        if "checkall" not in b:
            return
        for key in ("teams", "add", "house"):
            b[key].set_enabled(idle)
        b["check"].set_enabled(idle and has_team)
        b["checkall"].set_enabled(idle and has_team)
        b["run"].set_enabled(not self.working or self.state in ("running", "paused"))
        b["run"].config(text="Stop" if self.state in ("running", "paused") else "Run without presenting")
        b["watch"].set_enabled(idle and len(self.selected) == 2)
        self.hint.config(text="click two rows, then Watch" if len(self.selected) < 2 else
                         f"{self.display_name(self.selected[0])} vs {self.display_name(self.selected[1])}")

    def settings(self):
        return {"seed": self.num(self.seed_var, int, None),
                "workers": self.num(self.workers_var, int, default_workers()),
                "self_play": self.self_play_var.get(),
                "ref_weight": self.num(self.weight_var, float, 1.0),
                "out": self.out_var.get().strip(),
                "show_minutes": self.num(self.show_min_var, float, 6.0),
                "stage_speed": 30.0}

    def _set_hide_house(self):
        self.hide_house = self.hide_house_var.get()
        if self.rows:
            self.layout()

    def _escape(self):
        if self.presenting:
            self.present(False)
        else:
            super()._escape()

    def toggle_log(self):
        self.show_log = not self.show_log
        self.layout()

    # ---------------- presentation hooks ----------------

    def _reset_extra(self):
        self.top2, self.top2_cand = None, (None, 0.0)  # the two winning places, as announced
        # Presentation plays the results back in cycles (one cycle = every
        # pairing once): each cycle's house matches, then its team matches.
        self.phase = None             # "house" (cycle 1 grid), "house_summary", "flow"
        self.arrived = collections.defaultdict(collections.deque)  # (rep, group) -> results
        self.group_left, self.group_order, self.gpos = {}, [], 0
        self.plan = collections.deque()
        self.unplanned = self.unplanned_duels = self.planned_duels = 0
        self.planned_extras = self.plan_replays = self.unseen_pairs = 0
        self.carry_rate = 1.0
        self.show_started = self.paused_total = 0.0
        self.hold_time = 1.2
        self.fit_at = 0.0
        self.house_rate = 1.0
        self.house_summary = []
        self.hl_best, self.hl_worst = {}, {}   # highlight candidates, from every team match
        self.highlights, self.hl_idx, self.hl_title = [], 0, ""
        self.champion_pending = None
        self.phase_until = 0.0
        self.house_drawn_at = 0.0
        self.show_end = 0.0
        self.speed_factor = 1.0
        self.milestones = {0.25: "A quarter of the way through", 0.5: "Halfway there",
                           0.75: "Three quarters done: the table is settling"}

    def _on_run_start(self, reps, self_play, records, minutes):
        if self.run_presenting:
            self._setup_show(reps, self_play, records, minutes)

    def _priority(self, specs):
        if not self.run_presenting:
            return None
        kinds = [s["kind"] for s in specs]
        # Cycle by cycle, each cycle's house matches first.
        return lambda i, j, r: (r, 1 if kinds[i] == kinds[j] == "team" else 0)

    def _arrive(self, m):
        if self.run_presenting:
            i, j, rep = m[0], m[1], m[6]
            self.arrived[(rep, 1 if self._duel(i, j) else 0)].append(m)
        else:
            super()._arrive(m)

    def _advance(self, dt):
        if not self.run_presenting:
            return super()._advance(dt)
        if self.state == "running":
            self._direct(dt)
            if self._show_done():
                self._start_highlights()
        if self.state != "paused":
            for st in self.stages:
                st.step(dt, self.rps)
        st = self.stages[0]
        if not st.busy() and getattr(st, "wait_item", None):
            self.cv.itemconfig(st.wait_item, text=self.stage_hint())
        self.cv.tag_raise("house")
        self._draw_toasts()

    def apply(self, m):
        super().apply(m)
        if self.run_presenting:
            frac = self.applied / self.total
            for mark in sorted(self.milestones):
                if frac >= mark:
                    self._append_log(self.milestones.pop(mark), DIM)

    def note(self, text, color, toast=False):
        if toast and self.run_presenting:
            self.notify(text, color)
        else:
            super().note(text, color)

    def _ranks_changed(self, ranks, now):
        if self.presenting and self.applied and len(ranks) >= 2 and self.state != "final":
            top2 = tuple(sorted(ranks, key=ranks.get)[:2])
            if top2 != self.top2_cand[0]:
                self.top2_cand = (top2, now)
            elif top2 != self.top2 and now - self.top2_cand[1] >= 1.0:  # held, not a flicker
                self._announce_top2(self.top2, top2)
                self.top2 = top2

    def _finished(self, ranks, stats):
        if self.run_presenting:
            self.champion_pending = self.display_name(self.champion_index) if ranks else None
        else:
            super()._finished(ranks, stats)

    def on_board(self, i):
        """Anonymous house bots stay off the board in presentation mode."""
        return not (self.presenting and self.hide_house and self.specs[i]["kind"] == "ref")

    def stage_hint(self):
        if not self.presenting:
            return super().stage_hint()
        if self.phase == "highlights":
            return "Highlights\nPress → for the first one"
        if self.phase == "done":
            return ""
        if self.phase == "flow" and self.plan:
            cycle = self.plan[0][0][0] + 1
            return (f"Cycle {cycle} of {self.run_info.get('reps', '?')}\n"
                    "Nothing new in these matches: they tick straight onto the board")
        if self.state == "ready":
            return "Press SPACE to start"
        return "…"

    def _status_text(self):
        s = self.state
        if not self.presenting:
            return super()._status_text()
        if s == "ready":
            return f"{sum(1 for i in range(self.n) if self.on_board(i))} teams · press SPACE to start"
        if s == "final" and self.run_presenting and self.phase == "highlights":
            return (f"HIGHLIGHTS · {self.hl_idx} of {len(self.highlights)}"
                    + (f" · {self.hl_title}" if self.hl_idx else "") + " · press → for the next")
        if s == "running" and self.run_presenting and self.phase == "house_summary":
            return "HOUSE ROUND DONE · press → to continue"
        text = super()._status_text()
        if self.run_presenting and s in ("running", "paused") and self.applied < self.total:
            secs = max(0.0, self.show_end - time.perf_counter())
            label = " · house round" if self.phase in ("house", "house_summary") else ""
            text += f"{label} · ~{int(secs // 60)}:{int(secs % 60):02d} to go"
        return text

    def _progress(self):
        p = self.show_progress()
        if p is None or self.state == "final":
            return super()._progress()
        return p, p  # presentation: the bar follows the show, the header has the count

    def _layout_right(self, W, H, top, m):
        if not self.presenting:
            return super()._layout_right(W, H, top, m)
        bw = W * 0.5
        self.board = (m, top, bw - m / 2, H - m)
        rx = bw + m / 2
        rw = W - m - rx
        avail = H - top - m
        log_h = avail * 0.3 if self.show_log else 0.0
        st_h = avail - (log_h + m / 2 if self.show_log else 0.0)
        self.card_box = (rx, top, rw, st_h)
        self.stages[0].layout(*self.card_box)  # one large viewer
        self.log_box = (rx, top + st_h + m / 2, rw, log_h)
        self.log_win = self.cv.create_window(rx, self.log_box[1], window=self.logbox, anchor="nw",
                                             width=rw, height=max(1.0, log_h),
                                             state="normal" if self.show_log else "hidden")

    def _draw_overlays(self):
        self._draw_champion()
        self._draw_card()
        self._draw_house()
        self._draw_toasts(force=True)

    # ---------------- toasts: brief, prominent notifications ----------------

    def notify(self, text, color=None, kind=None):
        """Log it, and pop it up under the leaderboard for a few seconds. A newer
        notice of the same kind (e.g. the top two) replaces an older one at
        once, even the one on screen: old news isn't worth showing."""
        color = color or MEDALS[1]
        self._append_log(text, color)
        if not self.presenting:
            return
        if kind:
            self.toasts = [t for t in self.toasts if t[2] != kind]
        self.toasts.append([text, color, kind, None])

    TOAST_TIME = 3.5  # seconds on screen (2.2 when others are waiting)

    def _toast_box(self):
        """The free space under the leaderboard's rows (or the board's foot if full)."""
        x, y, x1, y1 = self.board
        s = self.scale
        rows_bottom = self.row_top + self.row_h * len(self.rows)
        h = 120 * s
        top = rows_bottom + 24 * s if y1 - rows_bottom >= h + 32 * s else y1 - h
        return x, top, x1, min(y1, top + h)

    def _draw_toasts(self, force=False):
        """Redrawn every frame while one is up: it pops in (a solid flash,
        slightly oversized, settling within a quarter second) and fades out."""
        now = time.perf_counter()
        if self.toasts and self.toasts[0][3] is not None:
            life = self.TOAST_TIME if len(self.toasts) == 1 else 2.2
            if now - self.toasts[0][3] > life:
                self.toasts.pop(0)
        if self.toasts and self.toasts[0][3] is None:
            self.toasts[0][3] = now
        self.cv.delete("toast")
        if not self.toasts or not self.presenting or not self.rows:
            return
        text, color, _, t0 = self.toasts[0]
        life = self.TOAST_TIME if len(self.toasts) == 1 else 2.2
        age = now - t0
        if age < 0.08:          # the flash: solid colour, oversized
            grow, fill, fg = 1.12, color, BG
        elif age < 0.25:        # snap back and settle
            k = (age - 0.08) / 0.17
            grow, fill, fg = 1.12 - 0.12 * k, mix(color, PANEL2, k), mix(BG, color, k)
        else:
            grow, fill, fg = 1.0, PANEL2, color
        outline = color
        if life - age < 0.35:   # fade out
            k = max(0.0, (life - age) / 0.35)
            fg, outline = mix(PANEL2, fg, k), mix(PANEL2, color, k)
        x0, y0, x1, y1 = self._toast_box()
        s = self.scale
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = (x1 - x0) * (1 + (grow - 1) * 0.25), (y1 - y0) * grow  # pop mostly in height
        self.cv.create_rectangle(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, fill=fill, outline=outline,
                                 width=4, tags="toast")
        self.cv.create_text(cx, cy, text=text, fill=fg, width=w - 40 * s, justify="center",
                            font=self.f_stage_name, tags="toast")

    def _build_vars(self):
        self.reps_var.set("100")
        self.show_min_var = tk.StringVar(value="6")
        self.stage_speed_var = tk.StringVar(value="30")
        self.seed_var = tk.StringVar(value="")
        self.workers_var = tk.StringVar(value=str(default_workers()))
        self.weight_var = tk.StringVar(value="1")
        self.self_play_var = tk.BooleanVar(value=False)
        self.baselines_var = tk.BooleanVar(value=True)
        self.hide_house_var = tk.BooleanVar(value=True)
        self.out_var = tk.StringVar(value="")
        self.baselines_var.trace_add("write", lambda *a: self._field_changed())
        self.hide_house = True
        self.hide_house_var.trace_add("write", lambda *a: self._set_hide_house())

    def _compose_field(self):
        self.specs = (self.team_specs + (baseline_specs() if self.baselines_var.get() else [])
                      + self.house_specs)

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

    def load_house(self, path):
        import importlib
        folder, fname = os.path.split(os.path.abspath(path))
        if folder not in sys.path:
            sys.path.insert(0, folder)  # worker processes inherit sys.path
        try:
            mod = importlib.import_module(os.path.splitext(fname)[0])
            specs = [dict(s, kind="ref") for s in mod.reference_specs()]
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

    def load_teams_dialog(self):
        path = filedialog.askopenfilename(title="Team manifest", filetypes=[("Manifest", "*.json")])
        if path:
            self.load_teams(path)

    def load_house_dialog(self):
        path = filedialog.askopenfilename(title="House bots (Python file with reference_specs())",
                                          filetypes=[("Python", "*.py")])
        if path:
            self.load_house(path)

    def choose_out(self):
        path = filedialog.askdirectory(title="Save results to")
        if path:
            self.out_var.set(path)

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

    def present(self, on=True):
        self.presenting = on
        self.root.attributes("-fullscreen", on)
        if on:
            self.selected = []
            self.stages[1].match = None  # presentation uses one large stage
        self.layout()
        self._refresh_buttons()
        if on:
            self._append_log("Presentation mode. SPACE start/pause · → next highlight · H house names · "
                             "L log · + − speed · Esc to leave", DIM)

    def space(self):
        if self.state in ("ready", "final") and not self.working:
            self.run_or_stop()
        elif self.state == "running":
            self.state, self.paused_at = "paused", time.perf_counter()
        elif self.state == "paused":
            self.state = "running"
            paused = time.perf_counter() - self.paused_at
            self.show_end += paused  # a pause doesn't eat the show
            self.paused_total += paused

    def speed(self, k):
        self.speed_factor = max(0.1, min(20.0, self.speed_factor * k))
        self.rps = max(2.0, min(800.0, self.rps * k))

    stage_speed = speed

    def _duel(self, i, j):
        return self.specs[i]["kind"] == "team" and self.specs[j]["kind"] == "team"

    def _setup_show(self, reps, self_play, records, minutes):
        """Presentation plays results back in a fixed order, cycle by cycle:
        (rep 0, house), (rep 0, teams), (rep 1, house), ... so the board is
        balanced at every cycle boundary and never runs on house results alone.
        Results are planned as they arrive (in that order), so the pacing knows
        exactly how many replays are left."""
        n = self.n
        pairs = [(i, j) for i in range(n) for j in range(i if self_play else i + 1, n)]
        duel_pairs = [p for p in pairs if self._duel(*p)]
        house_n = len(pairs) - len(duel_pairs)
        self.group_left = {}
        for r in range(reps):
            self.group_left[(r, 0)] = house_n
            self.group_left[(r, 1)] = len(duel_pairs)
        for rec in records:
            self.group_left[(rec["r"], 1 if self._duel(rec["i"], rec["j"]) else 0)] -= 1
        self.group_order = [k for k in sorted(self.group_left) if self.group_left[k] > 0]
        self.gpos = 0
        self.arrived = collections.defaultdict(collections.deque)
        self.plan = collections.deque()   # (group, match, replay?) in playback order
        self.unplanned = sum(self.group_left.values())
        self.unplanned_duels = sum(v for (r, g), v in self.group_left.items() if g == 1)
        self.planned_duels = self.planned_extras = self.plan_replays = 0
        self.unseen_pairs = sum(1 for p in duel_pairs if not self.pair_kinds.get(p))
        secs = max(0.5, minutes) * 60
        self.show_end = time.perf_counter() + secs
        self.show_started, self.paused_total, self.show_left_est = time.perf_counter(), 0.0, secs
        if self.group_left.get((0, 0), 0) > 0 and duel_pairs and house_n:
            self.phase = "house"
            self.house_rate = self.group_left[(0, 0)] / max(15.0, min(60.0, 0.2 * secs))
        else:
            self.phase = "flow"

    def _extend_plan(self):
        """Move arrived results into the plan, strictly in playback order,
        deciding which ones get replayed: a pairing's first match, and later
        ones only when they end differently."""
        while self.gpos < len(self.group_order):
            key = self.group_order[self.gpos]
            q = self.arrived[key]
            while q and self.group_left[key]:
                m = q.popleft()
                self.group_left[key] -= 1
                self.unplanned -= 1
                replay = False
                if key[1] == 1:
                    self.unplanned_duels -= 1
                    self.planned_duels += 1
                    self._consider_highlight(m)
                    i, j, pa, pb, n = m[:5]
                    shown = self.pair_kinds.setdefault((i, j), [])
                    kind = new_story(shown, pa / n, pb / n)
                    if kind is not None:
                        if shown:
                            self.planned_extras += 1
                        else:
                            self.unseen_pairs -= 1
                        shown.append((kind, pa / n, pb / n))
                        replay = True
                        self.plan_replays += 1
                self.plan.append((key, m, replay))
            if self.group_left[key]:
                return  # waiting for the engine
            self.gpos += 1

    def _fit(self):
        """Replay speed and the pace of everything else, so the show ends on time:
        ~80% of what's left goes to replays, the rest to results that tick on."""
        now = time.perf_counter()
        self.fit_at = now
        left = max(5.0, self.show_end - now)
        # Replays still to come: planned ones, plus an estimate for results
        # the engine hasn't delivered yet.
        extra = self.planned_extras / max(1, self.planned_duels)
        replays = self.plan_replays + min(self.unplanned_duels, self.unseen_pairs + extra * self.unplanned_duels)
        carried = max(0.0, len(self.plan) + self.unplanned - replays)
        if replays >= 0.5:
            # Results that tick on between replays get a short slice (the stage is
            # idle meanwhile); replays get the rest, each an equal slot, ~35% of it
            # holding the verdict on screen.
            carry_time = min(20.0, 0.1 * left) if carried else 0.0
            slot = (left - carry_time) / replays / self.speed_factor
            self.hold_time = max(0.5, min(4.0, 0.4 * slot))  # a beat to read the result, scaled to the time
            self.rps = max(10.0, min(800.0, 200 / max(0.1, slot - self.hold_time)))
            self.carry_rate = carried / max(1.0, carry_time) if carried else 1e9
        else:
            # Nothing left to replay: finish the remaining results in a few seconds
            # rather than leaving the stage empty until the show's end time.
            self.carry_rate = max(50.0, carried / 4.0) if carried else 1e9
        self.carry_rate = max(2.0, self.carry_rate * self.speed_factor)
        # Show progress for the bar: time still needed by the plan, against the
        # time already spent. Matches aren't evenly spread (a pairing's first
        # match, the one always replayed, is nearly always in cycle 1).
        per_replay = 200 / max(1.0, self.rps) + self.hold_time
        self.show_left_est = replays * per_replay + carried / self.carry_rate

    def show_progress(self):
        if not self.run_presenting or not self.show_started:
            return None
        now = time.perf_counter()
        spent = now - self.show_started - self.paused_total
        if self.phase == "house_summary" and self.state == "running":
            spent -= now - self.phase_until  # waiting for → isn't show time
        return spent / max(1e-6, spent + getattr(self, "show_left_est", 0.0))

    def _direct(self, dt):
        """Presentation: walk the plan. The board and the progress bar only move
        as things are shown: cycle 1's house matches fill the grid, a replayed
        match lands on the board with its verdict, and everything else ticks
        on between replays."""
        now = time.perf_counter()
        self._extend_plan()
        st = self.stages[0]
        if st.owes:
            if st.drawn >= st.match[4]:
                self.apply(st.match)
                st.owes = False
            else:
                return  # the board waits for the verdict
        if self.phase == "house_summary":
            return  # holds until → (advance_key)
        if self.phase == "house":
            self.budget = min(self.budget + self.house_rate * dt, self.house_rate * 0.5 + 1)
            while self.plan and self.plan[0][0] == (0, 0) and self.budget >= 1:
                self.apply(self.plan.popleft()[1])
                self.budget -= 1
            house_done = not self.group_left.get((0, 0)) and not (self.plan and self.plan[0][0] == (0, 0))
            if house_done:
                self.phase, self.phase_until = "house_summary", now  # phase_until: when it started
                self.house_summary = self._summarise_house()
                for line in self.house_summary:
                    self._append_log(line, MEDALS[1] if line.startswith("Best") else FG)
                self.budget = 0.0
                self._draw_house()
            elif now - self.house_drawn_at > 0.25:
                self._draw_house()
            self.show_left_est = max(0.0, self.show_end - now)
            return
        if now - self.fit_at > 0.5:
            self._fit()
        self.budget = min(self.budget + self.carry_rate * dt, self.carry_rate * 0.25 + 1)
        while self.plan:
            key, m, replay = self.plan[0]
            if replay:
                if st.busy():
                    return  # the previous verdict is still on screen
                self.plan.popleft()
                self.plan_replays -= 1
                self._fit()
                st.hold_time = self.hold_time
                st.start(m)
                st.owes = True
                return
            if self.budget < 1:
                return
            self.plan.popleft()
            self.apply(m)
            self.budget -= 1

    HIGHLIGHTS = [  # (title, metric, minimum worth showing)
        ("Closest to perfect cooperation", "coop", 2.5),
        ("The noisiest match", "flips", 12),
        ("The longest breakdown", "echo", 4),
        ("The longest mutual-defection lock", "lock", 8),
        ("The most unprovoked defections", "unprovoked", 3),
        ("The biggest extraction", "gap", 1.0),
    ]

    def _consider_highlight(self, m):
        i, j, pa, pb, n = m[:5]
        a, b = pa / n, pb / n
        _, met = match_story(*m[5], "", "")
        met = dict(met, coop=min(a, b), gap=abs(a - b))
        for title, key, _ in self.HIGHLIGHTS:
            if met[key] > self.hl_best.get(title, (float("-inf"), None))[0]:
                self.hl_best[title] = (met[key], m)
        for me, p in ((i, a), (j, b)):
            if p < self.hl_worst.get(me, (float("inf"), None))[0]:
                self.hl_worst[me] = (p, m)

    def _start_highlights(self):
        self.finish()
        champ = self.champion_index
        picks, used = [], set()
        for title, key, minimum in self.HIGHLIGHTS:
            score, m = self.hl_best.get(title, (None, None))
            if m is not None and score >= minimum and id(m) not in used:
                picks.append((title, m))
                used.add(id(m))
        if champ is not None and champ in self.hl_worst and id(self.hl_worst[champ][1]) not in used:
            picks.append((f"The champion's toughest match", self.hl_worst[champ][1]))
        self.highlights, self.hl_idx = picks, 0
        self.phase = "highlights"
        self.stages[0].clear()
        if picks:
            self.notify(f"Highlights: {len(picks)} matches. Press → for each one", MEDALS[1], kind="phase")
        else:
            self.next_highlight()

    def advance_key(self):
        """→ / Enter: leave the house-round summary, or play the next highlight."""
        if self.phase == "house_summary" and self.state == "running":
            waited = time.perf_counter() - self.phase_until
            self.show_end += waited  # waiting for the key doesn't eat the show
            self.paused_total += waited
            self.phase = "flow"
            self.cv.delete("house")
            self.notify("Now: team against team", FG, kind="phase")
        else:
            self.next_highlight()

    def next_highlight(self):
        if not (self.presenting and self.phase == "highlights"):
            return
        if self.hl_idx < len(self.highlights):
            title, m = self.highlights[self.hl_idx]
            self.hl_idx += 1
            self.rps = 40.0
            self.hl_title = title
            self.stages[0].start(m, pinned=True)
        else:
            self.phase = "done"
            self.stages[0].clear()
            self.champion = self.champion_pending
            self._draw_champion()
            if self.champion:
                teams = [i for i in self.order() if self.specs[i]["kind"] == "team"]
                self.notify(f"★ Champion: {self.champion}"
                                 + (f"   ·   Runner-up: {self.display_name(teams[1])}" if len(teams) > 1 else ""),
                                 MEDALS[1])

    def _show_done(self):
        return (self.run_presenting and self.final_stats and not self.plan
                and self.gpos >= len(self.group_order) and not self.stages[0].owes)

    def _house_cells(self):
        teams = [i for i in range(self.n) if self.specs[i]["kind"] == "team"]
        house = [i for i in range(self.n) if self.specs[i]["kind"] != "team"]
        cell = lambda t, h: (self.pair_pts[t][h] / self.pair_rnds[t][h]) if self.pair_rnds[t][h] else None

        def avg(t):
            p = sum(self.pair_pts[t][h] for h in house)
            r = sum(self.pair_rnds[t][h] for h in house)
            return p / r if r else None
        return teams, house, cell, avg

    def _summarise_house(self):
        teams, house, cell, avg = self._house_cells()
        lines = []
        scored = [(avg(t), t) for t in teams if avg(t) is not None]
        if scored:
            v, t = max(scored)
            lines.append(f"Best against the house: {self.display_name(t)}, {v:.2f} per round")
        cols = []
        for h in house:
            vals = [cell(t, h) for t in teams if cell(t, h) is not None]
            if vals:
                cols.append((sum(vals) / len(vals), h))
        if cols:
            v, h = min(cols)
            lines.append(f"Toughest house bot: {self.display_name(h)} (teams averaged {v:.2f} against it)")
            v, h = max(cols)
            lines.append(f"Most generous: {self.display_name(h)} (teams averaged {v:.2f} against it)")
        return lines

    @staticmethod
    def _heat(v):
        """Cell colour: red below the 2.25 midpoint, green above."""
        def mix(c1, c2, t):
            t = max(0.0, min(1.0, t))
            a = [int(c1[k:k + 2], 16) for k in (1, 3, 5)]
            b = [int(c2[k:k + 2], 16) for k in (1, 3, 5)]
            return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))
        if v < 2.25:
            return mix("#8a2c27", PANEL2, (v - 0.5) / 1.75)
        return mix(PANEL2, "#2f8a55", (v - 2.25) / 1.75)

    def _draw_house(self):
        cv = self.cv
        cv.delete("house")
        self.house_drawn_at = time.perf_counter()
        if not (self.run_presenting and self.phase in ("house", "house_summary")):
            return
        teams, house, cell, avg = self._house_cells()
        if not teams or not house:
            return
        x, y, w, h = self.card_box
        s = self.scale
        pad = 28 * s
        cv.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=LINE, width=2, tags="house")
        refs = any(self.specs[i]["kind"] == "ref" for i in house)
        cv.create_text(x + pad, y + 20 * s, text="HOUSE ROUND" if refs else "WARM-UP ROUND", anchor="nw",
                       fill=FAINT, font=self.f_head, tags="house")
        cv.create_text(x + pad, y + 44 * s, text="Every team against the house bots" if refs
                       else "Every bot against the sparring partners", anchor="nw", fill=FG,
                       font=self.f_stage_name, tags="house")
        summary_h = 150 * s if self.phase == "house_summary" else 20 * s
        top = y + 110 * s
        name_w = w * 0.26
        cols = len(house) + 1
        cw = (w - 2 * pad - name_w) / cols
        ch = min(72 * s, (y + h - summary_h - top - 30 * s) / max(1, len(teams)))
        f_cell = tkfont.Font(family=self.family, size=-max(8, int(min(ch, cw / 2.6) * 0.5)), weight="bold")
        f_name = tkfont.Font(family=self.family, size=-max(8, int(ch * 0.5)))
        gx = x + pad + name_w
        for k, hb in enumerate(house):
            label = self.display_name(hb).replace("House bot ", "") if self.hide_house                 else self.display_name(hb).replace("ref_", "")[:9]
            cv.create_text(gx + (k + 0.5) * cw, top + 12 * s, text=label, fill=DIM, font=f_name,
                           tags="house")
        cv.create_text(gx + (len(house) + 0.5) * cw, top + 12 * s, text="avg", fill=FG, font=f_name,
                       tags="house")
        order = sorted(teams, key=lambda t: -(avg(t) or 0))
        gy = top + 30 * s
        for r, t in enumerate(order):
            ry = gy + r * ch
            cv.create_text(gx - 12 * s, ry + ch / 2, text=self.display_name(t), anchor="e", fill=FG,
                           font=f_name, tags="house")
            for k, hb in enumerate(house + [None]):
                v = cell(t, hb) if hb is not None else avg(t)
                cx0 = gx + k * cw
                fill = self._heat(v) if v is not None else PANEL
                cv.create_rectangle(cx0 + 2, ry + 2, cx0 + cw - 2, ry + ch - 2, fill=fill,
                                    outline=FG if hb is None and v is not None else "", tags="house")
                if v is not None:
                    cv.create_text(cx0 + cw / 2, ry + ch / 2, text=f"{v:.2f}", fill=FG, font=f_cell,
                                   tags="house")
        if self.phase == "house_summary":
            sy = y + h - summary_h + 10 * s
            for k, line in enumerate(self.house_summary):
                cv.create_text(x + pad, sy + k * 40 * s, text=line, anchor="nw",
                               fill=MEDALS[1] if k == 0 else FG, font=self.f_card_label, tags="house")
            cv.create_text(x + w - pad, y + h - 14 * s, text="Press → to continue", anchor="se",
                           fill=DIM, font=self.f_card_detail, tags="house")

    def _draw_champion(self):
        """The reveal: a podium over the big viewer."""
        cv = self.cv
        cv.delete("champ")
        if not self.champion or not self.presenting:
            return
        x, y, w, h = self.card_box
        s = self.scale
        cv.create_rectangle(x, y, x + w, y + h, fill=PANEL2, outline=MEDALS[1], width=3, tags="champ")
        order = [i for i in self.order() if self.specs[i]["kind"] == "team"]
        cv.create_text(x + w / 2, y + h * 0.16, text="★  CHAMPION  ★", fill=MEDALS[1],
                       font=self.f_stage_name, tags="champ")
        cv.create_text(x + w / 2, y + h * 0.31, text=self.champion, fill=FG, font=self.f_champ, tags="champ")
        if order:
            cv.create_text(x + w / 2, y + h * 0.42, text=f"{self.score(order[0]):.3f} points per round",
                           fill=DIM, font=self.f_card_label, tags="champ")
        if len(order) > 1:
            cv.create_text(x + w / 2, y + h * 0.60, text="RUNNER-UP", fill=MEDALS[2],
                           font=self.f_stage_name, tags="champ")
            cv.create_text(x + w / 2, y + h * 0.72, text=self.display_name(order[1]), fill=FG,
                           font=self.f_champ, tags="champ")
            cv.create_text(x + w / 2, y + h * 0.83, text=f"{self.score(order[1]):.3f} points per round",
                           fill=DIM, font=self.f_card_label, tags="champ")

    def _announce_top2(self, old, new):
        """One shout per change to the two winning places."""
        name = self.display_name
        if old is None:
            msg = f"{name(new[0])} leads, {name(new[1])} second"
        elif set(old) == set(new):
            msg = f"{name(new[0])} overtakes {name(new[1])} for first place"
        else:
            parts = []
            if new[0] != old[0]:
                parts.append(f"{name(new[0])} takes the lead")
            for b in new:
                if b not in old and b != new[0]:
                    parts.append(f"{name(b)} climbs into the top two")
            dropped = [b for b in old if b not in new]
            if dropped:
                msg_drop = f"{' and '.join(name(d) for d in dropped)} drop{'s' if len(dropped) == 1 else ''} out"
                parts[-1] += f", {msg_drop}"
            msg = "; ".join(parts)
        self.notify(f"★ {msg}", MEDALS[1], kind="top2")



def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", nargs="?", help="teams to load (JSON manifest)")
    ap.add_argument("--reps", type=int, default=100)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--seed", type=int)
    ap.add_argument("--ref-weight", type=float, default=1.0)
    ap.add_argument("--self-play", action="store_true")
    ap.add_argument("--no-reference", action="store_true")
    ap.add_argument("--show-minutes", type=float, default=6.0)
    ap.add_argument("--out", default="results")
    ap.add_argument("--present", action="store_true", help="go straight to presentation mode")
    args = ap.parse_args()

    root = tk.Tk()
    app = Show(root)
    if args.manifest and not app.load_teams(args.manifest):
        sys.exit(f"could not load {args.manifest}")
    if not args.no_reference:
        app.load_house(os.path.join(HERE, "reference_bots.py"))
    for var, value in ((app.reps_var, args.reps), (app.workers_var, args.workers),
                       (app.seed_var, "" if args.seed is None else args.seed),
                       (app.weight_var, args.ref_weight), (app.show_min_var, args.show_minutes),
                       (app.out_var, os.path.abspath(args.out))):
        var.set(str(value))
    app.self_play_var.set(args.self_play)
    if args.present:
        root.after(300, lambda: app.present(True))
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
