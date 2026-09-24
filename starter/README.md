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

| Language | Template |
|---|---|
| Python | `python/my_bot.py` |
| Java | `java/MyBot.java` |
| C | `c/my_bot.c` |
| C++ | `cpp/my_bot.cpp` |

Each one is short, handles the protocol, and plays tit-for-tat: cooperate
first, then copy the opponent's last move. Copy the one for your language and
rewrite `choose()`, which is where the move is picked. Keep your bot in that
one file: it is what you submit. In Java, any extra classes go inside
`MyBot.java`.

## The Arena

Open `Arena.exe`. On the left is the board: every bot in the field. Beside it
is a panel whose tabs follow what you pick on the board (click a bot to pick
it, click it again to let go), and under that the log.

**+ Add bot** — pick your bot's source file (`.py`, `.java`, `.c` or `.cpp`);
you can select several at once. Java, C and C++ are compiled for you, the same
way the tournament compiles them. Right-click a bot to change its run command.

**Check** — pick your bot and open the **Check** tab: its **Check** button
plays your bot against the sparring partners and shows what, if anything, is
wrong, starting with the most common problem, a bot that doesn't flush stdout.
With nothing picked, **Check all** there checks every bot you added.

**Results** — after a run, the board shows every bot's points per round with a
confidence interval, and how often it cooperated. Pick a bot for its record
against each opponent. Pick two to compare them properly: they are judged on
the opponents they both faced, with the same noise, so luck doesn't muddy the
comparison. It tells you whether one really scores more, or whether you simply
haven't played enough matches to know. Use this before believing that your
latest tweak helped.

**Matches** — every match played, or only the picked bot's, or only the ones
between two picked bots. Click one to see it round by round, with the moves
noise flipped marked. Hover over a round to see what each side chose.

**Keep this version** freezes your bot as it is now: a copy joins the field as
a fixed opponent, `my_bot (v1)`, and stays exactly like that while you carry
on editing. After every run, the panel beside the board compares your bot
with the version you kept last, and says whether the change really helped or
whether you haven't played enough matches to know. Keep a version before each
big change. The copies are saved in a `versions` folder beside your bot.

**Run tournament** plays everyone against everyone: your bots plus sparring
partners (always-cooperate, always-defect, random, tit-for-tat, generous
tit-for-tat, Pavlov, grudger, tit-for-two-tats and suspicious tit-for-tat).
**Options** holds the rest: how many matches each pairing plays, the seed, and
where the tournament file is saved. Every match is saved to that file, so you
can close the Arena and open the results again later.

Anything your bot prints to stderr is saved to a log file; the Arena says where
after each run.

Run the Arena from the flash-drive kit: it brings Python, Java, C and C++
with it, so there is nothing to install and nothing to compile by hand. Add
your source file and the Arena builds and runs it the same way the tournament
does.

Scoring well against the sparring partners tells you little about the real
field. The tournament includes the other teams and some opponents that aren't
in this pack.
