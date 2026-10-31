"""Vietnamese subtitles for the main game's voice recorder.

    python3 visub.py tex OUTDIR            render SUBTITLE/00..24.tid in Vietnamese
    python3 visub.py swap SRC DST TEXDIR   replace them in a GAME_01.cpk that
                                           already carries them (voicesub.py cpk)

The main game's subtitles are pictures, not text: 25 pre-drawn
VOICERECORDER/SUBTITLE/%02u.tid, 672x456, one per row of the recorder (five
leads x five questions), drawn at (288, 88) by voicesub.s. The English build
paints each answer onto a speech-bubble panel with its question in the red bar.
This draws the same panel with the Vietnamese text instead.

THE TEXT
    work/voice/mainsub/vi.txt, the translation by Yui
    (https://ellipsus.com/read/4uVrcK02KldUe3FeYPQWVK, theme labyrinth), copied
    as plain text: per character a name line, then five lines
    "<question>: “<answer>”", then a blank line. Characters in the order Aiji,
    Kei, Mineo, Takeru, Kageyuki and questions in the English order (basic
    info, hobbies/skills, likes, dislikes, type), which is the order of
    voice_aiji01.tid ... voice_kageyuki05.tid. The file is gitignored like
    every other piece of content.

THE PANEL
    The English textures are BC7 in its GAME_01.CPK. No one of them is clean,
    but each pixel is uncovered in most of them: panel() takes, per pixel, the
    median of the 25 with every text pixel (and a 3-pixel ring round it) left
    out. The few pixels covered in all 25 (opening quotes at the left margin)
    take the panel's flat body colour; the question band of the red bar is
    interpolated top to bottom, column by column. Cached as panel.png.

THE FONT
    The game's own font_Normal.ffu (SYSTEM.cpk WINDOW/FONT/, the 2021 bytes the
    message window draws with), white glyphs with their dark edge, stepped
    `advance - 12` units as every horizontal line in the mod is (CLAUDE.md,
    letter spacing). The cells overlap at that step, so a line draws every
    glyph's dark edge before any of their white (Font.line). The question in
    the red bar gets a 2-texel dark outline instead, grown from the scaled
    letters: the font's own edge vanishes at 0.40. It has no glyph at the Vietnamese code points: the 2021
    patch drew each Vietnamese letter over a borrowed one (Greek, Cyrillic,
    circled digits) and its text uses those. VI_2021 is that table. Nothing in
    the repo recorded it, so it was read back out of the 2021 text in
    SYSTEM.cpk: every lowercase letter is attested by the words it spells
    there (Ω in "đến giết biết", Л in "được người nhưng"), the capitals follow
    the same tone order in their own blocks (С Т У Ф Х = À Á Ả Ã Ạ), and the
    three capitals this text uses (À Ừ Đ) were checked against their bitmaps.
    The em dash, which the font lacks, is drawn as its ― and the single curly
    quotes, which sit at the edges of full-width cells, are trimmed to their ink.

LAYOUT, measured off the English textures
    question: left at x 174 in the red bar (161..618, 19..61), centred on it
    answer:   opening quote at x 143, wrapped lines hang behind it, first line
              ink top at y 80; right edge 640
    The English answers are a third the length of these, so each texture
    takes the largest scale from 0.40 (cap height 18 px, as in English) down
    that keeps its last line above the panel's bottom frame (y 436).

The texture is DXT5 like every other JP texture (patch_sub re-encoded the
English BC7 for the same reason), header copied from the English file with
its fourcc changed. `swap` is unlsub.cmd_swap: SUBTITLE has the same directory
name in GAME_01 as in GAME_02, so it replaces the 25 files in place, appending
the new bytes after the content.
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'work', 'voice', 'mainsub')   # gitignored
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'event'))

EN_CPK = os.path.expanduser('~/Documents/Game/010083E00F40E000/romfs/GAME_01.CPK')
JP_SYSTEM = os.path.expanduser('~/Documents/Ryujinx/mods/contents/01002b400e9da000/'
                               'PatchVietHoa/romfs/CONTENTS/SYSTEM.cpk')
FONT_PATH = 'WINDOW/FONT/font_Normal.ffu'
TEXT = os.path.join(DATA, 'vi.txt')
PANEL = os.path.join(DATA, 'panel.png')
SUBDIR = 'VOICERECORDER/SUBTITLE'
CHARACTERS = ('Yanagi Aiji', 'Okazaki Kei', 'Enomoto Mineo', 'Sasazuka Takeru',
              'Shiraishi Kageyuki')

SIZE = (672, 456)
BAR = (161, 19, 619, 62)               # the red bar, exclusive
BAND = (166, 26, 615, 54)              # its question band, rows 26 and 54 kept
BODY = (138, 66, 645, 437)             # inside the frame, where text was
BODY_COLOUR = (8, 0, 2, 242)
Q_X, Q_SCALE, Q_STROKE = 174, 0.40, 2
STROKE_COLOUR, STROKE_ALPHA = (40, 6, 4), 230   # the question's outline
A_X, A_RIGHT, A_TOP, A_BOTTOM = 143, 640, 80, 436
A_SCALES = [s / 100 for s in range(40, 29, -1)]
SPACING = -12                          # units added to every advance
PITCH = 80                             # units from line to line; the cell is 75

# Vietnamese letter -> the code point the 2021 font_Normal draws it at.
VI_2021 = dict(zip(
    'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệ'
    'ỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ—',
    'СТЫФвг×мнчш÷ъ①②⑬ΑΒΛΔΣΤδεζπρАτБВНбΡ⑱⑰пθ④Дцο⑪ЛХΕУΓЧΗЦΖШΘЩΙЪΚЭΝЬΜЮΞЯΟаΠжΧдΥеΦиΩзΨйαкβлγ'
    'оηрιыυщσэχьφюψяωёЁтλсκуμфνхξ⑤Е③Г⑦З⑥Ж⑧И⑨Й⑩К⑫М⑯Р⑭О⑮П―'))
TRIM = '‘’'
EDGE_END = 5                           # palette indices below this are the edge                            # full-width cells, quote at one edge


def en_textures():
    """[(name, raw .tid bytes)] of SUBTITLE/00..24.tid in the English GAME_01.CPK,
    read without loading the 3 GB archive."""
    from cpk import UTF, crilayla
    out = []
    with open(EN_CPK, 'rb') as fh:
        hdr = UTF(bytearray(fh.read(0x800)), 0x10).rows[0]
        fh.seek(0)
        prefix = bytearray(fh.read(hdr['ContentOffset']))
        for r in UTF(prefix, hdr['TocOffset'] + 0x10).rows:
            if r['DirName'] != SUBDIR:
                continue
            fh.seek(hdr['TocOffset'] + r['FileOffset'])
            raw = fh.read(r['FileSize'])
            if raw[:8] == b'CRILAYLA':
                raw = crilayla(raw)
            out.append((r['FileName'], raw))
    out.sort()
    if [n for n, _r in out] != ['%02d.tid' % i for i in range(25)]:
        raise SystemExit('%s: unexpected %s files' % (EN_CPK, SUBDIR))
    return out


def is_text(p):
    r, g, b, a = p
    return a > 200 and min(r, g, b) > 110 and max(r, g, b) - min(r, g, b) < 40


def panel(images):
    """The English panel with no text on it; see the module notes."""
    from PIL import Image, ImageFilter
    if os.path.exists(PANEL):
        return Image.open(PANEL).convert('RGBA')
    w, h = SIZE
    pix = [im.load() for im in images]
    masks = []
    for p in pix:
        m = Image.new('L', SIZE)
        mp = m.load()
        for y in range(15, 446):
            for x in range(140, 666):
                if is_text(p[x, y]):
                    mp[x, y] = 255
        masks.append(m.filter(ImageFilter.MaxFilter(7)).load())
    out = Image.new('RGBA', SIZE)
    op = out.load()
    x0, y0, x1, y1 = BODY
    for y in range(h):
        for x in range(w):
            v = [pix[i][x, y] for i in range(len(pix)) if not masks[i][x, y]]
            if not v:
                if x0 <= x < x1 and y0 <= y < y1:
                    op[x, y] = BODY_COLOUR
                    continue
                v = [p[x, y] for p in pix]
            v.sort(key=lambda c: 3 * c[0] + 5 * c[1] + c[2] + c[3])
            op[x, y] = v[len(v) // 2]
    bx0, by0, bx1, by1 = BAND
    for x in range(bx0, bx1):
        top, bot = op[x, by0], op[x, by1]
        for y in range(by0 + 1, by1):
            t = (y - by0) / (by1 - by0)
            op[x, y] = tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(4))
    left = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if is_text(op[x, y])]
    if len(left) > 80:
        raise SystemExit('the cleaned panel still has %d text pixels' % len(left))
    out.save(PANEL)
    return out


def read_text():
    """[(question, answer)] x 25 from vi.txt, in texture order."""
    blocks = [b.strip() for b in open(TEXT, encoding='utf-8').read().split('\n\n') if b.strip()]
    if len(blocks) != len(CHARACTERS):
        raise SystemExit('%s: %d characters, expected %d' % (TEXT, len(blocks), len(CHARACTERS)))
    rows = []
    for name, block in zip(CHARACTERS, blocks):
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if lines[0] != name or len(lines) != 6:
            raise SystemExit('%s: block %r is not %s and five answers' % (TEXT, lines[0], name))
        for line in lines[1:]:
            q, _sep, a = line.partition(':')
            a = re.sub(r'\s+', ' ', a).strip()
            if not a.startswith('“') or not a.endswith('”'):
                raise SystemExit('%s: %s / %s is not quoted' % (TEXT, name, q))
            rows.append((q.strip(), a))
    return rows


class Font:
    """font_Normal.ffu drawn the way the game steps it."""

    def __init__(self):
        from cpk import CPK
        from ffu import FFU
        cpk = CPK(JP_SYSTEM)
        row = next(r for _i, full, r in cpk.files() if full == FONT_PATH)
        self.f = FFU(cpk.read(row))
        self.cache = {}

    def glyph(self, ch):
        """(step in units, ink image, edge image, x offset) of one character.

        The palette's indices 1-4 are a translucent black edge round the
        glyph, 5-15 its grey-to-white ink; the two are kept apart so a line
        can put every edge under every letter (see line()).
        """
        from PIL import Image
        if ch in self.cache:
            return self.cache[ch]
        gi = self.f.index(VI_2021.get(ch, ch))
        if gi is None:
            raise SystemExit('font_Normal has no %r' % ch)
        w, h, rows = self.f.bitmap(gi)
        pal = self.f.palettes[0]
        clear = (0, 0, 0, 0)
        ink = Image.new('RGBA', (w, h))
        ink.putdata([pal[v] if v >= EDGE_END else clear for r in rows for v in r])
        edge = Image.new('RGBA', (w, h))
        edge.putdata([pal[v] if 0 < v < EDGE_END else clear for r in rows for v in r])
        adv, dx = self.f.glyphs[gi]['adv'], 0
        if ch in TRIM:
            x0, _y0, x1, _y1 = ink.getbbox()
            ink, edge = ink.crop((x0, 0, x1, h)), edge.crop((x0, 0, x1, h))
            dx, adv = 4, x1 - x0 + 8 - SPACING
        self.cache[ch] = (adv + SPACING, ink, edge, dx)
        return self.cache[ch]

    def width(self, text):
        return sum(self.glyph(c)[0] for c in text)

    def line(self, text, scale, stroke=0):
        """RGBA image of one line at `scale`, cell rows 0..74 included.

        At `adv - 12` each cell overlaps the one before it, so drawing glyph by
        glyph lets a letter's dark edge cover the white of its neighbour: the
        question on the red bar came out smudged. Every edge goes down first,
        then every letter.

        The font's own edge is 1-4 px of translucent black at full size, under
        a pixel once scaled to 0.40: on the red bar it does not show. With
        `stroke` (texels) the edge is replaced by a solid dark outline grown
        from the scaled letters themselves, so it is even all round and never
        reaches into the next letter's white.
        """
        from PIL import Image, ImageFilter
        size = (max(self.width(text), 1) + 80, 75)
        im = Image.new('RGBA', size, (0, 0, 0, 0))
        for layer in ((1,) if stroke else (2, 1)):
            x = 0
            for c in text:
                g = self.glyph(c)
                im.alpha_composite(g[layer], (x + g[3], 0))
                x += g[0]
        im = im.convert('RGBa').resize((round(size[0] * scale), round(75 * scale)),
                                       Image.LANCZOS).convert('RGBA')
        if not stroke:
            return im
        pad = stroke + 1
        ink = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
        ink.alpha_composite(im, (pad, pad))
        grown = ink.getchannel('A').filter(ImageFilter.MaxFilter(2 * stroke + 1))
        grown = grown.filter(ImageFilter.GaussianBlur(0.6)).point(lambda v: min(255, v * STROKE_ALPHA // 255))
        out = Image.new('RGBA', ink.size, STROKE_COLOUR + (0,))
        out.putalpha(grown)
        out.alpha_composite(ink)
        return out.crop((pad, pad, pad + im.width, pad + im.height))


def wrap(font, text, width, indent):
    lines, cur = [], ''
    for word in text.split(' '):
        trial = (cur + ' ' + word).strip()
        if font.width(trial) <= width - (indent if lines else 0):
            cur = trial
        else:
            if not cur:
                raise SystemExit('%r does not fit a line' % word)
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def layout(font, answer):
    """(scale, lines, hanging indent in units) at the largest scale that fits."""
    indent = font.glyph('“')[0]
    for scale in A_SCALES:
        lines = wrap(font, answer, (A_RIGHT - A_X) / scale, indent)
        if A_TOP + scale * (PITCH * (len(lines) - 1) + 75) <= A_BOTTOM:
            return scale, lines, indent
    raise SystemExit('answer does not fit even at %.2f: %s...' % (A_SCALES[-1], answer[:40]))


def render(base, font, number, question, answer):
    img = base.copy()
    title = font.line('Câu %d: %s' % (number, question), Q_SCALE, Q_STROKE)
    bx0, by0, bx1, by1 = BAR
    if Q_X + title.width > bx1 - 8:
        raise SystemExit('question %r is wider than the bar' % question)
    img.alpha_composite(title, (Q_X, (by0 + by1 - title.height) // 2))
    scale, lines, indent = layout(font, answer)
    for i, text in enumerate(lines):
        ln = font.line(text, scale)
        img.alpha_composite(ln, (A_X + (round(indent * scale) if i else 0),
                                 round(A_TOP + scale * PITCH * i)))
    return img, scale, len(lines)


def tid_bytes(raw_en, img):
    from dxt5 import encode_into
    w, h = img.size
    payload = encode_into(b'\0' * (w * h), img, (0, 0, w, h))
    head = bytearray(raw_en[:0x80])
    if struct.unpack_from('<II', head, 0x44) != (w, h) or \
            struct.unpack_from('<I', head, 0x58)[0] != len(payload):
        raise SystemExit('English header does not describe a %dx%d texture' % (w, h))
    head[0x64:0x68] = b'DXT5'
    struct.pack_into('<I', head, 0x04, 0x80 + len(payload))
    return bytes(head) + payload


def cmd_tex(out):
    from tid import TID
    from PIL import Image
    en = en_textures()
    images = [TID(raw).image().convert('RGBA') for _n, raw in en]
    if any(im.size != SIZE for im in images):
        raise SystemExit('English subtitles are not %dx%d' % SIZE)
    base = panel(images)
    font = Font()
    rows = read_text()
    os.makedirs(out, exist_ok=True)
    sheet = Image.new('RGBA', (SIZE[0] * 5, SIZE[1] * 5), (40, 40, 40, 255))
    for k, ((name, raw), (q, a)) in enumerate(zip(en, rows)):
        img, scale, n = render(base, font, k % 5 + 1, q, a)
        with open(os.path.join(out, name), 'wb') as fh:
            fh.write(tid_bytes(raw, img))
        img.save(os.path.join(out, name[:-4] + '.png'))
        sheet.alpha_composite(img, ((k % 5) * SIZE[0], (k // 5) * SIZE[1]))
        print('  %s  %-22s scale %.2f, %2d lines' % (name, raw[0x20:0x40].rstrip(b'\0').decode(), scale, n))
    sheet.save(os.path.join(out, 'sheet.png'))
    print('25 textures -> %s' % out)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'tex' and len(sys.argv) == 3:
        cmd_tex(sys.argv[2])
    elif cmd == 'swap' and len(sys.argv) == 5:
        import unlsub
        if unlsub.SUBDIR != SUBDIR:
            raise SystemExit('unlsub swaps %s, not %s' % (unlsub.SUBDIR, SUBDIR))
        unlsub.cmd_swap(*sys.argv[2:5])
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
