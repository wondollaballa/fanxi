/* Dump the retail client's item names, one `id <TAB> kind <TAB> English name` per
 * line.  `kind` is res.h's RES_ITEM_*: 2 weapons, 3 armour, 0 general, 1 usable,
 * 4 automaton, 6 Maze, 7 Monstrosity, 8 Instinct.
 *
 * This is the source snapshot behind tools/client_item_names.tsv.  Build it
 * against the addon resource reader, then filter the equipment kinds:
 *
 *   clang -O2 -std=c11 -I host/addons -I runtime/portable -I runtime \
 *       -o /tmp/dump_client_items tools/dump_client_items.c \
 *       host/addons/res.c runtime/portable/vfs.c runtime/portable/plat_posix.c
 *   /tmp/dump_client_items "/path/to/FINAL FANTASY XI" > /tmp/client_items.tsv
 *   awk -F'\t' '($2 == 2 || $2 == 3) && $3 != "" && $3 != "." \
 *       { print $1 "\t" $3 }' /tmp/client_items.tsv \
 *       | sort -n > tools/client_item_names.tsv
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "res.h"

int main(int argc, char** argv)
{
    if (argc < 2)
    {
        fprintf(stderr, "usage: %s <FINAL FANTASY XI folder>\n", argv[0]);
        return 2;
    }
    res_init(argv[1], NULL, 0);
    res_set_default_lang(RES_LANG_EN);
    uint32_t count = 0;
    const ResItem* const* items = res_items(&count);
    for (uint32_t i = 0; i < count; ++i)
    {
        const ResItem* item = items[i];
        if (!item)
            continue;
        char* name = res_utf8_dup(item->name[0], 0);
        if (name && *name && strcmp(name, ".") != 0)
            printf("%u\t%d\t%s\n", item->id, item->kind, name);
        free(name);
    }
    res_shutdown();
    return 0;
}
