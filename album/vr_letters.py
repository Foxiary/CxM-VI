"""Voice Recorder titles for -Unlimited- in the English Voice Recorder's own letters.

The English -Unlimited- Voice Recorder (VOICERECORDER/voiceRecorderParts.tid, title
0100E3B00F412000) is not set in the face of the BGM/Movie lists: its letters are condensed
and twice as heavy (vertical stems ~4 px at a 28-30 px cap, against ~2 px for the BGM face
scaled to that cap). Drawing the Vietnamese titles with the BGM face therefore came out too
thin. This cuts the letters out of that atlas instead - the 16 names and 13 English titles -
and sets the five surnames and the Vietnamese titles with them.

    python3 vr_letters.py --check        # cut the letters, report coverage, write a specimen
    python3 vr_letters.py --dry-run      # build the texture, previews only
    python3 vr_letters.py                # build it and write it into every GAME_02.cpk copy

It runs inside CxM-VI's album/ code (imported from there); the English atlas and the
Unlimited originals are the ones CxM-VI already extracted into work/album/unl/.

JOINED LETTERS
    Strokes touch in this face (W-h, k-i, K-a, f-i). A piece that is wider than the
    narrowest of the letters it must contain is split at the column with the least ink,
    as many times as letters are missing. A line is used only if the split ends with
    exactly one piece per character.

LETTERS THE ENGLISH LINES DO NOT HAVE
    The Vietnamese titles also need D E V Y q z & and the Vietnamese marks. Those come
    from the BGM face (album_en_letters.Setter), scaled to this atlas's cap height and
    thickened (a 1-px dilation, done at 4x, until its stem matches these letters).
"""
import argparse, os, statistics, unicodedata
from collections import deque


from PIL import Image, ImageChops, ImageFilter               # noqa: E402
import album_en_letters as ae                                # noqa: E402
import en_glyphs as eg                                       # noqa: E402
import unlimited_album as ua                                 # noqa: E402
from tid import TID                                          # noqa: E402

NAMES = ['Aiji', 'Kei', 'Mineo', 'Takeru', 'Kageyuki', 'Saeki', 'Mochida', 'Sakuragawa',
         'Yoshinari', 'Mukai', 'Satake', 'Minegishi', 'Morioka', 'Kazuki', 'Sera', 'Isshiki']
TITLES = ['What I like about her', 'What I wish she would change', 'What I want to do along with her',
          'On Family', 'On Friendship', 'Favorite Season / Place', 'Obsessions and Pet Peeves',
          "Things I'm secretly worried about", "Things I'm keeping secret",
          'One thing I want to say to her', 'Self-Introduction',
          "Favorite things / Things I won't give up", 'A word to the protagonist']
NAME_BOX_X = (0, 152)
TITLE_X0 = 233
ROW = lambda r: 128 + 64 * r                                 # noqa: E731

# where the English set things, measured off its atlas
NAME_CAP, NAME_BASE, NAME_CENTRE = 28, 43, 78
TITLE_INK_X = 237                                            # English titles' first ink column
MARK_GAP = 3                                                 # dot of i above its stem, in this atlas
TITLE_BASE = 47                                              # English titles: baseline row + 46/47, caps from +17


# ---------------------------------------------------------------- cutting

def pieces_of(A, box):
    return sorted(eg.merge_stacked(eg.seeds(A, box)), key=lambda c: eg.bbox(c)[0])


def split_piece(A, pts, n):
    """Split one connected piece into n by cutting at the columns with the least ink."""
    px = A.load()
    x0, y0, x1, y1 = eg.bbox(pts)
    cols = {}
    for (x, y) in pts:
        cols[x] = cols.get(x, 0) + px[x, y]
    parts = [pts]
    for _ in range(n - 1):
        # cut the widest part at its weakest interior column
        parts.sort(key=lambda p: eg.bbox(p)[2] - eg.bbox(p)[0])
        widest = parts.pop()
        a, _, b, _ = eg.bbox(widest)
        lo, hi = a + max(3, (b - a) // 6), b - max(3, (b - a) // 6)
        if hi <= lo:
            parts.append(widest)
            break
        cut = min(range(lo, hi + 1), key=lambda x: cols.get(x, 0))
        parts += [[p for p in widest if p[0] < cut], [p for p in widest if p[0] >= cut]]
    return sorted([p for p in parts if p], key=lambda p: eg.bbox(p)[0])


def split_line(A, text, box):
    """Like en_glyphs.split_line, but separates touching letters. -> [(ch, img, x, top)], baseline"""
    chars = [c for c in text if c != ' ']
    comps = pieces_of(A, box)
    if len(comps) > len(chars):
        return None
    missing = len(chars) - len(comps)
    while missing:
        # the piece most out of proportion to an average letter width is the joined one
        avg = sum(eg.bbox(c)[2] - eg.bbox(c)[0] + 1 for c in comps) / len(chars)
        i = max(range(len(comps)), key=lambda k: (eg.bbox(comps[k])[2] - eg.bbox(comps[k])[0]) / avg)
        w = eg.bbox(comps[i])[2] - eg.bbox(comps[i])[0] + 1
        k = max(2, min(missing + 1, round(w / avg)))
        new = split_piece(A, comps[i], k)
        if len(new) < 2:
            return None
        comps = sorted(comps[:i] + new + comps[i + 1:], key=lambda c: eg.bbox(c)[0])
        missing = len(chars) - len(comps)
        if missing < 0:
            return None
    x0, y0, x1, y1 = box
    px = A.load()
    label, q = {}, deque()
    for k, pts in enumerate(comps):
        for p in pts:
            label[p] = k
            q.append(p)
    while q:
        a, b = q.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c, d = a + dx, b + dy
                if x0 <= c < x1 and y0 <= d < y1 and (c, d) not in label and px[c, d] > 0:
                    label[(c, d)] = label[(a, b)]
                    q.append((c, d))
    groups = [[] for _ in comps]
    for p, k in label.items():
        groups[k].append(p)
    out = []
    for ch, pts in zip(chars, groups):
        l, t, r, b = eg.bbox(pts)
        im = Image.new('L', (r - l + 1, b - t + 1), 0)
        ip = im.load()
        for (x, y) in pts:
            ip[x - l, y - t] = px[x, y]
        out.append((ch, im, l, t, eg.bbox([p for p in pts if px[p] > eg.SEED] or pts)))
    bottoms = sorted(s[3] for ch, im, l, t, s in out if ch in eg.BASE_SET)
    if not bottoms:
        return None
    return out, bottoms[len(bottoms) // 2] + 1


# Letters that only occur touching a neighbour: (line, row, char, x0, x1) cut by column at the
# gap seen in the atlas (Kazuki row 13: z at x 67..83, between a and u; Yoshinari row 8: Y at x 3..26).
EXTRA_CUTS = [('Kazuki', 13, 'z', 67, 84), ('Yoshinari', 8, 'Y', 3, 27)]


def cut_by_column(A, row, x0, x1):
    y0 = ROW(row)
    im = A.crop((x0, y0, x1, y0 + 64))
    bb = im.point(lambda v: 255 if v > 8 else 0).getbbox()
    return im.crop(bb), y0 + bb[1]


def cut_letters(atlas=None):
    """Letters from the lines whose pieces map one to one onto their characters.

    atlas = (alpha image, [(text, box)], extra_cuts) to cut another Voice Recorder atlas the
    same way (main_vr.py does this for the main game); default is the -Unlimited- one.

    Lines with touching letters (Kageyuki, Sakuragawa, Yoshinari, Minegishi, Kazuki and four
    titles) are measured for spacing only when a split leaves every piece a plausible width,
    and never feed the letter set: a wrong split there once handed over half of "Yo" as "Y".
    """
    if atlas is None:
        A = TID(open(ua.EN_VR, 'rb').read()).image().convert('RGBA').getchannel('A')
        jobs = [(n, (NAME_BOX_X[0], ROW(r), NAME_BOX_X[1], ROW(r) + 64)) for r, n in enumerate(NAMES)]
        jobs += [(t, (TITLE_X0, ROW(r), 1024, ROW(r) + 64)) for r, t in enumerate(TITLES)]
        extra = EXTRA_CUTS
    else:
        A, jobs, extra = atlas
    samples, lines = {}, []
    for text, box in jobs:
        clean = len(pieces_of(A, box)) == len([c for c in text if c != ' '])
        if not clean:
            continue
        res = split_line(A, text, box)
        if res:
            lines.append((text, res[0], res[1]))
    for text, pieces, base in lines:
        for ch, im, l, t, s in pieces:
            samples.setdefault(ch, []).append((im, t - base))
    lib = {}
    for ch, ss in samples.items():
        ss.sort(key=lambda s: (s[0].width, s[0].height))
        lib[ch] = ss[len(ss) // 2]
    for line, row, ch, x0, x1 in extra:
        if ch not in lib:
            # this line's own baseline: the bottom shared by its baseline letters
            cs = [eg.bbox(c) for c in pieces_of(A, (NAME_BOX_X[0], ROW(row), NAME_BOX_X[1], ROW(row) + 64))]
            bots = sorted(c[3] for c in cs)
            base = bots[len(bots) // 2] + 1
            im, top = cut_by_column(A, row, x0, x1)
            lib[ch] = (im, top - base)
    # Each sample keeps the +-1 px its own line happened to sit at, so letters taken from
    # different lines bob up and down when set together. Snap every letter that stands on the
    # baseline so its solid ink ends exactly on it, and every x-height / cap top to the
    # common value, as the English lines show them.
    for ch, (im, top) in list(lib.items()):
        if ch in SITS_ON_BASELINE:
            lib[ch] = (im, -solid_rows(im)[1] - 1 + (1 if ch in OVERSHOOT else 0))
    return lib, lines


SITS_ON_BASELINE = set('ABCDEFGHIKLMNOPRSTUVWXYZabcdefhiklmnorstuvwxz')
# Round letters overshoot the baseline in this face (S, O, a, e, o, s, c end 1 px lower than
# the flat-bottomed k, r, n, h, i in every English line), and the flat ones are what the eye
# reads as the line. Snapping both kinds to the same row is what made them bob.
OVERSHOOT = set('COSGQUJacegosqdbu')


def solid_rows(im, thr=96):
    w, h = im.size
    px = im.load()
    rows = [y for y in range(h) if max(px[x, y] for x in range(w)) >= thr]
    return (rows[0], rows[-1]) if rows else (0, h - 1)


# ---------------------------------------------------------------- setting

def hmax(image, n):
    """Horizontal-only max filter of width n (thickens vertical strokes, not the letter height)."""
    out = image
    for d in range(1, n // 2 + 1):
        for dx in (-d, d):
            out = ImageChops.lighter(out, ImageChops.offset(image, dx, 0))
    return out


def stem(im):
    w, h = im.size
    px = im.load()
    runs = []
    for y in range(int(h * 0.4), int(h * 0.7)):
        r = 0
        for x in range(w):
            if px[x, y] >= 128:
                r += 1
            elif r:
                runs.append(r)
                r = 0
    runs = [r for r in runs if r < w * 0.6]
    runs.sort()
    return runs[len(runs) // 2] if runs else 0


class VRSetter(ae.Setter):
    """album_en_letters.Setter with this atlas's letters and spacing, falling back to the
    BGM face (scaled to this cap, thickened to this stem) for anything the English lacks."""

    def __init__(self, libs, used, atlas=None):
        super().__init__('bgm', libs, used['bgm'])
        self.bgm_lib = dict(self.lib)          # the BGM face, before this atlas's letters replace it
        vr, lines = cut_letters(atlas)
        self.vr_lines = lines
        bgm_cap = ae.cap_height(libs['bgm'])
        vr_cap = statistics.median(vr[c][0].height for c in 'AIKMST' if c in vr)
        self.k_fallback = vr_cap / bgm_cap
        self.bgm_cap, self.vr_cap = bgm_cap, vr_cap
        self.bgm_xh = statistics.median(libs['bgm'][c][0].height for c in 'xnuvmr' if c in libs['bgm'])
        self.vr_xh = statistics.median(vr[c][0].height for c in 'nuvmrae' if c in vr)
        # weight of the fallback letters: dilate at 4x until stems match the English VR stems
        target = statistics.median(stem(vr[c][0]) for c in 'ilnmIM' if c in vr)
        best = None
        for grow in range(0, 9):
            got = statistics.median(stem(self._fallback(c, grow)[0]) for c in 'ilnm' if c in self.lib)
            if best is None or abs(got - target) < best[0]:
                best = (abs(got - target), grow)
        self.grow = best[1]
        fallback = {}
        for c in list(self.lib):
            if c not in vr:
                fallback[c] = self._fallback(c, self.grow)
        self.vr_src = {c: 'vr' for c in vr}
        self.vr_src.update({c: 'bgm' for c in fallback})
        self.lib = dict(fallback)
        self.lib.update(vr)
        self.cap = vr_cap
        # spacing: learn from this atlas's lines; bearings of fallback letters scaled
        used_vr = [(t, [(ch, im, l, top, s) for ch, im, l, top, s in p], b) for t, p, b in lines]
        L0, R0 = dict(self.L), dict(self.R)
        self.L = {c: v * self.k_fallback for c, v in L0.items()}
        self.R = {c: v * self.k_fallback for c, v in R0.items()}
        self.L, self.R, self.track, self.space, self.rms = self._learn(used_vr)
        self.target_stem = target

    def _fallback(self, c, grow):
        """A letter this atlas lacks, from the BGM face, made to sit like the English letters.

        Capitals and ascenders are scaled so their height is this atlas's cap height, x-height
        letters so theirs is its x-height, which a single scale factor cannot do (the two faces
        do not share proportions). The weight is added sideways only - a horizontal max filter
        at 4x - so the letter does not grow taller, and it is then snapped onto the baseline.
        """
        if c in self.bgm_lib:
            im, top = self.bgm_lib[c]
        else:                                   # not in the English BGM letters either: Old Standard
            im, _l, top = self.os.glyph(c)
        bottom = top + im.height
        tall = top < -0.8 * self.bgm_cap        # capital, ascender, & ...
        target = self.vr_cap if tall else self.vr_xh
        source = self.bgm_cap if tall else self.bgm_xh
        k = target / source
        big = im.resize((max(1, round(im.width * k * 4)), max(1, round(im.height * k * 4))), Image.LANCZOS)
        if grow:
            pad = Image.new('L', (big.width + 2 * grow, big.height), 0)
            pad.paste(big, (grow, 0))
            big = hmax(pad, 2 * grow + 1)
        small = big.resize((max(1, round(big.width / 4)), max(1, round(big.height / 4))), Image.BOX)
        # snap: a letter that sat on the baseline in the BGM face sits on it here
        if abs(bottom) <= 0.08 * self.bgm_cap:
            new_top = -self._ink_rows(small)[1] - 1
        else:                                   # descender (q, y...) keeps its depth ratio
            new_top = round(bottom * k) - small.height
        return small, new_top

    def _learn(self, used_vr):
        pairs, spaces = [], []
        for text, pieces, base in used_vr:
            k, breaks = 0, set()
            for w in text.split(' ')[:-1]:
                k += len(w)
                breaks.add(k - 1)
            for i in range(len(pieces) - 1):
                a, b = pieces[i], pieces[i + 1]
                gap = b[2] - (a[2] + a[1].width)
                (spaces if i in breaks else pairs).append((a[0], b[0], gap))
        L, R = dict(self.L), dict(self.R)
        for ch in self.lib:
            L.setdefault(ch, 1.0)
            R.setdefault(ch, 1.0)
        prior = {c: (L[c], R[c]) for c in L}
        track = 0.0
        for _ in range(60):
            for side in ('R', 'L'):
                acc = {}
                for a, b, g in pairs:
                    if side == 'R':
                        acc.setdefault(a, []).append(g - L[b] - track)
                    else:
                        acc.setdefault(b, []).append(g - R[a] - track)
                tgt = R if side == 'R' else L
                for c, vals in acc.items():
                    tgt[c] = (sum(vals) + prior[c][0 if side == 'L' else 1]) / (len(vals) + 1)
            track = statistics.mean(g - R[a] - L[b] for a, b, g in pairs)
        res = [g - R[a] - L[b] - track for a, b, g in pairs]
        rms = (sum(r * r for r in res) / len(res)) ** 0.5
        space = statistics.median(g - R[a] - L[b] for a, b, g in spaces) if spaces else 8
        return L, R, track, space, rms

    def base_glyph(self, c, has_above):
        if c in self.lib:
            im, top = self.lib[c]
            if c == 'i' and has_above:
                d = ae.dotless(im)
                return d, top + (im.height - d.height)
            return im, top
        self.drawn.add(c)
        return self._fallback(c, self.grow)

    def bear(self, c):
        return self.L.get(c, 1.0), self.R.get(c, 1.0)

    def letter(self, ch):
        """Base letter from this atlas; Vietnamese marks from the BGM face, scaled and thickened."""
        base, sub, marks = ae.split_marks(self.os, ch)
        if not marks:
            im, top = self.base_glyph(base, False)
            L, R = self.bear(base)
            return im, 0, top, im.width, L, R
        # build the accented letter in the BGM face, then rescale its marks onto our base
        bim, btop = self.base_glyph(base, sub != base)
        oim, _ol, ot = self.os.glyph(sub)
        L, R = self.bear(base)
        k = self.k_fallback
        parts = [(bim, 0, btop)]
        sx = bim.width / max(1, oim.width * k)
        # Marks above are stacked from the letter up with the gap this atlas uses between the
        # dot of i and its stem (MARK_GAP), lowest mark first: the BGM face's own offsets come
        # from a taller, lighter design and, scaled down and thickened, sat the marks right on
        # the letter. Horn, dot below and the d bar keep their mapped positions.
        above = sorted([m for m in marks if m[1] == 'above'], key=lambda m: -m[3])
        others = [m for m in marks if m[1] != 'above']
        ink_top = btop + self._ink_top(bim)
        for mim, kind, dx, dy in above:
            m = self._thicken(mim.resize((max(1, round(mim.width * k)), max(1, round(mim.height * k))), Image.LANCZOS))
            mt, mb = self._ink_rows(m)
            cx = (dx + mim.width / 2.0) * k
            ow = oim.width * k
            x = ow / 2 + (cx - ow / 2) * sx
            y = ink_top - MARK_GAP - mb - 1
            parts.append((m, round(x - m.width / 2), y))
            ink_top = y + mt
        for mim, kind, dx, dy in others:
            m = self._thicken(mim.resize((max(1, round(mim.width * k)), max(1, round(mim.height * k))), Image.LANCZOS))
            cx = (dx + mim.width / 2.0) * k
            ow, oh = oim.width * k, oim.height * k
            if kind == 'below':
                x = ow / 2 + (cx - ow / 2) * sx
                mt, mb = self._ink_rows(m)
                y = btop + bim.height + getattr(self, 'gap_below', MARK_GAP) - mt
            elif base in 'dD':
                right = base == 'd'
                x = ae.stem_x(bim, right) + (cx - ae.stem_x(oim, right) * k)
                y = btop + dy * k * (bim.height / max(1, oh))
            else:
                x = bim.width + (cx - ow) * sx
                y = btop + dy * k * (bim.height / max(1, oh))
            parts.append((m, round(x - m.width / 2), round(y)))
        x0 = min(p[1] for p in parts)
        y0 = min(p[2] for p in parts)
        x1 = max(p[1] + p[0].width for p in parts)
        y1 = max(p[2] + p[0].height for p in parts)
        out = Image.new('L', (x1 - x0, y1 - y0), 0)
        for im, x, y in parts:
            layer = Image.new('L', out.size, 0)
            layer.paste(im, (x - x0, y - y0))
            out = ImageChops.lighter(out, layer)
        if ch != base:
            R += max(0, (x1 - x0) - bim.width - max(0, -x0)) if base in 'ouOU' else 0
        return out, -x0, y0, bim.width, L, R

    @staticmethod
    def _ink_rows(im, thr=96):
        """First and last row holding solid ink."""
        w, h = im.size
        px = im.load()
        rows = [y for y in range(h) if max(px[x, y] for x in range(w)) >= thr]
        return (rows[0], rows[-1]) if rows else (0, h - 1)

    def _ink_top(self, im):
        return self._ink_rows(im)[0]

    def _thicken(self, im):
        """Marks: thickened like the fallback letters, sideways only."""
        if not self.grow:
            return im
        big = im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
        g = self.grow
        pad = Image.new('L', (big.width + 2 * g, big.height), 0)
        pad.paste(big, (g, 0))
        big = hmax(pad, 2 * g + 1)
        return big.resize((max(1, round(big.width / 4)), max(1, round(big.height / 4))), Image.BOX)


# ---------------------------------------------------------------- texture

def build_vr(setter):
    raw = ua.original(ua.VR)
    base_img = TID(raw).image().convert('RGBA')
    img = base_img.copy()
    eng = TID(open(ua.EN_VR, 'rb').read()).image().convert('RGBA')
    for r in range(13):
        ua.clear(img, (226, ROW(r), 1024, ROW(r) + 64))
    img.paste(eng.crop(ua.VR_NUMBER_RECT), ua.VR_NUMBER_RECT[:2])
    rows = []
    for r, n in enumerate(ua.VR_SURNAMES):
        y0 = ROW(r)
        ua.clear(img, (0, y0, 150, y0 + 64))
        # centred on the English names' centre, but kept inside x 2..149: the English set the
        # long ones (Minegishi, Sakuragawa) flush across the whole column the same way
        im, ox, base = setter.line(unicodedata.normalize('NFC', n), 0.0)
        w = im.width - ox
        centre = min(max(NAME_CENTRE, 2 + w / 2), 149 - w / 2)
        a, b, s = ua.place(img, setter, n, 0, 149, y0 + NAME_BASE, NAME_BASE - 1, 63 - NAME_BASE, 1.0,
                           centre=centre, shrink=False)
        assert 1 <= a and b <= 149, (n, a, b)
        rows.append(('name', n, a, b, 1.0))
    for r, t in enumerate(ua.VR_TITLES):
        y0 = ROW(r)
        a, b, s = ua.place(img, setter, t, TITLE_INK_X, ua.VR_TEXT_R, y0 + TITLE_BASE, TITLE_BASE,
                           64 - TITLE_BASE, 1.0)
        rows.append(('title', t, a, b, s))
    return raw, base_img, img, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    en = eg.read_en([v[0] for v in ae.TEXTURES.values()])
    libs, used = {}, {}
    for k in ae.TEXTURES:
        libs[k], used[k] = eg.build(k, en)
    setter = VRSetter(libs, used)
    print('English Voice Recorder: %d lines split cleanly, %d letters: %s'
          % (len(setter.vr_lines), sum(1 for v in setter.vr_src.values() if v == 'vr'),
             ''.join(sorted(c for c, v in setter.vr_src.items() if v == 'vr'))))
    print('cap %.0f px, stem %.1f px; fallback from BGM face x%.3f, dilated %d/4 px; spacing rms %.2f px'
          % (setter.vr_cap, setter.target_stem, setter.k_fallback, setter.grow, setter.rms))
    if a.check:
        return
    raw, base_img, img, rows = build_vr(setter)
    for kind, t, x0, x1, s in rows:
        print('  %-5s %-34s ink x %d..%d  scale %.3f' % (kind, t, x0, x1, s))
    if setter.drawn:
        print('  letters from the BGM face (thickened):', ''.join(sorted(setter.drawn)))
    new, changed = ae.encode(raw, base_img, img)
    print('  %s: %d DXT5 blocks re-encoded' % (ua.VR, changed))
    out = os.path.join(ua.PREVIEW, 'VOICERECORDER__voiceRecorderParts.vr-letters.png')
    TID(new).image().convert('RGBA').save(out)
    print('  preview', out)
    if a.dry_run:
        return
    final = {n: ua.read_file(ua.CPKS[0], n) for n in ua.NAMES}
    final[ua.VR] = new
    for p in ua.CPKS:
        ua.save_backup(p)
        if ua.matches_backup(p):
            ua.restore(p)
        ua.append_replace(p, final)


if __name__ == '__main__':
    main()
