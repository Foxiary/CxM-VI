"""Give the Vietnamese font_Normal.ffu the English build's letter spacing.

    python3 en_spacing.py <vn font_Normal.ffu> <en font_Normal.ffu> <out.ffu>

TWO THINGS MADE VIETNAMESE TEXT LOOK LETTER-SPACED

1. The engine stretches every ASCII step by 72/58.
   With #KerningOn (the Options menu, among others) a character is drawn at
   size / getSize() and steps
       single-byte:  size * advance / max_ascii_advance     (font byte 16)
       multi-byte:   size * advance / getSize()             (header byte 9 = 72)
   max_ascii_advance is computed at load time as the largest advance among the
   codes 0..255 the font has. In the patch that is 58 ('W', '%'), so every
   Latin letter steps 1.24x its own width. Aksys fixed this in the EN
   executable by making getSize() return byte 16 as well (EN 0x183200), which
   also scales every glyph up by 72/54 - that is why the EN Latin is drawn
   small. We keep the JP executable and the glyph size, and instead give the
   font a blank glyph at U+007F with advance 72: the maximum becomes 72, the
   two divisors agree, and nothing is drawn bigger. DEL never occurs in text.

2. The patch padded the Latin glyphs.
   88 of the 94 printable ASCII glyphs are the EN bitmaps pixel for pixel, moved
   right by 2-10 px with the advance grown by 4-16. The Vietnamese letters were
   drawn the same way, and the "w8" experiment then packed them to lsb 0 with
   the advance rounded up to a multiple of 8.

WHAT THIS WRITES
    ASCII 0x21-0x7E  ink placed at the EN glyph's left bearing, advance = EN
                     left bearing + ink + EN right bearing. Identical to EN for
                     all but '~', which the patch lowered on purpose.
    Vietnamese       every glyph in U+0180-U+01FF / U+1E00-U+1E13 (the
                     retargeted letters) and every older code point holding
                     the same bitmap (the Greek/Cyrillic/circled-number
                     encoding old saves still use): ink at x = 0, advance =
                     ink + 1, the EN average.
    U+007F           blank, advance 72.

Bitmap width = advance rounded up to even: the cell is 75 rows and 4bpp rows
are packed in pairs, so an odd width does not fit; EN uses width == advance.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 've-es', 'tools'))
from ffu import FFU                                             # noqa: E402

FULL_WIDTH = 72          # header byte 9 of font_Normal
DEL = '\x7f'


def chars(f):
    """(char, glyph index) for every code point in the range table."""
    for start, end, base in f.ranges:
        for v in range(start, end):
            b = v.to_bytes((v.bit_length() + 7) // 8 or 1, 'big')
            try:
                yield b.decode('utf-8'), base + v - start
            except UnicodeDecodeError:
                pass


def despeckle(rows):
    """Drop specks of at most 4 faint pixels (index <= 4) not touching the letter.

    The patch's n u W w _ ~ are the EN bitmaps plus 1-4 such pixels in the last
    column or row of the cell - whatever its tool read past the glyph. Left in,
    they widen the ink box of 'n' by 10 units.
    """
    h, w = len(rows), len(rows[0])
    rows = [r[:] for r in rows]
    seen = set()
    for y in range(h):
        for x in range(w):
            if not rows[y][x] or (y, x) in seen:
                continue
            todo, part = [(y, x)], []
            seen.add((y, x))
            while todo:
                a, b = todo.pop()
                part.append((a, b))
                for p in ((a + i, b + j) for i in (-1, 0, 1) for j in (-1, 0, 1)):
                    if 0 <= p[0] < h and 0 <= p[1] < w and rows[p[0]][p[1]] \
                            and p not in seen:
                        seen.add(p)
                        todo.append(p)
            if len(part) <= 4 and max(rows[a][b] for a, b in part) <= 4:
                for a, b in part:
                    rows[a][b] = 0
    return rows


def ink_box(rows):
    """(left, right) columns holding any non-zero pixel, or None."""
    cols = [x for x in range(len(rows[0])) if any(r[x] for r in rows)]
    return (cols[0], cols[-1]) if cols else None


def place(rows, box, lsb, adv):
    """Crop rows to box and redraw them at x = lsb in a cell of `adv` width."""
    left, right = box
    w = adv + (adv & 1)
    out = []
    for r in rows:
        line = [0] * w
        line[lsb:lsb + right - left + 1] = r[left:right + 1]
        out.append(line)
    return out


def bitmap_bytes(f, gi):
    g = f.glyphs[gi]
    return f.raw[f.off_bmp + g['off']:f.off_bmp + g['off'] + g['size']]


def main():
    vn = FFU(open(sys.argv[1], 'rb').read())
    en = FFU(open(sys.argv[2], 'rb').read())
    new = {}

    for code in range(0x21, 0x7f):
        ch = chr(code)
        rows = despeckle(vn.bitmap(vn.index(ch))[2])
        box = ink_box(rows)
        egi = en.index(ch)
        _, _, erows = en.bitmap(egi)
        ebox = ink_box(erows)
        if box is None or ebox is None:
            continue
        lsb = ebox[0]
        rsb = en.glyphs[egi]['adv'] - ebox[1] - 1
        adv = lsb + (box[1] - box[0] + 1) + rsb
        new[ch] = (adv, place(rows, box, lsb, adv))

    retargeted = [ch for ch, _ in chars(vn)
                  if 0x180 <= ord(ch) <= 0x1FF or 0x1E00 <= ord(ch) <= 0x1E13]
    shapes = {bitmap_bytes(vn, vn.index(ch)) for ch in retargeted}
    letters = [ch for ch, gi in chars(vn)
               if ord(ch) > 0x7F and bitmap_bytes(vn, gi) in shapes]
    for ch in letters:
        rows = despeckle(vn.bitmap(vn.index(ch))[2])
        box = ink_box(rows)
        if box is None:
            continue
        adv = box[1] - box[0] + 2
        new[ch] = (adv, place(rows, box, 0, adv))

    height = vn.glyphs[vn.index('a')]['h']
    new[DEL] = (FULL_WIDTH, [[0, 0] for _ in range(height)])

    out = vn.build(new)
    check = FFU(out)
    peak = max(check.glyphs[b + c - s]['adv']
               for s, e, b in check.ranges for c in range(s, e) if c < 256)
    assert peak == FULL_WIDTH, peak
    with open(sys.argv[3], 'wb') as fh:
        fh.write(out)
    print('ascii %d, vietnamese %d (%d retargeted + older twins), '
          'max ascii advance %d -> %s'
          % (sum(1 for c in new if '\x20' < c < DEL), len(letters),
             len(retargeted), peak, sys.argv[3]))


if __name__ == '__main__':
    main()
