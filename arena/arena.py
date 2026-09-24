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

# Where tournaments are saved unless Advanced says otherwise: one numbered file
# per run, so there is never an old one in the way.
TOURNAMENT_DIR = os.path.join(tempfile.gettempdir(), "arena-tournaments")

# One screen: the board, and beside it a panel whose tabs follow what is
# picked on the board. Everything else lives under Advanced.
TABS = {0: (("results", "Results"), ("check", "Check"), ("matches", "Matches")),
        1: (("results", "Results"), ("check", "Check"), ("matches", "Matches")),
        2: (("results", "Compare"), ("matches", "Matches"))}


class Arena(BaseApp):
    """The match runner: teams test their bot with it, the organizer plays the
    tournament with it and saves the file the show is made from."""

    TITLE = "ANALYTICA - INTEGRATE AND CONQUER"

    def __init__(self, root):
        self.view = "bots"
        self.options_open = False
        self.run_started = 0.0
        self._panel_at = 0.0
        self.explorer_top = 0        # first row shown in the match list
        self.explorer_rows = []      # the matches currently listed
        self.explorer_note = ""
        self.viewing = None          # the match open in the Matches tab
        self.last_summary = None     # the last Check all's results
        super().__init__(root)
        self.side_tab = "check"    # which tab the panel beside the board is on
        root.bind("<MouseWheel>", self._wheel)
        root.bind("<Button-4>", lambda e: self._wheel(e, 1))
        root.bind("<Button-5>", lambda e: self._wheel(e, -1))
        self.layout()
        self.log("Add your bots, check them, then run a tournament. The results appear beside "
                 "the board; Matches holds every match played.", FG)

    # ---------------- settings ----------------

    def _build_vars(self):
        self.reps_var.set("20")
        self.seed_var = tk.StringVar(value="")
        self.workers_var = tk.StringVar(value=str(default_workers()))
        self.weight_var = tk.StringVar(value="1")
        self.self_play_var = tk.BooleanVar(value=False)
        self.baselines_var = tk.BooleanVar(value=True)
        self.file_var = tk.StringVar(value="")
        self.resume = False      # carry on with the tournament in the file (see run_or_stop)
        self.delta_var = tk.StringVar(value="0.05")
        self.details_var = tk.BooleanVar(value=False)
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
                "resume": self.resume,
                "show_minutes": 0.0, "stage_speed": 30.0}

    # ---------------- toolbar ----------------

    def _build_toolbar(self, tb):
        bar = tk.Frame(tb, bg=BG)
        bar.pack(fill="x")
        # The bot buttons sit under the board, placed there at each layout.
        for key, text, cmd in (("add", "+ Add bot", self.add_bot),
                               ("keep", "Keep this version", self.keep_selected)):
            self.buttons[key] = FlatButton(self.cv, text, cmd)
        # Buttons that sit in the panel's tabs, placed there at each layout.
        self.panel_buttons = {"check": FlatButton(self.cv, "Check", self.check),
                              "checkall": FlatButton(self.cv, "Check all", self.check_all),
                              "back": FlatButton(self.cv, "‹ All matches", self.close_match)}

        # Run and Advanced on the right; the help line centred over the board
        # (placed at each layout, since the board's width follows the window's).
        self.opt_button = FlatButton(bar, "Advanced ▸", self.toggle_options)
        self.opt_button.pack(side="right")
        self.buttons["run"] = FlatButton(bar, "Run tournament", self.run_or_stop, primary=True)
        self.buttons["run"].pack(side="right", padx=(0, 8))
        self.hint = self._label(bar, "", FAINT)

        # Everything you rarely touch, in one place.
        opt = self.options = tk.Frame(tb, bg=PANEL, padx=14, pady=10, highlightthickness=1,
                                      highlightbackground=LINE)

        def line(title):
            f = tk.Frame(opt, bg=PANEL)
            f.pack(fill="x", pady=3)
            self._label(f, title, FAINT).pack(side="left", padx=(0, 12))
            return f

        f = line("TOURNAMENT ")
        self._label(f, "Matches per pairing").pack(side="left")
        self._spin(f, self.reps_var, 1, 1000, width=4).pack(side="left", padx=(6, 14))
        self._label(f, "Seed").pack(side="left")
        self._entry(f, self.seed_var, 8).pack(side="left", padx=(6, 14))
        self._label(f, "Workers").pack(side="left")
        self._spin(f, self.workers_var, 1, 64, width=3).pack(side="left", padx=(6, 14))
        self._checkbox(f, "Self-play", self.self_play_var).pack(side="left", padx=(0, 14))
        self._checkbox(f, "Sparring partners", self.baselines_var).pack(side="left", padx=(0, 14))
        FlatButton(f, "Load house bots…", self.load_house_dialog).pack(side="left")

        f = line("FILE       ")
        self._entry(f, self.file_var, 40).pack(side="left", padx=(0, 8))
        FlatButton(f, "Choose…", self.choose_file).pack(side="left", padx=(0, 8))
        FlatButton(f, "Open…", self.load_file_dialog).pack(side="left", padx=(0, 8))
        FlatButton(f, "Export CSV…", self.export_csv).pack(side="left")

        f = line("COMPARING  ")
        self._label(f, "House weight").pack(side="left")
        self._spin(f, self.weight_var, 0.5, 5, inc=0.5, width=4).pack(side="left", padx=(6, 14))
        self._label(f, "Difference worth detecting").pack(side="left")
        self._entry(f, self.delta_var, 6).pack(side="left", padx=(6, 6))
        self._label(f, "points per round", FAINT).pack(side="left", padx=(0, 14))
        self._checkbox(f, "Show the test's workings", self.details_var).pack(side="left")

    def toggle_options(self):
        self.options_open = not self.options_open
        if self.options_open:
            self.options.pack(fill="x", pady=(10, 0))
        else:
            self.options.pack_forget()
        self.opt_button.config(text="Advanced ▾" if self.options_open else "Advanced ▸")
        self.layout()

    def _refresh_buttons(self):
        if not self.buttons or not hasattr(self, "hint"):
            return
        idle = not self.working and self.state in ("ready", "final")
        has_team = any(s["kind"] == "team" for s in self.specs)
        self.buttons["add"].set_enabled(idle)
        self.panel_buttons["check"].set_enabled(idle and self._report_bot() is not None)
        self.panel_buttons["checkall"].set_enabled(idle and has_team)
        self.buttons["keep"].set_enabled(idle and self._keep_target() is not None)
        self.buttons["run"].set_enabled(not self.working or self.state in ("running", "paused"))
        self.buttons["run"].config(text="Stop" if self.state in ("running", "paused")
                                   else "Run tournament")
        self.hint.config(text=self._tab_hint())

    def _tab_hint(self):
        """One line saying what to do here."""
        if self.state == "running":
            return "playing…"
        if not any(s.get("added") for s in self.specs) and not self.tour:
            return "add your bot, then Check it"
        if len(self.selected) >= 2:
            return "comparing the two picked bots · click one again to drop it"
        if self.selected:
            return "click another bot to compare the two · click this one again to let go"
        if not self.tour:
            return "Check your bots, then Run tournament. Keep this version before a big change"
        return "click a bot for its results and check, two to compare them"

    # ---------------- tournament files ----------------

    def choose_file(self):
        path = filedialog.asksaveasfilename(title="Save the tournament to", defaultextension=".jsonl",
                                            initialfile="tournament-1.jsonl",
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
        self.side_tab, self.viewing = "results", None   # an opened tournament shows its results
        self.log(f"Opened {len(tour):,} matches from {os.path.basename(path)} "
                 f"({tour.n} bots, {tour.reps} per pairing, seed {tour.seed}).", UP)
        if not tour.complete():
            self.log("It is unfinished: Run tournament carries on with it.", DIM)
        self.layout()
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

    def _build_explorer_rows(self):
        """The matches of whatever is picked: all of them, one bot's, or the
        ones between two bots."""
        ms = self.matches or []
        picked = set(self.selected)
        if len(picked) == 1:
            ms = [m for m in ms if picked & {m["i"], m["j"]}]
        elif len(picked) == 2:
            ms = [m for m in ms if {m["i"], m["j"]} == picked]
        self.explorer_rows = ms

    def _wheel(self, event, direction=None):
        if self.side_tab != "matches" or self.viewing or not self.explorer_rows:
            return
        step = direction if direction is not None else (1 if event.delta > 0 else -1)
        self.explorer_top = max(0, self.explorer_top - step * 3)
        self.layout()

    def open_match(self, m):
        """Show one match in the Matches tab, all of it at once."""
        self.viewing = m
        self.layout()               # lays the viewer out in the tab
        self.stages[0].start((m["i"], m["j"], m["pa"], m["pb"], m["n"], (m["a"], m["b"])), pinned=True,
                             title=f"repetition {m['r'] + 1}")   # the names are already on show
        self.stages[0].reveal()

    def close_match(self):
        self.viewing = None
        self.stages[0].match = None
        self.layout()

    # ---------------- layout ----------------

    def _layout_content(self, W, H, top, m):
        """Always the same shape: the board on the left; on the right the
        panel, with tabs that follow what is picked, above the log."""
        avail = H - top - m
        bw = W * 0.5
        # Under the board: its buttons, centred. Over it: the help line.
        s = self.scale
        add, keep = self.buttons["add"], self.buttons["keep"]
        row_h = max(add.winfo_reqheight(), keep.winfo_reqheight())
        bottom = H - m - row_h - 12 * s
        self.board = (m, top, bw - m / 2, bottom)
        cx = (m + bw - m / 2) / 2
        gap = 10 * s
        left = cx - (add.winfo_reqwidth() + gap + keep.winfo_reqwidth()) / 2
        self.cv.create_window(left, H - m, window=add, anchor="sw")
        self.cv.create_window(left + add.winfo_reqwidth() + gap, H - m, window=keep, anchor="sw")
        self.hint.place(x=cx - m, rely=0.5, anchor="center")
        self._refresh_buttons()     # the help line and what can be pressed follow the layout
        rx, rw = bw + m / 2, W - m - (bw + m / 2)
        panel_h = avail * 0.64
        self.card_box = (rx, top, rw, panel_h)
        self.log_box = (rx, top + panel_h + m / 2, rw, avail - panel_h - m / 2)
        self._place_log(True)
        self._layout_board()
        if self.card:
            return                  # a check under way: drawn over this spot (_draw_overlays)
        if self.state == "running":
            self._draw_run_panel(*self.card_box)
            return
        self._draw_side(*self.card_box)

    def _place_log(self, visible):
        x, y, w, h = self.log_box
        self.log_win = self.cv.create_window(x, y, window=self.logbox, anchor="nw",
                                             width=max(1, w), height=max(1, h),
                                             state="normal" if visible else "hidden")

    # ---------------- one picked bot: its results and its check ----------------

    def _report_bot(self):
        """The team bot the panel is about, if exactly one is picked."""
        if len(self.selected) == 1:
            i = self.selected[0]
            if i < self.n and self.specs[i]["kind"] == "team":
                return i
        return None

    def _tabs(self):
        """(key, label, usable) for the panel's tabs, given what is picked."""
        n = min(2, len(self.selected))
        out = []
        for key, label in TABS[n]:
            if key == "check" and n == 1 and self._report_bot() is None:
                continue            # a sparring partner: nothing to check
            usable = {"results": n == 0 or bool(self.tour), "matches": bool(self.tour)}.get(key, True)
            if key == "check":
                name = self.specs[self.selected[0]]["name"] if n == 1 else None
                status = self.check_status.get(name) if name else None
                label += {"ok": "  ✓", "warn": "  !", "fail": "  ✗"}.get(status, "")
            out.append((key, label, usable))
        return out

    def _default_tab(self):
        """Where the panel opens after the pick changes: a bot that failed or
        warned its check opens on the check; otherwise the results, once
        there are any. The Matches tab stays open while you pick."""
        keys = {k for k, _, ok in self._tabs() if ok}
        if self.side_tab == "matches" and "matches" in keys:
            return "matches"
        one = self._report_bot()
        if one is not None:
            bad = self.check_status.get(self.specs[one]["name"]) in ("fail", "warn")
            return "check" if bad or not self.tour else "results"
        if not self.selected:
            return "results" if self.tour else "check"
        return "results"

    def _report_updated(self, name):
        i = self._report_bot()
        if i is not None and self.specs[i]["name"] == name:
            self.layout()

    def _card_changed(self):
        """A finished check moves into the Check tab: the bot's own, or, for
        Check all, the one shown with nothing picked."""
        c = self.card
        if not c or c.get("state") != "done":
            return
        self.card = None
        if c["kind"] == "check":
            k = next((k for k, s in enumerate(self.specs) if s["name"] == c["name"]), None)
            if k is not None:
                self.selected = [k]
        else:
            self.last_summary = c
            self.selected = []
        self.side_tab = "check"
        self.viewing = None
        self.layout()

    def _draw_side(self, x, y, w, h):
        """The tabs, and under them the one that is open."""
        cv, s = self.cv, self.scale
        tabs = self._tabs()
        keys = [k for k, _, ok in tabs if ok]
        if self.side_tab not in keys:
            self.side_tab = keys[0]
        tab_h = 44 * s
        tx = x
        for key, label, usable in tabs:
            active = key == self.side_tab
            t = cv.create_text(tx + 22 * s, y + tab_h / 2, text=label, anchor="w", font=self.f_card_label,
                               fill=(BG if active else FG if usable else FAINT), tags=("panel", f"tab_{key}"))
            x1 = cv.bbox(t)[2] + 22 * s
            r = cv.create_rectangle(tx, y, x1, y + tab_h - 4 * s, width=0, tags=("panel", f"tab_{key}"),
                                    fill=(ACCENT if active else PANEL2))
            cv.tag_raise(t, r)
            if usable and not active:
                cv.tag_bind(f"tab_{key}", "<Button-1>", lambda e, k=key: self._pick_tab(k))
            tx = x1 + 6 * s
        by, bh = y + tab_h, h - tab_h
        right = x + w                     # the tab strip's right end, for its button and notes
        if self.side_tab == "results":
            if not self.selected:
                self._draw_run_panel(x, by, w, bh)
            elif len(self.selected) == 1:
                self._draw_details(x, by, w, bh)
                trouble = self._tournament_trouble(self.selected[0])
                if trouble:
                    cv.create_text(x + w - 24 * s, by + 18 * s, anchor="ne", fill=DOWN,
                                   font=self.f_card_detail, text=trouble, tags="panel")
            else:
                self._draw_stats(x, by, w, bh)
        elif self.side_tab == "check":
            key = "check" if self.selected else "checkall"
            right = self._place_panel_button(key, right, y, tab_h)
            if self.selected:
                self._draw_bot_check(self.selected[0], x, by, w, bh, right, y + tab_h / 2)
            else:
                self._draw_all_checks(x, by, w, bh)
        else:
            if self.viewing:
                self._place_panel_button("back", right, y, tab_h)
                self.stages[0].layout(x, by, w, bh)
            else:
                self._build_explorer_rows()
                self._draw_match_list(x, by, w, bh)

    def _place_panel_button(self, key, right, y, tab_h):
        """Put one of the panel's buttons at the right end of the tab strip;
        returns where the space to its left ends."""
        b = self.panel_buttons[key]
        b.update_idletasks()
        self.cv.create_window(right, y + (tab_h - 4 * self.scale) / 2, window=b, anchor="e", tags="panel")
        return right - b.winfo_reqwidth() - 14 * self.scale

    def _draw_bot_check(self, i, x, y, w, h, right, mid):
        cv, s = self.cv, self.scale
        name = self.specs[i]["name"]
        got = self.check_reports.get(name)
        if got:
            stale = got.get("code") and got["code"] != harness.code_hash(self.specs[i])
            cv.create_text(right, mid, anchor="e", font=self.f_card_detail, tags="panel",
                           fill=WARN if stale else FAINT,
                           text=(f"changed since the check at {got['at']}: check again" if stale
                                 else f"checked at {got['at']}"))
        cv.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=LINE, tags="panel")
        if not got:
            cv.create_text(x + 28 * s, y + 28 * s, anchor="nw", fill=DIM, font=self.f_card_label,
                           width=w - 56 * s, tags="panel",
                           text=f"{name} hasn't been checked yet. Check tries it against the sparring "
                                "partners and tells you what, if anything, is wrong with it.")
            return
        card = {"kind": "check", "name": name, "state": "done", "report": got.get("report"),
                "build_error": got.get("build_error")}
        self._card_tag = "panel"
        try:
            self._draw_check_card(x, y, w, h, s, card=card)
        finally:
            self._card_tag = "card"

    def _draw_all_checks(self, x, y, w, h):
        cv, s = self.cv, self.scale
        cv.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=LINE, tags="panel")
        if not self.last_summary:
            cv.create_text(x + 28 * s, y + 28 * s, anchor="nw", fill=DIM, font=self.f_card_label,
                           width=w - 56 * s, tags="panel",
                           text="Check all tries every bot you added against the sparring partners. "
                                "Pick a bot on the board to check just that one.")
            return
        self._card_tag = "panel"
        try:
            self._draw_summary_card(x, y, w, h, s, card=self.last_summary)
        finally:
            self._card_tag = "card"

    def _pick_tab(self, key):
        self.side_tab = key
        if key != "matches":
            self.viewing = None
        self.layout()

    def _tournament_trouble(self, i):
        """One line on what went wrong for the bot in the tournament, if anything."""
        got = self.tour.stats_objects() if self.tour else {}
        st = got[i].summary() if i in got and got[i].loaded else None
        if not st:
            return ""
        bits = [f"{st[k]} {label}" for k, label in (("timeouts", "timeouts"), ("crashes", "crashes"),
                                                    ("forfeits", "forfeited rounds"),
                                                    ("junk_lines", "stray stdout lines")) if st.get(k)]
        return "in the tournament: " + ", ".join(bits) if bits else ""

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
        rh = min(30 * s, max(12 * s, (h - 130 * s) / max(1, len(order))))
        f = tkfont.Font(family=self.family, size=-max(9, int(rh * 0.5)))
        yy = ty + 92 * s
        for j in order:
            mine = self.pair_pts[i][j] / self.pair_rnds[i][j]
            theirs = self.pair_pts[j][i] / self.pair_rnds[j][i]
            cv.create_rectangle(tx, yy, tx + (w - 48 * s) * min(1.0, mine / harness.GAME.best), yy + rh - 4 * s,
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
        if c["sprt"]["verdict"] != "H1" and c["diff"] + c["ci"] < 0:
            # The test only asks whether the first bot scores more. When the
            # answer is a clear no, say which way it went: after Keep this
            # version, "the change made it worse" is the common case.
            verdict, colour = f"{nb} really does score more", DOWN
        lines = [
            (f"{na}   vs   {nb}", FG, self.f_stage_name),
            (f"{c['diff']:+.4f} ± {c['ci']:.4f} points per round", FG, self.f_stage_score),
            (f"over {c['pairs']:,} matches against the same opponents, with the same noise",
             DIM, self.f_card_detail),
            ("", FG, self.f_card_detail),
            (verdict, colour, self.f_stage_name),
            (f"resolving {delta:g} a round would take about {c['needed']:,} matches each"
             if c["needed"] else "", DIM, self.f_card_detail),
            (f"SPRT  llr {c['sprt']['llr']:+.2f}   bounds [{c['sprt']['lower']:.2f}, "
             f"{c['sprt']['upper']:.2f}]   δ = {delta:g}   ({c['sprt']['n']:,} paired matches)"
             if self.details_var.get() else "", FAINT, self.f_card_detail),
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
        picked = [self.display_name(k) for k in self.selected]
        tx, ty = self._panel(x, y, w, h, "MATCHES" + (": " + " v ".join(picked) if picked else ""))
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
                           fill={"up": UP, "down": DOWN, "warn": WARN}.get(
                               harness.GAME.kind_colour.get(kind, "dim"), DIM),
                           text=f"{a:.2f} – {b:.2f}   {kind}")
            cv.tag_bind(tag, "<Button-1>", lambda e, mm=mt: self.open_match(mm))
        shown = min(len(self.explorer_rows), self.explorer_top + fit)
        cv.create_text(x + w / 2, y + h - 18 * s, anchor="s", fill=FAINT, font=self.f_card_detail,
                       tags="panel", text=f"{self.explorer_top + 1}–{shown} of "
                                          f"{len(self.explorer_rows):,}   ·   scroll to move")

    # ---------------- hooks ----------------

    def show_badges(self):
        """Check results on the board until there are scores to show there."""
        return not self.show_scores()

    def show_scores(self):
        return bool(self.tour) or self.state in ("running", "paused")

    def _draw_overlays(self):
        self._draw_card()

    def click_row(self, i):
        super().click_row(i)
        if self.card and self.card.get("state") == "done":
            self.card = None        # the picked bot's panel, not an old check result
        self.viewing, self.explorer_top = None, 0
        self.stages[0].match = None
        self.side_tab = self._default_tab()
        self.layout()

    def _log_breakdown(self, i):
        pass  # the standings view shows this properly

    def _keep_target(self):
        """The bot Keep this version acts on: the selected one, or the only
        bot being worked on."""
        if self.selected:
            i = self.selected[-1]
            return i if self.can_keep(i) else None
        live = [i for i in range(self.n) if self.can_keep(i)]
        return live[0] if len(live) == 1 else None

    def keep_selected(self):
        i = self._keep_target()
        if i is not None:
            self.keep_version(i)

    def _compare_with_kept(self):
        """After a run, open the comparison a team wants: the bot they are
        working on against the version of it they kept most recently."""
        if self.selected:
            return
        by_name = {s["name"]: k for k, s in enumerate(self.specs)}
        kept = [(s.get("kept_order", 0), k) for k, s in enumerate(self.specs)
                if s.get("kept_from") in by_name]
        if kept:
            _, k = max(kept)
            self.selected = [by_name[self.specs[k]["kept_from"]], k]

    def _finished(self, ranks, stats):
        super()._finished(ranks, stats)
        self._compare_with_kept()
        self.side_tab, self.viewing = "results", None   # a finished run opens on its results
        if self.run_info.get("out"):
            self._append_log(f"Saved to {self.run_info['out']}", UP)
        self.layout()

    def _advance(self, dt):
        """No live replays while running: results just go onto the standings."""
        if self.state == "running":
            while self.pending:
                self.apply(self.pending.popleft())
            if self.final_stats and self.applied >= self.played:
                self.finish()
            now = time.perf_counter()
            if now - self._panel_at > 0.5:
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
            if self.card and self.card.get("state") == "done":
                self.card = None    # make room for the run
            path = self.file_var.get().strip()
            self.resume = self._can_resume(path)
            if not self.resume:
                base = path or os.path.join(TOURNAMENT_DIR, "tournament-1.jsonl")
                os.makedirs(os.path.dirname(os.path.abspath(base)), exist_ok=True)
                self.file_var.set(harness.TournamentFile.next_free(base))
                self.log(f"Saving to {self.file_var.get()}", DIM)
            self.run_started = time.perf_counter()
            self.layout()
        super().run_or_stop()


    def _can_resume(self, path):
        """Carry on with the tournament in `path` only if it is unfinished and
        was started with this very field: the same bots, the same code (see
        harness.code_hash) and the same settings. Anything else is a new
        tournament in a new file, so a team that edits its bot and runs again
        never gets the old version's results mixed in."""
        if not path or not os.path.exists(path):
            return False
        old = harness.TournamentFile.load(path)
        opts = self.settings()
        return (bool(old) and not old.complete() and harness.TournamentFile.compatible(
            old.header, self.specs, self.num(self.reps_var, int, 100), opts["self_play"], opts["seed"]))


SELFTEST_BOT = """import sys
FIRST = "{first}"
for line in sys.stdin:
    p = line.split()
    if p and p[0] == "ROUND":
        print(FIRST if p[1] == "-" else p[2], flush=True)   # copy the opponent
    elif p and p[0] == "END":
        break
"""


SELFTEST_TIMEOUT = 150   # seconds before a stuck self-test reports where it is and gives up


def selftest(report_path):
    """Headless check of a packaged build: a small round robin with a real
    subprocess bot, exercising worker processes and bot plumbing. Used by CI,
    where a windowed exe has no console, so the result goes to a file. The
    report is written as it goes, so a run that hangs still says how far it
    got; after SELFTEST_TIMEOUT seconds every thread's stack is added to it
    and the process exits."""
    import faulthandler
    ok = False
    t0 = time.perf_counter()
    report = open(report_path, "w", buffering=1)

    def say(line):
        report.write(f"[{time.perf_counter() - t0:6.1f}s] {line}\n")
        report.flush()

    faulthandler.dump_traceback_later(SELFTEST_TIMEOUT, exit=True, file=report)
    try:
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, "selftest_bot.py"), "w") as f:
            f.write(SELFTEST_BOT.format(first=harness.GAME.moves[0]))
        bot = user_bot_spec(os.path.join(folder, "selftest_bot.py"), "selftest_bot")
        say(f"game: {harness.GAME.key} · python: {bot['cmd'][0]}")
        say(f"bot command: {harness.join_cmd(bot['cmd'])}")
        rep = harness.smoke_test(bot["cmd"], cwd=bot["cwd"], rounds=50)
        say(f"protocol check: {rep.worst}")
        for line in rep.lines():
            say("    " + line)
        specs = [bot] + baseline_specs()
        say(f"round robin: {len(specs)} bots, 2 per pairing, 2 workers")
        marks = set()

        def progress(done, total, secs):
            step = done * 4 // max(1, total)
            if step not in marks:
                marks.add(step)
                say(f"  {done} of {total} matches")
        points, rounds, stats = harness.run_round_robin(specs, 2, seed=1, workers=2, log_dir=folder,
                                                        progress=progress)
        st = stats[0].summary()
        per_round = sum(points[0]) / max(1, sum(rounds[0]))
        say(f"selftest_bot: {per_round:.3f} pts/round, {st['moves']} moves, "
            f"{st['timeouts']} timeouts, {st['crashes']} crashes")
        ok = st["moves"] > 0 and not st["crashes"] and not st["timeouts"] and per_round > 0
    except Exception:
        say(traceback.format_exc())
    faulthandler.cancel_dump_traceback_later()
    say("PASS" if ok else "FAIL")
    report.close()
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tournament", nargs="?", help="a tournament file to open")
    ap.add_argument("--teams", metavar="MANIFEST", help="load a field of bots from a manifest")
    ap.add_argument("--house", metavar="PY", help="load house bots from a Python file")
    ap.add_argument("--reps", type=int, help="matches per pairing")
    ap.add_argument("--file", metavar="PATH", help="where to save the tournament")
    ap.add_argument("--run", action="store_true", help="start the tournament straight away")
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

    def preload():
        if args.tournament:
            app.load_tournament(args.tournament)
            return
        if args.teams:
            app.load_teams(args.teams)
        if args.house:
            app.load_house(args.house)
        if args.reps:
            app.reps_var.set(str(args.reps))
        if args.file:
            app.file_var.set(args.file)
        if args.run:
            app.run_or_stop()
    root.after(200, preload)
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
