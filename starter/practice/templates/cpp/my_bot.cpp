// A bot in C++. Build and run it with:
//     g++ -O2 -std=c++17 -o my_bot my_bot.cpp
//     my_bot
// Print only your moves. For debugging, use std::cerr instead.

#include <iostream>
#include <string>

std::string my;   // your moves so far this match, like "RPPS" (as they came out, after noise)
std::string opp;  // your opponent's moves so far this match

// Return 'R', 'P' or 'S'. This plays rock first, then whatever beats
// the opponent's last move.
char choose() {
    if (opp.empty()) return 'R';
    char last = opp.back();
    if (last == 'R') return 'P';  // paper beats rock
    if (last == 'P') return 'S';  // scissors beat paper
    return 'R';                   // rock beats scissors
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
