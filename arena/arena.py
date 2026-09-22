"""The Arena: run matches between bots and dig through the results.

Double-click this file, or run:  python arena.py

  Bots        add your bots, check they speak the protocol
  Run         play the round robin; every match is saved to a tournament file
  Standings   final scores, with confidence intervals
  Statistics  is one bot really better than another (paired test, SPRT)
  Explorer    every match played; open one and watch it round by round

Right-click a bot on the board to edit its run command or remove it.
"""

import argparse
import multiprocessing
import os
import runpy
import sys
import tempfile
import time
import traceback
import tkinter as tk
from tkinter import filedialog
from tkinter import font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game  # noqa: E402
import harness  # noqa: E402
import stats as stat  # noqa: E402
from ui import *  # noqa: E402,F401,F403
from ui import (ACCENT, BG, DIM, DOWN, FAINT, FG, LINE, PANEL, PANEL2, UP, WARN,  # noqa: E402
                BaseApp, FlatButton, adopt_portable_tools, baseline_specs, default_workers,
                user_bot_spec)

VIEWS = [("bots", "Bots"), ("run", "Run"), ("standings", "Standings"),
         ("stats", "Statistics"), ("explorer", "Explorer")]


class Arena(BaseApp):
    """The match runner: teams test their bot with it, the organizer plays the
    tournament with it and saves the file the show is made from."""

    TITLE = "IPD Arena"

    def __init__(self, root):
        self.view = "bots"
        self.run_started = 0.0
        self._panel_at = 0.0
        self.explorer_top = 0        # first row shown in the match list
        self.explorer_rows = []      # the matches currently listed
        self.explorer_filter = None  # a bot index, or None for all
        super().__init__(root)
        root.bind("<MouseWheel>", self._wheel)
        root.bind("<Button-4>", lambda e: self._wheel(e, 1))
        root.bind("<Button-5>", lambda e: self._wheel(e, -1))
        self.show_view("bots")
        self.log("Add your bots, check them, then run a tournament. Standings, Statistics and "
                 "Explorer come alive once a run finishes.", FG)

    # ---------------- settings ----------------

    def _build_vars(self):
        self.reps_var.set("20")
        self.seed_var = tk.StringVar(value="")
        self.workers_var = tk.StringVar(value=str(default_workers()))
        self.weight_var = tk.StringVar(value="1")
        self.self_play_var = tk.BooleanVar(value=False)
        self.baselines_var = tk.BooleanVar(value=True)
        self.file_var = tk.StringVar(value="")
        self.delta_var = tk.StringVar(value="0.05")
        self.baselines_var.trace_add("write", lambda *a: self._field_changed())

    def _compose_field(self):
        self.specs = (self.team_specs + (baseline_specs() if self.baselines_var.get() else [])
                      + self.house_specs)

    def settings(self):
        return {"seed": self.num(self.seed_var, int, None),
                "workers": self.num(self.workers_var, int, default_workers()),
                "self_play": self.self_play_var.get(),
                "ref_weight": self.num(self.weight_var, float, 1.0),
                "out": self.file_var.get().strip(),
                "show_minutes": 0.0, "stage_speed": 30.0}

    # ---------------- toolbar ----------------

    def _build_toolbar(self, tb):
        bar = tk.Frame(tb, bg=BG)
        bar.pack(fill="x")
        self.view_buttons = {}
        for key, text in VIEWS:
            b = FlatButton(bar, text, lambda k=key: self.show_view(k))
            b.pack(side="left", padx=(0, 6))
            self.view_buttons[key] = b
        self.hint = self._label(bar, "", FAINT)
        self.hint.pack(side="left", padx=16)

        self.rows_by_view = {}

        def row(view):
            f = tk.Frame(tb, bg=BG)
            self.rows_by_view[view] = f
            return f

        f = row("bots")
        for key, text, cmd in (("add", "+ Add bot", self.add_bot), ("check", "Check", self.check),
                               ("checkall", "Check all", self.check_all),
                               ("house", "Load house bots…", self.load_house_dialog)):
            b = FlatButton(f, text, cmd)
            b.pack(side="left", padx=(0, 8))
            self.buttons[key] = b
        self._checkbox(f, "Sparring partners", self.baselines_var).pack(side="left", padx=(8, 0))

        f = row("run")
        b = FlatButton(f, "Run tournament", self.run_or_stop, primary=True)
        b.pack(side="left", padx=(0, 10))
        self.buttons["run"] = b
        self._label(f, "Matches per pairing").pack(side="left")
        self._spin(f, self.reps_var, 1, 1000, width=4).pack(side="left", padx=(6, 14))
        self._label(f, "Seed").pack(side="left")
        self._entry(f, self.seed_var, 8).pack(side="left", padx=(6, 14))
        self._label(f, "Workers").pack(side="left")
        self._spin(f, self.workers_var, 1, 64, width=3).pack(side="left", padx=(6, 14))
        self._checkbox(f, "Self-play", self.self_play_var).pack(side="left", padx=(0, 14))
        self._label(f, "Tournament file").pack(side="left")
        self._entry(f, self.file_var, 24).pack(side="left", padx=(6, 6))
        FlatButton(f, "Choose…", self.choose_file).pack(side="left", padx=(0, 8))
        FlatButton(f, "Open…", self.load_file_dialog).pack(side="left")

        f = row("standings")
        self._label(f, "House weight").pack(side="left")
        self._spin(f, self.weight_var, 0.5, 5, inc=0.5, width=4).pack(side="left", padx=(6, 14))
        FlatButton(f, "Export CSV…", self.export_csv).pack(side="left", padx=(0, 8))
        self._label(f, "click a bot for its scores against each opponent", FAINT).pack(side="left")

        f = row("stats")
        self._label(f, "Click two bots on the board.   Difference worth detecting").pack(side="left")
        self._entry(f, self.delta_var, 6).pack(side="left", padx=(6, 8))
        self._label(f, "points per round", FAINT).pack(side="left")

        f = row("explorer")
        for text, cmd in (("Only the selected bot", self.filter_selected),
                          ("All matches", self.filter_none)):
            FlatButton(f, text, cmd).pack(side="left", padx=(0, 8))
        self.explorer_hint = self._label(f, "", FAINT)
        self.explorer_hint.pack(side="left", padx=8)

    def show_view(self, view):
        self.view = view
        for key, b in self.view_buttons.items():
            b.bg = ACCENT if key == view else PANEL2
            b.hover_bg = "#6f9cf2" if key == view else LINE
            b.set_enabled(True)
        for f in self.rows_by_view.values():
            f.pack_forget()
        self.rows_by_view[view].pack(fill="x", pady=(10, 0))
        if view == "explorer":
            self._build_explorer_rows()
        self.layout()
        self._refresh_buttons()

    def _refresh_buttons(self):
        if not self.buttons or not hasattr(self, "hint"):
            return
        idle = not self.working and self.state in ("ready", "final")
        has_team = any(s["kind"] == "team" for s in self.specs)
        for key in ("add", "house"):
            self.buttons[key].set_enabled(idle)
        self.buttons["check"].set_enabled(idle and has_team)
        self.buttons["checkall"].set_enabled(idle and has_team)
        self.buttons["run"].set_enabled(not self.working or self.state in ("running", "paused"))
        self.buttons["run"].config(text="Stop" if self.state in ("running", "paused")
                                   else "Run tournament")
        picked = [self.display_name(i) for i in self.selected]
        self.hint.config(text="   ·   ".join(picked) if picked else
                         f"{self.n} bots" + ("" if self.tour else " · no results yet"))

    # ---------------- tournament files ----------------

    def choose_file(self):
        path = filedialog.asksaveasfilename(title="Save the tournament to", defaultextension=".jsonl",
                                            initialfile="tournament.jsonl",
                                            filetypes=[("Tournament", "*.jsonl")])
        if path:
            self.file_var.set(path)

    def load_file_dialog(self):
        path = filedialog.askopenfilename(title="Open a tournament file",
                                          filetypes=[("Tournament", "*.jsonl *.gz"),
                                                     ("All files", "*.*")])
        if path:
            self.load_tournament(path)

    def load_tournament(self, path):
        """Open a saved tournament for the standings, statistics and explorer."""
        tour = harness.TournamentFile.load(path)
        if not tour:
            self.log(f"{path} is not a tournament file.", DOWN)
            return False
        self.team_specs = [dict(b) for b in tour.bots if b["kind"] == "team"]
        self.house_specs = [dict(b) for b in tour.bots if b["kind"] == "ref"]
        self.baselines_var.set(False)
        self.specs = [dict(b) for b in tour.bots]
        self._reset_standings()
        self.file_var.set(path)
        self.reps_var.set(str(tour.reps))
        self.seed_var.set(str(tour.seed))
        self.matches = tour.matches
        for m in tour.matches:
            self.apply((m["i"], m["j"], m["pa"], m["pb"], m["n"], (m.get("a", ""), m.get("b", ""))))
        self.tour = tour
        self.total = tour.expected()
        self.played = self.applied = len(tour.matches)
        self.state = "final"
        self.run_info = {"reps": tour.reps, "seed": tour.seed, "out": path,
                         "ref_weight": self.num(self.weight_var, float, 1.0)}
        self.log(f"Opened {len(tour):,} matches from {os.path.basename(path)} "
                 f"({tour.n} bots, {tour.reps} per pairing, seed {tour.seed}).", UP)
        self.show_view("standings")
        return True

    def export_csv(self):
        if not self.tour:
            self.log("Run or open a tournament first.", WARN)
            return
        folder = filedialog.askdirectory(title="Export leaderboard.csv and pairwise.csv to")
        if not folder:
            return
        points, rounds = self.tour.totals()
        harness.write_outputs(folder, self.specs, points, rounds, self._rows(), self.run_info)
        self.log(f"Wrote leaderboard.csv and pairwise.csv to {folder}", UP)

    def _rows(self):
        points, rounds = (self.tour.totals() if self.tour else (self.pair_pts, self.pair_rnds))
        got = self.tour.stats_objects() if self.tour else {}
        rows = harness.score_rows(self.specs, points, rounds,
                                  {i: got.get(i, harness.BotStats()) for i in range(self.n)},
                                  self.num(self.weight_var, float, 1.0))
        if self.tour:
            for r in rows:
                i = next(k for k, s in enumerate(self.specs) if s["name"] == r["name"])
                r["ci"] = stat.score_ci(self.tour, i)[1]
        return rows

    # ---------------- explorer ----------------

    def filter_selected(self):
        self.explorer_filter = self.selected[-1] if self.selected else None
        self.show_view("explorer")

    def filter_none(self):
        self.explorer_filter = None
        self.show_view("explorer")

    def _build_explorer_rows(self):
        ms = self.matches or []
        if self.explorer_filter is not None:
            f = self.explorer_filter
            ms = [m for m in ms if f in (m["i"], m["j"])]
        self.explorer_rows = ms
        who = "every bot" if self.explorer_filter is None else self.display_name(self.explorer_filter)
        self.explorer_hint.config(text=f"{len(ms):,} matches · {who} · click one to watch it")

    def _wheel(self, event, direction=None):
        if self.view != "explorer" or not self.explorer_rows:
            return
        step = direction if direction is not None else (1 if event.delta > 0 else -1)
        self.explorer_top = max(0, self.explorer_top - step * 3)
        self.layout()

    def open_match(self, m):
        """Replay one match from the file in the viewer."""
        self.rps = 60.0
        self.stages[0].start((m["i"], m["j"], m["pa"], m["pb"], m["n"], (m["a"], m["b"])), pinned=True,
                             title=f"{self.display_name(m['i'])} v {self.display_name(m['j'])}"
                                   f" · repetition {m['r'] + 1}")

    # ---------------- layout ----------------

    def _layout_content(self, W, H, top, m):
        view = self.view
        self.board = None
        if view == "run":
            avail = H - top - m
            self._draw_run_panel(m, top, W - 2 * m, avail * 0.4)
            self.log_box = (m, top + avail * 0.4 + m / 2, W - 2 * m, avail * 0.6 - m / 2)
            self._place_log(True)
            return
        if view == "explorer":
            lw = W * 0.44
            self.list_box = (m, top, lw - m / 2, H - m - top)
            self.card_box = (lw + m / 2, top, W - m - (lw + m / 2), H - m - top)
            self.log_box = (0, 0, 1, 1)
            self._place_log(False)
            self.stages[0].layout(*self.card_box)
            self._draw_match_list(*self.list_box)
            return
        bw = W * 0.5
        self.board = (m, top, bw - m / 2, H - m)
        rx, rw = bw + m / 2, W - m - (bw + m / 2)
        avail = H - top - m
        if view == "bots":
            self.card_box = (rx, top, rw, avail * 0.64)
            self.log_box = (rx, top + avail * 0.64 + m / 2, rw, avail * 0.36 - m / 2)
            self._place_log(True)
        else:
            self.card_box = (rx, top, rw, avail)
            self.log_box = (0, 0, 1, 1)
            self._place_log(False)
        self._layout_board()
        if view == "standings":
            self._draw_details(*self.card_box)
        elif view == "stats":
            self._draw_stats(*self.card_box)

    def _place_log(self, visible):
        x, y, w, h = self.log_box
        self.log_win = self.cv.create_window(x, y, window=self.logbox, anchor="nw",
                                             width=max(1, w), height=max(1, h),
                                             state="normal" if visible else "hidden")

    def _layout_board(self):
        if self.board is None:
            self.rows = {}
            return
        super()._layout_board()

    # ---------------- panels ----------------

    def _panel(self, x, y, w, h, title):
        cv, s = self.cv, self.scale
        cv.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=LINE, tags="panel")
        cv.create_text(x + 24 * s, y + 18 * s, text=title, anchor="nw", fill=FAINT, font=self.f_head,
                       tags="panel")
        return x + 24 * s, y + 54 * s

    def _draw_run_panel(self, x, y, w, h):
        cv, s = self.cv, self.scale
        tx, ty = self._panel(x, y, w, h, "RUN")
        if self.state == "running":
            rate = self.applied / max(0.001, time.perf_counter() - self.run_started)
            left = (self.total - self.applied) / max(0.5, rate)
            head = (f"{self.applied:,} / {self.total:,} matches   ·   {rate:,.0f} a second"
                    f"   ·   ~{int(left // 60)}:{int(left % 60):02d} left")
        elif self.tour:
            head = (f"{len(self.tour):,} matches · {self.tour.reps} per pairing · seed "
                    f"{self.tour.seed}")
        else:
            head = "Press Run tournament. Every match is saved to the tournament file."
        cv.create_text(tx, ty, text=head, anchor="nw", fill=FG, font=self.f_stage_name, tags="panel")
        if self.tour and self.tour.path:
            cv.create_text(tx, ty + 44 * s, text=self.tour.path, anchor="nw", fill=DIM,
                           font=self.f_card_detail, tags="panel")
        trouble = []
        got = self.tour.stats_objects() if self.tour else {}
        for i, sp in enumerate(self.specs):
            st = got[i].summary() if i in got and got[i].loaded else None
            if not st:
                continue
            bits = [f"{st[k]} {label}" for k, label in (("timeouts", "timeouts"),
                                                        ("crashes", "crashes"),
                                                        ("forfeits", "forfeited rounds"),
                                                        ("junk_lines", "stray stdout lines"))
                    if st.get(k)]
            if bits:
                trouble.append(f"{sp['name']}: " + ", ".join(bits))
        if trouble:
            cv.create_text(tx, ty + 84 * s, text="\n".join(trouble[:6]), anchor="nw", fill=DOWN,
                           font=self.f_card_detail, tags="panel")

    def _draw_details(self, x, y, w, h):
        """Standings: the selected bot against each opponent."""
        cv, s = self.cv, self.scale
        tx, ty = self._panel(x, y, w, h, "AGAINST EACH OPPONENT")
        if not self.tour:
            cv.create_text(tx, ty, text="Run or open a tournament first.", anchor="nw", fill=FAINT,
                           font=self.f_card_label, tags="panel")
            return
        if not self.selected:
            cv.create_text(tx, ty, text="Click a bot on the board.", anchor="nw", fill=FAINT,
                           font=self.f_card_label, tags="panel")
            return
        i = self.selected[-1]
        mean, ci = stat.score_ci(self.tour, i)
        cv.create_text(tx, ty, text=self.display_name(i), anchor="nw", fill=FG,
                       font=self.f_stage_name, tags="panel")
        cv.create_text(tx, ty + 42 * s, text=f"{mean:.3f} ± {ci:.3f} points per round", anchor="nw",
                       fill=DIM, font=self.f_card_label, tags="panel")
        order = sorted((j for j in range(self.n) if j != i and self.pair_rnds[i][j]),
                       key=lambda j: -self.pair_pts[i][j] / self.pair_rnds[i][j])
        rh = min(30 * s, max(18 * s, (h - 130 * s) / max(1, len(order))))
        f = tkfont.Font(family=self.family, size=-max(9, int(rh * 0.5)))
        yy = ty + 92 * s
        for j in order:
            mine = self.pair_pts[i][j] / self.pair_rnds[i][j]
            theirs = self.pair_pts[j][i] / self.pair_rnds[j][i]
            cv.create_rectangle(tx, yy, tx + (w - 48 * s) * min(1.0, mine / 5), yy + rh - 4 * s,
                                fill=PANEL2, width=0, tags="panel")
            cv.create_text(tx + 8 * s, yy + rh / 2 - 2 * s, text=self.display_name(j), anchor="w",
                           fill=FG, font=f, tags="panel")
            cv.create_text(x + w - 24 * s, yy + rh / 2 - 2 * s, anchor="e", fill=DIM, font=f,
                           text=f"{mine:.3f}   (they got {theirs:.3f})", tags="panel")
            yy += rh

    def _draw_stats(self, x, y, w, h):
        """Is one bot really better than another?"""
        cv, s = self.cv, self.scale
        tx, ty = self._panel(x, y, w, h, "IS ONE BOT BETTER?")
        if not self.tour or len(self.selected) < 2:
            msg = ("Run or open a tournament first." if not self.tour
                   else "Click two bots on the board to compare them.")
            cv.create_text(tx, ty, text=msg, anchor="nw", fill=FAINT, font=self.f_card_label,
                           tags="panel")
            return
        i, j = self.selected[-2], self.selected[-1]
        delta = self.num(self.delta_var, float, 0.05)
        c = stat.compare(self.tour, i, j, delta=delta)
        na, nb = self.display_name(i), self.display_name(j)
        verdict = {"H1": f"{na} really does score more",
                   "H0": f"no difference as big as {delta:g}",
                   "continue": "not enough matches to tell"}[c["sprt"]["verdict"]]
        colour = {"H1": UP, "H0": DIM, "continue": WARN}[c["sprt"]["verdict"]]
        lines = [
            (f"{na}   vs   {nb}", FG, self.f_stage_name),
            (f"{c['diff']:+.4f} ± {c['ci']:.4f} points per round", FG, self.f_stage_score),
            (f"over {c['pairs']:,} matches against the same opponents, with the same noise",
             DIM, self.f_card_detail),
            ("", FG, self.f_card_detail),
            (verdict, colour, self.f_stage_name),
            (f"SPRT  llr {c['sprt']['llr']:+.2f}   bounds [{c['sprt']['lower']:.2f}, "
             f"{c['sprt']['upper']:.2f}]   δ = {delta:g}", DIM, self.f_card_detail),
            (f"resolving {delta:g} a round would take about {c['needed']:,} matches each"
             if c["needed"] else "", DIM, self.f_card_detail),
            ("", FG, self.f_card_detail),
            (f"head to head:  {c['h2h'][0]:.3f}  vs  {c['h2h'][1]:.3f}   over {c['h2h'][2]} matches",
             FG, self.f_card_label),
        ]
        yy = ty
        for text, col, font in lines:
            if not text:
                yy += 16 * s
                continue
            item = cv.create_text(tx, yy, text=text, anchor="nw", fill=col, font=font,
                                  width=w - 48 * s, tags="panel")
            yy = cv.bbox(item)[3] + 8 * s

    def _draw_match_list(self, x, y, w, h):
        cv, s = self.cv, self.scale
        tx, ty = self._panel(x, y, w, h, "MATCHES")
        if not self.explorer_rows:
            cv.create_text(tx, ty, text="Run or open a tournament first.", anchor="nw", fill=FAINT,
                           font=self.f_card_label, tags="panel")
            return
        rh = 30 * s
        fit = max(1, int((h - 80 * s) / rh))
        f = tkfont.Font(family=self.family, size=-max(9, int(rh * 0.46)))
        self.explorer_top = max(0, min(self.explorer_top, max(0, len(self.explorer_rows) - fit)))
        for k in range(fit):
            idx = self.explorer_top + k
            if idx >= len(self.explorer_rows):
                break
            mt = self.explorer_rows[idx]
            a, b = mt["pa"] / mt["n"], mt["pb"] / mt["n"]
            kind = game.verdict(a, b)[0][0]
            yy = ty + k * rh
            tag = f"match{idx}"
            cv.create_rectangle(x + 12 * s, yy, x + w - 12 * s, yy + rh - 3 * s,
                                fill=PANEL2 if k % 2 else PANEL, width=0, tags=("panel", tag))
            cv.create_text(tx, yy + rh / 2, anchor="w", fill=FG, font=f, tags=("panel", tag),
                           text=f"{self.display_name(mt['i'])} v {self.display_name(mt['j'])}")
            cv.create_text(x + w - 24 * s, yy + rh / 2, anchor="e", font=f, tags=("panel", tag),
                           fill={"coop": UP, "lock": DOWN, "take": WARN}.get(kind, DIM),
                           text=f"{a:.2f} – {b:.2f}   {kind}")
            cv.tag_bind(tag, "<Button-1>", lambda e, mm=mt: self.open_match(mm))
        shown = min(len(self.explorer_rows), self.explorer_top + fit)
        cv.create_text(x + w / 2, y + h - 18 * s, anchor="s", fill=FAINT, font=self.f_card_detail,
                       tags="panel", text=f"{self.explorer_top + 1}–{shown} of "
                                          f"{len(self.explorer_rows):,}   ·   scroll to move")

    # ---------------- hooks ----------------

    def show_badges(self):
        return self.view == "bots"

    def _draw_overlays(self):
        if self.view == "bots":
            self._draw_card()

    def click_row(self, i):
        super().click_row(i)
        if self.view in ("standings", "stats"):
            self.layout()

    def _log_breakdown(self, i):
        pass  # the standings view shows this properly

    def _finished(self, ranks, stats):
        super()._finished(ranks, stats)
        if self.run_info.get("out"):
            self._append_log(f"Saved to {self.run_info['out']}", UP)
        self.show_view("standings")

    def _advance(self, dt):
        """No live replays while running: results just go onto the standings."""
        if self.state == "running":
            while self.pending:
                self.apply(self.pending.popleft())
            if self.final_stats and self.applied >= self.played:
                self.finish()
            now = time.perf_counter()
            if self.view == "run" and now - self._panel_at > 0.5:
                self._panel_at = now          # keep the run panel's counters moving
                self.layout()
        for st in self.stages:
            st.step(dt, self.rps)

    def _status_text(self):
        if self.state == "running":
            return f"running · {self.applied:,} / {self.total:,} matches"
        if self.tour:
            return f"{len(self.tour):,} matches · {self.n} bots"
        return f"{self.n} bots on the board"

    def run_or_stop(self):
        if self.state not in ("running", "paused"):
            if not self.file_var.get().strip():
                self.file_var.set(os.path.join(tempfile.gettempdir(), "ipd-tournament.jsonl"))
                self.log(f"No tournament file chosen; saving to {self.file_var.get()}", DIM)
            self.run_started = time.perf_counter()
            self.show_view("run")
        super().run_or_stop()


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
    ap.add_argument("tournament", nargs="?", help="a tournament file to open")
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
    app = Arena(root)
    if args.tournament:
        root.after(200, lambda: app.load_tournament(args.tournament))
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
