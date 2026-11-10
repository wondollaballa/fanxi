/* // command completion for the game's chat input.
 *
 * keys.c calls xi_complete_line when Tab is pressed while the chat line starts with //, or with
 * the legacy /! and ! spellings.  The function is deliberately free of host/SDL dependencies so
 * tests/chat_complete_test.py can compile it on its own.  A unique match completes with a trailing
 * space; an exact command name wins over longer names that start with it (`//home` -> `//home `,
 * not `//homepoint`).
 *
 * An ambiguous word never picks a command: the line is copied to `out` unchanged and 1 is still
 * returned so the caller consumes Tab without touching the input.  The typist adds letters and
 * presses Tab again (`//w` does nothing; `//wh` -> `//where `).  A line that is not a command, or
 * a word nothing matches, returns 0 and lets the game see Tab.
 *
 * Keep this table in step with `ZoneSession.command` (server/fanxi_server/game/zone.py) and
 * control.lua's //gs, //modes, //follow, //hud, //battle, //battleinfo and //partyinfo handlers.
 * The names
 * are the command words, not the help text.  cmd.c also consults it to decide whether a // line
 * is a server command to forward or a local "unknown command" error.
 *
 * The argument syntax lives here too (`COMMANDS`): //help <command> prints it with the arguments
 * coloured in the chat log's own codes, and the input line's hint will take the part after the
 * command word from it.  Like the rest of this file it has no host or SDL dependency, so the
 * tests can check it on its own.
 */
#include "complete.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

#define MAX_MATCHES 64

static const char* const TOP[] = {
    "warp", "zone", "where", "pos", "home", "hp", "homepoint", "heal", "sg", "merits",
    "character", "job", "cast", "ws", "ja", "abilities", "traits", "equip", "unequip",
    "model", "modelnext", "event", "door", "doors", "time", "entities", "storage", "locker", "recycle", "item",
    "bags", "magicbag", "stock", "r30",
    "odyssey", "rp30", "augment", "cape", "moghouse", "mh", "reload", "disengage", "gs",
    "follow", "trust", "makeparty", "invite", "battle", "help", "hint", "mount", "mounts",
    "songs", "chm",
};
/* Server commands that are not completed in chat: `wake` would make `//wa` ambiguous with
 * `//warp`, and both are for the launcher's park/resume path rather than everyday typing.
 * cmd.c still forwards them. */
static const char* const FORWARD_ONLY[] = { "sleep", "wake" };
/* The Chemist's chat route: the HUD's ability buttons and Chemistry tiles send these. */
static const char* const CHM_ACTIONS[] = {
    "status", "load", "select", "use", "toss", "mix", "catalyst", "amplify", "volatile",
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
static const char* const BATTLE_ACTIONS[] = {
    "toggle", "show", "hide", "assign", "engage", "camp", "save", "new", "load", "list",
    "delete", "start", "stop", "pause", "heal", "buff", "enfeeble", "dispel", "pull",
    "formation", "kite", "cure", "ws", "death", "loot", "suggest", "priority", "status", "help",
    "rally", "invite", "import", "skillchain",
};
static const char* const BATTLE_ROLES[] = { "tank", "puller", "kiter", "support", "melee", "ranged" };
static const char* const BATTLE_CAMP[] = { "set", "radius", "clear", "show" };
static const char* const BATTLE_ENGAGE[] = { "when", "tank", "puller", "player", "leader", "always", "none" };
static const char* const BATTLE_ADD[] = { "add", "remove", "on", "off" };
static const char* const BATTLE_DEATH[] = { "raise", "homepoint" };
static const char* const BATTLE_LOOT[] = { "free", "lot", "pass", "leader" };
static const char* const BATTLE_SUGGEST[] = { "heal", "buff", "enfeeble", "all" };
static const char* const FOLLOW_ACTIONS[] = {
    "me", "stop", "stopall", "p1", "p2", "p3", "p4",
};
static const char* const CHARACTER_ACTIONS[] = { "model" };
static const char* const LOCKER_ACTIONS[] = { "store", "grab", "list" };
static const char* const RECYCLE_ACTIONS[] = { "list", "restore", "drop", "purge" };
static const char* const ITEM_ACTIONS[] = { "move", "store", "pull" };
static const char* const INV_ACTIONS[] = { "on", "off", "toggle" };
static const char* const STORAGE_ACTIONS[] = { "organize", "store", "grab", "list" };
static const char* const AUGMENT_ACTIONS[] = { "A", "B", "C", "D", "list", "off" };
static const char* const CAPE_ACTIONS[] = { "build", "list", "off" };
static const char* const TRUST_ACTIONS[] = {
    "list", "release", "joachim", "luzaf", "qultada", "koru-moru", "sylvie-uc", "ygnas",
};
static const char* const SUPPORT_TRUST_NAMES[] = {
    "joachim", "luzaf", "qultada", "koru-moru", "sylvie-uc", "ygnas",
};
static const char* const TRUST_SUB_ACTIONS[] = { "set", "list", "songs", "spells", "rolls" };
static const char* const TRUST_SET_OPTIONS[] = { "songs", "spells", "rolls", "default" };
static const char* const INVITE_ACTIONS[] = { "subs", "all", "team" };
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

static int in_words(const char* value, const char* const* words, size_t count)
{
    for (size_t i = 0; i < count; ++i)
        if (equal_ci(value, words[i]))
            return 1;
    return 0;
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
    char first[64], second[64], third[64];
    word_at(body, 0, first, sizeof first);
    word_at(body, 1, second, sizeof second);
    word_at(body, 2, third, sizeof third);

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
        if (equal_ci(first, "recycle"))
            return collect(RECYCLE_ACTIONS, sizeof RECYCLE_ACTIONS / sizeof *RECYCLE_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "item"))
            return collect(ITEM_ACTIONS, sizeof ITEM_ACTIONS / sizeof *ITEM_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "bags") || equal_ci(first, "magicbag"))
            return collect(INV_ACTIONS, sizeof INV_ACTIONS / sizeof *INV_ACTIONS,
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
        if (equal_ci(first, "invite"))
            return collect(INVITE_ACTIONS, sizeof INVITE_ACTIONS / sizeof *INVITE_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "battle"))
            return collect(BATTLE_ACTIONS, sizeof BATTLE_ACTIONS / sizeof *BATTLE_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "job"))
            return collect(JOBS, sizeof JOBS / sizeof *JOBS, token, token_len, output);
        if (equal_ci(first, "chm"))
            return collect(CHM_ACTIONS, sizeof CHM_ACTIONS / sizeof *CHM_ACTIONS,
                           token, token_len, output);
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
        if (equal_ci(first, "trust")
            && in_words(second, SUPPORT_TRUST_NAMES,
                        sizeof SUPPORT_TRUST_NAMES / sizeof *SUPPORT_TRUST_NAMES))
            return collect(TRUST_SUB_ACTIONS,
                           sizeof TRUST_SUB_ACTIONS / sizeof *TRUST_SUB_ACTIONS,
                           token, token_len, output);
        if (equal_ci(first, "battle"))
        {
            if (equal_ci(second, "assign") || equal_ci(second, "pause"))
                return collect(BATTLE_ROLES, sizeof BATTLE_ROLES / sizeof *BATTLE_ROLES,
                               token, token_len, output);
            if (equal_ci(second, "camp"))
                return collect(BATTLE_CAMP, sizeof BATTLE_CAMP / sizeof *BATTLE_CAMP,
                               token, token_len, output);
            if (equal_ci(second, "engage"))
                return collect(BATTLE_ENGAGE, sizeof BATTLE_ENGAGE / sizeof *BATTLE_ENGAGE,
                               token, token_len, output);
            if (equal_ci(second, "cure") || equal_ci(second, "buff") || equal_ci(second, "enfeeble")
                || equal_ci(second, "dispel"))
                return collect(BATTLE_ADD, sizeof BATTLE_ADD / sizeof *BATTLE_ADD,
                               token, token_len, output);
            if (equal_ci(second, "death"))
                return collect(BATTLE_DEATH, sizeof BATTLE_DEATH / sizeof *BATTLE_DEATH,
                               token, token_len, output);
            if (equal_ci(second, "loot"))
                return collect(BATTLE_LOOT, sizeof BATTLE_LOOT / sizeof *BATTLE_LOOT,
                               token, token_len, output);
            if (equal_ci(second, "suggest"))
                return collect(BATTLE_SUGGEST, sizeof BATTLE_SUGGEST / sizeof *BATTLE_SUGGEST,
                               token, token_len, output);
            if (equal_ci(second, "heal") || equal_ci(second, "buff") || equal_ci(second, "enfeeble")
                || equal_ci(second, "dispel") || equal_ci(second, "pull") || equal_ci(second, "formation")
                || equal_ci(second, "kite"))
                return collect(ON_OFF, sizeof ON_OFF / sizeof *ON_OFF, token, token_len, output);
        }
    }

    /* The box form is //job <character> <job> <sub>: the third word is still a job. */
    if (words == 3 && equal_ci(first, "job"))
        return collect(JOBS, sizeof JOBS / sizeof *JOBS, token, token_len, output);
    if (words == 3 && equal_ci(first, "battle") && equal_ci(second, "camp")
        && equal_ci(third, "set"))
        return collect((const char* const[]){ "here", "there" }, 2, token, token_len, output);
    if (words == 3 && equal_ci(first, "trust")
        && in_words(second, SUPPORT_TRUST_NAMES,
                    sizeof SUPPORT_TRUST_NAMES / sizeof *SUPPORT_TRUST_NAMES)
        && equal_ci(third, "set"))
        return collect(TRUST_SET_OPTIONS,
                       sizeof TRUST_SET_OPTIONS / sizeof *TRUST_SET_OPTIONS,
                       token, token_len, output);
    return 0;
}

int xi_complete_line(const char* line, char* out, size_t cap)
{
    if (!line || !out || cap < 2)
        return 0;
    size_t prefix = 0;
    if (line[0] == '/' && line[1] == '/')
        prefix = 2;
    else if (line[0] == '/' && line[1] == '!')
        prefix = 2; /* legacy spelling: kept so old macros and habits still complete */
    else if (line[0] == '!')
        prefix = 1; /* legacy spelling */
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

/* The word being typed is at `token_start` in the body; how many complete words are before it? */
static int words_before(const char* body, size_t token_start)
{
    int words = 0, in_word = 0;
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
    return words;
}

int xi_complete_assumable(const char* line)
{
    if (!line)
        return 0;
    size_t prefix = 0;
    if (line[0] == '/' && line[1] == '/')
        prefix = 2;
    else if (line[0] == '/' && line[1] == '!')
        prefix = 2; /* legacy spelling */
    else if (line[0] == '!')
        prefix = 1;
    else
        return 0;
    const char* body = line + prefix;
    size_t token_start = 0;
    for (size_t i = 0; body[i]; ++i)
        if (body[i] == ' ' || body[i] == '\t')
            token_start = i + 1;
    if (words_before(body, token_start) == 0)
        return 1; /* the command word: a closed list */
    /* `//warp <alias>` and `//invite <name>` put a free-text value where the keywords are, so a
     * keyword completion there would shadow a player or a saved place. */
    char first[64];
    word_at(body, 0, first, sizeof first);
    return !equal_ci(first, "warp") && !equal_ci(first, "invite");
}

int xi_complete_is_command(const char* word)
{
    if (!word || !*word)
        return 0;
    const char* const* found = NULL;
    int count = collect(TOP, sizeof TOP / sizeof *TOP, word, strlen(word), &found);
    if (count == 1 && equal_ci(found[0], word))
        return 1;
    count = collect(FORWARD_ONLY, sizeof FORWARD_ONLY / sizeof *FORWARD_ONLY,
                    word, strlen(word), &found);
    return count == 1 && equal_ci(found[0], word);
}

/* --- argument syntax -------------------------------------------------------------------------- */

/* One line per command: the word, the syntax as typed (with `[choice]` and `<placeholder>` marks),
 * and what it does.  //help prints the line coloured; the input line's hint takes the part after
 * the word.  Keep it in step with the handlers the top comment names, and mark the arguments of a
 * new command here when it joins TOP. */
typedef struct Command
{
    const char* name;
    const char* usage;
    const char* title;
} Command;

static const Command COMMANDS[] = {
    { "warp", "//warp mark [alias] | list [page] | me|all <n|alias> | all me | call <name|all> | "
              "delete <n|alias> | rename <n> <alias>", "save, list and travel to your own places" },
    { "zone", "//zone <id> [x y z [rot]]", "move to another zone, at a position if given" },
    { "where", "//where", "the zone and position you are in" },
    { "pos", "//pos <x> <y> <z> [rot]", "move within the zone" },
    { "home", "//home", "back to your home point" },
    { "hp", "//hp [menu number|zone]", "the Home Points list, or travel to one" },
    { "homepoint", "//homepoint [menu number|zone]", "the same as //hp" },
    { "heal", "//heal", "restore HP and MP" },
    { "sg", "//sg [n]", "the survival guides, or travel to one" },
    { "merits", "//merits [points]", "set your merit points" },
    { "character", "//character model <race> <1-48|random>", "change a character's model" },
    { "job", "//job <job> [sub] | //job <character> <job> <sub>",
      "change a job, yours or a sub-account's" },
    { "chm", "//chm status | load <item> [qty] | select <item> | use <item> | "
             "toss | mix | catalyst | amplify | volatile",
      "the Chemist Battle Bag, Toss/Mix and stances" },
    { "cast", "//cast <spell>", "cast a spell by name" },
    { "ws", "//ws <name>", "a weapon skill by name" },
    { "ja", "//ja <name>", "a job ability by name" },
    { "abilities", "//abilities", "refresh the ability list" },
    { "traits", "//traits", "the current job pair's traits" },
    { "equip", "//equip <item>", "equip an item by name" },
    { "unequip", "//unequip <slot>", "empty an equip slot" },
    { "model", "//model <item> <id>", "change an item's model id" },
    { "modelnext", "//modelnext <item>", "step an item's model id up by one" },
    { "event", "//event <id> [p1..p8]", "play a cutscene event" },
    { "door", "//door <id>", "add a door target here" },
    { "doors", "//doors auto [on|off]", "automatic doors in cities and outdoors" },
    { "mount", "//mount [all] <mount|off|list>",
      "call a mount; //mount all calls it for every online sub-account box" },
    { "mounts", "//mounts [on|off|toggle]", "the Mount HUD: every mount, with its picture" },
    { "time", "//time <hour>", "set Vana'diel time" },
    { "entities", "//entities", "list the entities around you" },
    { "storage", "//storage organize | store <job|all> | grab <job|all> | list [job|all]",
      "keep only the current job's gear out; the 9999 locker holds the rest" },
    { "locker", "//locker store|grab|list <all|ammo|back|materials|jsecapes|name> [n]",
      "the mog locker" },
    { "recycle", "//recycle [list|restore <slot>|drop <bag> <slot>|purge]",
      "the 30-day recycle bin" },
    { "item", "//item move <bag> <slot> <to-bag> [n] | store locker <bag> <slot> [n] | pull <slip|locker> <id> [extra] [n]",
      "move, store or pull one Magic Bag row" },
    { "bags", "//bags [on|off|toggle]", "the Magic Bag inventory HUD" },
    { "magicbag", "//magicbag [on|off|toggle]", "the same HUD" },
    { "stock", "//stock", "top up the working stock from the locker" },
    { "r30", "//r30 [item]", "an item's Rank 30 rows" },
    { "odyssey", "//odyssey [item]", "the same as //r30" },
    { "rp30", "//rp30", "re-stamp the Limbus Rank 30 augments you carry" },
    { "augment", "//augment <A-D|index|off|list> <item>", "augment an item" },
    { "cape", "//cape <build|off|list> <item>", "re-encode an Ambuscade job cape" },
    { "moghouse", "//moghouse [enter|out]", "enter or leave the mog house" },
    { "mh", "//mh out [name|all]", "step the family out of the mog house" },
    { "reload", "//reload", "re-read the launcher's data" },
    { "disengage", "//disengage", "break a kept range engagement" },
    { "gs", "//gs lock|unlock <slot> | rest|kite|state <on|off> | "
            "focus <auto|dt|pdt|mdt|eva|meva> | status", "GearSwap's live controls" },
    { "follow", "//follow me|stop|stopall|p1..p4", "the follow group" },
    { "battle", "//battle toggle|show|hide | assign <role> <name...> | engage when <name> | "
                "camp set here|there | camp radius <n> | save [name] | start | stop | pause <role>",
      "the Battle hub and automation" },
    { "trust", "//trust [list | release <spell id|name|all> | "
               "<joachim|luzaf|qultada|koru-moru|sylvie-uc|ygnas> "
               "[set songs|spells|rolls \"<name>\" ... | set default]]",
      "alter egos and support-trust actions" },
    { "makeparty", "//makeparty", "drop your online subs from their parties, then invite them" },
    { "invite", "//invite [subs|all|team|<name>]", "party your online sub team, or invite one player" },
    { "help", "//help [command]", "the command list, or one command's syntax" },
    { "hint", "//hint on|off|color <n>|colors [first]|caret on|off|probe",
      "the input line's typeahead and its colour" },
    { "songs", "//songs", "the songs on you, with the time left and the values they give" },
    { "sleep", "//sleep", "park this box without logging out" },
    { "wake", "//wake", "resume a parked box" },
};

/* The chat log's colour slots (Menu > Font Colors, indexed by a 0x1F pair): the choice span in the
 * party colour, a placeholder in the linkshell one, then back to the line's own colour.  Both slots
 * are the player's to restyle, so all the help needs of them is that they differ from the line. */
#define CHAT_CHOICE "\x1F" "\x05"
#define CHAT_PLACE "\x1F" "\x06"
#define CHAT_RESET "\x1E" "\x01"

static const Command* command_of(const char* word)
{
    if (!word || !*word)
        return NULL;
    for (size_t i = 0; i < sizeof COMMANDS / sizeof *COMMANDS; ++i)
        if (equal_ci(COMMANDS[i].name, word))
            return &COMMANDS[i];
    return NULL;
}

size_t xi_complete_words(const char* const** words)
{
    if (words)
        *words = TOP;
    return sizeof TOP / sizeof *TOP;
}

const char* xi_command_usage(const char* word)
{
    const Command* c = command_of(word);
    return c ? c->usage : NULL;
}

const char* xi_command_args(const char* word)
{
    const Command* c = command_of(word);
    if (!c)
        return NULL;
    size_t skip = 2 + strlen(c->name); /* past "//" and the word */
    return c->usage[skip] ? c->usage + skip : NULL;
}

const char* xi_command_title(const char* word)
{
    const Command* c = command_of(word);
    return c ? c->title : NULL;
}

static void put_at(char* out, size_t cap, size_t at, char ch)
{
    if (out && at + 1 < cap)
        out[at] = ch;
}

size_t xi_command_usage_colored(const char* word, char* out, size_t cap)
{
    const Command* c = command_of(word);
    if (!c)
    {
        if (out && cap)
            out[0] = 0;
        return 0;
    }
    /* The spans nest (`[subs | all | <name>]`), so keep the colours on a stack: a `]` or `>` goes
     * back to the span that held it, and the last one closes to the line's own colour. */
    int stack[4], depth = 0, want = 0, have = 0;
    size_t n = 0;
    for (const char* p = c->usage; *p; ++p)
    {
        if ((*p == '[' || *p == '<') && depth < 4)
            stack[depth++] = want, want = *p == '[' ? 1 : 2;
        if (want != have)
        {
            const char* code = want == 1 ? CHAT_CHOICE : want == 2 ? CHAT_PLACE : CHAT_RESET;
            while (*code)
                put_at(out, cap, n++, *code++);
            have = want;
        }
        put_at(out, cap, n++, *p);
        if ((*p == ']' || *p == '>') && depth)
            want = stack[--depth];
    }
    if (out && cap)
        out[n < cap ? n : cap - 1] = 0;
    return n;
}
