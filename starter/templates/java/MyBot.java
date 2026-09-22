// Starter bot (Java). Build and run with:
//     javac MyBot.java
//     java MyBot
//
// The protocol plumbing is done: edit choose() and leave main() alone
// unless you know why. System.out is ONLY for moves; debug to System.err.

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class MyBot {
    static final char C = 'C', D = 'D';

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

    // Return C or D for the next round. Default: generous tit-for-tat.
    char choose() {
        return generousTft(1.0 / 3);
    }

    // ---- the textbook floor; beat these ----

    char titForTat() {
        return opp.isEmpty() ? C : last(opp);
    }

    char generousTft(double p) {
        if (opp.isEmpty() || last(opp) == C) return C;
        return rng.nextDouble() < p ? C : D;
    }

    char pavlov() {
        if (my.isEmpty()) return C;
        boolean won = last(opp) == C;
        return won ? last(my) : (last(my) == C ? D : C);
    }

    static char last(List<Character> xs) {
        return xs.get(xs.size() - 1);
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
