/* // command completion (complete.c), called from keys.c while the chat line is open. */
#pragma once

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Fill `out` with the completion for a chat line beginning // (or the legacy /! and !).  A unique
 * match is written with a trailing space; when the word matches more than one command, `out` is
 * the line unchanged so the caller can keep Tab without guessing.  Returns 1 when handled
 * (including the ambiguous case), 0 when the line is not a command or nothing matches (the caller
 * lets the game see Tab). */
int xi_complete_line(const char* line, char* out, size_t cap);

/* Whether `word` is one of the top-level command words, exactly (case-insensitive).  cmd.c uses
 * this to tell a // Fanxi command from an unknown // console line. */
int xi_complete_is_command(const char* word);

/* Tests use this between cases; the chat hook never needs it. */
void xi_complete_reset(void);

#ifdef __cplusplus
}
#endif
