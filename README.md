# ANALYTICA 2026: Integrate and Conquer

The final round of Analytica 2026, run by the Department of Mathematics at
St. Xavier's College (Autonomous), Kolkata. Teams of two had 90 minutes to
write a bot for the **noisy iterated prisoner's dilemma**. Every bot then played
every other bot, and the tournament was replayed live on the projector.

This repository holds everything the event ran on:
- the toolkit the teams used;
- the starter pack and problem statement;
- the flash-drive kit;
- the organisers' show and house bots;
- the CI that built it all.

The event is over and the repository is archived, so it's read-only.

## The game

Each round, both bots choose to cooperate (`C`) or defect (`D`) at the same
time:

|            | They play C | They play D |
|------------|-------------|-------------|
| You play C | 3, 3        | 0, 5        |
| You play D | 5, 0        | 1, 1        |

- **Noise.** Each move has a 7% chance of coming out as the other one. Both bots
  are told what actually happened, so a flipped move can't be told apart from
  a deliberate one.
- **Matches.** A match lasts 150–250 rounds. The bots aren't told how many.
- **The tournament.** Every pair of bots plays 100 matches, with the same match
  lengths and noise for every pairing.
- **Scoring and winners.** A bot's score is its average points per round. The field also had house bots
  written by the organisers. The two highest-scoring team bots won.
- **The bots.** A bot is one source file in Python, Java, C or C++. It talks over
  stdin/stdout, one line per message: `RESET`, `ROUND <mine> <theirs>`, `END`
  in; `C` or `D` out.
- **Limits.** A move gets 50 ms. A crash or a slow move ends the match there,
  and the rounds that bot didn't play score zero.

The full statement is [`starter/problem.typ`](starter/problem.typ)
(`typst compile starter/problem.typ`).

## Two branches

| Branch | Game | Used for |
|---|---|---|
| `ipd` | Noisy iterated prisoner's dilemma | The event |
| `rps` | Rock, paper, scissors, with the same noise | Practice, handed out beforehand |

The practice game let teams learn the tools without learning the real game:
- the protocol;
- checking a bot;
- running tournaments;
- reading the results.

The two branches have the same folders and the same code. They differ only in:
- the game spec: `arena/rules.py`;
- the bots: `arena/sparring.py`, `organizer/`, `starter/templates/`;
- each game's documents.

A practice build is checked so that nothing in it names the real game.

## What's here

| Folder | What it is |
|---|---|
| [`arena/`](arena) | **The Arena**: the teams' toolkit, and the engine it runs on. Add a bot, check it, run a round robin, watch any match round by round, compare two versions of a bot properly. `harness.py` is the engine, `rules.py` the game. |
| [`starter/`](starter) | What teams got: the problem statement, `README.md` for the Arena, and a tit-for-tat template in each of the four languages. |
| [`organizer/`](organizer) | Organisers only: `show.py` (the reveal on the projector), `reference_bots.py` (the house bots), `simbots/` (a simulated field for rehearsals), `testbots/` (bots that break the rules on purpose), manifests, curated highlights and strategy notes. |
| [`kit/`](kit) | The flash-drive kit: the Arena, Python, a JDK and gcc/g++ in one folder, for Windows (`make-kit.ps1`) and macOS (`make-kit-macos.sh`). Nothing to install. See [`kit/README.md`](kit/README.md). |
| [`ci/`](ci) | `local_workflow.py`: the GitHub workflow's steps, run locally after each commit. |
| [`.github/workflows/`](.github/workflows) | The release build: see below. |

## Running it

You need Python 3.12 or later with tkinter. To play bots in other languages,
you also need `javac` and `gcc`/`g++` on the PATH. The flash-drive kit brings
all of that.

**The Arena:**

```bash
python arena/arena.py
```

**A full event tournament:** the teams' bots from a manifest, plus the house
bots, 100 matches per pairing:

```bash
python arena/arena.py --teams manifest.json --house organizer/reference_bots.py --reps 100 --run
```

A manifest lists each team's bot: `{"bots": [{"name": ..., "dir": ..., "run": ...}]}`
(see `organizer/manifest.demo.json`). Every match is saved to a tournament
file (`.jsonl`), so a stopped run carries on where it left off.

**The show**, from a tournament file:

```bash
python organizer/show.py tournament.jsonl --present
```

The show runs in three stages:
1. **Highlights**: a handful of matches, stepped through with →.
2. **The timelapse**: the leaderboard fills in.
3. **The winners.**

Its toolbar sets how many highlights there are, how fast they replay and how
long the timelapse takes. `Highlights…` and `Strategy notes…` load curated
highlights and one-line strategy notes, in the formats of
`organizer/picks.json` and `organizer/notes.json`.

## Builds and releases

Publishing a GitHub release runs [`build-arena.yml`](.github/workflows/build-arena.yml)
on Windows, on that release's branch. It:
1. Checks that a practice build doesn't name the real game.
2. Builds every template and plays it.
3. Builds `Arena.exe` and the show's `Show.exe` with PyInstaller, and
   self-tests both.
4. Builds the flash-drive kit and tests it.
5. Attaches everything to the release.

| Release | Branch | Files |
|---|---|---|
| `ipd-v1.0`, IPD Final | `ipd` | `Arena.zip`, `Arena-Kit.zip` (Windows kit), `Show.exe` |
| `rps-v0.3` | `rps` | `Arena.zip`, `Arena-Kit.zip` (Windows kit), `Arena-Kit-macOS.zip` |

The macOS kit is built by hand with `kit/make-kit-macos.sh`.
