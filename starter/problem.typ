// The problem statement handed out at the start of the event.
// Build with:  typst compile problem.typ

#let accent = rgb("#2f6fdf")
#let coop = rgb("#1f9d55")
#let defect = rgb("#d64541")

// Things the organisers fill in before printing. They show up in orange so
// none slips through.
#let todo(body) = highlight(fill: rgb("#ffe2b8"), extent: 1pt)[#body]

#set document(title: "The Noisy Prisoner's Dilemma")
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

#let C = text(fill: coop, weight: "bold")[C]
#let D = text(fill: defect, weight: "bold")[D]

#align(center)[
  #text(size: 22pt, weight: "bold")[The Noisy Prisoner's Dilemma]
  #v(-0.4em)
  #text(size: 11pt, fill: luma(90))[Write a bot. Play every other bot, hundreds of rounds at a time. Score the most points.]
]

#v(0.6em)

= The game

Each round, you and your opponent each choose one of two moves at the same
time: *cooperate* (#C) or *defect* (#D). Then you both score:

#align(center, table(
  columns: (auto, 7.5em, 7.5em),
  align: center + horizon,
  fill: (x, y) => if x == 0 or y == 0 { luma(242) },
  [], [*They play #C*], [*They play #D*],
  [*You play #C*], [3 each], [you 0, they 5],
  [*You play #D*], [you 5, they 0], [1 each],
))

Cooperating together (3 each) beats defecting together (1 each). But whatever
your opponent does, you score more by defecting, and so do they. That is the
dilemma. Play once and defecting is hard to argue with; play the same opponent
round after round and it isn't, because they will remember what you did.

A *match* is many rounds against one opponent. You are not told how many, and
it varies from match to match, so you cannot plan around the last round.

= Noise

*Each move has a 7% chance of coming out as the other move.* You choose #C,
and 7% of the time #D is what gets played and scored, and the other way round.
Your opponent's moves suffer the same noise, independently.

Every round you are told what *actually* happened, for both of you. So when
your opponent's move comes back as #D, you cannot tell whether they chose it
or noise did. When your own move comes back as something you didn't choose,
you know, and your opponent does not.

Over a match of a couple of hundred rounds, expect about 14 of your moves and
14 of theirs to be changed by noise. A strategy that punishes every #D forever
will not last long.

= The tournament

- *Everyone plays everyone.* Every bot plays every other bot 100 times, in
  matches of varying length. Your score is your *average points per round*
  across all of those matches. Winning a match does not matter; the points you
  get for yourself do. Beating an opponent 1.5 to 1.2 a round is worse than
  losing to them 2.9 to 3.0.
- *House bots.* As well as the teams' bots, the field includes bots written
  by the organisers. We are not saying how many there are or how they play.
  Your matches against them count the same as matches against teams, and
  their scores appear on the leaderboard alongside yours.
- *Fair noise.* Every pairing's 100 matches use the same sequence of match
  lengths and noise, so no bot is luckier than another with the dice.
- *The two highest-scoring team bots win.* House bots can't win, though they
  can finish above you.

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
  [from your bot], [`C` or `D`], [Your move for this round.],
  [to your bot], [`END`], [The tournament is over. Exit.],
)

An exchange looks like this (`>` is what your bot receives, `<` what it
sends):

```
> RESET
> ROUND - -
< C
> ROUND C C        both cooperated
< C
> ROUND C D        they defected, or noise did it
< D
> ROUND C D        you chose D, but noise turned it into C
< C
> RESET            a new match against someone else
```

== Rules

+ *Flush standard output after every move*, or your bot will appear to hang
  and forfeit every round. This is the most common way to lose an hour:
  - Python: `print(move, flush=True)`
  - Java: `System.out.println(move); System.out.flush();`
  - C: `printf("%c\n", move); fflush(stdout);`
  - C++: `std::cout << move << std::endl;` (`"\n"` alone does not flush)
+ *Standard output is for moves only.* Print anything else to standard error.
+ *No memory between matches.* Clear everything on `RESET`. Recognising an
  opponent from an earlier match is against the rules, even though the harness
  can't stop you.
+ *50 ms per move.* A move that takes longer forfeits the round. Aim for well
  under 1 ms on average: every bot makes hundreds of thousands of moves, and
  the whole tournament has to finish in minutes. Your first reply gets 10
  seconds, to give Java time to start.
+ *Forfeits score 0.* A forfeited round counts as #D for your opponent and 0
  for you. A bot that crashes forfeits the rest of that match and is
  restarted for the next one. One that fails to start three times in a row is
  out.
+ *One source file: Python, Java, C or C++*, standard library only. Nothing
  is installed on the tournament machine beyond the language itself, and we
  compile your bot exactly as the Arena does (see `README.md`). In Java, the
  file's public class must share its name, and any other classes go inside the
  same file.
+ *No network, no files, no other processes.* Your bot talks to the
  tournament over standard input and output and nothing else.
+ *One bot per team.* Bots may not work together.

= What you get

The starter pack has:

- *Templates* in Python, Java, C and C++, in `templates/`. Each one already
  handles the protocol and plays generous tit-for-tat, with tit-for-tat and Pavlov included to switch to.
  Copy the one for your language and change how it chooses its move. These are
  the textbook answers, the floor to build on.
- *The Arena* (`Arena.exe`). It runs your bot the same way the tournament does,
  against sparring partners and against your own bots, and tells you whether a
  change really helped or whether you haven't played enough matches to know.
  See `README.md`.

Scoring well against the sparring partners tells you little about the real
field. The tournament includes the other teams, and house bots that aren't in
the pack.

= Timeline

#table(
  columns: (auto, 1fr),
  fill: (x, y) => if x == 0 { luma(242) },
  [*0:00*], [Start building.],
  [*1:25*], [*Submissions close.* #todo[How to submit: where the files go, and what to name them.]],
  [*1:25 – 1:35*], [We check every bot starts and responds. If yours doesn't, we'll find you.],
  [*1:35 – 1:45*], [The tournament runs.],
  [*1:45 – 2:00*], [Highlights, the leaderboard, and the winners.],
)

Submit your bot's one source file. Submit early and resubmit as often as you like; we take
the last version in by 1:25.
