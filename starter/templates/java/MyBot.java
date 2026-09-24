// A bot in Java.
// Print only your moves. For debugging, use System.err.println(...) instead.

import java.util.Scanner;

public class MyBot {
    static String my = "";   // your moves so far this match, like "CCDC" (as they came out, after noise)
    static String opp = "";  // your opponent's moves so far this match

    // Return 'C' or 'D'. This plays tit-for-tat: cooperate first, then
    // copy whatever the opponent did last round.
    static char choose() {
        if (opp.isEmpty()) return 'C';
        return opp.charAt(opp.length() - 1);
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
