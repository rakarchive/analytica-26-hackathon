// A bot in Java. Build and run it with:
//     javac MyBot.java
//     java MyBot
// Print only your moves. For debugging, use System.err.println(...) instead.

import java.util.Scanner;

public class MyBot {
    static String my = "";   // your moves so far this match (as they came out, after noise)
    static String opp = "";  // your opponent's moves so far this match

    // Return 'R', 'P' or 'S'. This plays rock first, then whatever beats
    // the opponent's last move.
    static char choose() {
        if (opp.isEmpty()) return 'R';
        char last = opp.charAt(opp.length() - 1);
        if (last == 'R') return 'P';  // paper beats rock
        if (last == 'P') return 'S';  // scissors beat paper
        return 'R';                   // rock beats scissors
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        while (in.hasNext()) {
            String command = in.next();
            if (command.equals("RESET")) {          // a new match: forget the last one
                my = "";
                opp = "";
            } else if (command.equals("ROUND")) {
                String mine = in.next();
                String theirs = in.next();
                if (!mine.equals("-")) {            // "-" means the first round: nothing to record
                    my += mine;
                    opp += theirs;
                }
                System.out.println(choose());
                System.out.flush();                 // required
            } else if (command.equals("END")) {
                break;
            }
        }
    }
}
