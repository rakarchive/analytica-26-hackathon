/* Starter bot (C). Build and run with:
 *     gcc -O2 -o my_bot my_bot.c -lm
 *     ./my_bot                       (my_bot.exe on Windows)
 *
 * The protocol plumbing is done: edit choose() and leave main() alone
 * unless you know why. stdout is ONLY for moves; debug to stderr.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define C 'C'
#define D 'D'

/* Your ACTUAL moves so far (after noise) and the opponent's, oldest first:
 * my[0 .. n-1] and opp[0 .. n-1]. */
static char *my = NULL, *opp = NULL;
static size_t n = 0, cap = 0;

/* New match. Clear everything that belongs to one opponent. Keeping state
 * across matches is against the rules. */
static void reset(void) {
    n = 0;
}

static double random01(void) {
    return rand() / (RAND_MAX + 1.0);
}

/* ---- the textbook floor; beat these ---- */

static char tit_for_tat(void) {
    return n ? opp[n - 1] : C;
}

static char generous_tft(double p) {
    if (n == 0 || opp[n - 1] == C) return C;
    return random01() < p ? C : D;
}

static char pavlov(void) {
    if (n == 0) return C;
    int won = opp[n - 1] == C;
    return won ? my[n - 1] : (my[n - 1] == C ? D : C);
}

/* Return C or D for the next round. Default: generous tit-for-tat. */
static char choose(void) {
    (void)tit_for_tat;
    (void)pavlov;
    return generous_tft(1.0 / 3);
}

static void record(char mine, char theirs) {
    if (n == cap) {
        cap = cap ? cap * 2 : 256;
        my = realloc(my, cap);
        opp = realloc(opp, cap);
        if (!my || !opp) {
            fprintf(stderr, "out of memory\n");
            exit(1);
        }
    }
    my[n] = mine;
    opp[n] = theirs;
    n++;
}

int main(void) {
    char line[64], cmd[16], a[8], b[8];
    srand((unsigned)time(NULL));
    while (fgets(line, sizeof line, stdin)) {
        int k = sscanf(line, "%15s %7s %7s", cmd, a, b);
        if (k < 1) continue;
        if (strcmp(cmd, "RESET") == 0) {
            reset();
        } else if (strcmp(cmd, "ROUND") == 0 && k == 3) {
            if (a[0] != '-') record(a[0], b[0]);
            printf("%c\n", choose());
            fflush(stdout); /* NOT optional */
        } else if (strcmp(cmd, "END") == 0) {
            break;
        }
    }
    return 0;
}
