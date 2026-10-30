/* The chat line's typeahead (//hint).
 *
 * The suggestion is the completion of the line so far, written into the input line's own text
 * after the caret, in the chat log's colour codes.  The input line reads them (//hint probe showed
 * two colours), so the suggestion sits in the line itself: it takes the font, the size and the
 * position the game draws with, and nothing has to be anchored over it.
 *
 * The caret stays at the end of the typed text.  A typed character therefore lands before the
 * suggestion, and the next frame strips the old suggestion and recomputes from the longer line --
 * no per-key bookkeeping, and Backspace keeps working because it deletes behind the caret.  The
 * line is only rewritten when what it should hold actually changes, so a still line costs a read
 * and a compare.
 *
 * Pure string work: no game, no SDL.  hooks.c does the reading and writing.
 */
#include "typeahead.h"

#include <stdio.h>
#include <string.h>

#include "complete.h"

/* The chat font-colour slot the suggestion is drawn in (Menu > Font Colors).  It starts on the
 * linkshell slot (0x1F 06: light blue on the client the probe ran on); //hint color picks another,
 * since which slot is a quiet grey depends on the player's own colours.  The slot matters, not the
 * hue: the suggestion has to read as an aside rather than as typed text. */
static int g_colour = 6;
static int g_shift = 1; /* the caret sits after the colour pair (//hint caret off reverts) */

void typeahead_caret_after_code(int on) { g_shift = on ? 1 : 0; }
int typeahead_caret_shifted(void) { return g_shift; }

int typeahead_colour(int index)
{
    if ((index > 0 && index < 256) || (index > 256 && index < 512))
    {
        g_colour = index;
        return 1;
    }
    return 0; /* 0 and 256 have no colour byte that a C string can carry (a NUL) */
}

int typeahead_colour_index(void) { return g_colour; }

void typeahead_init(Typeahead* t)
{
    t->ghost[0] = 0;
    t->plain[0] = 0;
    t->base = 0;
}

/* The printable text of a line: colour pairs and other control bytes dropped.  The keyboard
 * cannot type them, so what is left is what the player wrote, even if a suggestion was damaged in
 * place (a Delete over its first code byte, say). */
static size_t printable(const char* in, size_t n, char* out, size_t cap)
{
    size_t o = 0;
    for (size_t i = 0; i < n;)
    {
        unsigned char b = (unsigned char)in[i];
        if ((b == 0x1E || b == 0x1F) && i + 1 < n)
            i += 2;
        else
        {
            if (b >= 0x20 && o + 1 < cap)
                out[o++] = in[i];
            ++i;
        }
    }
    out[o] = 0;
    return o;
}

/* The completion of `typed` as a suggestion in `t`.  1 when there is one to show. */
static int suggest(const char* typed, Typeahead* t)
{
    char done[512];
    size_t tlen = strlen(typed);
    typeahead_init(t);
    if (tlen < 2 || !xi_complete_line(typed, done, sizeof done))
        return 0;
    if (!xi_complete_assumable(typed))
        return 0; /* a keyword must not shadow a name or an alias: Tab only */
    size_t dlen = strlen(done);
    if (dlen <= tlen || memcmp(done, typed, tlen) != 0)
        return 0;
    /* The slot's two bytes, then the rest of the line, then back to the line's own colour. */
    size_t rest = strlen(done + tlen);
    if (2 + rest + 2 >= sizeof t->ghost)
        return typeahead_init(t), 0;
    t->ghost[0] = (char)(g_colour < 256 ? 0x1F : 0x1E);
    t->ghost[1] = (char)(g_colour & 0xFF);
    memcpy(t->ghost + 2, done + tlen, rest);
    t->ghost[2 + rest] = (char)0x1E;
    t->ghost[3 + rest] = (char)0x01;
    t->ghost[4 + rest] = 0;
    snprintf(t->plain, sizeof t->plain, "%s", done + tlen);
    t->base = tlen;
    return 1;
}

/* `typed` then `ghost`, caret after the typed part. */
static void edit_text(TypeaheadEdit* edit, const char* typed, size_t tlen, const char* ghost)
{
    size_t glen = strlen(ghost);
    if (tlen + glen >= sizeof edit->text)
        glen = sizeof edit->text - tlen - 1;
    memcpy(edit->text, typed, tlen);
    memcpy(edit->text + tlen, ghost, glen);
    edit->text[tlen + glen] = 0;
    edit->caret = (int)tlen;
    edit->write = 1;
}

void typeahead_step(Typeahead* t, const char* raw, int caret, TypeaheadEdit* edit)
{
    char typed[512], plain[512], want[1024];
    size_t n = strlen(raw);
    size_t glen = strlen(t->ghost);
    int showed = glen != 0;
    size_t base = t->base;
    size_t tlen;
    edit->write = 0;
    plain[0] = 0;
    if (showed)
        snprintf(plain, sizeof plain, "%s", t->plain);

    if (showed && n >= glen && memcmp(raw + n - glen, t->ghost, glen) == 0)
    {
        /* The line still carries our suggestion. */
        tlen = n - glen;
        memcpy(typed, raw, tlen);
        typed[tlen] = 0;
        if (caret != (int)(tlen + (g_shift ? 2 : 0)))
        {
            /* The caret left the suggestion: take it out from under the caret, keeping the caret
             * where the player put it. */
            edit->write = 1;
            snprintf(edit->text, sizeof edit->text, "%s", typed);
            edit->caret = caret >= 0 && (size_t)caret <= tlen ? caret : (int)tlen;
            typeahead_init(t);
            return;
        }
    }
    else
    {
        /* The text is not the one we left: a damaged suggestion, a recalled history line, the
         * line cleared.  Keep what the player wrote and drop the suggestion. */
        tlen = printable(raw, n, typed, sizeof typed);
        if (showed && plain[0])
        {
            size_t p = strlen(plain);
            if (tlen >= p && memcmp(typed + tlen - p, plain, p) == 0)
                typed[tlen -= p] = 0;
        }
        if (!showed && caret != (int)n)
        {
            typeahead_init(t);
            return; /* no suggestion of ours here: only the end of the line completes */
        }
    }

    /* A space typed where the suggestion starts takes it: the completion brings its own trailing
     * space, so the typed one is the acceptance, not a character of its own. */
    if (showed && plain[0] && plain[0] != ' ' && tlen == base + 1 && typed[base] == ' ')
    {
        char joined[512];
        int w = snprintf(joined, sizeof joined, "%.*s%s", (int)base, typed, plain);
        if (w > 0 && (size_t)w < sizeof joined)
        {
            memcpy(typed, joined, (size_t)w + 1);
            tlen = (size_t)w;
            showed = 0;
        }
    }

    /* What the line should hold now, and where the caret goes.  Writing only when that differs
     * from the line keeps a still line free of rewrites. */
    Typeahead next;
    int have = suggest(typed, &next);
    memcpy(want, typed, tlen);
    want[tlen] = 0;
    if (have)
        snprintf(want + tlen, sizeof want - tlen, "%s", next.ghost);
    size_t wlen = tlen + (have ? strlen(next.ghost) : 0);
    int at = (int)(have ? tlen + (g_shift ? 2 : 0) : tlen);
    if (n == wlen && memcmp(raw, want, wlen) == 0 && caret == at)
    {
        if (have)
            *t = next;
        else
            typeahead_init(t);
        return;
    }
    edit->write = 1;
    snprintf(edit->text, sizeof edit->text, "%s", want);
    edit->caret = at;
    if (have)
        *t = next;
    else
        typeahead_init(t);
}

int typeahead_accept(Typeahead* t, const char* raw, TypeaheadEdit* edit)
{
    char typed[512];
    size_t n = strlen(raw), glen = strlen(t->ghost);
    edit->write = 0;
    if (!glen || n < glen || memcmp(raw + n - glen, t->ghost, glen) != 0)
    {
        typeahead_init(t);
        return 0;
    }
    size_t tlen = n - glen;
    memcpy(typed, raw, tlen);
    typed[tlen] = 0;
    edit_text(edit, typed, tlen, t->plain); /* the completion, now real text */
    edit->caret = (int)(tlen + strlen(t->plain));
    typeahead_init(t);
    return 1;
}

int typeahead_drop(Typeahead* t, const char* raw, TypeaheadEdit* edit)
{
    size_t n = strlen(raw), glen = strlen(t->ghost);
    edit->write = 0;
    if (!glen || n < glen || memcmp(raw + n - glen, t->ghost, glen) != 0)
    {
        typeahead_init(t);
        return 0;
    }
    size_t tlen = n - glen;
    edit->write = 1;
    snprintf(edit->text, sizeof edit->text, "%.*s", (int)tlen, raw);
    edit->caret = (int)tlen;
    typeahead_init(t);
    return 1;
}

int typeahead_sanitize(const char* raw, TypeaheadEdit* edit)
{
    char clean[512];
    size_t n = strlen(raw);
    edit->write = 0;
    size_t len = printable(raw, n, clean, sizeof clean);
    if (len == n)
        return 0;
    edit_text(edit, clean, len, "");
    return 1;
}
