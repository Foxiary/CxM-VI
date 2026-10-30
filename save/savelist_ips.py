"""Exefs patch for Collar x Malice letter spacing (save list, dialogs, messages).

    python3 savelist_ips.py <jp main NSO> <out dir>

1. SAVE LIST: multi-byte letters step a fixed cell
    The save/load list draws its four lines (slot, date, chapter, choice text)
    through one routine at .text 0x173630. Per character it picks the step:

        1739e4  ldr   s0, [sp, #20]        ; style pitch, a fixed cell
        1739e8  cmn   w8, #3               ; -3 = glyph came from the font's
        1739ec  fcsel s0, s15, s0, eq      ;      single-byte table
        1739f0  fadd  s0, s0, s14

    s15 is size / cell_height * advance. So an ASCII letter steps by its own
    advance and every multi-byte character steps by the fixed cell, whatever
    its glyph is. Japanese is all full-width, English is all ASCII, so neither
    shows it. Vietnamese letters are multi-byte (Greek/Cyrillic code points in
    the patch, Latin Extended-B after the retarget) and each one gets a
    full cell: "Lự a chọ n". Measured off a screenshot the step is 66-67 units
    of font_Normal against advances of 24-42, and it does not move with the
    advance, so no font metric can fix it. The EN executable has the same
    three instructions (0x18091c); Aksys did not touch it.

    "fmov s0, s15" steps every character by its advance. Full-width characters
    then step size * 72 / 75 instead of the style pitch - a few pixels wider on
    『』.

2. DRAWER 1 AT DICTIONARY SPACING (applied - see PATCHES)

3. NEGATIVE LETTER SPACING (not applied - SPACING_PATCHES)
    The engine has two text drawers and both subtract a per-UI spacing from
    every step. EN keeps every value below; the 2021 patch padded each Latin
    glyph by ~9 units to absorb them, which is what made the -2 menus look
    letter-spaced. With the EN-spaced glyphs of en_spacing.py they run letters
    together, so SPACING_PATCHES reduced them where the drawers add them. That
    pair was reverted: the 2021 font and stock spacings read more evenly.

    Drawer 1 (0x17CA90; tags, kerning): spacing in screen pixels, setter
    0x17E230. -7 AdvCstmUiSimple, -5 advUiSelectText, -2 the kerning menus.

    Drawer 2 (0x1281A0; step = scale * (advance + spacing)): spacing in font
    units at style+16 of a 56-byte style (template rodata 0x2B61DC, created
    through 0x39970). -6 ADV_TALK_MSG (the message window) and advUiSelectText,
    -8 UI_CONF_MSG_TEXT (Options dialogs) / UI_CONF_ITEM_TEXT / memory, -5
    UI_SIMPLE_TEXT, -12 / -14 the dictionary. The Options reset dialog fits
    step = advance - 7.46 px at 0.888 px/unit (0.37 px rms), i.e. -8 units;
    patching only the drawer-1 -7 changed nothing on screen.

OUTPUT
    <build id>.ips, offsets relative to the NSO header (+0x100), the layout both
    Ryujinx and Atmosphere expect under exefs_patches/<name>/.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 've-es', 'tools'))
from exefs import nso_segments                                  # noqa: E402

# (.text offset, original, patched)
PATCHES = [
    # Save list (both discs - -Unlimited- runs the same routine): every
    # character steps its own advance minus the Dictionary's 12 units,
    # s15 - 12 * s15 / adv, where s15 = size / cell * adv is also the width
    # the glyph is drawn at. The fixed-cell selector and the zero spacing in
    # s14 leave five slots; the three glyph-missing exits, which arrive with
    # s0 = 0, move one instruction on to skip them.
    (0x1739E0, 'a84356b8', 'a10356bc'),  # ldur w8,[x29,#-156] -> ldur s1,[x29,#-160] (adv)
    (0x1739E4, 'e01740bd', '21d8215e'),  # ldr s0,[sp,#20] -> scvtf s1,s1
    (0x1739E8, '1f0d0031', 'e119211e'),  # cmn w8,#3 -> fdiv s1,s15,s1 (scale)
    (0x1739EC, 'e00d201e', '0010351e'),  # fcsel s0,s15,s0,eq -> fmov s0,#-12.0
    (0x1739F0, '00282e1e', '003c011f'),  # fadd s0,s0,s14 -> fmadd s0,s0,s1,s15
    (0x1737E8, '40100035', '60100035'),  # cbnz w0 -> 0x1739F4
    (0x17381C, 'a00ef837', 'c00ef837'),  # tbnz w0,#31 -> 0x1739F4
    (0x17382C, '2b0e0054', '4b0e0054'),  # b.lt -> 0x1739F4

    # Drawer 1 steps like the Dictionary: advance - 12 font units. The
    # Dictionary is drawer 2 at -12 with the 2021 font, and is the one screen
    # that looked right; drawer 1 (chapter list, Options, help bars, the
    # centred ADV banner) stepped a fixed cell instead - size for multi-byte,
    # size * max_ascii_adv / 72 for ASCII - or, with #KerningOn (the 11
    # UI_OPTION_* screens), ASCII at adv / 58 against glyphs drawn at / 72.
    # Every character now takes the proportional path, divides by getSize()
    # whatever its width in bytes, and loses 12 units. getSize is a leaf
    # (ldrb w0,[x0,#9]); s9/s11 are callee-saved. Each UI's own pixel
    # spacing (-7/-5/-2) is dropped: -12 units is the whole Dictionary
    # spacing. The 2021 font has no advance below 12 (space 30), and kana /
    # kanji (72, ink ~59) still clear each other at 60.
    #
    # The record's +56 is both the pen step and the glyph's cell, and the
    # glyph drawer (0x17B670) compares the cell with the glyph's own width,
    # scale * atlas width, the atlas width being the GTAB advance byte
    # (0x176FDC, 0x177128): narrower is centred in the cell, wider is
    # squeezed into it. So -12 on its own squeezed every letter to ~0.65 and
    # left the gaps as they were - measured off a screenshot, pitch = 0.86 *
    # (adv - 12) px exactly, ink ~0.65 of the font's. Drawing every glyph at
    # its own width from the pen makes +56 the step alone. The atlas region
    # starts at bitmap column 0, so the letter lands at pen + lsb as designed.
    (0x17BF44, '08021037', '10000014'),  # tbnz w8,#2,+0x40 -> b +0x40   always proportional
    (0x17BF98, '68064039', 'e00316aa'),  # ldrb w8,[x19,#1] -> mov x0,x22
    (0x17BF9C, 'e00316aa', 'c9e8ff97'),  # mov x0,x22 -> bl getSize
    (0x17BFA0, '28010034', '0110351e'),  # cbz w8 -> fmov s1,#-12.0
    (0x17BFA4, 'c7e8ff97', '2929211e'),  # bl getSize -> fadd s9,s9,s1 (adv)
    (0x17C20C, 'ea011037', '0f000014'),  # same for the line-width pass
    (0x17C2A8, '78000034', '06e8ff97'),  # cbz w24 -> bl getSize
    (0x17C2AC, '05e8ff97', '0110351e'),  # bl getSize -> fmov s1,#-12.0
    (0x17C2B0, '02000014', '6b29211e'),  # b -> fadd s11,s11,s1 (adv)
    (0x17C2B4, 'b3e9ff97', '1f2003d5'),  # bl byte16 -> nop
    (0x17C2D0, '614e40bd', 'e103271e'),  # ldr s1,[x19,#76] -> fmov s1,wzr  wrap
    (0x17C32C, '614e40bd', 'e103271e'),  # ldr s1,[x19,#76] -> fmov s1,wzr  step
    (0x17C720, '615e41bd', 'e103271e'),  # ldr s1,[x19,#348] -> fmov s1,wzr  whole-string layout
    (0x17B750, 'e5000054', '08000014'),  # b.pl squeeze -> b 0x17B770 (skip centring too)
    (0x17B774, '0201221e', '1f2003d5'),  # scvtf s2,w8 -> nop: draw width = scale * width

    # Drawer 2 at the Dictionary's -12 for every horizontal style. Its step
    # is scale * (advance + style spacing) and it already draws glyphs at
    # their own width - the Dictionary measures pitch = adv - 12 with ink
    # at full size. The STORY panel of the chapter screen measured adv - 3,
    # ADV_TALK_MSG is -6, the Options dialogs -8, the Dictionary list -14.
    # Vertical text (0x127FE4, 0x1284EC) keeps its own value.
    (0x1286E8, '2801080b', '08310051'),  # add w8,w9,w8 -> sub w8,w8,#12
]

# Tried with en_spacing.py's EN-spaced font and reverted with it: that font
# mixed EN side bearings on ASCII with lsb 0 on the Vietnamese letters, and
# every screen looked uneven. Kept here because each was verified to do what
# it says.
SPACING_PATCHES = [
    # drawer 1, pixels
    (0x0490A0, '0090331e', '0010301e'),  # fmov s0,#-7.0 -> #-2.0  AdvCstmUiSimple
    (0x04BBC0, '0090321e', '0010301e'),  # fmov s0,#-5.0 -> #-2.0  advUiSelectText
    # Where the spacing is added, whatever set it - the message window's value
    # was never found among the constants. Drawer 2 keeps each UI's own value
    # divided by 4 (asr: -14 -4, -12 -3, -8/-6/-5 -2, 0 stays 0): forcing -2
    # everywhere ran the dictionary's description past its frame, which was
    # designed tight and in the 2021 patch came out at EN advance - 3.
    # Vertical text (0x127FE4, 0x1284EC) is left alone.
    (0x1286E8, '2801080b', '0809890b'),  # add w8,w9,w8 -> add w8,w8,w9,asr #2 drawer 2 step
    # Dictionary word lists: text x = list x + [entry+2120]. JP puts it against
    # the red row marker, which kana clear with their own side bearing; EN adds
    # 4.0 to x in both list functions (EN 0x63968, 0x67638). Done in place:
    # loading the offsets straight from x27 frees the two address adds for
    # "fmov s16,#4.0" and "fadd s0,s0,s16". x8/x9 are rewritten before any
    # read on every path and s16 is unused in both functions. A cave in the
    # .text page padding crashed the game on this screen - code past the
    # segment size in the header is not executable there.
    (0x066348, '68232191', '1010221e'),  # add x8,x27,#2120 -> fmov s16,#4.0
    (0x066354, '000140bd', '604b48bd'),  # ldr s0,[x8] -> ldr s0,[x27,#2120]
    (0x066358, '69332191', '0028301e'),  # add x9,x27,#2124 -> fadd s0,s0,s16
    (0x066360, '200140bd', '604f48bd'),  # ldr s0,[x9] -> ldr s0,[x27,#2124]
    (0x06A0F4, '68232191', '1010221e'),  # same, second list
    (0x06A100, '000140bd', '604b48bd'),
    (0x06A104, '69332191', '0028301e'),
    (0x06A10C, '200140bd', '604f48bd'),
]
NSO_HEADER = 0x100


def ips(records):
    out = bytearray(b'PATCH')
    for off, data in records:
        assert off < 0x1000000 and off != 0x454F46
        out += off.to_bytes(3, 'big') + len(data).to_bytes(2, 'big') + data
    return bytes(out + b'EOF')


def main():
    src, out_dir = sys.argv[1], sys.argv[2]
    nso = open(src, 'rb').read()
    text = nso_segments(nso)[0][1]
    records = []
    for off, original, patched in PATCHES:
        have = text[off:off + len(original) // 2].hex()
        if have != original:
            sys.exit('0x%X holds %s, expected %s - wrong build?'
                     % (off, have, original))
        records.append((off + NSO_HEADER, bytes.fromhex(patched)))
    build_id = nso[0x40:0x54].hex().upper()
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, build_id + '.ips')
    with open(dst, 'wb') as fh:
        fh.write(ips(records))
    print(dst)


if __name__ == '__main__':
    main()
