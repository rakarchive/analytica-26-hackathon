"""The Defectors."""

from protocol import C, D, Bot, run


class AllD(Bot):
    def choose(self):
        return D


if __name__ == "__main__":
    run(AllD())
