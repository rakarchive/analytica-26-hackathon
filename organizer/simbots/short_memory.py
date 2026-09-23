"""Short Memory: beats the opponent's favourite over the last 10 rounds, so
it keeps up with an opponent that changes its habits."""

from protocol import S, Bot, beat, run


class ShortMemory(Bot):
    def choose(self):
        top = self.favourite(window=10)
        return beat(top) if top else S


if __name__ == "__main__":
    run(ShortMemory())
