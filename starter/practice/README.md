# Practice pack

This is the Arena you will use on the day, running a throwaway game: rock,
paper, scissors. The game on the day is different and is not this one. What
carries over is everything around it — how your bot talks to the Arena, how
you check it, how you run matches and read the results — which is exactly the
part you do not want to be learning when the clock is running.

The `templates` folder has a working bot in each language. Copy the one for
yours.

Get your bot talking to the Arena now, in the language you plan to use, on the
machine you plan to use. On the day you change how your bot chooses a move,
and nothing else.

## Protocol

Your bot is one source file in Python, Java, C or C++: a program that reads
commands on stdin and writes moves on stdout. The Arena starts it **once** and keeps it running for the whole tournament.
One message per line.

| Direction | Message | Meaning |
|---|---|---|
| → bot | `RESET` | New match against a new opponent. Clear all per-match state. |
| → bot | `ROUND - -` | First round of a match. No history yet. |
| → bot | `ROUND <mine> <theirs>` | The previous round's **actual** moves. |
| ← bot | a move | Your move for this round: `R`, `P` or `S` here. |
| → bot | `END` | Tournament over. Exit. |

- **Flush stdout after every move.** If you don't, your bot hangs and forfeits
  every round. This is the single most common way to lose a hackathon hour:
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

## The Arena

Open `Arena.exe`. It has three tabs:

**Bots** — click **+ Add bot** and pick your bot's source file (`.py`, `.java`,
`.c` or `.cpp`); you can select several at once. Then click **Check**. Java, C
and C++ are compiled for you. Right-click a bot to change its run command.

**Results** — after a run, every bot's points per round with a confidence
interval. Click a bot for its record against each opponent, two bots to
compare them properly: same opponents, same noise, and a verdict on whether
the difference is real or whether you simply haven't played enough matches.

**Matches** — every match played. Click one to watch it round by round, with
the moves noise changed marked. Hover over a round for the details.

**Run tournament** plays your bots against the sparring partners. Options
holds the rest: how many matches per pairing, the seed, and where the
tournament file is saved.

## What you need installed

- **Python:** nothing, the Arena has its own. Python 3 from python.org also works.
- **Java:** a JDK, with `java` and `javac` on your PATH.
- **C and C++:** `gcc` and `g++` on your PATH (MinGW-w64 on Windows).

If you are using the flash-drive kit, all three come with it and nothing needs
installing.
