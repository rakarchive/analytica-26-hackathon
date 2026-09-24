/* A bot in C.
 * Print only your moves. For debugging, use fprintf(stderr, ...) instead.
 */

#include <stdio.h>
#include <string.h>

char my[10000];   /* your moves so far this match (as they came out, after noise) */
char opp[10000];  /* your opponent's moves so far this match */
int n = 0;        /* how many rounds have been played this match */

/* Return 'C' or 'D'. This plays tit-for-tat: cooperate first, then
 * copy whatever the opponent did last round. */
char choose(void) {
    if (n == 0) return 'C';
    return opp[n - 1];
}

int main(void) {
    char command[16], mine[4], theirs[4];
    while (scanf("%15s", command) == 1) {
        if (strcmp(command, "RESET") == 0) {      /* a new match: forget the last one */
            n = 0;
        } else if (strcmp(command, "ROUND") == 0) {
            scanf("%3s %3s", mine, theirs);
            if (mine[0] != '-' && n < 10000) {    /* "-" means the first round: nothing to record */
                my[n] = mine[0];
                opp[n] = theirs[0];
                n++;
            }
            printf("%c\n", choose());
            fflush(stdout);                       /* required */
        } else if (strcmp(command, "END") == 0) {
            break;
        }
    }
    return 0;
}
