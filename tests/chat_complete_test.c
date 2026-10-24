/* Unit test for host/addons/complete.c (the /! Tab completion table).
 *
 * Built and run by tests/chat_complete_test.py; no game or SDL required. */
#include <stdio.h>
#include <string.h>

#include "complete.h"

static int failures;

static void fail(const char* name, const char* line, const char* got, const char* want)
{
    printf("FAIL %-28s line=%s got=%s want=%s\n", name, line, got, want);
    ++failures;
}

/* A unique completion from one line. */
static void expect(const char* name, const char* line, const char* want)
{
    char out[400] = "";
    xi_complete_reset();
    int ok = xi_complete_line(line, out, sizeof out);
    if (!ok || strcmp(out, want) != 0)
        fail(name, line, ok ? out : "(none)", want);
}

/* Ambiguous: handled (Tab is kept) but the line must come back exactly as typed. */
static void expect_unchanged(const char* name, const char* line)
{
    char out[400] = "";
    xi_complete_reset();
    int ok = xi_complete_line(line, out, sizeof out);
    if (!ok || strcmp(out, line) != 0)
        fail(name, line, ok ? out : "(none)", line);
}

/* Not a /! command, or nothing matches: the game keeps Tab. */
static void expect_none(const char* name, const char* line)
{
    char out[400] = "";
    xi_complete_reset();
    if (xi_complete_line(line, out, sizeof out))
        fail(name, line, out, "(none)");
}

int main(void)
{
    expect("command prefix", "/!wa", "/!warp ");
    expect("command prefix without slash", "!war", "!warp ");
    expect("where prefix", "/!wh", "/!where ");
    expect("merits prefix", "/!mer", "/!merits ");
    expect("unique subcommand", "/!warp li", "/!warp list ");
    expect("unique subcommand, upper", "/!WARP LI", "/!WARP list ");
    expect("mark prefix", "/!warp ma", "/!warp mark ");
    expect("job abbreviation", "/!job n", "/!job NIN ");
    expect("job word", "/!job war", "/!job WAR ");
    expect("storage action", "/!storage gr", "/!storage grab ");
    expect("locker action", "/!locker li", "/!locker list ");
    expect("augment action", "/!augment b", "/!augment B ");
    expect("trust action", "/!trust rel", "/!trust release ");
    expect("character action", "/!character m", "/!character model ");
    expect("follow action", "/!follow stopa", "/!follow stopall ");
    expect("focus word", "/!gs focus p", "/!gs focus pdt ");

    /* A word that is already a command completes itself, even when a longer command shares it. */
    expect("exact beats longer", "/!home", "/!home ");
    expect("exact command", "/!warp", "/!warp ");
    expect("exact job", "/!job", "/!job ");

    /* More than one match: keep the line and keep Tab; type more and press Tab again. */
    expect_unchanged("ambiguous top level w", "/!w");
    expect_unchanged("ambiguous top level m", "/!m");
    expect_unchanged("ambiguous top level c", "/!c");
    expect_unchanged("ambiguous home/homepoint", "/!hom");
    expect_unchanged("ambiguous warp actions", "/!warp ");
    expect_unchanged("ambiguous warp m", "/!warp m");
    expect_unchanged("ambiguous gs focus", "/!gs focus ");
    expect_unchanged("ambiguous jobs w", "/!job w");
    expect_unchanged("ambiguous storage", "/!storage ");

    expect_none("plain text", "hello there");
    expect_none("unknown command", "/!nothing");
    expect_none("full command with space", "/!warp mark ");
    expect_none("alias text", "/!warp me ca");

    if (failures)
    {
        printf("chat_complete_test: %d failure(s)\n", failures);
        return 1;
    }
    printf("chat_complete_test: PASS\n");
    return 0;
}
