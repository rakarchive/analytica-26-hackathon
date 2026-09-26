"""The show: open a tournament file and perform the reveal.

    python show.py [tournament.jsonl] [--present]

Without a file it asks for one when it starts.

The matches were all played beforehand by the Arena, so nothing is computed
here: this is a player. It goes

  1. Highlights   a handful of matches worth watching, chosen from the whole
                  tournament, stepped through by hand with →. The standings
                  stay hidden, so nobody knows who won yet.
  2. Timelapse    the leaderboard fills from empty, cycle by cycle, bars
                  racing, with a shout whenever the top two change.
  3. The winner   champion and runner-up.

The toolbar sets how many highlights there are, how fast they replay and
how long the timelapse takes; the settings are remembered between runs.

Keys:  SPACE start/pause · → next · H house bot names · L log · Esc leave
       presentation · F11 fullscreen
"""

import argparse
import json
import os
import sys
import tempfile
import time
import tkinter as tk
from tkinter import filedialog
from tkinter import font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "arena"))

import finder  # noqa: E402
import harness  # noqa: E402
from ui import *  # noqa: E402,F401,F403
from ui import (BG, DIM, DOWN, FAINT, FG, GLOW, LINE, MEDALS, PANEL, PANEL2, UP, WARN,  # noqa: E402
                BaseApp, FlatButton, Stage)


def mix(c1, c2, t):
    """Blend two #rrggbb colours: t=0 gives c1, t=1 gives c2."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[k:k + 2], 16) for k in (1, 3, 5)]
    b = [int(c2[k:k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


# The presentation's settings, from the toolbar: (default, lowest, highest).
SETTINGS = {"highlights": (10, 0, 30),       # matches shown before the winner's, unless curated
            "speed": (45, 5, 400),           # rounds per second, replaying a highlight
            "timelapse": (90, 10, 600)}      # seconds for the leaderboard to fill
# Remembered between runs, so a restart on the day keeps them.
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".analytica-show.json")


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    return {k: saved.get(k, d) if isinstance(saved.get(k), (int, float)) else d
            for k, (d, _, _) in SETTINGS.items()}


class Show(BaseApp):
    """A player: no engine, no bots, just the file and the reveal."""

    TITLE = "ANALYTICA - INTEGRATE AND CONQUER"

    def __init__(self, root, tour=None, highlights=None, timelapse=None, speed=None, save=True):
        values = load_settings()
        for k, v in (("highlights", highlights), ("timelapse", timelapse), ("speed", speed)):
            if v is not None:
                values[k] = v
        self.save_settings = save
        self.setting_vars = {k: tk.StringVar(root, value=f"{v:g}") for k, v in values.items()}
        self.tour = None
        self.show_log = False        # the log is behind a disclosure (L)
        self.toasts = []             # [text, color, kind, shown_at]
        self.phase = "empty"         # empty, ready, highlights, timelapse, final
        self.highlights, self.hl_idx, self.hl_title = [], 0, ""
        self.queue = []              # matches still to apply in the timelapse
        self.budget = 0.0
        self.champion_pending = None
        self._panel_at = 0.0
        self.champ_index = None
        self.picks_path = None     # curated highlights, if any
        self.notes = {}            # bot name -> what it plays, one line
        self.top2, self.top2_cand = None, (None, 0.0)
        super().__init__(root)
        for key, fn in (("<space>", self.space), ("<Right>", self.advance), ("<Return>", self.advance),
                        ("<Key-h>", self.toggle_house), ("<Key-l>", self.toggle_log)):
            root.bind(key, lambda e, fn=fn: fn())
        for var in self.setting_vars.values():
            var.trace_add("write", lambda *_: self._settings_changed())
        if tour:
            self.open(tour)

    # ---------------- setup ----------------

    def setting(self, key):
        """A setting's value, kept in range; the default while a box holds
        something that isn't a number (half-typed, say)."""
        default, lo, hi = SETTINGS[key]
        try:
            return max(lo, min(hi, float(self.setting_vars[key].get())))
        except ValueError:
            return default

    @property
    def highlight_count(self):
        return int(self.setting("highlights"))

    @property
    def timelapse_secs(self):
        return self.setting("timelapse")

    def _settings_changed(self):
        if self.save_settings:
            try:
                with open(SETTINGS_FILE, "w") as f:
                    json.dump({k: self.setting(k) for k in SETTINGS}, f)
            except OSError:
                pass
        if self.phase == "highlights":
            self.rps = self.setting("speed")
        if self.tour and self.phase == "ready" and not self.picks_path:
            self._pick_highlights()
            self._ready_hint()

    def _build_toolbar(self, tb):
        f = tk.Frame(tb, bg=BG)
        f.pack(fill="x")
        FlatButton(f, "Open tournament…", self.open_dialog).pack(side="left", padx=(0, 8))
        FlatButton(f, "Highlights…", self.open_picks_dialog).pack(side="left", padx=(0, 8))
        FlatButton(f, "Strategy notes…", self.open_notes_dialog).pack(side="left", padx=(0, 8))
        self.buttons["start"] = FlatButton(f, "▶  Present", self.start, primary=True)
        self.buttons["start"].pack(side="left", padx=(0, 12))
        self.hint = self._label(f, "Open a tournament file saved by the Arena.", FAINT)
        self.hint.pack(side="left")

        f = tk.Frame(tb, bg=BG)
        f.pack(fill="x", pady=(10, 0))
        for key, label, unit, inc in (
                ("highlights", "Highlights", "matches, then the winner's best", 1),
                ("speed", "Replay speed", "rounds a second", 5),
                ("timelapse", "Leaderboard timelapse", "seconds", 10)):
            _, lo, hi = SETTINGS[key]
            self._label(f, label).pack(side="left")
            self._spin(f, self.setting_vars[key], lo, hi, inc=inc, width=4).pack(side="left", padx=(6, 4))
            self._label(f, unit, FAINT).pack(side="left", padx=(0, 18))

    def _refresh_buttons(self):
        if "start" in self.buttons:
            self.buttons["start"].set_enabled(self.tour is not None)

    def settings(self):
        return {"seed": None, "workers": 1, "self_play": False, "ref_weight": 1.0,
                "out": "", "show_minutes": 0.0, "stage_speed": 40.0}

    def open_picks_dialog(self):
        """Curated highlights: which matches to show, with the words to go
        with them. Without one, the show picks its own."""
        path = filedialog.askopenfilename(title="Open curated highlights",
                                          filetypes=[("Highlights", "*.json"), ("All files", "*.*")])
        if path:
            self.picks_path = path
            if self.tour:
                self._pick_highlights()
                self._ready_hint()
                self.layout()

    def open_notes_dialog(self):
        path = filedialog.askopenfilename(title="Open strategy notes",
                                          filetypes=[("Notes", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self.notes = {k: (v if isinstance(v, str) else v.get("label", ""))
                          for k, v in (data.get("bots", data)).items()}
        except (OSError, ValueError, AttributeError) as e:
            self.log(f"Could not read {os.path.basename(path)}: {e}", DOWN)
            return
        self.log(f"Strategy notes for {len(self.notes)} bots.", UP)
        self.layout()

    def _pick_highlights(self):
        """Curated highlights if a file was given, otherwise the finder's."""
        auto = finder.find_highlights(self.tour, self.highlight_count, champion=self.champ_index)
        picks = [{"title": p["title"], "match": p["match"], "captions": None, "focus": None}
                 for p in auto]
        if self.picks_path:
            try:
                with open(self.picks_path) as f:
                    data = json.load(f)
                by_key = {(m["i"], m["j"], m["r"]): m for m in self.tour.matches}
                curated = []
                for item in data.get("highlights", data):
                    m = (self.tour.matches[item["index"]] if "index" in item
                         else by_key.get((item["i"], item["j"], item["r"])))
                    if m is None:
                        self.log(f"Highlight not found in this tournament: {item}", WARN)
                        continue
                    curated.append({"title": item.get("title", "A match worth seeing"), "match": m,
                                    "captions": item.get("commentary"), "focus": item.get("focus")})
                if curated:
                    picks = curated
                    self.log(f"{len(curated)} curated highlights from "
                             f"{os.path.basename(self.picks_path)}.", UP)
            except (OSError, ValueError, KeyError, TypeError) as e:
                self.log(f"Could not read the highlights file: {e}", DOWN)
        self.highlights = picks
        self.hl_idx = 0

    def open_dialog(self):
        # Start where the Arena saves its tournaments, if it has saved any.
        arena_dir = os.path.join(tempfile.gettempdir(), "arena-tournaments")
        path = filedialog.askopenfilename(title="Open a tournament file",
                                          initialdir=arena_dir if os.path.isdir(arena_dir) else None,
                                          filetypes=[("Tournament", "*.jsonl *.gz"),
                                                     ("All files", "*.*")])
        return bool(path) and self.open(path)

    def open(self, path):
        tour = harness.TournamentFile.load(path)
        if not tour:
            self.log(f"{path} is not a tournament file.", DOWN)
            return False
        if tour.header.get("game", harness.GAME.key) != harness.GAME.key:
            self.log(f"{os.path.basename(path)} is a {tour.header['game']} tournament, "
                     f"and this show plays {harness.GAME.key}.", DOWN)
            return False
        if not tour.has_moves():
            self.log("That file has no moves in it, so there is nothing to replay.", DOWN)
            return False
        self.specs = [dict(b) for b in tour.bots]
        self._reset_standings()      # clears the standings, and self.tour with them
        self.tour = tour
        self.hide_house = True

        # The final standings decide the champion, and the champion decides
        # one of the highlights. Worked out now, shown at the very end.
        points, rounds = tour.totals()
        rows = harness.score_rows(self.specs, points, rounds, tour.stats_objects(), 1.0)
        teams = [r for r in rows if r["kind"] == "team"]
        champ = next((i for i, s in enumerate(self.specs)
                      if teams and s["name"] == teams[0]["name"]), None)
        self.champion_pending = self.display_name(champ) if champ is not None else None
        self.runner_up = (self.display_name(next(i for i, s in enumerate(self.specs)
                                                 if s["name"] == teams[1]["name"]))
                          if len(teams) > 1 else None)
        self.champ_index = champ
        self._pick_highlights()
        self.phase = "ready"
        self.queue = tour.in_cycles()
        self.total = len(self.queue)
        self.log(f"{os.path.basename(path)}: {len(tour):,} matches, {tour.n} bots, "
                 f"{tour.reps} per pairing. {len(self.highlights)} highlights ready.", UP)
        self._ready_hint()
        self.layout()
        self._refresh_buttons()
        return True

    def _ready_hint(self):
        self.hint.config(text=f"{len(self.highlights)} highlights, then the timelapse. Press Present.")

    # ---------------- running the show ----------------

    def start(self):
        if not self.tour:
            return
        self.present(True)
        self.phase = "highlights"
        self.rps = self.setting("speed")
        self.notify(f"{len(self.highlights)} matches worth watching. Press → for each one",
                    MEDALS[1], kind="phase")
        self.advance()

    def present(self, on=True):
        self.presenting = on
        self.root.attributes("-fullscreen", on)
        self.layout()

    def _escape(self):
        if self.presenting:
            self.present(False)
        else:
            super()._escape()

    def toggle_house(self):
        self.hide_house = not self.hide_house
        if self.hide_house is False:
            self.notify("House bots revealed", FG, kind="phase")
        self.layout()

    def space(self):
        if self.phase == "ready":
            self.start()
        elif self.phase == "timelapse":
            self.state = "paused" if self.state != "paused" else "running"
        elif self.phase == "highlights":
            self.advance()

    def advance(self):
        """→ : the next highlight, then the timelapse."""
        if self.phase == "highlights":
            if self.hl_idx < len(self.highlights):
                pick = self.highlights[self.hl_idx]
                self.hl_idx += 1
                self.hl_title = pick["title"]
                m = pick["match"]
                self.stages[0].start((m["i"], m["j"], m["pa"], m["pb"], m["n"], (m["a"], m["b"]),
                                      *harness.match_rounds(m), m.get("end")),
                                     pinned=True,
                                     title=f"{self.hl_idx} of {len(self.highlights)} · {pick['title']}",
                                     labels=(self.notes.get(self.tour.names[m["i"]]),
                                             self.notes.get(self.tour.names[m["j"]])),
                                     captions=pick.get("captions"), focus=pick.get("focus"))
            else:
                self.begin_timelapse()
        elif self.phase == "ready":
            self.start()

    def begin_timelapse(self):
        self.phase = "timelapse"
        self.state = "running"
        self.stages[0].clear()
        self.applied = 0
        self.budget = 0.0
        self.started = time.perf_counter()
        # Fixed from the start: recomputing from what is left would slow down
        # for ever and never finish.
        self.rate = len(self.queue) / max(1.0, self.timelapse_secs)
        self.notify("And now the standings, from the first match to the last", MEDALS[1], kind="phase")
        self.layout()

    def _advance(self, dt):
        if self.phase == "timelapse" and self.state == "running":
            self.budget = min(self.budget + self.rate * dt, self.rate * 0.5 + 1)
            k = min(int(self.budget), len(self.queue))
            self.budget -= k
            for _ in range(k):
                m = self.queue.pop(0)
                self.apply((m["i"], m["j"], m["pa"], m["pb"], m["n"], (m["a"], m["b"]),
                            *harness.match_rounds(m), m.get("end")))
            if not self.queue:
                self.finish_show()
            elif time.perf_counter() - self._panel_at > 0.2:
                self._panel_at = time.perf_counter()
                self.cv.delete("panel")          # the counters have moved on
                self._draw_progress(*self.card_box)
        for st in self.stages:
            st.step(dt, self.rps)
        self._draw_toasts()

    def finish_show(self):
        self.phase = "final"
        self.state = "final"
        self.champion = self.champion_pending
        self.notify(f"★ Champion: {self.champion}"
                    + (f"   ·   Runner-up: {self.runner_up}" if self.runner_up else ""), MEDALS[1])
        self.layout()

    def _ranks_changed(self, ranks, now):
        if self.phase != "timelapse" or not self.applied or len(ranks) < 2:
            return
        top2 = tuple(sorted(ranks, key=ranks.get)[:2])
        if top2 != self.top2_cand[0]:
            self.top2_cand = (top2, now)
        elif top2 != self.top2 and now - self.top2_cand[1] >= 1.0:
            self._announce_top2(self.top2, top2)
            self.top2 = top2

    def on_board(self, i):
        """Anonymous house bots stay off the board until H reveals them."""
        return not (self.hide_house and self.specs[i]["kind"] == "ref")

    def note(self, text, color, toast=False):
        if toast:
            self.notify(text, color)
        else:
            self._append_log(text, color)

    # ---------------- layout ----------------

    def _layout_content(self, W, H, top, m):
        self.board = None
        avail = H - top - m
        log_h = avail * 0.25 if self.show_log else 0.0
        body = avail - (log_h + m / 2 if self.show_log else 0.0)
        if self.phase in ("timelapse", "final"):
            bw = W * 0.74
            self.board = (m, top, bw - m / 2, top + body)
            self.card_box = (bw + m / 2, top, W - m - (bw + m / 2), body)
            self._layout_board()
            if self.phase == "final":
                self._draw_champion()
            else:
                self._draw_progress(*self.card_box)
        else:
            self.card_box = (m, top, W - 2 * m, body)
            self.stages[0].layout(*self.card_box)
        self.log_box = (m, top + body + m / 2, W - 2 * m, log_h)
        self.log_win = self.cv.create_window(m, self.log_box[1], window=self.logbox, anchor="nw",
                                             width=W - 2 * m, height=max(1, log_h),
                                             state="normal" if self.show_log else "hidden")

    def _draw_progress(self, x, y, w, h):
        cv, s = self.cv, self.scale
        cv.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=LINE, tags="panel")
        done = self.applied
        cycle = (self.queue[0]["r"] + 1) if self.queue else self.tour.reps
        cv.create_text(x + w / 2, y + h * 0.30, text=f"Cycle {cycle}", fill=FG, font=self.f_champ,
                       tags="panel")
        cv.create_text(x + w / 2, y + h * 0.40, text=f"of {self.tour.reps}", fill=DIM,
                       font=self.f_stage_name, tags="panel")
        bar = (x + 30 * s, y + h * 0.52, x + w - 30 * s, y + h * 0.55)
        cv.create_rectangle(*bar, fill=PANEL2, width=0, tags="panel")
        cv.create_rectangle(bar[0], bar[1], bar[0] + (bar[2] - bar[0]) * done / max(1, self.total),
                            bar[3], fill=UP, width=0, tags="panel")
        cv.create_text(x + w / 2, y + h * 0.63, text=f"{done:,} of {self.total:,} matches",
                       fill=DIM, font=self.f_card_label, tags="panel")

    def _draw_overlays(self):
        self._draw_toasts(force=True)

    def stage_hint(self):
        if self.phase == "empty":
            return "Open a tournament file saved by the Arena"
        if self.phase == "ready":
            return f"{len(self.highlights)} highlights, then the timelapse\nPress SPACE to begin"
        if self.phase == "highlights":
            return "Press → for the next highlight"
        return ""

    def _status_text(self):
        if self.phase == "highlights":
            return (f"HIGHLIGHTS · {self.hl_idx} of {len(self.highlights)}"
                    + (f" · {self.hl_title}" if self.hl_idx else "") + " · press → for the next")
        if self.phase == "timelapse":
            left = max(0.0, self.timelapse_secs - (time.perf_counter() - self.started))
            return (f"{'PAUSED · ' if self.state == 'paused' else ''}"
                    f"{self.applied:,} / {self.total:,} matches · {left:.0f}s")
        if self.phase == "final":
            return f"FINAL · {self.total:,} matches"
        if self.tour:
            return f"{len(self.tour):,} matches · ready"
        return "no tournament open"

    def _progress(self):
        if self.phase in ("timelapse", "final"):
            f = self.applied / max(1, self.total)
            return f, f
        if self.phase == "highlights":
            f = self.hl_idx / max(1, len(self.highlights))
            return f, f
        return 0.0, 0.0

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
            note = self.notes.get(self.specs[order[0]]["name"])
            if note:
                cv.create_text(x + w / 2, y + h * 0.49, text=note, fill=GLOW, width=w - 60 * self.scale,
                               justify="center", font=self.f_card_label, tags="champ")
        if len(order) > 1:
            cv.create_text(x + w / 2, y + h * 0.60, text="RUNNER-UP", fill=MEDALS[2],
                           font=self.f_stage_name, tags="champ")
            cv.create_text(x + w / 2, y + h * 0.72, text=self.display_name(order[1]), fill=FG,
                           font=self.f_champ, tags="champ")
            cv.create_text(x + w / 2, y + h * 0.83, text=f"{self.score(order[1]):.3f} points per round",
                           fill=DIM, font=self.f_card_label, tags="champ")

    def toggle_log(self):
        self.show_log = not self.show_log
        self.layout()

    def _unused_set_hide_house(self):
        self.hide_house = self.hide_house_var.get()
        if self.rows:
            self.layout()


def selftest(report_path, tournament):
    """A check of a packaged build, for CI: open the file (the Arena's
    self-test saves one), step through every highlight and play the timelapse
    to the champion, in the real window with the real event loop. A windowed
    exe has no console, so the result goes to a file, written as it goes."""
    import traceback
    ok = False
    report = open(report_path, "w", buffering=1)
    try:
        root = tk.Tk()
        app = Show(root, None, highlights=3, timelapse=10, save=False)
        if not app.open(tournament):
            raise RuntimeError(f"could not open {tournament}")
        report.write(f"game: {harness.GAME.key} · {len(app.tour)} matches, "
                     f"{len(app.highlights)} highlights\n")
        # Present when a person would: once the window is on screen.
        deadline = time.perf_counter() + 20
        while app.cv.winfo_width() < 50 and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        report.write(f"window: {app.cv.winfo_width()}x{app.cv.winfo_height()}\n")
        app.start()
        deadline = time.perf_counter() + 60
        while app.phase != "final" and time.perf_counter() < deadline:
            if app.phase == "highlights":
                app.advance()
            for _ in range(20):
                root.update()
                time.sleep(0.01)
        report.write(f"reached: {app.phase} · champion: {app.champion}\n")
        ok = app.phase == "final" and app.champion is not None and app.highlights
        root.destroy()
    except Exception:
        report.write(traceback.format_exc())
    report.write("PASS\n" if ok else "FAIL\n")
    report.close()
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tournament", nargs="?", help="a tournament file saved by the Arena")
    ap.add_argument("--highlights", type=int, help="how many matches to show")
    ap.add_argument("--speed", type=float, help="rounds a second, replaying a highlight")
    ap.add_argument("--timelapse", type=float, help="seconds for the leaderboard")
    ap.add_argument("--present", action="store_true", help="go straight to fullscreen")
    ap.add_argument("--selftest", metavar="REPORT", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest(args.selftest, args.tournament))
    root = tk.Tk()
    app = Show(root, args.tournament, args.highlights, args.timelapse, args.speed)
    if app.tour:
        if args.present:
            root.after(300, lambda: app.present(True))
    else:
        # No file given: ask for one as soon as the window is up.
        root.after(200, lambda: app.open_dialog() and args.present and app.present(True))
    root.mainloop()


if __name__ == "__main__":
    main()
