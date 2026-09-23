/* Practice bot (C). Build and run with:
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

#define ROCK 'R'
#define PAPER 'P'
#define SCISSORS 'S'

/* Your ACTUAL moves so far (after noise) and the opponent's, oldest first:
 * my[0 .. n-1] and opp[0 .. n-1]. */
static char *my = NULL, *opp = NULL;
static size_t n = 0, cap = 0;

/* New match. Clear everything that belongs to one opponent. Keeping state
 * across matches is against the rules. */
static void reset(void) {
    n = 0;
}

/* What beats a move. */
static char beaten_by(char m) {
    return m == ROCK ? PAPER : m == PAPER ? SCISSORS : ROCK;
}

/* ---- a few to start from ---- */

static char random_move(void) {
    return "RPS"[rand() % 3];
}

static char beat_their_last(void) {
    return n ? beaten_by(opp[n - 1]) : ROCK;
}

static char beat_their_favourite(void) {
    size_t count[3] = {0, 0, 0};
    const char *moves = "RPS";
    if (n == 0) return ROCK;
    for (size_t i = 0; i < n; i++)
        count[strchr(moves, opp[i]) - moves]++;
    int best = 0;
    for (int m = 1; m < 3; m++)
        if (count[m] > count[best]) best = m;
    return beaten_by(moves[best]);
}

/* Return R, P or S for the next round. */
static char choose(void) {
    (void)random_move;
    (void)beat_their_favourite;
    return beat_their_last();
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
