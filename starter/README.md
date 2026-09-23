# Starter pack

Your bot is one source file in Python, Java, C or C++: a program that reads
commands on stdin and writes moves on stdout. The tournament starts it
**once** and keeps it running for the whole tournament.

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
  - C: `printf("%c\n", move); fflush(stdout);`
  - C++: `std::cout << move << std::endl;` (`"\n"` alone does not flush)
- **stdout is for moves only.** Print debug output to stderr.
- **Keeping state across matches is against the rules.** Clear everything on `RESET`.
- **Timing:** a move that takes more than 50 ms forfeits the round. A
  forfeited round is played as `D` and scores you 0. Aim for well under 1 ms
  on average: every bot makes hundreds of thousands of moves, and the
  tournament has to finish in minutes.
- Exit when stdin closes, as well as on `END`.

## Getting started

The `templates` folder has a working bot in each language:

| Language | Template | Built with |
|---|---|---|
| Python | `python/my_bot.py` | nothing to build |
| Java | `java/MyBot.java` | `javac MyBot.java` |
| C | `c/my_bot.c` | `gcc -O2 -o my_bot my_bot.c -lm` |
| C++ | `cpp/my_bot.cpp` | `g++ -O2 -std=c++17 -o my_bot my_bot.cpp` |

Each one already handles the protocol and plays generous tit-for-tat.
Tit-for-tat and Pavlov are included too. Copy the one for your language and
change how it chooses its move. Keep your bot in that one file: it is what you
submit. In Java, any extra classes go inside `MyBot.java`.

## The Arena

Open `Arena.exe`. It has three tabs:

**Bots** — click **+ Add bot** and pick your bot's source file (`.py`,
`.java`, `.c` or `.cpp`); you can select several at once. Then click
**Check**: this catches the most common problem, a bot that doesn't flush
stdout. Java, C and C++ are compiled for you, the same way the tournament
compiles them. Right-click a bot to change its run command.

**Results** — after a run, every bot's points per round with a confidence
interval, and how often it cooperated. Click a bot for its record against each
opponent. Click two bots to compare them properly: they are judged on the
opponents they both faced, with the same noise, so luck doesn't muddy the
comparison. It tells you whether one really scores more, or whether you simply
haven't played enough matches to know. Use this before believing that your
latest tweak helped.

**Matches** — every match played. Click one to watch it round by round, with
the moves noise flipped marked. Hover over a round to see what each side chose.

**Run tournament** plays everyone against everyone: your bots plus sparring
partners (always-cooperate, always-defect, random, tit-for-tat, generous
tit-for-tat, Pavlov, grudger, tit-for-two-tats and suspicious tit-for-tat).
**Options** holds the rest: how many matches each pairing plays, the seed, and
where the tournament file is saved. Every match is saved to that file, so you
can close the Arena and open the results again later.

Anything your bot prints to stderr is saved to a log file; the Arena says where
after each run.

The Arena runs your bot the same way the tournament does, so your bot needs
its language's tools installed:

- **Python:** nothing to install, but Python 3 from python.org also works.
- **Java:** a JDK, with `java` and `javac` on your PATH.
- **C and C++:** `gcc` and `g++` on your PATH (MinGW-w64 on Windows).

If you are using the flash-drive kit, all of these come with it.

Scoring well against the sparring partners tells you little about the real
field. The tournament includes the other teams and some opponents that aren't
in this pack.
