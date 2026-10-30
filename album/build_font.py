"""Build an OTF + TTF out of the Latin letters the USA Collar x Malice draws its BGM / Movie titles in.

    .venv/bin/python build_font.py            # -> fonts/out/CxMAlbum-Regular.otf / .ttf + specimen

WHERE EACH GLYPH COMES FROM
    1. The English build's own letters (en_glyphs.py cuts them out of BGM/bgm_Parts.tid and
       MOVIE/movieParts.tid in 010083E00F40E000's GAME_01.CPK). Every sample of a letter is
       aligned on its ink box and averaged at 4x, which cancels most of the BC7 noise, then
       traced to cubic outlines (potrace). Cap height there is 57 px.
    2. Letters the English titles never use (j q z J O Q U X Y Z, digits, punctuation) come from
       Old Standard TT, the face these titles were matched to, at the matching size. Its
       hairlines already match the English ones; its vertical stems are ~1.4x heavier, so they
       are thinned horizontally until they match the English stems.
    3. Vietnamese marks (tone marks, circumflex, breve, horn, dot below, the bar of d) are Old
       Standard's own marks, thinned the same way, placed against the English letter
       exactly where Old Standard places them against its letter. The đ / Đ bar is hung on
       the English stem. Every letter of the Vietnamese alphabet, all 134 accented forms and
       their capitals, is a real glyph - no reliance on mark positioning in the renderer.

SPACING
    Side bearings are fitted to the gaps measured between neighbouring letters in the English
    titles (album_en_letters.learn_spacing), so text set with this font spaces the way the
    game's titles do. Letters without English samples keep Old Standard's bearings.

LICENCE
    Part 2 and 3 are derived from Old Standard TT (SIL Open Font License 1.1), so the result
    is released under the OFL too and must not be named "Old Standard".
"""
import os, statistics, sys, unicodedata
import numpy as np
import pathops
import potrace
from PIL import Image, ImageChops, ImageDraw
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

import album_en_letters as ae
import en_glyphs as eg

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'work', 'album')    # game files and output, gitignored
OS_PATH = os.path.join(DATA, 'fonts', 'OldStandardTT-Regular.ttf')
OUT = os.path.join(DATA, 'fonts', 'out')
FAMILY = 'CxM Album'
PS_NAME = 'CxMAlbum-Regular'
VERSION = '1.000'

UPM = 1000
CAP = 712                  # Old Standard's cap height; the English cap (57 px) maps onto it
SS = 4                     # supersampling of the averaged bitmaps before tracing
LEVEL = 0.5                # coverage threshold traced as the outline

VIET = ('aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵđ')
VIET = VIET + VIET.upper().replace('Đ', '') + 'Đ'
BASIC = [chr(c) for c in range(0x20, 0x7F)] + list('‘’“”–—…·×÷«»€©®°§¶•ıÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýÄÖÜäöüßÇçÑñ')


# ---------------------------------------------------------------- 1. English letters

def samples():
    """{char: [alpha image]} from the BGM and Movie atlases, at their native 57 px cap."""
    en = eg.read_en(['BGM/bgm_Parts.tid', 'MOVIE/movieParts.tid'])
    out = {}
    for key in ('bgm', 'movie'):
        _lib, used = eg.build(key, en)
        for _text, pieces, baseline in used:
            for ch, im, l, t, strong in pieces:
                out.setdefault(ch, []).append((im, t - baseline))
    return out


def average(ims):
    """Align samples on their ink box centre and average them at SS x; returns (image, top)."""
    W = max(im.width for im, _ in ims)
    tops = [t for _, t in ims]
    bots = [t + im.height for im, t in ims]
    top, bot = min(tops), max(bots)
    acc = np.zeros(((bot - top) * SS, W * SS), np.float64)
    for im, t in ims:
        big = np.asarray(im.resize((im.width * SS, im.height * SS), Image.BICUBIC), np.float64)
        x = (W - im.width) * SS // 2
        y = (t - top) * SS
        acc[y:y + big.shape[0], x:x + big.shape[1]] += big
    acc /= len(ims)
    return Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8)), top


# ---------------------------------------------------------------- tracing

def trace(img, scale, dx, dy):
    """Potrace a coverage image into a pathops.Path in font units.

    img pixel (x, y) maps to font (dx + x * scale, dy - y * scale). This potrace binding
    outlines the FALSE pixels of the bitmap it is given, so it gets the complement of the ink;
    pathops then fixes the winding to the TrueType convention.
    """
    a = np.asarray(img) >= int(255 * LEVEL)
    a = np.pad(a, 2)
    bm = potrace.Bitmap(~a)
    plist = bm.trace(turdsize=4 * SS, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
                     alphamax=1.0, opticurve=True, opttolerance=0.2)
    path = pathops.Path()
    pen = path.getPen()

    def P(p):
        return (dx + (p.x - 2) * scale, dy - (p.y - 2) * scale)

    for curve in plist:
        pen.moveTo(P(curve.start_point))
        for s in curve.segments:
            if s.is_corner:
                pen.lineTo(P(s.c))
                pen.lineTo(P(s.end_point))
            else:
                pen.curveTo(P(s.c1), P(s.c2), P(s.end_point))
        pen.closePath()
    return pathops.simplify(path, fix_winding=True, clockwise=False)


# ---------------------------------------------------------------- 2/3. Old Standard, stroke-matched

class OldStandard:
    def __init__(self, stroke_units):
        self.f = TTFont(OS_PATH)
        self.gs = self.f.getGlyphSet()
        self.cmap = self.f.getBestCmap()
        self.hmtx = self.f['hmtx']
        self.stroke = stroke_units

    def path(self, name):
        rec = DecomposingRecordingPen(self.gs)
        self.gs[name].draw(rec)
        p = pathops.Path()
        rec.replay(p.getPen())
        p = pathops.simplify(p, fix_winding=True, clockwise=False)
        if self.stroke > 0:
            # thin vertical stems only: intersect with copies shifted left and right, which
            # erodes left/right edges by `stroke` units and leaves hairlines untouched
            k = self.stroke
            for d in (k, -k):
                p = pathops.op(p, p.transform(translateX=d), pathops.PathOp.INTERSECTION,
                               fix_winding=True, clockwise=False)
            p = p.transform(translateX=0)
        return p

    def char(self, ch):
        n = self.cmap.get(ord(ch))
        return None if n is None else (n, self.path(n), self.hmtx[n][0])

    def name(self, ch):
        return self.cmap.get(ord(ch))


def raster(path, px_per_unit, pad=4):
    """Rasterise a path at a given scale (for weight matching / checks)."""
    x0, y0, x1, y1 = path.bounds
    w = int((x1 - x0) * px_per_unit) + 2 * pad
    h = int((y1 - y0) * px_per_unit) + 2 * pad
    im = Image.new('L', (w * SS, h * SS), 0)
    from fontTools.pens.basePen import BasePen
    from fontTools.pens.recordingPen import RecordingPen
    rp = RecordingPen()
    path.draw(rp)

    class Poly(BasePen):
        def __init__(self):
            super().__init__(None)
            self.polys, self.cur = [], []

        def _moveTo(self, p):
            self.cur = [p]

        def _lineTo(self, p):
            self.cur.append(p)

        def _curveToOne(self, a, b, c):
            p0 = self.cur[-1]
            for i in range(1, 9):
                t = i / 8
                mt = 1 - t
                self.cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * a[0] + 3 * mt * t * t * b[0] + t ** 3 * c[0],
                                 mt ** 3 * p0[1] + 3 * mt * mt * t * a[1] + 3 * mt * t * t * b[1] + t ** 3 * c[1]))

        def _closePath(self):
            self.polys.append(self.cur)
            self.cur = []

    pp = Poly()
    rp.replay(pp)
    k = px_per_unit * SS
    mask = Image.new('L', im.size, 0)
    for poly in pp.polys:
        layer = Image.new('L', im.size, 0)
        ImageDraw.Draw(layer).polygon([((x - x0) * k + pad * SS, (y1 - y) * k + pad * SS) for x, y in poly], fill=255)
        mask = ImageChops.difference(mask, layer)       # even-odd
    return mask.resize((w, h), Image.BOX)


def hairline(im):
    w, h = im.size
    px = im.load()
    return sum(px[w // 2, y] for y in range(h // 2)) / 255.0


# ---------------------------------------------------------------- build

def main():
    os.makedirs(OUT, exist_ok=True)
    raw = samples()
    cap_px = statistics.median([im.height for c in 'EHILT' if c in raw for im, _ in raw[c]])
    unit = CAP / cap_px                    # font units per English pixel
    print('English letters: %d kinds, %d samples; cap %.0f px -> %d units (%.2f u/px)'
          % (len(raw), sum(map(len, raw.values())), cap_px, CAP, unit))

        # Old Standard's stems are ~1.4x the English ones while its hairlines already match, so
    # its vertical stems are thinned (horizontally only) until they are as wide as the
    # English stems, compared at the English size on l, H, o.
    def stem_runs(im):
        w, h = im.size
        px = im.load()
        runs = []
        for y in range(int(h * 0.35), int(h * 0.65)):
            run = 0
            for x in range(w):
                if px[x, y] >= 128:
                    run += 1
                else:
                    if run:
                        runs.append(run)
                    run = 0
        runs = [r for r in runs if r < w * 0.5]
        return sorted(runs)[len(runs) // 2]

    probe = 'lHo'
    mine = {ch: stem_runs(average(raw[ch])[0]) / SS for ch in probe}
    best = None
    for st in range(0, 26, 2):
        o = OldStandard(st)
        err = sum((stem_runs(raster(o.path(o.name(ch)), SS / unit)) / SS - mine[ch]) ** 2 for ch in probe)
        if best is None or err < best[0]:
            best = (err, st)
    stroke = best[1]
    OS = OldStandard(stroke)
    print('Old Standard stems thinned by %d units each side (stem match)' % stroke)

    glyphs, advance, source = {}, {}, {}

    # spacing learned from the English titles (pixels, at the English size)
    en = eg.read_en(['BGM/bgm_Parts.tid', 'MOVIE/movieParts.tid'])
    libs, used = {}, {}
    for k in ('bgm', 'movie'):
        libs[k], used[k] = eg.build(k, en)
    merged = dict(libs['movie'])
    merged.update(libs['bgm'])                 # every letter either list has
    libs['both'] = merged
    ae.FALLBACK['both'] = []
    ae.SIZE['both'] = ae.SIZE['bgm']
    setter = ae.Setter('both', libs, used['bgm'] + used['movie'])
    Lb, Rb, track = setter.L, setter.R, setter.track

    # 1. English letters. Bearings were measured between the edges of each letter's full
    # anti-aliased box, not its 50% outline, so the glyph is placed by that box.
    for ch, ims in raw.items():
        img, top = average(ims)
        W = img.width / SS
        box_w = statistics.median(im.width for im, _ in ims)
        lsb = Lb.get(ch, 0)
        rsb = Rb.get(ch, 0) + track
        dx = (lsb - (W - box_w) / 2) * unit
        glyphs[ch] = trace(img, unit / SS, dx, -top * unit)
        advance[ch] = round((lsb + box_w + rsb) * unit)
        source[ch] = 'en'

    # 2. everything else from Old Standard, in the same metrics
    for ch in BASIC + ['ı']:
        if ch in glyphs or ch == ' ':
            continue
        nfd = unicodedata.normalize('NFD', ch)
        if len(nfd) > 1 and nfd[0] in raw:      # accented letter on an English base: built in 3.
            continue
        r = OS.char(ch)
        if r is None:
            continue
        n, p, adv = r
        advance[ch] = adv
        glyphs[ch] = p
        source[ch] = 'os'
    space_px = setter.space - setter.track
    glyphs[' '] = pathops.Path()
    advance[' '] = round(space_px * unit + 0)
    source[' '] = 'en'

    # 3. Vietnamese: English (or 2.) base + Old Standard marks, placed the way Old Standard places them
    def build_viet(ch):
        if ch in 'đĐ':
            b = 'd' if ch == 'đ' else 'D'
        else:
            b = unicodedata.normalize('NFD', ch)[0]
        above = any(unicodedata.combining(c) == 230 for c in unicodedata.normalize('NFD', ch)[1:])
        sub = 'ı' if b == 'i' and above else b
        full = OS.path(OS.name(ch))
        obase = OS.path(OS.name(sub))
        marks = pathops.op(full, obase, pathops.PathOp.DIFFERENCE, fix_winding=True, clockwise=False)
        # keep only real mark pieces (drop slivers from the subtraction)
        pieces = []
        for c in marks.contours:
            x0, y0, x1, y1 = c.bounds
            if (x1 - x0) * (y1 - y0) > 400:
                pieces.append(c)
        if not pieces:
            return None
        ox0, oy0, ox1, oy1 = obase.bounds
        target = glyphs[b] if b != 'i' or not above else glyphs.get('ı', glyphs['i'])
        if b == 'i' and above and source.get('i') == 'en':
            target = dotless_i()
        tx0, ty0, tx1, ty1 = target.bounds
        out = pathops.Path()
        target.draw(out.getPen())
        sx = (tx1 - tx0) / max(1, ox1 - ox0)
        for c in pieces:
            cx0, cy0, cx1, cy1 = c.bounds
            cxm = (cx0 + cx1) / 2
            if cy0 >= oy1 - 5:                      # above: same gap above the letter
                dx = tx0 + (tx1 - tx0) / 2 + (cxm - (ox0 + ox1) / 2) * sx - cxm
                dy = ty1 - oy1
            elif cy1 <= oy0 + 5:                    # below
                dx = tx0 + (tx1 - tx0) / 2 + (cxm - (ox0 + ox1) / 2) * sx - cxm
                dy = ty0 - oy0
            elif b in 'dD':                         # bar on the stem
                right = b == 'd'
                dx = stem_center(target, right) - stem_center(obase, right)
                dy = 0
            else:                                   # horn: keep its distance from the right edge
                dx = tx1 - ox1
                dy = (ty1 - oy1) * 0.5
            moved = c.transform(translateX=dx, translateY=dy)
            moved.draw(out.getPen())
        out = pathops.simplify(out, fix_winding=True, clockwise=False)
        return out, advance[b] + max(0, round(out.bounds[2] - target.bounds[2]) if b in 'ouOU' else 0)

    def stem_center(path, right):
        im = raster(path, 0.1)
        w, h = im.size
        px = im.load()
        cov = [sum(px[x, y] for y in range(h)) for x in range(w)]
        peak = max(cov)
        xs = [x for x in range(w) if cov[x] >= 0.6 * peak]
        side = max(xs) if right else min(xs)
        run = [x for x in xs if abs(x - side) <= w // 4]
        return path.bounds[0] + (sum(run) / len(run) - 4) / 0.1

    def dotless_i():
        p = glyphs['i']
        cs = sorted(p.contours, key=lambda c: c.bounds[1])
        out = pathops.Path()
        cs[0].draw(out.getPen())
        return out

    glyphs['ı'] = dotless_i() if source.get('i') == 'en' else glyphs.get('ı')
    advance['ı'] = advance['i']
    source['ı'] = source['i']
    accented = [c for c in BASIC if len(unicodedata.normalize('NFD', c)) > 1 and c not in glyphs]
    for ch in list(VIET) + accented:
        if ch in glyphs:
            continue
        r = build_viet(ch)
        if r:
            glyphs[ch], advance[ch] = r
            source[ch] = 'en+marks' if source.get(unicodedata.normalize('NFD', ch)[0], source.get('d')) == 'en' else 'os+marks'

    write(glyphs, advance, source, stroke)


def gname(ch):
    if ch == ' ':
        return 'space'
    n = {'ı': 'dotlessi', 'đ': 'dcroat', 'Đ': 'Dcroat'}.get(ch)
    if n:
        return n
    from fontTools import agl
    return agl.UV2AGL.get(ord(ch), 'uni%04X' % ord(ch))


def write(glyphs, advance, source, stroke):
    order = ['.notdef'] + sorted((gname(c) for c in glyphs), key=lambda n: (n != 'space', n))
    cmap = {ord(c): gname(c) for c in glyphs}
    by_name = {gname(c): c for c in glyphs}
    notdef = pathops.Path()
    pen = notdef.getPen()
    for (a, b, c, d) in [(50, 0, 450, 700), (100, 50, 400, 650)]:
        pen.moveTo((a, b)); pen.lineTo((c, b)); pen.lineTo((c, d)); pen.lineTo((a, d)); pen.closePath()
    notdef = pathops.simplify(notdef, fix_winding=True, clockwise=False)
    paths = {'.notdef': notdef}
    paths.update({n: glyphs[c] for n, c in by_name.items()})
    adv = {'.notdef': 500}
    adv.update({n: advance[c] for n, c in by_name.items()})

    def lsb(n):
        b = paths[n].bounds
        return 0 if b == (0, 0, 0, 0) else round(b[0])

    asc, desc = 900, -260
    names = {
        'copyright': 'Latin letters traced from the English release of Collar x Malice; '
                     'additional glyphs and marks derived from Old Standard TT, Copyright 2011 '
                     'The Old Standard Project Authors.',
        'familyName': FAMILY, 'styleName': 'Regular', 'uniqueFontIdentifier': PS_NAME + ' ' + VERSION,
        'fullName': FAMILY + ' Regular', 'psName': PS_NAME, 'version': 'Version ' + VERSION,
        'licenseDescription': 'This Font Software is licensed under the SIL Open Font License, Version 1.1.',
        'licenseInfoURL': 'https://openfontlicense.org',
    }
    for flavour in ('otf', 'ttf'):
        fb = FontBuilder(UPM, isTTF=(flavour == 'ttf'))
        fb.setupGlyphOrder(order)
        fb.setupCharacterMap(cmap)
        if flavour == 'ttf':
            tt = {}
            for n in order:
                pen = TTGlyphPen(None)
                paths[n].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
                tt[n] = pen.glyph()
            fb.setupGlyf(tt)
        else:
            cs = {}
            for n in order:
                pen = T2CharStringPen(adv[n], None)
                paths[n].draw(pen)
                cs[n] = pen.getCharString()
            fb.setupCFF(PS_NAME, {'FullName': FAMILY + ' Regular', 'FamilyName': FAMILY}, cs, {})
        fb.setupHorizontalMetrics({n: (adv[n], lsb(n)) for n in order})
        fb.setupHorizontalHeader(ascent=asc, descent=desc)
        fb.setupNameTable(names)
        fb.setupOS2(sTypoAscender=asc, sTypoDescender=desc, sTypoLineGap=0, usWinAscent=asc + 40,
                    usWinDescent=-desc + 40, sxHeight=round(statistics.median(
                        [paths[gname(c)].bounds[3] for c in 'xnuvz' if c in glyphs])),
                    sCapHeight=CAP, fsType=0, achVendID='NONE', usWeightClass=400)
        fb.setupPost()
        path = os.path.join(OUT, PS_NAME + '.' + flavour)
        fb.save(path)
        print('wrote', path, os.path.getsize(path), 'bytes')
    counts = {}
    for c, s in source.items():
        counts[s] = counts.get(s, 0) + 1
    print('glyph sources:', counts)


if __name__ == '__main__':
    main()
