// Practice bot (Java). Build and run with:
//     javac MyBot.java
//     java MyBot
//
// The protocol plumbing is done: edit choose() and leave main() alone
// unless you know why. System.out is ONLY for moves; debug to System.err.

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public class MyBot {
    static final char ROCK = 'R', PAPER = 'P', SCISSORS = 'S';
    static final Map<Character, Character> BEATEN_BY = new HashMap<>();
    static {
        BEATEN_BY.put(ROCK, PAPER);
        BEATEN_BY.put(PAPER, SCISSORS);
        BEATEN_BY.put(SCISSORS, ROCK);
    }

    final Random rng = new Random();
    // Your ACTUAL moves so far (after noise) and the opponent's, oldest first.
    List<Character> my = new ArrayList<>();
    List<Character> opp = new ArrayList<>();

    // New match. Clear everything that belongs to one opponent. Keeping
    // state across matches is against the rules.
    void reset() {
        my.clear();
        opp.clear();
    }

    // Return R, P or S for the next round.
    char choose() {
        return beatTheirLast();
    }

    // ---- a few to start from ----

    char randomMove() {
        return "RPS".charAt(rng.nextInt(3));
    }

    char beatTheirLast() {
        return opp.isEmpty() ? ROCK : BEATEN_BY.get(opp.get(opp.size() - 1));
    }

    char beatTheirFavourite() {
        if (opp.isEmpty()) return ROCK;
        char best = ROCK;
        int bestCount = -1;
        for (char m : new char[] {ROCK, PAPER, SCISSORS}) {
            int count = 0;
            for (char x : opp) if (x == m) count++;
            if (count > bestCount) { bestCount = count; best = m; }
        }
        return BEATEN_BY.get(best);
    }

    public static void main(String[] args) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        MyBot bot = new MyBot();
        String line;
        while ((line = in.readLine()) != null) {
            String[] parts = line.trim().split("\\s+");
            switch (parts[0]) {
                case "RESET":
                    bot.reset();
                    break;
                case "ROUND":
                    if (!parts[1].equals("-")) {
                        bot.my.add(parts[1].charAt(0));
                        bot.opp.add(parts[2].charAt(0));
                    }
                    System.out.println(bot.choose());
                    System.out.flush(); // NOT optional
                    break;
                case "END":
                    return;
                default:
                    break;
            }
        }
    }
}
