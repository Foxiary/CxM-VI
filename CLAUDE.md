# CLAUDE.md

Notes for the Vietnamese mod of Collar×Malice and Collar×Malice -Unlimited-
(Switch, JP, title `01002B400E9DA000`). Everything here was reverse-engineered
from the shipped files and checked in game on Ryujinx.

## What this repository is

The tools that build the mod, on top of the 2021 PatchVietHoa. They do not
translate text themselves: the generic readers and writers for `.cpk`,
`.tid`, `.ffu`, `.gbin` and the executable live in VE-ES, the Virche Evermore
toolkit, pinned here as the `ve-es/` submodule. Every script puts
`ve-es/tools` on its path.

    voice/   exefs/main: subtitles in both voice recorders and on the
             -Unlimited- Extra screen, the Dictionary marquee, and the
             segment move that makes room for all of it (voicesub.py builds)
    save/    the .ips for letter spacing and the save list; dictionary rewraps
    album/   the Extra / Album / BGM / ending list textures and their font
    story/   repairs to STORY scripts
    event/   a small DXT5 encoder the others use
    movie/   the English route-intro movies on -Unlimited-

The repo holds no game content. Each script reads and writes under
`work/<folder>/` (gitignored, `DATA` in the script): the stock and English
executables, the English assets they copy art from, and every build output.

## Where the mod is installed

Two mods are enabled for `01002b400e9da000` and both carry `romfs/CONTENTS`:
`~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa` and
`~/Documents/Ryujinx/sdcard/atmosphere/contents/01002b400e9da000`. Keep them
identical - a day once went to testing against mismatched copies. The
executable (`exefs/main` plus the `.ips` keyed to build ID 35A63D73...) lives
only in the PatchVietHoa mod.

Archive ids in the executable: 0 SYSTEM, 1 STORY_01, 2 STORY_02, 3 GAME_01,
4 GAME_02. The disc global (GOT 0x340960 in the stock layout) is 0 for the main
game and 1 for -Unlimited-; `_01` files belong to the first, `_02` to the second.

**Keep the 2021 encoding in STORY text.** The 2021 patch writes Vietnamese
with borrowed code points (Greek, Cyrillic, circled digits), all in CP932.
Re-encoding to Latin Extended-B broke the game even after its pointer damage was
repaired: the EVENT CG view went black and the Voice Recorder showed every entry
locked. The shipped fonts draw old and new code points with identical bitmaps,
so the old encoding costs nothing. Anything that rewrites STCM2L text should
touch only data-block payloads, at the same length.

## Letter spacing on UI screens

The Load/Save slot list shows `Lự a chọ n`, a gap after every accented letter,
and **no font metric changes it**. The slot text is the choice text copied into
`SaveInfos.bin` at save time, so old saves keep whatever encoding the script had
then. It is drawn by one routine (JP `main` `.text` 0x173630; the same `fcsel` is at
0x180920 in EN), which picks each character's step here:

```
1739e4  ldr   s0, [sp, #20]      ; style pitch: a fixed cell
1739e8  cmn   w8, #3             ; -3 = glyph from the font's single-byte table
1739ec  fcsel s0, s15, s0, eq    ; s15 = size / cell_height * advance
```

ASCII steps by its advance; **every multi-byte character steps the fixed cell**,
whatever its glyph. Japanese is all full-width and English all ASCII, so neither
build shows it - EN has the same three instructions. Measured off a screenshot,
Vietnamese steps 66-67 units of `font_Normal` against advances of 24-42, and a
fit with a constant step beats a proportional one (0.33 px rms against 1.4).
That is why trimming the em box, repacking to EN style, widths in multiples of
8 and retargeting to Latin Extended-B all left it as it was: the last one only
moves the letters to other multi-byte code points.

The fix is one instruction, `fcsel` → `fmov s0, s15`, shipped as an IPS keyed
on the build ID (`save/savelist_ips.py`, offset +0x100 for the NSO
header). Full-width characters then step `size * 72 / 75`, a few pixels wider
than the style pitch on `『』`. Whether Virche Evermore's save list has the same
routine is not checked.

**With `#KerningOn` (the Options menu) the JP engine stretches ASCII by
`72 / max_ascii_advance`.** There a glyph is drawn at `size / getSize()` and
steps `size * adv / byte16` if single-byte, `size * adv / getSize()` if not.
`getSize()` (JP 0x1762C0) is header byte 9 = 72; byte 16 is the largest
advance among codes 0-255, computed at load - 58 in the patch, so every Latin
letter stepped 1.24x its width (measured 1.23). Aksys changed `getSize()` to
return byte 16 (EN 0x183200), which also draws every glyph 72/54 larger - why
the EN Latin is rendered small. Keeping the JP executable, a blank 72-advance
glyph at U+007F makes byte 16 equal 72 instead, with no change in glyph size.
The patch also padded its Latin: 88 of 94 printable ASCII bitmaps are the EN
ones moved right 2-10 px, the rest carry 1-4 stray pixels from its tool, which
widened `n` by 10 units. `save/en_spacing.py` does both.

**That padding was there for the negative letter spacing**, which every UI
subtracts from each step and EN keeps unchanged. There are two text drawers:

- Drawer 1 (0x17CA90, tags, kerning): pixels, setter 0x17E230. -7
  `AdvCstmUiSimple`, -5 `advUiSelectText`, -2 the kerning menus.
- Drawer 2 (0x1281A0, step = scale * (advance + spacing)): font units at
  `style+16` of a 56-byte style created through 0x39970. -6 `ADV_TALK_MSG` and
  `advUiSelectText`, -8 `UI_CONF_MSG_TEXT` / `UI_CONF_ITEM_TEXT` / memory, -5
  `UI_SIMPLE_TEXT`, -12 / -14 the dictionary.

The Options reset dialog is `UI_CONF_MSG_TEXT`: patching the drawer-1 -7
changed nothing on screen, while a fit at its glyph scale gives -8 units. With
EN-spaced Latin these values run letters together, and the padding that
absorbed them made the -2 menus look loose, so no one font serves both.
Patching those constants missed the message window, which still stepped
`advance - 10` units - its value is set somewhere not found - so
`savelist_ips.py` changes the spacing where each drawer adds it instead. Drawer
1 uses a constant -2 px (0x17C2D0 / 0x17C32C). Drawer 2 keeps each UI's value
divided by 4 (0x1286E8, `add w8, w8, w9, asr #2`): a flat -2 ran the
dictionary's descriptions past their frame, and a quarter keeps the dictionary
at about the 2021 width (-12 → -3) while -8 / -6 / -5 land on -2. Three
dictionary lines still overflow at -3; they did in 2021 too and need a `#n`,
not a spacing change. Drawer 1 without
`#KerningOn` steps a fixed cell instead (size for multi-byte, `size * byte16 /
byte9` for ASCII); the U+007F glyph made that the full size and the chapter
list printed `C h a p t e`, so the patch also sends every character down the
proportional path (0x17BF44, 0x17C20C). The dictionary word lists put text
against their red row marker, which kana clear with their own side bearing; EN
adds 4.0 to the list x (EN 0x63968, 0x67638), and the patch does the same in
place: loading the entry offsets straight from `x27` frees two address adds for
`fmov s16, #4.0` / `fadd`. **A cave in the .text page padding crashed the game**
the moment the screen opened - code past the text size in the NSO header is not
executable under the emulator, page-aligned or not, so an IPS cannot add code;
only a rebuilt `main` with a larger text segment can. A column-profile fit cannot
tell glyph scale from spacing on its own, so pin the scale from a glyph's
height first.

**What ships instead: every horizontal line at the Dictionary's spacing.** The
Dictionary (drawer 2, -12 units, 2021 font) was the one screen that read tight
and even. Measured off a screenshot it draws each glyph at full size and steps
`adv - 12`. Elsewhere:

- **Drawer 1 used a fixed cell** - chapter list, Options, help bars, the centred
  ADV banner. `savelist_ips.py` sends every drawer-1 character down the
  proportional path and divides by `getSize()` for single- and multi-byte alike,
  so there is no `adv / 58` stretch under `#KerningOn`. It subtracts 12 units
  in the glyph and line-width passes and drops each UI's pixel spacing.
- **Drawer 2 kept each style's own spacing.** The chapter screen's STORY panel
  measured `adv - 3`, the message window is -6. It now uses a flat -12
  (0x1286E8), the Dictionary list's -14 included; vertical text keeps its own.
- **The save list (0x173630) stepped `adv` once its `fcsel` was gone**, with
  zero spacing. Both discs use this one routine; -Unlimited- has no copy of its
  own. Its step is now `s15 - 12 * s15 / adv` (0x1739E0-0x1739F0), where `s15` is
  also the width the glyph is drawn at. The three glyph-missing exits move to
  0x1739F4 to make room.

The 2021 font has no advance under 12, and 72-wide kana/kanji with ~59 of ink
still clear each other at 60.

**Drawer 1's record `+56` is both the pen step and the glyph's cell**, and
its glyph drawer (0x17B670) centres a glyph narrower than the cell and squeezes
one wider into it. The glyph's own width is scale × the atlas width byte, which
is the GTAB advance (0x176FDC). Cutting `+56` alone therefore squeezed every
letter to ~0.65 and left the gaps where they were: pitch was `0.86 * (adv - 12)`
px, but the ink was a third short. The drawer now always uses the glyph's own
width, so `+56` is only the step. The atlas region starts at bitmap column 0,
so a letter still lands at `pen + lsb`. Confirmed in game on 2026-10-30.

**Everything else from the first attempt was reverted.** In game the
EN-spaced font with the -2 px / `asr #2` spacings looked uneven on every screen,
the message window and the Dictionary most of all. That font gave ASCII its EN
side bearings and the Vietnamese letters lsb 0, so no single spacing suited both.
`font_Normal` / `font_Mail` are back to the 2021 bytes, which pad both alike.
The U+007F glyph, those spacings and the dictionary +4 went with the font; they
are kept in `savelist_ips.py` as `SPACING_PATCHES`, unused. The re-broken
dictionary lines stay - the 2021 font at -12 lands on the same width as
EN-spaced glyphs at -3. Two
dictionary titles that the 2021 patch abbreviated were later written out in full
(`dbDictionary_01` records 12 and 37), at 804 and 1009 units against 753 for
the widest other title. They do not fit the list column, so `main` now clips each row at
the end of its red bar and scrolls the selected one (`voice/marquee.s`,
linked by `voice/voicesub.py`). Rebuild `main` only through that script.

## Message window colour by speaker

The window's colour comes from the speaker name. The name instruction's
handler (JP 0x3FFD0) calls 0x906E0, which `strcmp`s the name against field 0
of each row of `dbCharaNameInfo_01` (`_02` on -Unlimited-, picked by the disc
global at 0x90658). It stores the first match's `+132` at window `+552`, and
no match gives 7, the neutral window. The table spells each lead three ways,
all in Japanese, while the 2021 patch names every speaker on both discs in
English, family name first, so nothing matched.

**The name the game reads is not the instruction's own data block.** The
2021 scripts moved their text to a section after the code and point the
name instruction's first parameter there (stock JP points it at the inline
block). The inline block still holds a stale string that nothing reads -
`Aiji Yanagi` in STORY_01, Japanese in 3000-3004.DAT and all of STORY_02.
Reading the inline blocks, a first fix wrote `Aiji Yanagi` into the table and
changed nothing on screen. Follow the parameter for any 2021 script text.

`save/name_colour.py` puts `Yanagi Aiji`, `Hoshino #Name[1]`, ... into rows
0-5 of both tables, the full-width-space spelling no script uses, and keeps
their colour fields: 24,748 of 32,098 speaker names match in STORY_01 and
1,638 of 1,993 in STORY_02. The rest are side characters (also 7 in JP), bare
given names and `A & B`.

## Subtitles the English build has and JP does not

**-Unlimited-'s voice-recorder subtitles are text, not textures.** The main
game's English subtitles are 25 pre-drawn `SUBTITLE/%02u.tid`. The English
-Unlimited- (`0100E3B00F412000`) instead keeps 83 rows of (voice id, question,
answer) as C strings in its `main`, at `.data` 0x3442D8. That is one row per
row of `dbLibVoiceRecorder_02` - the JP and EN databases hold the same voice
ids in the same order - but **the table is not in database order**:

- the five leads (rows 0–49) agree;
- the 33 other characters' rows are listed in a different character order.

The game names a clip by its database row, so the textures are numbered by
that row, and each row's text is looked up in the table by voice id.
Numbering by table position put Kotoho's answers under Mochida's questions.
Aksys rewrote the recorder around these strings, and none of that code exists
in JP. `voice/unlsub.py` renders each row as one DXT5 texture:

- the English panel art from its BC7 `voiceRecorderParts.tid`;
- the English `sysfont.ffu` at ×1.57, the scale measured off a screenshot;
- 2 texels per unit of the engine's 960×540 space, which is what the
  sub-rect draw 0xE0940 expects.

It adds them to GAME_02 as `VOICERECORDER/SUBTITLE/00..82.tid`. There are 2,896
bytes of TOC slack, so every file name reuses a string already in the pool.
`unlsub.s` hooks play (0xC6888), the list's cursor input (0xC652C, which
scrolls the answer while it is up), draw (0xC7A3C) and teardown (0xC7FEC).
Confirmed in game on 2026-10-31.

The character's line on the -Unlimited- Extra screen is the same story: 225
(voice id, line) pairs at EN `.data` 0x3434C8, and a message box Aksys added to
`extra_charParts.tid`. The box is drawn at (350, 400) only while a line plays.
`unlsub.py` renders box and line as `SUBTITLE/<voice id>.tid`. `unlsub.s` hooks:

- the three greetings (0xC162C, 0xC1758, 0xC19F8);
- the draw handler's last part (0xC3298);
- the close (0xC22A4).

225 more TOC rows did not fit the 2,896 bytes of slack, so `unlsub.py cpk`
moves the GTOC and the content down and adds the same delta to every
`FileOffset`, which is relative to `TocOffset`. Confirmed in game on
2026-10-31.

**The main game's 25 recorder subtitles are in Vietnamese** (`voice/visub.py`).
They are still pictures at `SUBTITLE/00..24.tid` in GAME_01. The script
redraws them on the English panel, with the text wiped out by a per-pixel median
of all 25. The translation, by Yui on Ellipsus, is copied as plain text into
`work/voice/mainsub/vi.txt`. The text is drawn in the game's own
`font_Normal.ffu`, stepped at `adv - 12` like every other line. Its answers
run about three times the English length, so they are drawn at scale 0.40
(0.37 for one of them), up to 12 lines. `visub.py swap` replaces the files in
place in the installed GAME_01. Not yet checked in game.

**The 2021 Vietnamese encoding** (`VI_2021` in `visub.py`) was not written
down anywhere and has been read back out of the 2021 SYSTEM text:
- the lowercase letters, from the words they spell;
- the capitals, from the same tone order in their own blocks;
- `Ê` = `×` and `Ô` = `÷`.
Any new text drawn in the 2021 fonts goes through that table.

## Growing exefs/main

**Growing .text means moving everything after it.** The cave in the page
padding before `.rodata` filled up at 1.5 KB. JP `.text` has no dead code to
reuse: every function its FDEs list is referenced. So `voicesub.py` now moves
`.rodata`/`.data`/`.bss` up a page via `voice/nsoshift.py`, which
rebases each kind of reference across the boundary:

- ADRP;
- 440 `ldrsw; add; br` jump tables (entry -= D) - the ones an earlier try
  missed. Find them from the `ldrsw`, not the `br`: 0x10D968's `br` sits
  past a run of argument moves. Matching from the `br` found 439, and that
  one switch crashed the game on entering the main story;
- RELA offsets and addends;
- address-valued dynamic tags;
- dynsym;
- MOD0;
- `.eh_frame_hdr` and FDE `pc_begin`.

`verify()` decodes all of them in stock and in the build and compares them.
A switch's size comes from its `cmp` guard, which is not always next to it:

- 0x157C08 enters by `b.ls`;
- 0x429A4 by `cbz` with flags set earlier;
- 0x4488C compares a different copy of the index.

Cave data still goes after `.rodata`, in its page padding.

## English saves on the JP build

The per-slot `SaveDataXXXXXX.sav` files are the same format in both releases
and carry over. `SystemData0000.sav` (Extra unlocks, read marks, system flags)
does not: JP holds both discs in one file, English splits them over two
titles, so copying either English file locks the other disc's Extra and puts
-Unlimited-'s flags on the wrong indices (disc 2's 365 flags start at 76 in JP,
at 6 in English). `save/merge_en_system.py` builds the JP file from the two
English ones; the layout is in its docstring.

## Route-intro movies on -Unlimited-

Each -Unlimited- route opens its first chapter with `pro01..06.usm`
(`dbEntryMovie_02` rows 7-12) in MOVIE_02.cpk, Japanese text burned into the
picture. The English -Unlimited- has the same cuts with English text, same
VP9 1080p stream, same `total_frames` and `total_samples`, so
`movie/pro_en.py` swaps the six files as they are. op and ed01-06 stay JP.
Not yet checked in game.
