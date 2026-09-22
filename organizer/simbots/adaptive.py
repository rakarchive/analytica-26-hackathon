"""Axelrod Acolytes."""

from protocol import C, D, Bot, run


class Adaptive(Bot):
    """Probe once, then classify from how the opponent reacts to my (intended
    and noise-flipped) defections: exploit pushovers, defect against
    defectors and randoms, otherwise play contrite TFT."""
    def choose(self):
        t = self.t()
        if t < 2:
            return C
        if t == 2:
            return D  # probe
        provoked = retal = unprov_n = unprov_d = 0
        for k in range(1, t):
            if self.my[k - 1] == D:
                provoked += 1
                retal += self.opp[k] == D
            else:
                unprov_n += 1
                unprov_d += self.opp[k] == D
        retal_rate = retal / provoked if provoked else 1.0
        unprov_rate = unprov_d / unprov_n if unprov_n else 0.0
        if t >= 20 and self.opp_d_rate(20) > 0.7:
            return D
        if t >= 12 and unprov_rate > 0.35:
            return D
        if provoked >= 3 and retal_rate < 0.15 and unprov_rate < 0.2:
            return D  # never punishes: take everything
        if provoked >= 2 and retal_rate < 0.3 and unprov_rate < 0.2:
            return C if self.intent[-1] == D else D  # punishes only doubles: alternate
        excused = self.state.setdefault("excused", set())
        if self.my[-1] == D and self.intent[-1] == C:
            excused.add(t)
        if self.opp[-1] == D and (t - 1) not in excused:
            return D
        return C


if __name__ == "__main__":
    run(Adaptive())
