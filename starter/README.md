# Practice pack

This is the Arena you will use on the day, running a throwaway game: rock,
paper, scissors. The game on the day is different and is not this one. What
carries over is everything around it — how your bot talks to the Arena, how
you check it, how you run matches and read the results — which is exactly the
part you do not want to be learning when the clock is running.

Get your bot talking to the Arena now, in the language you plan to use, on the
machine you plan to use. On the day you change how your bot chooses a move,
and nothing else.

Your bot is one source file in Python, Java, C or C++: a program that reads
commands on stdin and writes moves on stdout. The Arena starts it **once**
and keeps it running for the whole tournament.

## Protocol

One message per line.

| Direction | Message | Meaning |
|---|---|---|
| → bot | `RESET` | New match against a new opponent. Clear all per-match state. |
| → bot | `ROUND - -` | First round of a match. No history yet. |
| → bot | `ROUND <mine> <theirs>` | The previous round's **actual** moves, after noise. |
| ← bot | a move | Your move for this round: `R`, `P` or `S` here. |
| → bot | `END` | Tournament over. Exit. |

- **Flush stdout after every move.** If you don't, your bot hangs and forfeits
  every round. Here's how to flush in each language:
  - Python: `print(move, flush=True)`
  - Java: `System.out.println(move); System.out.flush();`
  - C: `printf("%c\n", move); fflush(stdout);`
  - C++: `std::cout << move << std::endl;` (`"\n"` alone does not flush)
- **stdout is for moves only.** Print debug output to stderr.
- **Keeping state across matches is against the rules.** Clear everything on `RESET`.
- **Timing:** a move that takes more than 50 ms forfeits the round. Aim for
  well under 1 ms on average: every bot makes hundreds of thousands of moves.
- Exit when stdin closes, as well as on `END`.

**Why you are told your own move.** Moves are noisy: sometimes what comes out
is not what you sent. `<mine>` is what you actually played, which may differ
from what you chose. The same is true on the day, so write your bot to read
its own history rather than assume it.

## Getting started

The `templates` folder has a working bot in each language:

| Language | Template |
|---|---|
| Python | `python/my_bot.py` |
| Java | `java/MyBot.java` |
| C | `c/my_bot.c` |
| C++ | `cpp/my_bot.cpp` |

Each one is short, handles the protocol, and plays rock first, then whatever
beats the opponent's last move. Copy the one for your language and rewrite
`choose()`, which is where the move is picked. Keep your bot in that one
file: it is what you submit. In Java, any extra classes go inside
`MyBot.java`.

## The Arena

Open `Arena.exe`. It has two tabs:

**Bots** — click **+ Add bot** and pick your bot's source file (`.py`,
`.java`, `.c` or `.cpp`); you can select several at once. Then click
**Check**: this catches the most common problem, a bot that doesn't flush
stdout. Java, C and C++ are compiled for you, the same way the tournament
compiles them. Right-click a bot to change its run command.

**Keep this version** freezes your bot as it is now: a copy joins the field as
a fixed opponent, `my_bot (v1)`, and stays exactly like that while you carry
on editing. After every run, the panel beside the board compares your bot
with the version you kept last, and says whether the change really helped or
whether you haven't played enough matches to know. Keep a version before each
big change. The copies are saved in a `versions` folder beside your bot.

**After a run**, the board shows every bot's points per round with a confidence
interval. Click a bot for its record against each opponent. Click two bots to
compare them properly: same opponents, same noise, and a verdict on whether
the difference is real or whether you simply haven't played enough matches.

**Matches** — every match played. Click one to see it round by round, with
the moves noise changed marked. Hover over a round for the details.

**Run tournament** plays everyone against everyone: your bots plus sparring
partners (always-rock, random, a cycler, a mirror, beat-your-last and
beat-your-favourite). **Options** holds the rest: how many matches each
pairing plays, the seed, and where the tournament file is saved.

Anything your bot prints to stderr is saved to a log file; the Arena says where
after each run.

Run the Arena from the flash-drive kit: it brings Python, Java, C and C++
with it, so there is nothing to install and nothing to compile by hand. Add
your source file and the Arena builds and runs it the same way the tournament
does.
