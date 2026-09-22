# Starter pack

Your bot is a program that reads commands on stdin and writes moves on stdout.
It can be in any allowed language. The tournament starts it **once** and keeps
it running for the whole tournament.

## Protocol

One message per line.

| Direction | Message | Meaning |
|---|---|---|
| → bot | `RESET` | New match against a new opponent. Clear all per-match state. |
| → bot | `ROUND - -` | First round of a match. No history yet. |
| → bot | `ROUND <mine> <theirs>` | The previous round's **actual** moves, after noise. |
| ← bot | `C` or `D` | Your move for this round. |
| → bot | `END` | Tournament over. Exit. |

- **Flush stdout after every move.** If you don't, your bot hangs and forfeits
  every round. Here's how to flush in each language:
  - Python: `print(move, flush=True)`
  - Java: `System.out.println(move); System.out.flush();`
  - C++: `std::cout << move << std::endl;` (`"\n"` alone does not flush)
- **stdout is for moves only.** Print debug output to stderr.
- **Keeping state across matches is against the rules.** Clear everything on `RESET`.
- **Timing:** a move that takes more than 50 ms forfeits the round. A
  forfeited round is played as `D` and scores you 0. Aim for well under 1 ms
  on average: every bot makes hundreds of thousands of moves, and the
  tournament has to finish in minutes.
- Exit when stdin closes, as well as on `END`.

## Getting started

The `templates` folder has a working bot in Python and in Java. Each one
already handles the protocol and plays generous tit-for-tat. Tit-for-tat and
Pavlov are included too. Copy the one for your language and change how it
chooses its move.

## The Arena

Open `Arena.exe`. It has five views:

**Bots** — click **+ Add bot** and pick your bot's main file (`.py`, `.java`,
`.cpp`, …); you can select several at once. Then click **Check**: this catches
the most common problem, a bot that doesn't flush stdout. Java and C++ are
compiled for you before each run. Right-click a bot to change its run command.

**Run** — play everyone against everyone: your bots, plus sparring partners
(always-cooperate, always-defect, random, tit-for-tat, generous tit-for-tat,
Pavlov, grudger, tit-for-two-tats and suspicious tit-for-tat). Set how many
matches each pairing plays. Every match is saved to a tournament file, so you
can close the Arena and open the results again later.

**Standings** — the final table, each bot's points per round with a confidence
interval, and how cooperative it was. Click a bot to see how it did against
each opponent.

**Statistics** — click two bots to compare them properly. They are judged on
the opponents they both faced, with the same noise, so the comparison isn't
muddied by luck. It tells you whether one really scores more, or whether you
simply haven't played enough matches to know, and how many more it would take.
Use this before believing that your latest tweak helped.

**Explorer** — every match played. Click one to watch it round by round, with
the moves noise flipped marked. Hover over a round to see what each side chose.

Anything your bot prints to stderr is saved to a log file; the Arena says where
after each run.

The Arena runs your bot the same way the tournament does, so your bot needs
its language's tools installed:

- **Python:** nothing to install, but Python 3 from python.org also works.
- **Java:** a JDK, with `java` and `javac` on your PATH.
- **C++:** `g++` on your PATH.

Scoring well against the sparring partners tells you little about the real
field. The tournament includes the other teams and some opponents that aren't
in this pack.
