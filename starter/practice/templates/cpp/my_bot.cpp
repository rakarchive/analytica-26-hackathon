// Practice bot (C++). Build and run with:
//     g++ -O2 -std=c++17 -o my_bot my_bot.cpp
//     ./my_bot                       (my_bot.exe on Windows)
//
// The protocol plumbing is done: edit choose() and leave main() alone
// unless you know why. std::cout is ONLY for moves; debug to std::cerr.

#include <algorithm>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

const char ROCK = 'R', PAPER = 'P', SCISSORS = 'S';

// What beats a move.
char beaten_by(char m) {
    return m == ROCK ? PAPER : m == PAPER ? SCISSORS : ROCK;
}

struct Bot {
    std::mt19937 rng{std::random_device{}()};
    // Your ACTUAL moves so far (after noise) and the opponent's, oldest first.
    std::vector<char> my, opp;

    // New match. Clear everything that belongs to one opponent. Keeping
    // state across matches is against the rules.
    void reset() {
        my.clear();
        opp.clear();
    }

    // Return R, P or S for the next round.
    char choose() {
        return beat_their_last();
    }

    // ---- a few to start from ----

    char random_move() {
        return "RPS"[std::uniform_int_distribution<int>(0, 2)(rng)];
    }

    char beat_their_last() {
        return opp.empty() ? ROCK : beaten_by(opp.back());
    }

    char beat_their_favourite() {
        if (opp.empty()) return ROCK;
        char best = ROCK;
        long best_count = -1;
        for (char m : {ROCK, PAPER, SCISSORS}) {
            long count = std::count(opp.begin(), opp.end(), m);
            if (count > best_count) {
                best_count = count;
                best = m;
            }
        }
        return beaten_by(best);
    }
};

int main() {
    Bot bot;
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream in(line);
        std::string cmd, mine, theirs;
        in >> cmd;
        if (cmd == "RESET") {
            bot.reset();
        } else if (cmd == "ROUND") {
            in >> mine >> theirs;
            if (mine != "-") {
                bot.my.push_back(mine[0]);
                bot.opp.push_back(theirs[0]);
            }
            std::cout << bot.choose() << std::endl;  // endl flushes: NOT optional
        } else if (cmd == "END") {
            break;
        }
    }
}
