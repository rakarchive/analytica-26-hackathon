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

Open `Arena.exe` to test your bot:

1. Click **+ Add bot** and pick your bot's main file (`.py`, `.java`, `.cpp`, …).
   The Arena picks a run command and compiles Java and C++ for you before
   each run. To change the run command, right-click your bot on the board.
2. Click **Check**. This catches the most common problem: a bot that
   doesn't flush stdout.
3. Click **Run tournament**. Your bots play a set of sparring partners:
   always-cooperate, always-defect, random, tit-for-tat, generous tit-for-tat,
   Pavlov, grudger, tit-for-two-tats and suspicious tit-for-tat. The board
   fills in live, and the stages replay matches as they finish. Afterwards,
   click any row to see its score against each opponent.
4. To watch a particular match, click two rows on the board, then click
   **Watch**. The replay marks the moves that noise flipped. Once it
   finishes, hover over a round to see what each side chose.

You can add several bots, for example two versions of your own, and they
play each other as well. Anything your bot prints to stderr is saved to a log
file; the Arena tells you where after each tournament.

The Arena runs your bot the same way the tournament does, so your bot needs
its language's tools installed:

- **Python:** Python 3 from python.org.
- **Java:** a JDK, with `java` and `javac` on your PATH.
- **C++:** `g++` on your PATH.

Scoring well against the sparring partners tells you little about the real
field. The tournament includes the other teams and some opponents that aren't
in this pack.
