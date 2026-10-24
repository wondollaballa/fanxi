# Ambuscade JSE cape augments

Every job's Ambuscade cape (`Artio's Mantle` for Beastmaster, item 26254;
`Andartia's Mantle` for Ninja, item 26258; `Ankou's Mantle` for Dark Knight,
item 26253; `Taranus's Cape` for Black Mage, item 26249) is augmented with
five standard augment slots.  The block is

```
02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12
```

where each slot is a little-endian u16 holding `id:11 | value:5`.  The
client prints `(value + offset) * multiplier` for the id, so `HP+60` is
id 2 (offset 33) with value 27 and `Enmity-10` is id 0x028 (multiplier
-1) with value 9.  Empty slots are zero.

## Beastmaster (Artio's Mantle)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |
| `mabws` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / MND+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203059a5098054a47493648000000000000000000000000` |
| `pet_tp` | Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20 / Pet: Attack+10 Pet: Rng.Atk.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037c986b486f4870200000000000000000000000000000` |
| `pet_dt` | Pet: M.Acc.+20 Pet: M.Dmg.+20 / Pet: Accuracy+20 Pet: Rng. Acc.+20 / Pet: Mag. Acc.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037d986a9864486f487020000000000000000000000000` |

## Ninja (Andartia's Mantle)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `dw` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / "Dual Wield"+10 / Phys. dmg. taken-10% | `0203019a4498014a92483648000000000000000000000000` |
| `fc` | HP+60 / Mag. Acc+20 /Mag. Dmg.+20 / Evasion+10 / "Fast Cast"+10 / Phys. dmg. taken-10% | `020302d850981f488c483648000000000000000000000000` |
| `ninjutsu` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / "Mag.Atk.Bns."+10 / Phys. dmg. taken-10% | `0203049a5098044a85483648000000000000000000000000` |
| `ws_agi` | AGI+20 / Accuracy+20 Attack+20 / AGI+10 / Weapon skill damage +10% / Damage taken-5% | `0203039a4498034a47494720000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Dark Knight (Ankou's Mantle)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `fc` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `macc` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203049a5098234828483648000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |
| `ws_int` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203049a5098044a47493648000000000000000000000000` |
| `enmity` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity+10 / Phys. dmg. taken-10% | `020302d851981f4827483648000000000000000000000000` |

## Black Mage (Taranus's Cape)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `fcmp` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `macc` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203049a5098234828483648000000000000000000000000` |
| `nuke` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / "Mag.Atk.Bns."+10 / Phys. dmg. taken-10% | `0203049a5098044a85483648000000000000000000000000` |
| `mabws` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203049a5098044a47493648000000000000000000000000` |

## Slots

All nine Beastmaster builds are copies of item 26254, so the client shows
nine `Artio's Mantle` entries; hover each to see which build it is.  The bag
copy that already existed is the `tp` build; the rest sit in bag slots 1-24.

All eleven Ninja builds are copies of item 26258.  The wardrobe copy that
already existed is the `tp` build; the other ten were placed in the first free
main-bag slots by `0082_nin_capes.sql`.

All ten Dark Knight builds are copies of item 26253.  The wardrobe copy that
already existed is the `tp` build; the other nine were placed in wardrobe 3
slots 1-9 by `0088_drk_capes.sql`.

All nine Black Mage builds are copies of item 26249.  The wardrobe copy that
already existed is the `tp` build; the other eight were placed in wardrobe 6
slots 66-73 by `0101_blm_capes.sql`.

`!cape <build> <item>` re-encodes a cape in place (it reads the item's job from
the cape name), and `!cape list` prints the builds.  `tools/gen_capes.py --check`
keeps this page and the migrations in step with `server/fanxi_server/game/capes.py`.

The five-slot block is read back into the stat sheet: `FanxiService.equipped_mods()`
passes each equipped cape's block through `augment_stats`, which renders the slots
with the same table `!cape` prints and adds their modifiers, so a `tp` cape's
DEX+20 / Accuracy+30 / Attack+20 / Store TP+10 / Phys. dmg. taken-10% counts in
combat.
