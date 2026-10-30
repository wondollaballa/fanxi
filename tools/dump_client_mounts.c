/* Dump the retail client's mount table, one `id <TAB> English name <TAB> description <TAB>
 * Japanese name` per line.  The names come from the client's own string tables, which is also
 * where the game's Mount menu reads them:
 *
 *   mounts.names         NA ROM3/351/84.DAT (file id 55681)   JP ROM3/351/82.DAT (55561)
 *   mounts.descriptions  NA ROM3/351/85.DAT (file id 55682)   JP ROM3/351/83.DAT (55562)
 *
 * The entry's index is the mount id the protocol uses: the bit for that id in 0x0AE
 * MountDataTbl unlocks it, and 0x037/0x00D carry the same id when the player is riding.
 *
 * This is the source snapshot behind tools/client_mount_names.tsv.  Build it against the addon
 * resource reader, then keep the tab-separated text as it comes:
 *
 *   clang -O2 -std=c11 -I host/addons -I runtime/portable -I runtime \
 *       -o /tmp/dump_client_mounts tools/dump_client_mounts.c \
 *       host/addons/res.c host/addons/trust_faces.c host/addons/sc_icons.c \
 *       runtime/portable/vfs.c runtime/portable/plat_posix.c
 *   /tmp/dump_client_mounts "/path/to/FINAL FANTASY XI" > tools/client_mount_names.tsv
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
    uint32_t count = res_string_count("mounts.names", RES_LANG_EN);
    for (uint32_t i = 0; i < count; ++i)
    {
        char* name = res_utf8_dup(res_string("mounts.names", i, RES_LANG_EN), 0);
        char* desc = res_utf8_dup(res_string("mounts.descriptions", i, RES_LANG_EN), 0);
        char* ja = res_utf8_dup(res_string("mounts.names", i, RES_LANG_JA), 0);
        if (name && *name)
            printf("%u\t%s\t%s\t%s\n", i, name, desc ? desc : "", ja ? ja : "");
        free(name);
        free(desc);
        free(ja);
    }
    res_shutdown();
    return 0;
}
