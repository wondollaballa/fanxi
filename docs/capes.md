# Ambuscade JSE cape augments

All 22 jobs have one Ambuscade cape, and every cape build is a copy of the
same job item with a five-slot standard augment block:

```
02 03  <slot 0> <slot 1> <slot 2> <slot 3> <slot 4>  00 * 12
```

Each slot is a little-endian u16 holding `id:11 | value:5`.  The client
prints `(value + offset) * multiplier` for the id, so `HP+60` is id 2
(offset 33) with value 27 and `Enmity-10` is id 0x028 (multiplier -1) with
value 9.  Empty slots are zero.  There are **198 builds** in total.

All of them live in the hidden 9,999-slot locker (`char_locker`, migration
`0116_all_capes_locker.sql`), not in a client bag.  `//job <job>` grabs that
job's builds out of the locker, and the normal job-change tidy moves the loose
copies into the Mog Wardrobes; the job's cape is then equipped from the
wardrobe.  The other jobs' capes stay in the locker until their turn.
`//locker grab jsecapes` takes all 198 out and `//locker store jsecapes` puts
them back.

`//cape <build> <item>` re-encodes one cape in place, `//cape list` prints the
builds, and `tools/gen_capes.py --check` keeps this page and the migration
in step with `server/fanxi_server/game/capes.py`.

## Launcher augment editor

The launcher's **Data** page has an **Ambuscade capes** card that edits the
same block without a command.  Pick one of the 22 capes (or add a fresh copy
to the inventory), then choose one row per BG Wiki material:

| Material | Slot | Rows | Items to cap |
| --- | --- | --- | --- |
| Abdhaljs Thread | 0 | HP, MP, attributes, pet accuracy | 20 |
| Abdhaljs Dust | 1 | Accuracy/attack, ranged, magic and evasion pairs | 20 |
| Abdhaljs Dye | 2 | HP, MP, attributes and single combat stats | 10 |
| Abdhaljs Sap | 3 | Store TP, Fast Cast, damage and job traits | 10 |
| Abdhaljs Resin | 4 | DEF, evasion, damage taken, block and parry | 5 |

Each row has a stage from 1 to its cap; **Finish augment** writes the five
slots, and **Max selected** takes every chosen row to its cap.  A material
left untouched keeps the word already on the copy, so the pet-focused builds
below survive a partial edit; choosing `— none —` clears just that slot and
**Clear augments** writes the empty block `//cape off` uses.  A live client
receives `//reload`, so the new tooltip is visible without zoning.

The stat sheet reads the block back: `FanxiService.equipped_mods()` passes
each equipped cape through `augment_stats`, which renders the same text
`//cape` prints and adds the modifiers, so a `tp` cape's DEX+20 /
Accuracy+30 / Attack+20 / Store TP+10 / Phys. dmg. taken-10% counts in
combat.

## Warrior (Cichol's Mantle, item 26246)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `enmity` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity+10 / Phys. dmg. taken-10% | `020302d851981f4827483648000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |
| `ws_vit` | VIT+20 / Accuracy+20 Attack+20 / VIT+10 / Weapon skill damage +10% / Damage taken-5% | `0203029a4498024a47494720000000000000000000000000` |

## Monk (Segomo's Mantle, item 26247)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## White Mage (Alaunus's Cape, item 26248)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `cure` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / MND+10 / "Cure Potency"+10% / Phys. dmg. taken-10% | `0203059a5098054a49493648000000000000000000000000` |
| `fc` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `macc` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203059a5098234828483648000000000000000000000000` |
| `ws_mnd` | MND+20 / Accuracy+20 Attack+20 / MND+10 / Weapon skill damage +10% / Damage taken-5% | `0203059a4498054a47494720000000000000000000000000` |

## Black Mage (Taranus's Cape, item 26249)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `fcmp` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `mabws` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203049a5098044a47493648000000000000000000000000` |
| `macc` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203049a5098234828483648000000000000000000000000` |
| `nuke` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / "Mag.Atk.Bns."+10 / Phys. dmg. taken-10% | `0203049a5098044a85483648000000000000000000000000` |

## Red Mage (Sucellos's Cape, item 26250)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `cure` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / MND+10 / "Cure Potency"+10% / Phys. dmg. taken-10% | `0203059a5098054a49493648000000000000000000000000` |
| `fc` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `mabws` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / MND+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203059a5098054a47493648000000000000000000000000` |
| `macc` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203049a5098234828483648000000000000000000000000` |
| `nuke` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / "Mag.Atk.Bns."+10 / Phys. dmg. taken-10% | `0203049a5098044a85483648000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `ws_mnd` | MND+20 / Accuracy+20 Attack+20 / MND+10 / Weapon skill damage +10% / Damage taken-5% | `0203059a4498054a47494720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Thief (Toutatis's Cape, item 26251)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `dw` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / "Dual Wield"+10 / Phys. dmg. taken-10% | `0203019a4498014a92483648000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |

## Paladin (Rudianos's Mantle, item 26252)

| Build | Augments | Block |
| --- | --- | --- |
| `dd` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `block` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity+10 / Chance of successful block +5 | `020302d85198254827486b21000000000000000000000000` |
| `cure` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / MND+10 / "Cure Potency"+10% / Phys. dmg. taken-10% | `0203059a5098054a49493648000000000000000000000000` |
| `fc` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `ws_mnd` | MND+20 / Accuracy+20 Attack+20 / MND+10 / Weapon skill damage +10% / Damage taken-5% | `0203059a4498054a47494720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Dark Knight (Ankou's Mantle, item 26253)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `enmity` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity+10 / Phys. dmg. taken-10% | `020302d851981f4827483648000000000000000000000000` |
| `fc` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `macc` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203049a5098234828483648000000000000000000000000` |
| `ws_int` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203049a5098044a47493648000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Beastmaster (Artio's Mantle, item 26254)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `mabws` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / MND+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203059a5098054a47493648000000000000000000000000` |
| `pet_dt` | Pet: M.Acc.+20 Pet: M.Dmg.+20 / Pet: Accuracy+20 Pet: Rng. Acc.+20 / Pet: Mag. Acc.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037d986a9864486f487020000000000000000000000000` |
| `pet_tp` | Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20 / Pet: Attack+10 Pet: Rng.Atk.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037c986b486f4870200000000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Bard (Intarabus's Cape, item 26255)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `chrws` | CHR+20 / Accuracy+20 Attack+20 / CHR+10 / Weapon skill damage +10% / Damage taken-5% | `0203069a4498064a47494720000000000000000000000000` |
| `dexws` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `maccfc` | CHR+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / "Fast Cast"+10 / Damage taken-5% | `0203069a509823488c484720000000000000000000000000` |

## Ranger (Belenus's Cape, item 26256)

| Build | Augments | Block |
| --- | --- | --- |
| `ranged_tp` | AGI+20 / Rng.Acc.+20 Rng.Atk.+20 / AGI+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203039a4598034a8e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `mabws` | AGI+20 / Mag. Acc+20 /Mag. Dmg.+20 / AGI+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203039a5098034a47493648000000000000000000000000` |
| `snapshot` | AGI+20 / Rng.Acc.+20 Rng.Atk.+20 / AGI+10 / "Snapshot"+10 / Phys. dmg. taken-10% | `0203039a4598034ad3483648000000000000000000000000` |
| `ws_agi` | AGI+20 / Accuracy+20 Attack+20 / AGI+10 / Weapon skill damage +10% / Damage taken-5% | `0203039a4498034a47494720000000000000000000000000` |

## Samurai (Smertrios's Mantle, item 26257)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Ninja (Andartia's Mantle, item 26258)

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

## Dragoon (Brigantia's Mantle, item 26259)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `pet_dt` | Pet: M.Acc.+20 Pet: M.Dmg.+20 / Pet: Accuracy+20 Pet: Rng. Acc.+20 / Pet: Mag. Acc.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037d986a9864486f487020000000000000000000000000` |
| `pet_mab` | Pet: M.Acc.+20 Pet: M.Dmg.+20 / Mag. Acc+20 /Mag. Dmg.+20 / Pet: Mag. Acc.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037d98509864486f487020000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Summoner (Campestres's Cape, item 26260)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `fc` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `mabws` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203049a5098044a47493648000000000000000000000000` |
| `macc` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203059a5098234828483648000000000000000000000000` |
| `pet_dt` | Pet: M.Acc.+20 Pet: M.Dmg.+20 / Pet: Accuracy+20 Pet: Rng. Acc.+20 / Pet: Mag. Acc.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037d986a9864486f487020000000000000000000000000` |
| `pet_mab` | Pet: M.Acc.+20 Pet: M.Dmg.+20 / Mag. Acc+20 /Mag. Dmg.+20 / Pet: Mag. Acc.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037d98509864486f487020000000000000000000000000` |
| `pet_tp` | Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20 / Pet: Attack+10 Pet: Rng.Atk.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037c986b486f4870200000000000000000000000000000` |

## Blue Mage (Rosmerta's Cape, item 26261)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `evafc` | AGI+20 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / "Fast Cast"+10 / Evasion+15 | `0203039a51981f488c481f70000000000000000000000000` |
| `mabws` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / MND+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203059a5098054a47493648000000000000000000000000` |
| `macc` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203049a5098234828483648000000000000000000000000` |
| `nuke` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / "Mag.Atk.Bns."+10 / Phys. dmg. taken-10% | `0203049a5098044a85483648000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `ws_mnd` | MND+20 / Accuracy+20 Attack+20 / MND+10 / Weapon skill damage +10% / Damage taken-5% | `0203059a4498054a47494720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Corsair (Camulus's Mantle, item 26262)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `ranged_tp` | AGI+20 / Rng.Acc.+20 Rng.Atk.+20 / AGI+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203039a4598034a8e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `mab_agi` | AGI+20 / Mag. Acc+20 /Mag. Dmg.+20 / AGI+10 / "Mag.Atk.Bns."+10 / Phys. dmg. taken-10% | `0203039a5098034a85483648000000000000000000000000` |
| `mabws` | AGI+20 / Mag. Acc+20 /Mag. Dmg.+20 / AGI+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203039a5098034a47493648000000000000000000000000` |
| `roll` | CHR+20 / Mag. Acc+20 /Mag. Dmg.+20 / CHR+10 / Enmity-10 / Phys. dmg. taken-10% | `0203069a5098064a28483648000000000000000000000000` |
| `snapshot` | AGI+20 / Rng.Acc.+20 Rng.Atk.+20 / AGI+10 / "Snapshot"+10 / Phys. dmg. taken-10% | `0203039a4598034ad3483648000000000000000000000000` |
| `ws_agi` | AGI+20 / Accuracy+20 Attack+20 / AGI+10 / Weapon skill damage +10% / Damage taken-5% | `0203039a4498034a47494720000000000000000000000000` |

## Puppetmaster (Visucius's Mantle, item 26263)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `pet_dt` | Pet: M.Acc.+20 Pet: M.Dmg.+20 / Pet: Accuracy+20 Pet: Rng. Acc.+20 / Pet: Mag. Acc.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037d986a9864486f487020000000000000000000000000` |
| `pet_mab` | Pet: M.Acc.+20 Pet: M.Dmg.+20 / Mag. Acc+20 /Mag. Dmg.+20 / Pet: Mag. Acc.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037d98509864486f487020000000000000000000000000` |
| `pet_tp` | Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20 / Pet: Attack+10 Pet: Rng.Atk.+10 / Pet: Haste+10 / Pet: Damage taken -5% | `02037c986b486f4870200000000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |

## Dancer (Senuna's Mantle, item 26264)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `dw` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / "Dual Wield"+10 / Phys. dmg. taken-10% | `0203019a4498014a92483648000000000000000000000000` |
| `waltz` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / "Waltz" potency+10% / Phys. dmg. taken-10% | `0203019a4498014a4a493648000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |

## Scholar (Lugh's Cape, item 26265)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `cure` | MND+20 / Mag. Acc+20 /Mag. Dmg.+20 / MND+10 / "Cure Potency"+10% / Phys. dmg. taken-10% | `0203059a5098054a49493648000000000000000000000000` |
| `fc` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `mabws` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203049a5098044a47493648000000000000000000000000` |
| `macc` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203049a5098234828483648000000000000000000000000` |
| `nuke` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / "Mag.Atk.Bns."+10 / Phys. dmg. taken-10% | `0203049a5098044a85483648000000000000000000000000` |

## Geomancer (Nantosuelta's Cape, item 26266)

| Build | Augments | Block |
| --- | --- | --- |
| `tp` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `pdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Phys. dmg. taken-10% | `020302d851981f4828483648000000000000000000000000` |
| `mdt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Mag. Evasion+10 / Enmity-10 / Magic dmg. taken-10% | `020302d85198254828483748000000000000000000000000` |
| `maxhp` | HP+60 / Eva.+20 /Mag. Eva.+20 / HP+20 / Enmity-10 / Damage taken-5% | `020302d85198019828484720000000000000000000000000` |
| `dt` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity-10 / Damage taken-5% | `020302d851981f4828484720000000000000000000000000` |
| `fc` | MP+60 / Mag. Acc+20 /Mag. Dmg.+20 / MP+20 / "Fast Cast"+10 / Phys. dmg. taken-10% | `02030ad8509809988c483648000000000000000000000000` |
| `mabws` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / Weapon skill damage +10% / Phys. dmg. taken-10% | `0203049a5098044a47493648000000000000000000000000` |
| `macc` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / Mag. Acc.+10 / Enmity-10 / Phys. dmg. taken-10% | `0203049a5098234828483648000000000000000000000000` |
| `nuke` | INT+20 / Mag. Acc+20 /Mag. Dmg.+20 / INT+10 / "Mag.Atk.Bns."+10 / Phys. dmg. taken-10% | `0203049a5098044a85483648000000000000000000000000` |

## Rune Fencer (Ogma's Cape, item 26267)

| Build | Augments | Block |
| --- | --- | --- |
| `dd` | DEX+20 / Accuracy+20 Attack+20 / Accuracy+10 / "Store TP"+10 / Phys. dmg. taken-10% | `0203019a449817488e483648000000000000000000000000` |
| `sird` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity+10 / Spell interruption rate down-10% | `020302d851981f4827483548000000000000000000000000` |
| `tank` | HP+60 / Eva.+20 /Mag. Eva.+20 / Evasion+10 / Enmity+10 / Parrying rate+5% | `020302d851981f482748c025000000000000000000000000` |
| `ws_dex` | DEX+20 / Accuracy+20 Attack+20 / DEX+10 / Weapon skill damage +10% / Damage taken-5% | `0203019a4498014a47494720000000000000000000000000` |
| `ws_mnd` | MND+20 / Accuracy+20 Attack+20 / MND+10 / Weapon skill damage +10% / Damage taken-5% | `0203059a4498054a47494720000000000000000000000000` |
| `ws_str` | STR+20 / Accuracy+20 Attack+20 / STR+10 / Weapon skill damage +10% / Damage taken-5% | `0203009a4498004a47494720000000000000000000000000` |
