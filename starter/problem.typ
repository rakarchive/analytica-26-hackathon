// The practice problem statement, handed out with the practice pack.
// Build with:  typst compile problem.typ

#let accent = rgb("#2f6fdf")
#let rock = rgb("#4f6fd8")
#let paper = rgb("#2f9f5f")
#let scissors = rgb("#c8861f")

// Things the organisers fill in before printing. They show up in orange so
// none slips through.
#let todo(body) = highlight(fill: rgb("#ffe2b8"), extent: 1pt)[#body]

#set document(title: "Practice: Rock, Paper, Scissors")
#set page(paper: "a4", margin: (x: 2.2cm, y: 2cm), numbering: "1 / 1",
          number-align: center)
#set text(font: ("Helvetica Neue", "Arial"), size: 10.5pt, lang: "en")
#set par(justify: false, leading: 0.62em, spacing: 1.05em)
#set heading(numbering: none)
#show heading.where(level: 1): it => {
  v(1.1em, weak: true)
  text(size: 13.5pt, weight: "bold", fill: accent, it.body)
  v(0.35em)
}
#show heading.where(level: 2): it => {
  v(0.8em, weak: true)
  text(size: 11pt, weight: "bold", it.body)
  v(0.15em)
}
#show raw: set text(font: ("Menlo", "Consolas", "DejaVu Sans Mono"), size: 9.5pt)
#show raw.where(block: true): block.with(fill: luma(246), inset: 9pt, radius: 3pt, width: 100%)
#set table(stroke: 0.5pt + luma(200), inset: 7pt)

#let R = text(fill: rock, weight: "bold")[R]
#let P = text(fill: paper, weight: "bold")[P]
#let S = text(fill: scissors, weight: "bold")[S]

#align(center)[
  #text(size: 22pt, weight: "bold")[Practice: Rock, Paper, Scissors]
  #v(-0.4em)
  #text(size: 11pt, fill: luma(90))[Get your bot talking to the Arena now, so that on the day you only write strategy.]
]

#v(0.6em)

= Why this exists

The game on the day is *not* rock, paper, scissors. What carries over is
everything around the game: how your bot talks to the Arena, how you check it,
and how you run matches and read the results. That is the part you do not
want to be learning when the clock is running.

So get a bot working in the language you plan to use, on the machine you plan
to use. On the day, you change how your bot picks its move, and nothing else.

= The game

Each round, you and your opponent each choose rock (#R), paper (#P) or
scissors (#S) at the same time. Rock beats scissors, scissors beat paper,
paper beats rock. A win scores 2, a draw 1 each, a loss 0:

#align(center, table(
  columns: (auto, 8.5em, 8.5em, 8.5em),
  align: center + horizon,
  fill: (x, y) => if x == 0 or y == 0 { luma(242) },
  [], [*They play #R*], [*They play #P*], [*They play #S*],
  [*You play #R*], [1 each], [you 0, they 2], [you 2, they 0],
  [*You play #P*], [you 2, they 0], [1 each], [you 0, they 2],
  [*You play #S*], [you 0, they 2], [you 2, they 0], [1 each],
))

A *match* is many rounds against one opponent. You are not told how many, and
it varies from match to match.

= Noise

*Each move has a 7% chance of coming out as one of the other two moves.*
Your opponent's moves suffer the same noise, independently. Every round you
are told what *actually* happened, for both of you, which may not be what
either of you chose.

= The tournament

- *Everyone plays everyone*, many times, in matches of varying length. Your
  score is your *average points per round* across all of those matches.
- *Sparring partners.* The Arena comes with a few simple bots to play
  against. On the day, the field also includes bots written by the
  organisers.

#pagebreak(weak: true)
= Your bot

Your bot is *one source file* in Python, Java, C or C++. It reads commands on
standard input and writes moves on standard output, one per line. It is
started *once* and kept running for the whole tournament, playing match after
match.

#table(
  columns: (auto, auto, 1fr),
  fill: (x, y) => if y == 0 { luma(242) },
  [*Direction*], [*Message*], [*Meaning*],
  [to your bot], [`RESET`], [A new match against a new opponent. Forget everything about the last one.],
  [to your bot], [`ROUND - -`], [The first round of a match. There's no history yet.],
  [to your bot], [`ROUND <mine> <theirs>`], [The previous round's *actual* moves, after noise: first yours, then theirs.],
  [from your bot], [`R`, `P` or `S`], [Your move for this round.],
  [to your bot], [`END`], [The tournament is over. Exit.],
)

An exchange looks like this (`>` is what your bot receives, `<` what it
sends):

```
> RESET
> ROUND - -
< R
> ROUND R S        you won
< R
> ROUND R P        they won
< S
> ROUND P P        you chose S, but noise turned it into P
< S
> RESET            a new match against someone else
```

== Rules

These are the rules on the day too.

+ *Flush standard output after every move*, or your bot will appear to hang
  and forfeit every round. This is the most common way to lose an hour:
  - Python: `print(move, flush=True)`
  - Java: `System.out.println(move); System.out.flush();`
  - C: `printf("%c\n", move); fflush(stdout);`
  - C++: `std::cout << move << std::endl;` (`"\n"` alone does not flush)
+ *Standard output is for moves only.* Print anything else to standard error.
+ *No memory between matches.* Clear everything on `RESET`.
+ *50 ms per move.* A move that takes longer forfeits the round. Aim for well
  under 1 ms on average. Your first reply gets 10 seconds, to give Java time
  to start.
+ *Forfeits score 0.* A bot that crashes forfeits the rest of that match and
  is restarted for the next one. One that fails to start three times in a row
  is out.
+ *One source file: Python, Java, C or C++*, standard library only. We
  compile your bot exactly as the Arena does. In Java, the
  file's public class must share its name, and any other classes go inside the
  same file.
+ *No network, no files, no other processes.* Your bot talks to the
  tournament over standard input and output and nothing else.

#pagebreak(weak: true)
= What you get

- *Templates* in Python, Java, C and C++, in `templates/`. Each one is short,
  handles the protocol, and plays rock first, then whatever beats the
  opponent's last move. Copy the one for your language and rewrite `choose()`.
- *The Arena* (`Arena.exe`), the same one you will use on the day. It runs
  your bot the way the tournament does, against the sparring partners and
  your own bots. See `README.md`.

= Before the day

+ Open the Arena, add your template bot, and click *Check*.
+ Change `choose()` to something of your own, and check it again.
+ Run a tournament and look through the results and the matches.

If the check passes on the machine you'll use, you're ready.
#todo[Who to ask if it doesn't.]
