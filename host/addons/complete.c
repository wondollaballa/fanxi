/* /! command completion for the game's chat input.
 *
 * keys.c calls xi_complete_line when Tab is pressed while the chat line starts with /! or !.
 * The function is deliberately free of host/SDL dependencies so tests/chat_complete_test.py can
 * compile it on its own.  A unique match completes with a trailing space; an exact command name
 * wins over longer names that start with it (`!home` -> `!home `, not `!homepoint`).
 *
 * An ambiguous word never picks a command: the line is copied to `out` unchanged and 1 is still
 * returned so the caller consumes Tab without touching the input.  The typist adds letters and
 * presses Tab again (`!w` does nothing; `!wh` -> `!where `).  A line that is not a /! command, or
 * a word nothing matches, returns 0 and lets the game see Tab.
 *
 * Keep this table in step with `ZoneSession.command` (server/fanxi_server/game/zone.py) and
 * control.lua's /!gs and /!follow handlers.  The names are the command words, not the help text.
 */
#include "complete.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

#define MAX_MATCHES 64

static const char* const TOP[] = {
    "warp", "zone", "where", "pos", "home", "hp", "homepoint", "heal", "sg", "merits",
    "character", "job", "cast", "ws", "ja", "abilities", "traits", "equip", "unequip",
    "model", "event", "door", "time", "entities", "storage", "locker", "stock", "r30",
    "odyssey", "rp30", "augment", "cape", "moghouse", "reload", "disengage", "gs",
    "follow", "trust", "help",
};
static const char* const WARP_ACTIONS[] = {
    "mark", "list", "me", "all", "delete", "rename", "help",
};
static const char* const GS_ACTIONS[] = {
    "lock", "unlock", "rest", "kite", "focus", "state", "status",
};
static const char* const GS_SLOTS[] = {
    "main", "sub", "range", "ranged", "ammo", "head", "body", "hands", "legs", "feet",
    "neck", "waist", "ear1", "ear2", "ring1", "ring2", "back",
};
static const char* const GS_FOCUS[] = { "auto", "dt", "pdt", "mdt", "eva", "meva" };
static const char* const ON_OFF[] = { "on", "off" };
static const char* const FOLLOW_ACTIONS[] = {
    "me", "stop", "stopall", "p1", "p2", "p3", "p4",
};
static const char* const CHARACTER_ACTIONS[] = { "model" };
static const char* const LOCKER_ACTIONS[] = { "store", "grab", "list" };
static const char* const STORAGE_ACTIONS[] = { "store", "grab" };
static const char* const AUGMENT_ACTIONS[] = { "A", "B", "C", "D", "list", "off" };
static const char* const CAPE_ACTIONS[] = { "build", "list", "off" };
static const char* const TRUST_ACTIONS[] = { "list", "release" };
static const char* const JOBS[] = {
    "WAR", "MNK", "WHM", "BLM", "RDM", "THF", "PLD", "DRK", "BST", "BRD", "RNG",
    "SAM", "NIN", "DRG", "SMN", "BLU", "COR", "PUP", "DNC", "SCH", "GEO", "RUN",
};

void xi_complete_reset(void)
{
    /* Stateless now; kept so the unit test can reset between cases. */
}

static int lower(int c)
{
    return c >= 'A' && c <= 'Z' ? c - 'A' + 'a' : c;
}

static int equal_ci(const char* a, const char* b)
{
    while (*a && *b)
    {
        if (lower((unsigned char)*a) != lower((unsigned char)*b))
            return 0;
        ++a, ++b;
    }
    return *a == 0 && *b == 0;
}

static int starts_with_ci(const char* text, const char* prefix, size_t prefix_len)
{
    for (size_t i = 0; i < prefix_len; ++i)
        if (!text[i] || lower((unsigned char)text[i]) != lower((unsigned char)prefix[i]))
            return 0;
    return 1;
}

static void word_at(const char* body, int wanted, char* out, size_t cap)
{
    size_t used = 0;
    int index = -1;
    const char* p = body;
    out[0] = 0;
    while (*p)
    {
        while (*p == ' ' || *p == '\t')
            ++p;
        if (!*p)
            break;
        ++index;
        size_t length = 0;
        while (p[length] && p[length] != ' ' && p[length] != '\t')
            ++length;
        if (index == wanted)
        {
            if (length >= cap)
                length = cap - 1;
            for (size_t i = 0; i < length; ++i)
                out[used + i] = (char)lower((unsigned char)p[i]);
            out[length] = 0;
            return;
        }
        p += length;
    }
}

static int collect(const char* const* items, size_t count, const char* token,
                   size_t token_len, const char* const** output)
{
    static const char* list[MAX_MATCHES];
    int found = 0;
    *output = NULL;
    for (size_t i = 0; i < count && found < MAX_MATCHES; ++i)
    {
        if (!starts_with_ci(items[i], token, token_len))
            continue;
        /* The word is already a command: complete it instead of treating it as a prefix of a
         * longer command (`home` is both a command and the start of `homepoint`). */
        if (strlen(items[i]) == token_len)
        {
            list[0] = items[i];
            *output = list;
            return 1;
        }
        list[found++] = items[i];
    }
    *output = list;
    return found;
}

static int command_matches(const char* body, const char* token, size_t token_len,
                           const char* const** output)
{
    char first[64], second[64];
    word_at(body, 0, first, sizeof first);
    word_at(body, 1, second, sizeof second);

    /* How many complete words are before the token being typed?  `warp m` is one, `gs focus a`
     * is two, and `warp` with no space is zero. */
    size_t token_start = (size_t)(token - body);
    int words = 0;
    int in_word = 0;
    for (size_t i = 0; i < token_start; ++i)
    {
        if (body[i] == ' ' || body[i] == '\t')
            in_word = 0;
        else if (!in_word)
        {
            ++words;
            in_word = 1;
        }
    }

    if (words == 0)
        return collect(TOP, sizeof TOP / sizeof *TOP, token, token_len, output);

    if (words == 1)
    {
        if (equal_ci(first, "warp"))
            return collect(WARP_ACTIONS, sizeof WARP_ACTIONS / sizeof *WARP_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "gs"))
            return collect(GS_ACTIONS, sizeof GS_ACTIONS / sizeof *GS_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "follow"))
            return collect(FOLLOW_ACTIONS, sizeof FOLLOW_ACTIONS / sizeof *FOLLOW_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "character"))
            return collect(CHARACTER_ACTIONS, sizeof CHARACTER_ACTIONS / sizeof *CHARACTER_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "locker"))
            return collect(LOCKER_ACTIONS, sizeof LOCKER_ACTIONS / sizeof *LOCKER_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "storage"))
            return collect(STORAGE_ACTIONS, sizeof STORAGE_ACTIONS / sizeof *STORAGE_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "augment"))
            return collect(AUGMENT_ACTIONS, sizeof AUGMENT_ACTIONS / sizeof *AUGMENT_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "cape"))
            return collect(CAPE_ACTIONS, sizeof CAPE_ACTIONS / sizeof *CAPE_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "trust"))
            return collect(TRUST_ACTIONS, sizeof TRUST_ACTIONS / sizeof *TRUST_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "job"))
            return collect(JOBS, sizeof JOBS / sizeof *JOBS, token, token_len, output);
        return 0;
    }

    if (words == 2)
    {
        if (equal_ci(first, "gs"))
        {
            if (equal_ci(second, "lock") || equal_ci(second, "unlock"))
                return collect(GS_SLOTS, sizeof GS_SLOTS / sizeof *GS_SLOTS,
                               token, token_len, output);
            if (equal_ci(second, "rest") || equal_ci(second, "kite"))
                return collect(ON_OFF, sizeof ON_OFF / sizeof *ON_OFF, token, token_len, output);
            if (equal_ci(second, "focus"))
                return collect(GS_FOCUS, sizeof GS_FOCUS / sizeof *GS_FOCUS,
                               token, token_len, output);
        }
        if (equal_ci(first, "job"))
            return collect(JOBS, sizeof JOBS / sizeof *JOBS, token, token_len, output);
    }
    return 0;
}

int xi_complete_line(const char* line, char* out, size_t cap)
{
    if (!line || !out || cap < 2)
        return 0;
    size_t prefix = 0;
    if (line[0] == '/' && line[1] == '!')
        prefix = 2;
    else if (line[0] == '!')
        prefix = 1;
    else
        return 0;

    const char* body = line + prefix;
    size_t body_len = strlen(body);
    size_t token_start = 0;
    for (size_t i = 0; i < body_len; ++i)
        if (body[i] == ' ' || body[i] == '\t')
            token_start = i + 1;
    const char* token = body + token_start;
    size_t token_len = body_len - token_start;

    const char* const* found = NULL;
    int count = command_matches(body, token, token_len, &found);
    if (count == 0)
        return 0;
    if (count > 1)
    {
        /* Ambiguous: leave the line exactly as typed and let the caller keep Tab. */
        size_t length = strlen(line);
        if (length + 1 > cap)
            return 0;
        memcpy(out, line, length + 1);
        return 1;
    }

    size_t keep = (size_t)(token - line);
    int written = snprintf(out, cap, "%.*s%s ", (int)keep, line, found[0]);
    if (written < 0 || (size_t)written >= cap)
        return 0;
    return 1;
}
