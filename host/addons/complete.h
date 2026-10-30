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

/* --- argument syntax (//help, and the input line's hint) -------------------------------------- */

/* The command words the table knows, in table order (what Tab completes): *words is set to the
 * array and the count returned.  For //help and the tests. */
size_t xi_complete_words(const char* const** words);

/* A command's syntax line, e.g. "//invite [subs | all | team | <name>]"; NULL for a word the table
 * does not know.  `[..]` marks a choice of words and `<..>` a placeholder the typist replaces. */
const char* xi_command_usage(const char* word);

/* What is still to be typed after the command word (" [subs | all | team | <name>]"), or NULL when
 * the command takes no argument.  Points into the usage string. */
const char* xi_command_args(const char* word);

/* A one-line description of the command, or NULL. */
const char* xi_command_title(const char* word);

/* Whether the word being typed may be taken as it completes.  1 for a command name or a
 * subcommand from a closed list; 0 for a position that also takes a free-text value (a warp alias,
 * a player's name), where assuming a keyword would shadow the value.  The input line's typeahead
 * only suggests where this is 1; Tab still completes everywhere. */
int xi_complete_assumable(const char* line);

/* The usage line with the chat log's colour codes around the bracketed parts.  Writes at most
 * cap-1 bytes plus a NUL; returns the length the whole line needs (like snprintf).  Empty when the
 * word is unknown. */
size_t xi_command_usage_colored(const char* word, char* out, size_t cap);

/* Tests use this between cases; the chat hook never needs it. */
void xi_complete_reset(void);

#ifdef __cplusplus
}
#endif
