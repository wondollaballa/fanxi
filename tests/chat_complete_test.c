/* Unit test for host/addons/complete.c (the // Tab completion table).
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

/* Whether the word being typed may be taken as it completes. */
static void expect_assumable(const char* name, const char* line, int want)
{
    int got = xi_complete_assumable(line);
    if (got != want)
    {
        printf("FAIL %-28s line=%s got=%d want=%d\n", name, line, got, want);
        ++failures;
    }
}

/* Whether cmd.c will forward a // line as a server command. */
static void expect_command(const char* name, const char* word, int want)
{
    int got = xi_complete_is_command(word);
    if (got != want)
    {
        printf("FAIL %-28s word=%s got=%d want=%d\n", name, word, got, want);
        ++failures;
    }
}

/* Not a command, or nothing matches: the game keeps Tab. */
static void expect_none(const char* name, const char* line)
{
    char out[400] = "";
    xi_complete_reset();
    if (xi_complete_line(line, out, sizeof out))
        fail(name, line, out, "(none)");
}

/* The argument syntax //help prints, and the part of it the input line's hint can show. */
static void expect_usage(const char* name, const char* word, const char* want)
{
    const char* got = xi_command_usage(word);
    if (!want)
    {
        if (got)
            fail(name, word, got, "(none)");
        return;
    }
    if (!got || strcmp(got, want) != 0)
        fail(name, word, got ? got : "(none)", want);
}

static void expect_args(const char* name, const char* word, const char* want)
{
    const char* got = xi_command_args(word);
    if (!want)
    {
        if (got)
            fail(name, word, got, "(none)");
        return;
    }
    if (!got || strcmp(got, want) != 0)
        fail(name, word, got ? got : "(none)", want);
}

static void expect_title(const char* name, const char* word, const char* want)
{
    const char* got = xi_command_title(word);
    if (want && (!got || strcmp(got, want) != 0))
        fail(name, word, got ? got : "(none)", want);
    else if (!want && got)
        fail(name, word, got, "(none)");
}

/* The chat log's colour pairs are two bytes: 0x1E or 0x1F and one argument. */
static size_t strip_codes(const char* in, char* out, size_t cap)
{
    size_t n = 0;
    for (size_t i = 0; in[i];)
    {
        unsigned char b = (unsigned char)in[i];
        if ((b == 0x1E || b == 0x1F) && in[i + 1])
        {
            i += 2;
            continue;
        }
        if (n + 1 < cap)
            out[n++] = in[i];
        ++i;
    }
    out[n] = 0;
    return n;
}

/* The coloured usage: the plain text once the codes come out, at least one code, and the length
 * a short buffer reports as snprintf does. */
static void expect_colored(const char* name, const char* word)
{
    char line[512], plain[512], small[8];
    size_t n = xi_command_usage_colored(word, line, sizeof line);
    const char* want = xi_command_usage(word);
    if (n != strlen(line))
    {
        printf("FAIL %-28s word=%s length %zu want %zu\n", name, word, n, strlen(line));
        ++failures;
        return;
    }
    strip_codes(line, plain, sizeof plain);
    if (strcmp(plain, want) != 0)
    {
        fail(name, word, plain, want);
        return;
    }
    /* A line with a bracketed part carries a code per span; one with none carries no code. */
    if (strpbrk(want, "[<"))
    {
        if (!strstr(line, "\x1F\x05") && !strstr(line, "\x1F\x06"))
            fail(name, word, line, "a colour code");
    }
    else if (strstr(line, "\x1F") || strstr(line, "\x1E"))
        fail(name, word, line, "no code at all");
    size_t short_n = xi_command_usage_colored(word, small, sizeof small);
    size_t fit = n < sizeof small - 1 ? n : sizeof small - 1;
    if (short_n != n || strlen(small) != fit)
    {
        printf("FAIL %-28s word=%s short buffer %zu/%zu want %zu\n", name, word, short_n,
            strlen(small), n);
        ++failures;
    }
}

/* Every word Tab completes has a syntax line and a description (a command added to TOP without
 * one would leave //help <it> to the server's list). */
static void expect_all_documented(void)
{
    const char* const* words = NULL;
    size_t count = xi_complete_words(&words);
    if (!words || count == 0)
    {
        printf("FAIL %-28s the table is empty\n", "commands documented");
        ++failures;
        return;
    }
    for (size_t i = 0; i < count; ++i)
    {
        const char* usage = xi_command_usage(words[i]);
        if (!usage || strncmp(usage, "//", 2) != 0)
        {
            printf("FAIL %-28s word=%s has no //usage\n", "commands documented", words[i]);
            ++failures;
            continue;
        }
        if (!xi_command_title(words[i]))
        {
            printf("FAIL %-28s word=%s has no title\n", "commands documented", words[i]);
            ++failures;
        }
        expect_colored("commands documented: colour", words[i]);
    }
}

int main(void)
{
    expect("command prefix", "//wa", "//warp ");
    expect("where prefix", "//wh", "//where ");
    expect("merits prefix", "//mer", "//merits ");
    expect("unique subcommand", "//warp li", "//warp list ");
    expect("unique subcommand, upper", "//WARP LI", "//WARP list ");
    expect("mark prefix", "//warp ma", "//warp mark ");
    expect("job abbreviation", "//job n", "//job NIN ");
    expect("job word", "//job war", "//job WAR ");
    expect("box job main", "//job threedough n", "//job threedough NIN ");
    expect("box job sub", "//job threedough nin wa", "//job threedough nin WAR ");
    expect("storage action", "//storage gr", "//storage grab ");
    expect("storage organize", "//storage org", "//storage organize ");
    expect("storage list", "//storage li", "//storage list ");
    expect("locker action", "//locker li", "//locker list ");
    expect("recycle action", "//recycle re", "//recycle restore ");
    expect("item action", "//item m", "//item move ");
    expect("bags command", "//bag", "//bags ");
    expect("magicbag command", "//magic", "//magicbag ");
    expect("augment action", "//augment b", "//augment B ");
    expect("trust action", "//trust rel", "//trust release ");
    expect("joachim action", "//trust joa", "//trust joachim ");
    expect("support trust action", "//trust ygn", "//trust ygnas ");
    expect("joachim songs", "//trust joachim so", "//trust joachim songs ");
    expect("joachim set", "//trust joachim se", "//trust joachim set ");
    expect("joachim default", "//trust joachim set d", "//trust joachim set default ");
    expect("make party command", "//makep", "//makeparty ");
    expect("invite command", "//inv", "//invite ");
    expect("invite action", "//invite su", "//invite subs ");
    expect("character action", "//character m", "//character model ");
    expect("follow action", "//follow stopa", "//follow stopall ");
    expect("focus word", "//gs focus p", "//gs focus pdt ");
    expect("battle action", "//battle ass", "//battle assign ");
    expect("battle role", "//battle assign su", "//battle assign support ");
    expect("battle camp action", "//battle camp r", "//battle camp radius ");
    expect("battle camp set", "//battle camp set th", "//battle camp set there ");
    expect("battle engage", "//battle engage pu", "//battle engage puller ");

    /* The legacy /! and ! spellings still complete while old macros catch up. */
    expect("legacy slash-bang", "/!wa", "/!warp ");
    expect("legacy bang", "!war", "!warp ");

    /* A word that is already a command completes itself, even when a longer command shares it. */
    expect("exact beats longer", "//home", "//home ");
    expect("exact command", "//warp", "//warp ");
    expect("exact job", "//job", "//job ");

    /* More than one match: keep the line and keep Tab; type more and press Tab again. */
    expect_unchanged("ambiguous top level w", "//w");
    expect_unchanged("ambiguous top level m", "//m");
    expect_unchanged("ambiguous top level c", "//c");
    expect_unchanged("ambiguous home/homepoint", "//hom");
    expect_unchanged("ambiguous warp actions", "//warp ");
    expect_unchanged("ambiguous warp m", "//warp m");
    expect_unchanged("ambiguous gs focus", "//gs focus ");
    expect_unchanged("ambiguous jobs w", "//job w");
    expect_unchanged("ambiguous storage", "//storage ");

    /* wake is forwarded but not completed: it would make //wa ambiguous with //warp. */
    expect_none("wake stays out of the table", "//wake");

    expect_none("plain text", "hello there");
    expect_none("unknown command", "//nothing");
    expect_none("full command with space", "//warp mark ");
    expect_none("alias text", "//warp me ca");

    /* cmd.c forwards only exact command words, case-insensitively. */
    expect_command("known server command", "warp", 1);
    expect_command("known forward-only command", "wake", 1);
    expect_command("known command upper", "WARP", 1);
    expect_command("a prefix is not a command", "war", 0);
    expect_command("an unknown word", "nothing", 0);
    expect_command("an empty word", "", 0);
    expect_command("doors is forwarded", "doors", 1);
    expect_command("songs is forwarded", "songs", 1);
    expect_command("mh is forwarded", "mh", 1);
    expect_command("hint is a host command", "hint", 1);

    /* //help: the syntax line, the part left to type, and the colours around the arguments. */
    expect_usage("invite usage", "invite", "//invite [subs|all|team|<name>]");
    expect_usage("case-insensitive usage", "INVITE", "//invite [subs|all|team|<name>]");
    expect_usage("zone usage", "zone", "//zone <id> [x y z [rot]]");
    expect_usage("nested spans", "locker",
        "//locker store|grab|list <all|ammo|back|materials|jsecapes|name> [n]");
    expect_usage("unknown word has no usage", "nothing", NULL);
    expect_args("invite leaves the argument", "invite", " [subs|all|team|<name>]");
    expect_args("no arguments", "where", NULL);
    expect_args("unknown word has no arguments", "nothing", NULL);
    expect_title("warp title", "warp", "save, list and travel to your own places");
    expect_title("unknown word has no title", "nothing", NULL);
    expect_colored("invite coloured", "invite");

    /* Enter may take a completion only where the word cannot also be a value the player wrote. */
    expect_assumable("command word", "//invi", 1);
    expect_assumable("closed argument", "//gs l", 1);
    expect_assumable("closed argument deeper", "//gs lock ma", 1);
    expect_assumable("job argument", "//job n", 1);
    expect_assumable("invite name", "//invite su", 0);
    expect_assumable("warp alias", "//warp ma", 0);
    expect_assumable("plain text", "hello", 0);
    expect_colored("zone coloured", "zone");
    expect_colored("no arguments, no codes", "where");
    expect_all_documented();

    if (failures)
    {
        printf("chat_complete_test: %d failure(s)\n", failures);
        return 1;
    }
    printf("chat_complete_test: PASS\n");
    return 0;
}
