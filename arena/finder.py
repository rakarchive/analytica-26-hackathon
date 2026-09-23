"""Find the matches worth showing.

The show replays a handful of matches out of thousands, so the picking has to
be good: every one should be a different story, and between them they should
cover the field. Given a finished tournament this ranks every team-against-team
match, then picks with constraints rather than just taking the top scores.
"""

import game
import harness


def measure(tour, m):
    """Everything interesting about one match, for ranking. What counts as
    interesting depends on the game: see Game.measure and Game.highlights."""
    return harness.GAME.measure(m)


def find_highlights(tour, count=10, champion=None):
    """A varied set of matches to show, best first within each category.

    One per pairing at most, every team appears if the count allows, and each
    category appears at most once. `champion` (a bot index) adds that bot's
    toughest match at the end, which is the one the room most wants to see."""
    duels = [m for m in tour.matches if tour.duel(m) and "a" in m]
    if not duels:
        return []
    scored = [(m, measure(tour, m)) for m in duels]
    by_match = {id(m): met for m, met in scored}
    picks, used_pairs, used_teams, used_stories = [], set(), set(), set()

    def story(m, met):
        """What the audience would see: the verdict and the captions. Two
        matches often tell the same story, because every repetition uses the
        same noise draws, so two pairings that both collapse into permanent
        defection play out identically."""
        return (game.verdict(m["pa"] / m["n"], m["pb"] / m["n"])[0],
                tuple(game.match_story(m["a"], m["b"], "one", "other")[0]))

    def take(title, m):
        pair = (m["i"], m["j"])
        met = by_match[id(m)]
        if pair in used_pairs or story(m, met) in used_stories:
            return False
        picks.append({"title": title, "match": m, "metrics": dict(met)})
        used_pairs.add(pair)
        used_teams.update(pair)
        used_stories.add(story(m, met))
        return True

    for title, key, minimum in harness.GAME.highlights:
        if len(picks) >= count:
            break
        for m, met in sorted(scored, key=lambda x: -x[1][key]):
            if met[key] < minimum:
                break
            if take(title, m):
                break

    # Fill up with the most dramatic matches left, preferring teams not yet seen.
    rest = sorted(scored, key=lambda x: -x[1]["drama"])
    for m, met in rest:
        if len(picks) >= count:
            break
        if not ({m["i"], m["j"]} - used_teams):
            continue
        take("A match worth seeing", m)
    for m, met in rest:
        if len(picks) >= count:
            break
        take("A match worth seeing", m)

    if champion is not None:
        mine = []
        for m in duels:
            if champion in (m["i"], m["j"]):
                mine.append((m["pa"] / m["n"] if m["i"] == champion else m["pb"] / m["n"], m))
        for _, m in sorted(mine, key=lambda x: x[0]):
            if (m["i"], m["j"]) in used_pairs:
                continue  # that pairing has already been shown
            picks.append({"title": "The champion's toughest match", "match": m,
                          "metrics": dict(by_match[id(m)])})
            break
    return picks


def describe(tour, pick):
    """(headline, caption lines) for a pick, using the bots' names."""
    m = pick["match"]
    na, nb = tour.names[m["i"]], tour.names[m["j"]]
    a, b = m["pa"] / m["n"], m["pb"] / m["n"]
    captions, _ = game.match_story(m["a"], m["b"], na, nb)
    return game.headline(a, b, na, nb), captions
