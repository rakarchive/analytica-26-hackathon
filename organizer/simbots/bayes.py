"""Bayes Watch."""

from protocol import C, D, Bot, run


class Bayes(Bot):
    """Estimates P(opp C | my previous actual move) and picks the move with
    the better payoff now plus the opponent's expected response next round."""
    def choose(self):
        t = self.t()
        if t < 2:
            return C
        cc = cd = nc = nd = 1  # Laplace
        for k in range(1, t):
            if self.my[k - 1] == C:
                nc += 1
                cc += self.opp[k] == C
            else:
                nd += 1
                cd += self.opp[k] == C
        p_after_c, p_after_d = cc / (nc + 1), cd / (nd + 1)
        p_now = p_after_c if self.my[-1] == C else p_after_d
        v_c = 3 * p_now + 3 * p_after_c
        v_d = 5 * p_now + (1 - p_now) + 3 * p_after_d
        return D if v_d > v_c else C


if __name__ == "__main__":
    run(Bayes())
