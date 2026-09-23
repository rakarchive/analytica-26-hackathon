// A bot in C++. Build and run it with:
//     g++ -O2 -std=c++17 -o my_bot my_bot.cpp
//     my_bot
// Print only your moves. For debugging, use std::cerr instead.

#include <iostream>
#include <string>

std::string my;   // your moves so far this match (as they came out, after noise)
std::string opp;  // your opponent's moves so far this match

// Return 'C' or 'D'. This plays tit-for-tat: cooperate first, then
// copy whatever the opponent did last round.
char choose() {
    if (opp.empty()) return 'C';
    return opp.back();
}

int main() {
    std::string command;
    while (std::cin >> command) {
        if (command == "RESET") {                 // a new match: forget the last one
            my = "";
            opp = "";
        } else if (command == "ROUND") {
            std::string mine, theirs;
            std::cin >> mine >> theirs;
            if (mine != "-") {                    // "-" means the first round: nothing to record
                my += mine;
                opp += theirs;
            }
            std::cout << choose() << std::endl;   // std::endl flushes, which is required
        } else if (command == "END") {
            break;
        }
    }
}
