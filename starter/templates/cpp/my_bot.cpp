// Starter bot (C++). Build and run with:
//     g++ -O2 -std=c++17 -o my_bot my_bot.cpp
//     ./my_bot                       (my_bot.exe on Windows)
//
// The protocol plumbing is done: edit choose() and leave main() alone
// unless you know why. std::cout is ONLY for moves; debug to std::cerr.

#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

const char C = 'C', D = 'D';

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

    // Return C or D for the next round. Default: generous tit-for-tat.
    char choose() {
        return generous_tft(1.0 / 3);
    }

    // ---- the textbook floor; beat these ----

    char tit_for_tat() {
        return opp.empty() ? C : opp.back();
    }

    char generous_tft(double p) {
        if (opp.empty() || opp.back() == C) return C;
        return random01() < p ? C : D;
    }

    char pavlov() {
        if (my.empty()) return C;
        bool won = opp.back() == C;
        return won ? my.back() : (my.back() == C ? D : C);
    }

    double random01() {
        return std::uniform_real_distribution<double>(0.0, 1.0)(rng);
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
