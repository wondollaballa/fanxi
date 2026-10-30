/* The chat input line's typeahead (//hint): the completion of what is being typed, kept after the
 * caret as a coloured "ghost" so it is visibly not typed.  Tab and Enter take it.
 *
 * The line belongs to the game: this module only decides what it should hold.  hooks.c reads the
 * line the game has, calls typeahead_step, and writes back what it returns; the unit test drives
 * the same functions without a game, so the buffer reconciliation is checked on its own. */
#pragma once

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct Typeahead
{
    char ghost[512]; /* the coloured bytes written after the typed text, "" when none is showing */
    char plain[512]; /* the same completion without the colour codes */
    size_t base;     /* the typed length the suggestion was made for (it starts at `base`) */
} Typeahead;

typedef struct TypeaheadEdit
{
    char text[1024]; /* what the line should hold */
    int caret;       /* where the caret goes, in bytes */
    int write;       /* 0: leave the line alone */
} TypeaheadEdit;

/* No suggestion showing. */
void typeahead_init(Typeahead* t);

/* The chat font-colour slot the suggestion is drawn in: 1-255 for a 0x1F pair, 257-511 for a 0x1E
 * one.  1 when taken; 0 for a value that has no slot. */
int typeahead_colour(int index);
int typeahead_colour_index(void);

/* Whether the caret sits after the suggestion's colour pair (1) or on it (0).  The input line
 * does not apply a colour code that is at the caret, so a suggestion written after the caret
 * needs the code behind it to take the colour. */
void typeahead_caret_after_code(int on);
int typeahead_caret_shifted(void);

/* `raw` and `caret` are the line as the game has it, and the edit the line needs now (if any).
 * Handles the suggestion still being there, the player typing into the text, the caret moving,
 * and the line changing under us (history recall, a damaged suggestion). */
void typeahead_step(Typeahead* t, const char* raw, int caret, TypeaheadEdit* edit);

/* Tab or Enter: the suggestion becomes real text and the caret goes after it.  1 when there was
 * one to take (edit says what to write). */
int typeahead_accept(Typeahead* t, const char* raw, TypeaheadEdit* edit);

/* Enter with no suggestion: any colour pairs left in the line come out, so they are never
 * submitted.  1 when the line needed the rewrite. */
int typeahead_sanitize(const char* raw, TypeaheadEdit* edit);

/* Take the suggestion out and leave the typed text (what Backspace and Delete need before they
 * edit: otherwise they would eat the colour pair).  1 when there was one to drop. */
int typeahead_drop(Typeahead* t, const char* raw, TypeaheadEdit* edit);

#ifdef __cplusplus
}
#endif
