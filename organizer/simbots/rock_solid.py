"""Rock Solid: rock, every round."""

from protocol import R, Bot, run


class RockSolid(Bot):
    def choose(self):
        return R


if __name__ == "__main__":
    run(RockSolid())
