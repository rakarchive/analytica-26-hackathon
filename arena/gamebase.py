"""What every game has to provide. The game itself is in rules.py, which
sets GAME; everything else in the Arena reads the rules from there."""


class Game:
    """The rules, the words and the sparring partners for one game.

    key          short name, recorded in tournament files
    moves        the letters a bot may send, in a fixed order
    payoff       {(mine, theirs): (my points, their points)}
    best         the most a round can be worth (for the bars)
    noise        chance that a move comes out as a different one
    rounds       (fewest, most) rounds in a match, drawn per repetition
    colour       {move: colour on screen}
    verb/past    {move: "play rock"} / {move: "played rock"}, for captions
    stat         (column heading, {moves counted}) for the board, or None
    baselines    strategy classes to spar against, as (module, class) names
    smoke        three of those, used by the protocol check
    highlights   (title, metric, least worth showing) for the show's finder
    """

    key = ""
    moves = ()
    payoff = {}
    best = 1
    noise = 0.0
    rounds = (150, 250)
    colour = {}
    verb = {}
    past = {}
    stat = None
    baselines = ()
    smoke = ()
    kind_colour = {}
    forfeit = ""            # what a dead bot is treated as having played
    highlights = ()

    def other_moves(self, move):
        return [m for m in self.moves if m != move]

    def verdict(self, a, b):
        """(kind, headline template) for a match's points per round. The kind
        says what sort of match it was; two matches with the same kind tell
        the same story."""
        raise NotImplementedError

    def story(self, ma, mb, na, nb):
        """(caption lines, metrics) describing what happened inside a match,
        from the two move strings (see harness.encode_record)."""
        raise NotImplementedError

    def measure(self, m):
        """The numbers the show's finder ranks a match by: the story's
        metrics, the points gap, and "drama" for filling up the show once
        the highlights' categories are used."""
        _, met = self.story(m["a"], m["b"], "", "")
        met["gap"] = abs(m["pa"] - m["pb"]) / m["n"]
        met.setdefault("forfeits", 0)
        met["drama"] = met["gap"] * 2 + met["forfeits"]
        return met
