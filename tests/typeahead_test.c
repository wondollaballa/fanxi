/* Unit test for host/addons/typeahead.c (the //hint suggestion in the chat line).
 *
 * Built and run by tests/chat_complete_test.py; no game or SDL required.  The driver stands in
 * for the game's text field: a key inserts at the caret, then the typeahead is asked what the
 * line should hold. */
#include <stdio.h>
#include <string.h>

#include "typeahead.h"

static int failures;

/* The suggestion's colour and reset, as typeahead.c writes them. */
#define GHOST "\x1F" "\x06"
#define RESET "\x1E" "\x01"

typedef struct Line
{
    char text[512];
    int caret;
} Line;

static void screen(const char* name, const Line* l, const char* want, int want_caret)
{
    if (strcmp(l->text, want) != 0)
    {
        printf("FAIL %-32s got=[%s] want=[%s]\n", name, l->text, want);
        ++failures;
    }
    else if (l->caret != want_caret)
    {
        printf("FAIL %-32s caret=%d want=%d\n", name, l->caret, want_caret);
        ++failures;
    }
}

/* The game's text field: a character goes in at the caret. */
static void press(Line* l, char ch)
{
    size_t n = strlen(l->text);
    memmove(l->text + l->caret + 1, l->text + l->caret, n - (size_t)l->caret + 1);
    l->text[l->caret++] = ch;
}

/* One frame: the typeahead sees the line and says what it should hold. */
static void pump(Typeahead* t, Line* l)
{
    TypeaheadEdit edit;
    typeahead_step(t, l->text, l->caret, &edit);
    if (edit.write)
    {
        snprintf(l->text, sizeof l->text, "%s", edit.text);
        l->caret = edit.caret;
    }
}

static void type(Typeahead* t, Line* l, const char* keys)
{
    for (const char* k = keys; *k; ++k)
    {
        press(l, *k);
        pump(t, l);
    }
}

/* Tab or Enter: the suggestion becomes text. */
static void accept(Typeahead* t, Line* l)
{
    TypeaheadEdit edit;
    if (typeahead_accept(t, l->text, &edit) && edit.write)
    {
        snprintf(l->text, sizeof l->text, "%s", edit.text);
        l->caret = edit.caret;
    }
}

int main(void)
{
    Typeahead t;
    Line l;
    typeahead_caret_after_code(0); /* the default is on; the caret-on code cases come later */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;

    /* A command prefix gets its rest after the caret, in the suggestion colour. */
    type(&t, &l, "//invi");
    screen("command prefix suggests the rest", &l, "//invi" GHOST "te " RESET, 6);

    /* Same line, next frame: nothing to write. */
    TypeaheadEdit edit;
    typeahead_step(&t, l.text, l.caret, &edit);
    if (edit.write)
    {
        printf("FAIL %-32s a still line was rewritten\n", "still line");
        ++failures;
    }

    /* Typing lands before the suggestion and the suggestion follows. */
    type(&t, &l, "t");
    screen("typing moves the suggestion", &l, "//invit" GHOST "e " RESET, 7);

    /* Tab takes it: plain text, caret after it. */
    accept(&t, &l);
    screen("tab takes the completion", &l, "//invite ", 9);

    /* An argument from a closed list completes the same way. */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//gs l");
    screen("closed argument value", &l, "//gs l" GHOST "ock " RESET, 6);
    accept(&t, &l);
    screen("closed argument accepted", &l, "//gs lock ", 10);

    /* Where the word may also be a free-text value nothing is suggested: `//invite su` could be
     * a player called Susan, `//warp ma` a saved place named market.  Tab still completes. */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invite su");
    screen("a name position has no suggestion", &l, "//invite su", 11);
    type(&t, &l, "bs");
    screen("the keyword typed through", &l, "//invite subs", 13);

    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//warp ma");
    screen("an alias position has no suggestion", &l, "//warp ma", 9);

    /* A word with more than one match shows nothing, and narrows as it is typed. */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//gs ");
    screen("ambiguous word has no suggestion", &l, "//gs ", 5);
    type(&t, &l, "l");
    screen("ambiguous word narrows", &l, "//gs l" GHOST "ock " RESET, 6);

    /* A character that breaks the completion takes the suggestion away. */
    type(&t, &l, "x");
    screen("no completion drops the suggestion", &l, "//gs lx", 7);

    /* A word that is not a command is left alone. */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "hello");
    screen("plain text", &l, "hello", 5);

    /* The caret leaving the end takes the suggestion out from under it, and leaves the caret
     * where it was put. */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invi");
    l.caret = 2;
    pump(&t, &l);
    screen("caret moved takes it away", &l, "//invi", 2);

    /* A space typed at the suggestion takes it, and the next word continues the line: this is
     * the `//invi subs` path, where the completion is accepted by carrying on. */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invi");
    type(&t, &l, " ");
    screen("space takes the completion", &l, "//invite ", 9);
    type(&t, &l, "subs");
    screen("the next word follows", &l, "//invite subs", 13);

    /* A suggestion that follows a space is not taken by the space that is already in the line:
     * `//character ` suggests `model ` and must stay that way until a key arrives. */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//character ");
    screen("a suggestion after a space", &l, "//character " GHOST "model " RESET, 12);
    pump(&t, &l);
    screen("the space in the line is no acceptance", &l, "//character " GHOST "model " RESET, 12);

    /* A damaged suggestion (a Delete over its first code byte) is remade, not kept as text. */
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invi"); /* the suggestion is in the line now */
    memmove(l.text + 6, l.text + 7, strlen(l.text + 7) + 1); /* Delete over its 0x1F */
    l.caret = 6;
    pump(&t, &l);
    screen("damaged suggestion is remade", &l, "//invi" GHOST "te " RESET, 6);

    /* Enter with no suggestion in the state still cannot submit colour codes. */
    snprintf(l.text, sizeof l.text, "//invi" GHOST "te " RESET);
    if (!typeahead_sanitize(l.text, &edit) || !edit.write)
    {
        printf("FAIL %-32s codes were left in the line\n", "sanitize before submit");
        ++failures;
    }
    else
    {
        snprintf(l.text, sizeof l.text, "%s", edit.text);
        l.caret = edit.caret;
        screen("sanitize before submit", &l, "//invite ", 9);
    }

    /* With the caret after the colour pair (//hint caret on) the line still completes: typing
     * lands after the code, the space still takes it, and the host drops the suggestion before
     * Backspace edits the text. */
    typeahead_caret_after_code(1);
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invi");
    screen("caret after the code", &l, "//invi" GHOST "te " RESET, 8);
    type(&t, &l, "t");
    screen("typing after the code", &l, "//invit" GHOST "e " RESET, 9);

    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invi");
    type(&t, &l, " ");
    screen("space after the code takes it", &l, "//invite ", 9);

    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invi");
    TypeaheadEdit dropped;
    if (!typeahead_drop(&t, l.text, &dropped) || !dropped.write)
    {
        printf("FAIL %-32s the suggestion was not dropped\n", "drop before backspace");
        ++failures;
    }
    else
    {
        snprintf(l.text, sizeof l.text, "%s", dropped.text);
        l.caret = dropped.caret;
    }
    if (l.caret > 0) /* the game's Backspace on what the drop left */
    {
        memmove(l.text + l.caret - 1, l.text + l.caret, strlen(l.text + l.caret) + 1);
        --l.caret;
    }
    pump(&t, &l);
    screen("backspace edits the text", &l, "//inv" GHOST "ite " RESET, 7);
    typeahead_caret_after_code(0);

    /* The suggestion's colour slot is selectable: 1-255 address the 0x1F table, 257-511 the
     * 0x1E one, and anything else is refused. */
    if (!typeahead_colour(12))
    {
        printf("FAIL %-32s colour 12 refused\n", "suggestion colour");
        ++failures;
    }
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invi");
    screen("a chosen colour slot", &l, "//invi" "\x1F\x0C" "te " RESET, 6);

    if (!typeahead_colour(258))
    {
        printf("FAIL %-32s colour 258 refused\n", "suggestion colour");
        ++failures;
    }
    typeahead_init(&t);
    l.text[0] = 0, l.caret = 0;
    type(&t, &l, "//invi");
    screen("a 0x1E colour slot", &l, "//invi" "\x1E\x02" "te " RESET, 6);

    if (typeahead_colour(0) || typeahead_colour(256) || typeahead_colour(512) ||
        typeahead_colour_index() != 258)
    {
        printf("FAIL %-32s a slot without a colour byte was taken\n", "suggestion colour");
        ++failures;
    }
    typeahead_colour(6); /* back to the default for anything after this */

    if (failures)
    {
        printf("typeahead_test: %d failure(s)\n", failures);
        return 1;
    }
    printf("typeahead_test: PASS\n");
    return 0;
}
