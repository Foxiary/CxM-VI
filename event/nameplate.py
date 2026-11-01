"""Character name plates (ADV/EFFECT/401-434) with the mod's names and Vietnamese titles.

    python3 event/nameplate.py build      render work/plate/out/<n>_<disc>.CL3 + previews
    python3 event/nameplate.py install    write them into GAME_01 / GAME_02 of both mods
    python3 event/nameplate.py restore    put the JP plates back

When a character first appears, the effect ADV/EFFECT/4nn.CL3 ("ネームプレート")
slides in a plate: a 400x200 sprite (TI block 0, uv 0..0.78 of a 1024x512
texture) with the name in big letters, the age, and a smaller title under it.
JP writes both in Japanese. The English builds kept the CWD and TI byte for
byte and only redrew the texture; disc 2 adds nine plates (426-434, Someya
Yuka and later versions of 407-414).

This draws the plate on the English texture of the same number, so the
frame, the background streaks and the leading triangle are the English ones:
  - the name line in the English plates' own letters: each big initial (a
    red-grey capital, h 90 in the first word, 64 in the second) and each
    small white letter is cut out of the 55 English plates, keyed by the
    known English names, and set family name first;
  - the age "(nn)" is moved along, as cut;
  - the title, in Vietnamese, in Old Standard TT at the English title's
    size (cap 23 px) - the English title face is a Didone of the same cut,
    and Old Standard covers the Vietnamese marks.
The background under the old letters is taken from another English plate
where those pixels are clear (every plate shares one background).

The new texture goes back as DXT5 (the English one is BC7 / format 0x94),
with the JP texture's header, into the JP CL3, whose CWD and TI are the same.
"""
import os
import struct
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 've-es', 'tools'))
sys.path.insert(0, HERE)
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from cpk import CPK  # noqa: E402
from dxt5 import encode_into  # noqa: E402
from tid import TID  # noqa: E402
from nameplate_text import NAMES, TITLES  # noqa: E402

DATA = os.path.join(ROOT, 'work', 'plate')
FONT = os.path.join(ROOT, 'work', 'album', 'fonts', 'OldStandardTT-Regular.ttf')
MODS = [os.path.expanduser('~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa/romfs/CONTENTS'),
        os.path.expanduser('~/Documents/Ryujinx/sdcard/atmosphere/contents/01002b400e9da000/romfs/CONTENTS')]
EN = {1: 'en1', 2: 'en2'}           # English CL3s, pulled by pull()
JP = {1: 'jp1', 2: 'jp2'}
EN1_CPK = os.path.expanduser('~/Documents/Game/010083E00F40E000/romfs/GAME_01.CPK')
EN2_NSP = os.path.expanduser('~/Documents/Game/Collar X Malice -Unlimited [0100E3B00F412000] [USA] [v0].nsp')
VENV_PY = os.path.join(ROOT, 'work', 'album', '.venv', 'bin', 'python')

# English names on the plates (given name first), to key the letters
EN_NAMES = {n: '%s %s' % (g, f) for n, (f, g, _a, _b) in NAMES.items()}
EN_NAMES[409] = 'Yuzuru Saeki'
EN_NAMES[418] = 'Keisuke Sanjo'
EN_NAMES[413] = 'Kenzou Satake'
EN_NAMES[415] = 'Yuusaku Takaeda'
EN_NAMES[421] = 'Manabu Souda'

NAME_BOX = (0, 20, 545, 150)        # name line: initials, small letters, age
TITLE_BOX = (30, 160, 540, 256)     # title lines
WHITE = 150                         # small letters / title: grey level above this is ink
TITLE_SIZE = 31                     # Old Standard: cap 23 px, as the English titles
TITLE_X = 36
BG_LEVEL = 14                       # red level of the plate's dark field behind the name
RIGHT = 520                         # name and title ink stop here: the PROFILE strip starts at
                                    # 542 and the English plates keep 8+ px off it (widest 534)
GAP_WORDS = 18                      # px between the end of a word and the next initial


def plates(disc):
    return sorted(n for n, v in NAMES.items() if v[2 if disc == 1 else 3] is not None)


# ------------------------------------------------------------------ files

def cl3_members(b):
    i = b.find(b'FILE_COLLECTION')
    cnt, _size, off = struct.unpack_from('<III', b, i + 0x20)
    out = {}
    for k in range(cnt):
        e = off + k * 0x230
        fn = b[e:e + 0x200].split(b'\0')[0].decode('cp932')
        _idx, o, sz = struct.unpack_from('<3I', b, e + 0x200)
        out[fn.rsplit('.', 1)[-1]] = (off + o, sz)
    return out


def tex_of(b):
    o, sz = cl3_members(b)['tid']
    t = b[o:o + sz]
    if t[3] == 0x94:
        w, h = struct.unpack_from('<II', t, 0x44)
        return Image.frombytes('RGBA', (w, h), bytes(t[0x80:0x80 + w * h]), 'bcn', 7)
    return TID(t).image().convert('RGBA')


def pull():
    """Copy the 4nn CL3s of the four sources into work/plate/<src>/."""
    import subprocess
    want = ['ADV/EFFECT/%d.CL3' % n for n in NAMES]
    for src, path in (('jp1', os.path.join(MODS[1], 'GAME_01.cpk')), ('jp2', os.path.join(MODS[1], 'GAME_02.cpk')),
                      ('en1', EN1_CPK)):
        d = os.path.join(DATA, src)
        os.makedirs(d, exist_ok=True)
        if len(os.listdir(d)) >= len(plates(1 if src.endswith('1') else 2)):
            continue
        c = CPK(path)
        for _i, f, r in c.files():
            if f in want:
                open(os.path.join(d, os.path.basename(f)), 'wb').write(c.read(r))
    d = os.path.join(DATA, 'en2')
    os.makedirs(d, exist_ok=True)
    for n in plates(2):
        p = os.path.join(d, '%d.CL3' % n)
        if os.path.exists(p):
            continue
        subprocess.check_call([VENV_PY, os.path.join(HERE, 'nsp_cpk_file.py'), EN2_NSP, 'GAME_02.CPK',
                               'ADV/EFFECT/%d.CL3' % n, d], stdout=subprocess.DEVNULL)
        os.rename(os.path.join(d, 'ADV__EFFECT__%d.CL3' % n), p)


# ------------------------------------------------------------- letters

def components(im, box, keep):
    """Connected ink components inside box; keep(r, g, b, a) says what is ink."""
    px = im.load()
    x0, y0, x1, y1 = box
    ink = {(x, y) for y in range(y0, y1) for x in range(x0, x1) if keep(*px[x, y])}
    out, seen = [], set()
    for p in sorted(ink, key=lambda q: (q[0], q[1])):
        if p in seen:
            continue
        q, pts = deque([p]), []
        seen.add(p)
        while q:
            cx, cy = q.popleft()
            pts.append((cx, cy))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (cx + dx, cy + dy)
                    if n in ink and n not in seen:
                        seen.add(n)
                        q.append(n)
        if len(pts) >= 12:
            xs = [a for a, _ in pts]
            ys = [b for _, b in pts]
            out.append((min(xs), max(xs), min(ys), max(ys), pts))
    return out


def is_initial(r, g, b, a):
    return a > 80 and r > 60 and r > g + 40          # red-grey capitals


def is_white(r, g, b, a):
    return a > 80 and min(r, g, b) > WHITE


def name_parts(im):
    """[(initial comp, [letter comps in x order])] for each word, and the age comps."""
    caps = components(im, NAME_BOX, is_initial)
    caps = [c for c in caps if c[3] - c[2] > 40]
    smalls = [c for c in components(im, NAME_BOX, is_white) if c[0] < 540]
    caps.sort(key=lambda c: c[0])
    words = []
    for i, c in enumerate(caps):
        nxt = caps[i + 1][0] if i + 1 < len(caps) else 10 ** 6
        mine = [s for s in smalls if c[0] - 15 <= s[0] < nxt - 15 and s[0] > c[0] + (c[1] - c[0]) * 0.55]
        words.append((c, sorted(mine, key=lambda s: s[0])))
    return words


def cut(im, comp, pad=2, red=False):
    """Cut-out of a component: flat ink colour, alpha from how far each pixel stands above the
    plate's dark field. Red capitals are measured on r - g, so the grey streaks of the
    background that cross them (r == g) stay out; white letters on brightness."""
    x0, x1, y0, y1, pts = comp
    out = Image.new('RGBA', (x1 - x0 + 1 + 2 * pad, y1 - y0 + 1 + 2 * pad), (0, 0, 0, 0))
    px = im.load()
    o = out.load()
    s = set(pts)
    ink = (205, 92, 92) if red else (255, 255, 255)
    for y in range(y0 - pad, y1 + pad + 1):
        for x in range(x0 - pad, x1 + pad + 1):
            if not any((x + dx, y + dy) in s for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)):
                continue
            r, g, b, _a = px[x, y]
            if red:
                t = (r - g - 2) / (205 - 92 - 2)
            else:
                t = (min(r, g, b) - BG_LEVEL) / (255 - BG_LEVEL)
            t = max(0.0, min(1.0, t))
            o[x - x0 + pad, y - y0 + pad] = ink + (round(255 * t),)
    return out, x0 - pad, y0 - pad


CAP_CLEAR = 8
LETTER_GAP = 4                      # ink gap between lowercase letters (EN median)


def clear_of(cap, cap_y, gi, gy, x):
    """Smallest x >= the given one at which glyph gi (top gy, left x) keeps CAP_CLEAR px of
    dark between its ink and the initial's (cap at 0, top cap_y), row by row within
    CAP_CLEAR rows either way."""
    def rows(im, top, right):
        a = im.split()[3].load()
        out = {}
        for j in range(im.height):
            cols = [i for i in range(im.width) if a[i, j] > 64]
            if cols:
                out[j + top] = max(cols) if right else min(cols)
        return out
    cap_r = rows(cap, cap_y, True)
    g_l = rows(gi, gy, False)
    need = 0
    for y, left in g_l.items():
        for dy in range(-CAP_CLEAR + 1, CAP_CLEAR):
            if y + dy in cap_r:
                need = max(need, cap_r[y + dy] + CAP_CLEAR - left)
    return max(x, need)


XLET = 'acemnorsuvwxzi'                # no ascender or descender (i without its dot)


def word_metrics(im, n):
    """[(baseline y, x-height, size class)] of the two words of English plate n. The English
    plates set the first word's lowercase at x-height ~30 and the second's at ~25 (both ~25 on
    most -Unlimited- plates); the class is 'L' or 'S'."""
    out = []
    for (cap, ls), word in zip(name_parts(im), EN_NAMES[n].split()):
        body = [c for c in ls if c[3] - c[2] > 12][:len(word) - 1]
        xs = [c for c, ch in zip(body, word[1:]) if ch in XLET]
        base = sorted(c[3] for c in xs)[len(xs) // 2] if xs else cap[3] - 8
        xh = sorted(c[3] - c[2] + 1 for c in xs)[len(xs) // 2] if xs else 30
        out.append((base, xh, 'L' if xh >= 29 else 'S'))
    return out


class Letters:
    """Glyphs cut from the English plates: initials per word slot, lowercase per size class,
    every glyph's top kept relative to its word's baseline so a word sits on one line."""

    def __init__(self, ims):
        self.caps = {1: {}, 2: {}}          # word slot -> letter -> (img, top - baseline)
        self.kern = {}                      # (slot, initial) -> [EN ink gap to the next letter, px]
        self.small = {'L': {}, 'S': {}}     # size class -> letter -> (img, top - baseline, ink width)
        self.xh = {'L': [], 'S': []}
        for n, im in ims.items():
            words = name_parts(im)
            given, family = EN_NAMES[n].split()
            if len(words) != 2:
                raise SystemExit('plate %d: %d words' % (n, len(words)))
            metrics = word_metrics(im, n)
            for slot, ((cap, letters), word, (base, xh, cls)) in enumerate(
                    zip(words, (given, family), metrics), 1):
                ci, cx, cy = cut(im, cap, red=True)
                self.caps[slot].setdefault(word[0], (ci, cy - base))
                self.xh[cls].append(xh)
                if letters:
                    self.kern.setdefault((slot, word[0]), []).append(letters[0][0] - cap[1])
                body = [c for c in letters if c[3] - c[2] > 12]
                dots = [c for c in letters if c[3] - c[2] <= 12]
                rest = word[1:]
                if slot == 2:
                    age = body[len(rest):]
                    body = body[:len(rest)]
                    dots = [d for d in dots if not age or d[0] < age[0][0] - 5]
                if len(body) != len(rest):
                    continue
                for comp, ch in zip(body, rest):
                    mine = [d for d in dots if comp[0] - 3 <= (d[0] + d[1]) / 2 <= comp[1] + 3]
                    merged = (min([comp[0]] + [d[0] for d in mine]), max([comp[1]] + [d[1] for d in mine]),
                              min([comp[2]] + [d[2] for d in mine]), max([comp[3]] + [d[3] for d in mine]),
                              comp[4] + sum((d[4] for d in mine), []))
                    if ch not in self.small[cls]:
                        gi, gx, gy = cut(im, merged)
                        # letters without a descender sit with their own ink bottom on the
                        # baseline (the English baseline wanders a pixel or two per plate)
                        bottom = base if ch in 'gjpqy' else merged[3]
                        self.small[cls][ch] = (gi, gy - bottom, merged[1] - merged[0] + 1)
        for cls in self.xh:
            v = sorted(self.xh[cls])
            self.xh[cls] = v[len(v) // 2]

    def glyph(self, ch, cls):
        """(img, top - baseline, ink width) of a lowercase letter in size class cls; taken from
        the other class and scaled by the x-height ratio when this one never had it."""
        if ch in self.small[cls]:
            return self.small[cls][ch]
        other = 'S' if cls == 'L' else 'L'
        gi, rel, w = self.small[other][ch]
        f = self.xh[cls] / self.xh[other]
        gi = gi.resize((max(1, round(gi.width * f)), max(1, round(gi.height * f))), Image.LANCZOS)
        return gi, round(rel * f), round(w * f)

    def age_of(self, im, n):
        """The age "(nn)" cut from this very plate (disc 1 and disc 2 differ on 417)."""
        words = name_parts(im)
        family = EN_NAMES[n].split()[1]
        body = [c for c in words[1][1] if c[3] - c[2] > 12][len(family) - 1:]
        if not body:
            return None
        dots = [d for d in words[1][1] if d[3] - d[2] <= 12 and d[0] > body[0][0] - 5]
        return [cut(im, c) for c in body + dots]

    def clean(self, im):
        """This plate with every letter pixel (red cap, white letter, their anti-aliased rims)
        replaced by the background the plates share."""
        out = im.copy()
        px, bg = out.load(), self.background.load()
        for y in list(range(NAME_BOX[1], 143)) + list(range(163, 256)):
            for x in range(0, 540):
                r, g, b, _a = px[x, y]
                if r - g > 30 or min(r, g, b) > 70:
                    for dx in (-2, -1, 0, 1, 2):
                        for dy in (-2, -1, 0, 1, 2):
                            if 0 <= x + dx < 540 and (NAME_BOX[1] <= y + dy < 145 or 161 <= y + dy < 256):
                                px[x + dx, y + dy] = bg[x + dx, y + dy]
        return out

    def word(self, text, slot, base, cls):
        """[(img, x, y)] of one word on baseline `base`, x from its initial's left edge; the
        initial is this slot's, the lowercase of size class cls."""
        cap = self.caps[slot].get(text[0]) or self.caps[3 - slot].get(text[0])
        if cap is None:
            raise SystemExit('no initial %r' % text[0])
        ci, rel = cap
        if text[0] not in self.caps[slot]:
            # borrowed from the other word: scale to this slot's cap height; the first word's
            # initial sits 8 px below the baseline, the second's 1 px
            want = 90 if slot == 1 else 64
            f = want / (ci.height - 4)
            ci = ci.resize((round(ci.width * f), round(ci.height * f)), Image.LANCZOS)
            rel = (8 if slot == 1 else 1) - ci.height + 2
        cy = base + rel
        out = [(ci, 0, cy)]
        # The first letter starts where it does after this initial in English: same gap from
        # the initial's last ink column to the letter's first (median over the plates; it is
        # negative under Y and T, whose arms overhang). Cut-outs carry 2 px of padding, so the
        # initial's ink ends at width - 3 and a letter's ink starts 2 px into its image.
        own = (slot, text[0]) in self.kern
        gaps = sorted(self.kern[(slot, text[0])] if own else self.kern[(3 - slot, text[0])])
        gap = gaps[len(gaps) // 2]
        if not own:
            gap = gap * (ci.width - 4) / (self.caps[3 - slot][text[0]][0].width - 4)
        x = round(ci.width - 3 + gap - 2)
        # then keep the letter CLEAR of the initial: at least CAP_CLEAR px between their ink
        # (the English set lowercase against M's serif; in game it read as touching)
        gi, grel, _w = self.glyph(text[1], cls)
        x = clear_of(ci, cy, gi, base + grel, x)
        for ch in text[1:]:
            gi, grel, adv = self.glyph(ch, cls)
            out.append((gi, x, base + grel))
            x += adv + LETTER_GAP - 1        # next ink starts LETTER_GAP after this ink ends
        return out, x


# ------------------------------------------------------------- render

def render(n, disc, en_im, letters):
    fam, giv, age1, age2 = NAMES[n]
    age = age1 if disc == 1 else age2
    out = en_im.copy()
    bg = letters.background
    # wipe the name and title areas back to the shared background
    out = letters.clean(out)
    # name line: lay it out at full size, then shrink it about its baseline if it overruns,
    # the way the English plates start long names further left and set them tighter
    layer = Image.new('RGBA', (900, 256), (0, 0, 0, 0))
    pen = 0
    # one baseline for the whole line, as the English plates read
    metrics = word_metrics(en_im, n)
    line_base = 113
    for slot, word in ((1, fam), (2, giv)):
        _b, _xh, cls = metrics[slot - 1]
        base = line_base
        parts, width = letters.word(word, slot, base, cls)
        for gi, x, y in parts:
            layer.alpha_composite(gi, (pen + x, y))
        pen += width + GAP_WORDS
    pieces = letters.age_of(en_im, n)
    if pieces:
        ax0 = min(x for _i, x, _y in pieces)
        for gi, x, y in pieces:
            layer.alpha_composite(gi, (pen - 4 + x - ax0, y + line_base - metrics[1][0]))
        pen += max(x + gi.width for gi, x, _y in pieces) - ax0
    left = 39 if pen <= RIGHT - 39 else 22
    room = RIGHT - left
    if pen > room:
        f = room / pen
        base = 121
        layer = layer.resize((round(900 * f), round(256 * f)), Image.LANCZOS)
        dy = round(base - base * f)
        tmp = Image.new('RGBA', (900, 256), (0, 0, 0, 0))
        tmp.alpha_composite(layer, (0, dy))
        layer = tmp
    out.alpha_composite(layer.crop((0, 0, 600 - left, 256)), (left, 0))
    # title
    f = ImageFont.truetype(FONT, TITLE_SIZE)
    lines = TITLES[n][1]
    base1 = 198 if len(lines) == 2 else 216
    d = ImageDraw.Draw(out)
    for i, line in enumerate(lines):
        size = TITLE_SIZE
        while d.textlength(line, font=ImageFont.truetype(FONT, size)) > RIGHT - TITLE_X and size > 20:
            size -= 1
        fz = ImageFont.truetype(FONT, size)
        d.text((TITLE_X, base1 + 33 * i), line, font=fz, fill=(255, 255, 255, 255), anchor='ls')
    return out


def build():
    pull()
    ims = {}
    for disc in (1, 2):
        for n in plates(disc):
            ims[(disc, n)] = tex_of(open(os.path.join(DATA, EN[disc], '%d.CL3' % n), 'rb').read())
    letters = Letters({n: ims[(2, n)] for n in plates(2)})
    from PIL import ImageChops
    bg = None
    for im in ims.values():
        a = im.crop((0, 0, 600, 256))
        bg = a if bg is None else ImageChops.darker(bg, a)
    full = Image.new('RGBA', (600, 256))
    full.paste(bg, (0, 0))
    letters.background = full
    os.makedirs(os.path.join(DATA, 'out'), exist_ok=True)
    sheet = []
    for (disc, n), im in sorted(ims.items()):
        new = render(n, disc, im, letters)
        jp = bytearray(open(os.path.join(DATA, JP[disc], '%d.CL3' % n), 'rb').read())
        o, sz = cl3_members(jp)['tid']
        hdr = bytearray(jp[o:o + 0x80])
        w, h = struct.unpack_from('<II', hdr, 0x44)
        if bytes(hdr[0x64:0x68]) != b'DXT5' or new.size != (w, h):
            raise SystemExit('%d: JP texture is not a %dx%d DXT5' % (n, w, h))
        payload = encode_into(b'\0' * (w // 4 * h // 4 * 16), new, (0, 0, w, h))
        if 0x80 + len(payload) != sz:
            raise SystemExit('%d: size %d != %d' % (n, 0x80 + len(payload), sz))
        jp[o + 0x80:o + sz] = payload
        open(os.path.join(DATA, 'out', '%d_%d.CL3' % (n, disc)), 'wb').write(jp)
        prev = Image.new('RGBA', (400, 200), (40, 40, 40, 255))
        prev.alpha_composite(TID(bytes(jp[o:o + sz])).image().convert('RGBA').crop((0, 0, 400, 200)))
        sheet.append(prev)
    cols = 4
    S = Image.new('RGB', (cols * 400, ((len(sheet) + cols - 1) // cols) * 200), (90, 90, 90))
    for i, p in enumerate(sheet):
        S.paste(p.convert('RGB'), ((i % cols) * 400, (i // cols) * 200))
    S.save(os.path.join(DATA, 'out', 'sheet.png'))
    print('  %d plates -> %s' % (len(sheet), os.path.join(DATA, 'out')))


def install():
    sys.path.insert(0, os.path.join(ROOT, 'voice'))
    import clock_en
    for disc, cpk in ((1, 'GAME_01.cpk'), (2, 'GAME_02.cpk')):
        for d in MODS:
            p = os.path.join(d, cpk)
            for n in plates(disc):
                name = 'ADV/EFFECT/%d.CL3' % n
                blob = open(os.path.join(DATA, 'out', '%d_%d.CL3' % (n, disc)), 'rb').read()
                clock_en.NAME = name
                if clock_en.read_file(p, name) != blob:
                    clock_en.swap(p, blob)
            print('  ->', p)


def restore():
    sys.path.insert(0, os.path.join(ROOT, 'voice'))
    import clock_en
    for disc, cpk in ((1, 'GAME_01.cpk'), (2, 'GAME_02.cpk')):
        for d in MODS:
            p = os.path.join(d, cpk)
            for n in plates(disc):
                clock_en.NAME = 'ADV/EFFECT/%d.CL3' % n
                clock_en.swap(p, open(os.path.join(DATA, JP[disc], '%d.CL3' % n), 'rb').read())
            print('  restored', p)


if __name__ == '__main__':
    {'build': build, 'install': install, 'restore': restore}[sys.argv[1]]()
