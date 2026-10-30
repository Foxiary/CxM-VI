"""Rebuild the Vietnamese BGM / Movie / Ending List titles out of the English build's own letters.

Every base letter is a bitmap the USA release (010083E00F40E000, GAME_01.CPK) drew for its
BGM / Movie titles, cut out by en_glyphs.py. Those two lists share one typeface; the USA Ending
List uses a different, heavier one. The Ending List here is set in the BGM / Movie face too, at
the BGM spacing, and then scaled down to the Ending List's own cap height, so all three lists
read as one typeface. Only what the English titles never needed
is drawn here: the Vietnamese marks (tone marks, circumflex, breve, horn, dot below, the bar of
đ/Đ). Each mark is the difference between Old Standard's accented letter and its plain letter,
rendered at the size and stroke weight that match that list's English letters, and placed
against the English base letter the way the font places it. Letter spacing follows side
bearings learned from the English lines, so the result is set the way the English titles are.

Slots, columns and baselines are those of the Japanese atlases this game reads. The Ending List
starts from the Japanese original, so every fixed label (÷ [Division], HAPPY END, ? ? ?, digits,
the scroll parts at x >= 1570) comes back byte for byte. The new .tid files are the size of the
old ones and are stored uncompressed, so they are written in place into GAME_01.cpk.

    python3 album_en_letters.py               # render + write into both GAME_01.cpk copies
    python3 album_en_letters.py --dry-run     # previews only
    python3 album_en_letters.py --restore     # put the textures from before this script back
"""
import argparse, hashlib, os, shutil, statistics, unicodedata
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import album_fontsize as af
import en_glyphs as eg
from tid import TID

DATA = af.DATA
FONT = os.path.join(DATA, 'fonts', 'OldStandardTT-Regular.ttf')
CPKS = [af.CPK_PATH, os.path.expanduser(
    '~/Documents/Game/01002B400E9DA000/PatchVietHoa/romfs/CONTENTS/GAME_01.cpk')]
OLD = os.path.join(DATA, 'backup-truoc-doi-co-chu')        # the patch as it shipped
PREV = os.path.join(DATA, 'backup-truoc-chu-en')           # what this script replaced
SS = 4
MIN_TRACK = -2.0

# Old Standard size whose letters match each list's English letters (fitted on ink heights).
SIZE = {'bgm': 73.5, 'movie': 72.5, 'endlist': 53.3}
FALLBACK = {'bgm': ['movie'], 'movie': ['bgm'], 'endlist': ['bgm', 'movie']}
# whose letters and spacing each list is set with; the Ending List borrows the BGM face
STYLE = {'bgm': 'bgm', 'movie': 'movie', 'endlist': 'bgm'}


def cap_height(lib):
    return statistics.median(lib[c][0].height for c in 'EHILT' if c in lib)

# (key, left ink x, right ink limit, clear x0, clear x1, row top, baseline, text)
BGM_ROWS = [(0, 'Thị trấn đơn sắc'), (5, 'Ai cũng thế'), (6, 'Hộp kín & Chìa khóa'), (7, 'Hồi ức buồn'),
            (8, 'Hồi ức yêu thương'), (9, 'Bi thủy tinh ngân vang'), (10, 'Bi thủy tinh rung rinh'),
            (11, 'Điên dại dưới ánh trăng'), (16, 'Thí nghiệm tư duy'), (17, 'Thí nghiệm giả tưởng'),
            (18, 'Vết đạn')]
# Right ink limits are NOT the slot edges. The engine draws only a fixed-width rectangle of
# each list row: on the BGM screen a title is cut at atlas x ~731-735 (measured off an in-game
# screenshot, three rows cut at the same x). Each limit is the widest ink the shipped English
# or Japanese atlas puts in that column, which the game is known to show whole.
BGM_RIGHT = 729                       # EN 'A Closed Box and A Key' ends at 729
# The Movie screen shows every title in one TITLE column, whichever atlas column it comes from,
# and cuts it ~565 atlas px after its left ink edge (two in-game rows measured: 565 and 569).
# EN's widest title is 560, so 556 keeps a margin.
MOVIE_W = 556
MOVIE_COLS = {'L': (137, 137 + MOVIE_W, 128, 736), 'R': (744, 744 + MOVIE_W, 738, 1340)}
MOVIE_ROWS = [(0, 'L', 'Nhiễu lặng'), (1, 'L', 'Cảnh trong mơ'), (1, 'R', 'Vĩnh cửu kề bên'),
              (2, 'L', 'Cỏ bốn lá'), (2, 'R', 'Mèo cưng hạnh phúc'), (3, 'L', 'Ký ức khắc sâu')]
END_COLS = {'L': (8, 772, 0, 782), 'R': (791, 1443, 784, 1570)}        # EN L 772, R 1443
END_ROWS = [
    (0, 'L', 'Ý chí bị thử thách'), (0, 'R', 'Chú mèo bị bỏ rơi'), (1, 'L', 'Thông báo về X-Day'),
    (2, 'L', 'Ngục tù của ác ý'), (2, 'R', 'Em muốn nghe giọng anh'),
    (3, 'L', 'Không xứng làm fan'), (3, 'R', 'Búp bê nhắm mắt'),
    (4, 'L', 'Em đúng là người kỳ lạ'), (4, 'R', 'Chỉ là nhất thời'), (5, 'L', 'Dẫu biết không phải em'),
    (6, 'L', 'Lời nguyện cuối cùng'), (6, 'R', 'Tiếng khóc đẫm máu'),
    (7, 'L', 'Ngón tay lạnh lẽo & Lời của ác quỷ'), (8, 'R', 'Hãy hối lỗi dưới địa ngục'),
    (9, 'L', 'Đồng minh của công lý'), (9, 'R', 'Không thể mất, nên đành mất'),
    (10, 'L', 'Tự do đoạt được'), (10, 'R', 'Nơi nỗi buồn vẫn kéo dài'),
    (11, 'L', 'Tội lỗi thuộc về ai?'), (11, 'R', 'Xiềng xích tình yêu'),
    (12, 'L', 'Chú thỏ nhuốm màu đỏ'), (12, 'R', 'Đổi lại, hãy kết liễu anh đi'),
    (13, 'L', 'Án mạng công khai'), (13, 'R', 'Thành phố không có em'), (14, 'L', 'Công lý giả tạo'),
    (15, 'R', 'Những kẻ kết án đồng điệu'), (16, 'L', 'Đôi mắt u ám'),
    (17, 'L', 'Chân tướng của vị thần'), (18, 'L', 'Nòng súng để bảo vệ'), (19, 'L', 'Đòn quyết định'),
    (20, 'L', 'Anh xin lỗi')]
# Fixed labels the game ships as pictures, drawn at 53 px cap - a third bigger than the titles
# around them. Redrawn here in the same letters and size as the titles, from the left edge the
# shipped sprite starts at: (row, column, left ink x, text).
END_LABELS = [(1, 'R', 804, '- [Subtraction]'), (5, 'R', 788, 'HAPPY END'), (7, 'R', 804, '÷ [Division]'),
              (8, 'L', 24, '× [Multiplication]'), (14, 'R', 811, '= [Equal]'), (15, 'L', 26, '+ [Addition]')]


# Movie CATEGORY labels: the engine shows one 288 x 96 cell of the atlas per label (cells at
# x = 288k on rows y 168 and 264). They are copied verbatim from the English build - "OP",
# "PROLOGUE", "Aiji ED", "Kei ED", "Mineo ED", "Takeru ED", "Kageyuki ED" - which sit exactly
# in those cells. (The patch had drawn surnames wider than a cell, so each screen showed a
# neighbour's last letter and lost its own.)
CATEGORY_RECTS = [(0, 168, 1728, 264), (0, 264, 288, 352)]


def slots(key):
    if key == 'bgm':
        return [(12, BGM_RIGHT, 0, 768, 96 * r, 96 * r + 69, t) for r, t in BGM_ROWS]
    if key == 'movie':
        return [MOVIE_COLS[c][:2] + MOVIE_COLS[c][2:] + (453 + 96 * r, 453 + 96 * r + 70, t)
                for r, c, t in MOVIE_ROWS]
    return ([END_COLS[c] + (96 * r, 96 * r + 68, t) for r, c, t in END_ROWS] +
            [(x,) + END_COLS[c][1:] + (96 * r, 96 * r + 68, t) for r, c, x, t in END_LABELS])


TEXTURES = {
    'bgm': ('BGM/bgm_Parts.tid', 'BGM/bgm_Parts.png'),
    'movie': ('MOVIE/movieParts.tid', 'MOVIE/movieParts.png'),
    'endlist': ('ENDLIST/endlistParts.tid', 'ENDLIST/endlistParts.png'),
}


# ---------------------------------------------------------------- Old Standard, weight-matched

class OS:
    def __init__(self, size, stroke=0):
        self.size, self.stroke = size, stroke
        self.f = ImageFont.truetype(FONT, int(round(size * SS)))
        self._cache = {}

    def glyph(self, ch):
        """(alpha image, ink left rel. pen, ink top rel. baseline) at 1x."""
        if ch in self._cache:
            return self._cache[ch]
        px = int(round(self.size * SS))
        pad = SS * (px // SS + 2)
        im = Image.new('L', (3 * pad, 3 * pad), 0)
        ImageDraw.Draw(im).text((pad, 2 * pad), ch, font=self.f, fill=255, anchor='ls',
                                stroke_width=max(self.stroke, 0), stroke_fill=255)
        if self.stroke < 0:          # thinner than the face: erode at the supersampled scale
            im = im.filter(ImageFilter.MinFilter(2 * -self.stroke + 1))
        im = im.resize((im.width // SS, im.height // SS), Image.BOX)
        bb = im.point(lambda v: 255 if v > 8 else 0).getbbox()
        r = (im.crop(bb), bb[0] - pad // SS, bb[1] - 2 * pad // SS) if bb else (Image.new('L', (1, 1)), 0, 0)
        self._cache[ch] = r
        return r

    def bearings(self, ch):
        im, l, t = self.glyph(ch)
        adv = self.f.getlength(ch) / SS
        return l, adv - (l + im.width), adv


def mass(im):
    return sum(im.tobytes()) / 255.0


def hairline(im):
    """Ink across the top hairline of a round letter, at its centre column (px)."""
    w, h = im.size
    px = im.load()
    return sum(px[w // 2, y] for y in range(h // 2)) / 255.0


def match_stroke(key, lib):
    """Stroke (in 1/SS px) that gives Old Standard the hairline weight of this list's English letters.

    Tone marks, the circumflex and the breve are hairline-and-wedge shapes, so the hairline is
    what has to match; matching total ink would make them thinner than the English letters.
    """
    best = None
    for k in range(-3, 5):
        o = OS(SIZE[key], k)
        err = sum((hairline(o.glyph(ch)[0]) - hairline(lib[ch][0])) ** 2 for ch in 'oe' if ch in lib)
        if best is None or err < best[0]:
            best = (err, k)
    return best[1]


# ---------------------------------------------------------------- marks

def split_marks(os_font, ch):
    """Vietnamese letter -> (base letter, [(mark image, kind, dx, dy)]) relative to the OS base glyph.

    kind 'above' / 'below' are placed by keeping the font's gap to the base letter, 'attached'
    (horn, đ bar) by mapping its position through the base letter's ink box.
    """
    if ch in 'đĐ':
        base = 'd' if ch == 'đ' else 'D'
    else:
        d = unicodedata.normalize('NFD', ch)
        base = d[0]
        if len(d) == 1:
            return ch, ch, []
    # the font builds í ì ỉ ĩ on a dotless i: subtract that, or the mark lands inside the dot
    above = any(unicodedata.combining(c) == 230 for c in unicodedata.normalize('NFD', ch)[1:])
    sub = 'ı' if base == 'i' and above else base
    full, fl, ft = os_font.glyph(ch)
    bim, bl, bt = os_font.glyph(sub)
    # the accented glyph may not draw its base at exactly the same spot; find the best fit
    best = None
    for sx in range(-3, 4):
        canvas = Image.new('L', full.size, 0)
        canvas.paste(bim, (bl - fl + sx, bt - ft))
        rest = ImageChops.subtract(full, canvas)
        m = mass(rest)
        if best is None or m < best[0]:
            best = (m, sx, rest)
    _, sx, rest = best
    rest = rest.point(lambda v: v if v > 24 else 0)
    # group the remaining ink into connected pieces
    px = rest.load()
    w, h = rest.size
    seen, pieces = set(), []
    for y in range(h):
        for x in range(w):
            if px[x, y] > 60 and (x, y) not in seen:
                st, pts = [(x, y)], []
                seen.add((x, y))
                while st:
                    a, b = st.pop()
                    pts.append((a, b))
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            c, e = a + dx, b + dy
                            if 0 <= c < w and 0 <= e < h and (c, e) not in seen and px[c, e] > 24:
                                seen.add((c, e))
                                st.append((c, e))
                if len(pts) >= 6:
                    pieces.append(pts)
    btop = bt - ft
    bbot = btop + bim.height - 1
    groups = {}
    for pts in pieces:
        ys = [p[1] for p in pts]
        if max(ys) < btop:
            kind = 'above'
        elif min(ys) > bbot:
            kind = 'below'
        else:
            kind = 'attached'
        groups.setdefault(kind, []).extend(pts)
    marks = []
    fp = full.load()
    for kind, pts in groups.items():
        # a free-standing mark keeps a 1 px fringe; a horn or a đ bar reaches 2 px back into
        # the base letter, taking those pixels from the accented glyph, so it stays joined
        # to the English stem instead of floating beside it
        grow, src = (1, px) if kind != 'attached' else (2, fp)
        keep = set()
        for (x, y) in pts:
            for dx in range(-grow, grow + 1):
                for dy in range(-grow, grow + 1):
                    if 0 <= x + dx < w and 0 <= y + dy < h:
                        keep.add((x + dx, y + dy))
        keep = [p for p in keep if src[p] > 0]
        xs = [p[0] for p in keep]
        ys = [p[1] for p in keep]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        im = Image.new('L', (x1 - x0 + 1, y1 - y0 + 1), 0)
        ip = im.load()
        for (x, y) in keep:
            ip[x - x0, y - y0] = src[x, y]
        # position relative to the OS base glyph's ink box
        marks.append((im, kind, x0 - (bl - fl + sx), y0 - btop))
    return base, sub, marks


def stem_x(im, right):
    """Centre x of the heaviest vertical stem of a letter (rightmost for d, leftmost for D)."""
    w, h = im.size
    px = im.load()
    cov = [sum(px[x, y] for y in range(h)) for x in range(w)]
    peak = max(cov)
    xs = [x for x in range(w) if cov[x] >= 0.6 * peak]
    side = max(xs) if right else min(xs)
    run = [x for x in xs if abs(x - side) <= w // 4]
    return sum(run) / len(run)


def dotless(im):
    """English 'i' without its dot: drop everything above the first empty row band."""
    w, h = im.size
    px = im.load()
    rows = [max(px[x, y] for x in range(w)) for y in range(h)]
    y = 0
    while y < h and rows[y] > 0:
        y += 1
    if y >= h // 2:
        return im
    while y < h and rows[y] == 0:
        y += 1
    out = im.copy()
    out.paste(0, (0, 0, w, y))
    return out.crop(out.getbbox())


# ---------------------------------------------------------------- spacing learned from the English lines

def learn_spacing(key, used, os_font, lib):
    """Per-letter left/right bearings (px) and the space width, fitted to the English lines."""
    prior = {ch: os_font.bearings(ch)[:2] for ch in lib}
    L = {c: v[0] for c, v in prior.items()}
    R = {c: v[1] for c, v in prior.items()}
    pairs, spaces = [], []
    for text, pieces, _base in used:
        chars = [c for c in text if c != ' ']
        k = 0
        breaks = set()
        for w in text.split(' ')[:-1]:
            k += len(w)
            breaks.add(k - 1)
        for i in range(len(pieces) - 1):
            a, b = pieces[i], pieces[i + 1]
            gap = b[2] - (a[2] + a[1].width)
            (spaces if i in breaks else pairs).append((a[0], b[0], gap))
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
    space = statistics.median(g - R[a] - L[b] for a, b, g in spaces) if spaces else os_font.bearings(' ')[2]
    return L, R, track, space, rms


# ---------------------------------------------------------------- one list

class Setter:
    def __init__(self, key, libs, used):
        self.key = key
        self.lib = dict(libs[key])
        self.src = {c: key for c in self.lib}
        for other in FALLBACK[key]:
            f = SIZE[key] / SIZE[other]
            for c, (im, top) in libs[other].items():
                if c not in self.lib:
                    self.lib[c] = (im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))),
                                             Image.LANCZOS), round(top * f))
                    self.src[c] = other
        self.stroke = match_stroke(key, libs[key])
        self.os = OS(SIZE[key], self.stroke)
        self.L, self.R, self.track, self.space, self.rms = learn_spacing(key, used, self.os, libs[key])
        self.drawn = set()          # letters that had to come from Old Standard

    def base_glyph(self, c, has_above):
        if c in self.lib:
            im, top = self.lib[c]
            if c == 'i' and has_above:
                d = dotless(im)
                top = top + (im.height - d.height)
                im = d
            return im, top
        self.drawn.add(c)
        im, _l, t = self.os.glyph(c)
        return im, t

    def bear(self, c):
        if c in self.L:
            return self.L[c], self.R[c]
        l, r, _ = self.os.bearings(c)
        return l, r

    def letter(self, ch):
        """(alpha image, left offset of base ink, top rel. baseline, base ink width, L, R)."""
        base, sub, marks = split_marks(self.os, ch)
        bim, btop = self.base_glyph(base, sub != base)
        oim, _ol, ot = self.os.glyph(sub)
        L, R = self.bear(base)
        if ch != base:
            R += self.os.bearings(ch)[2] - self.os.bearings(base)[2]   # horn widens the advance
        parts = [(bim, 0, btop)]
        sx = bim.width / max(1, oim.width)
        sy = bim.height / max(1, oim.height)
        for mim, kind, dx, dy in marks:
            cx = dx + mim.width / 2.0
            if kind == 'above':
                x = (oim.width / 2.0 + (cx - oim.width / 2.0) * sx) * 1.0
                y = btop + dy                      # same gap above the base as in the font
            elif kind == 'below':
                x = oim.width / 2.0 + (cx - oim.width / 2.0) * sx
                y = btop + bim.height + (dy - oim.height)
            elif base in 'dD':
                # the bar of đ / Đ is hung on the stem, wherever the English letter has it
                right = base == 'd'
                x = stem_x(bim, right) + (cx - stem_x(oim, right))
                y = btop + dy * sy
            else:
                # horn: keep its distance from the right edge of the letter
                x = bim.width + (cx - oim.width) * sx
                y = btop + dy * sy
            parts.append((mim, round(x - mim.width / 2.0), round(y)))
        x0 = min(p[1] for p in parts)
        y0 = min(p[2] for p in parts)
        x1 = max(p[1] + p[0].width for p in parts)
        y1 = max(p[2] + p[0].height for p in parts)
        out = Image.new('L', (x1 - x0, y1 - y0), 0)
        for im, x, y in parts:
            layer = Image.new('L', out.size, 0)
            layer.paste(im, (x - x0, y - y0))
            out = ImageChops.lighter(out, layer)
        return out, -x0, y0, bim.width, L, R

    def line(self, text, track):
        """Alpha image of the whole line, x of the first base ink, y of the baseline inside it."""
        items, pen, prev = [], 0.0, None
        for i, ch in enumerate(text):
            if ch == ' ':
                pen += self.space - self.track
                continue
            im, bx, top, bw, L, R = self.letter(ch)
            if prev is not None:
                pen += prev + L + self.track + track
            items.append((im, round(pen) - bx, top))
            pen += bw
            prev = R
        x0 = min(x for _, x, _ in items)
        y0 = min(t for _, _, t in items)
        x1 = max(x + im.width for im, x, _ in items)
        y1 = max(t + im.height for im, _, t in items)
        out = Image.new('L', (x1 - x0, y1 - y0), 0)
        for im, x, t in items:
            layer = Image.new('L', out.size, 0)
            layer.paste(im, (x - x0, t - y0))
            out = ImageChops.lighter(out, layer)
        return out, -x0, -y0

    def fit(self, text, room, top_room, bottom_room):
        """Tighten up to 2 px per gap, then shrink the whole line until it fits its slot."""
        track = 0.0
        while True:
            im, ox, base = self.line(text, track)
            if im.width - ox <= room or track <= MIN_TRACK:
                break
            track -= 0.5
        scale = 1.0
        while True:
            w = (im.width - ox) * scale
            above, below = base * scale, (im.height - base) * scale
            if w <= room and above <= top_room and below <= bottom_room:
                break
            scale -= 0.005
        if scale < 1.0:
            nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
            im = im.resize((nw, nh), Image.LANCZOS)
            ox, base = round(ox * scale), round(base * scale)
        return im, ox, base, track, scale


# ---------------------------------------------------------------- texture I/O

def locate_all(names):
    found = [af.locate(p, names) for p in CPKS]
    assert all(f == found[0] for f in found), 'the GAME_01.cpk copies disagree on offsets'
    return found[0]


def read_at(path, off, size):
    with open(path, 'rb') as f:
        f.seek(off)
        return f.read(size)


def encode(raw_base, base_img, new_img):
    """Re-encode only the 4x4 blocks that differ from the base texture; keep every other block verbatim."""
    t = TID(raw_base)
    payload = bytearray(t.body())
    b, a = base_img.load(), new_img.load()
    bw = t.width // 4
    changed = 0
    for by in range(t.height // 4):
        for bx in range(bw):
            cells = [(bx * 4 + i, by * 4 + j) for j in range(4) for i in range(4)]
            pix = [a[p] for p in cells]
            if pix == [b[p] for p in cells]:
                continue
            o = (by * bw + bx) * 16
            payload[o:o + 16] = af.enc_alpha([p[3] for p in pix]) + af.WHITE
            changed += 1
    out = raw_base[:t.data_off] + bytes(payload) + raw_base[t.data_off + t.payload_size:]
    assert len(out) == len(raw_base)
    return out, changed


def flat(im, bg=(28, 28, 44, 255)):
    out = Image.new('RGBA', im.size, bg)
    out.alpha_composite(im)
    return out.convert('RGB')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--restore', action='store_true')
    ap.add_argument('--png-out', default=os.path.join(DATA, 'anh-sua'))
    ap.add_argument('--preview', default=os.path.join(DATA, 'preview-chu-en'))
    a = ap.parse_args()

    names = [v[0] for v in TEXTURES.values()]
    where = locate_all(names)
    os.makedirs(PREV, exist_ok=True)
    os.makedirs(a.preview, exist_ok=True)
    for name, png in TEXTURES.values():
        bak = os.path.join(PREV, os.path.basename(name))
        if not os.path.exists(bak):
            open(bak, 'wb').write(read_at(CPKS[0], *where[name]))
            shutil.copyfile(os.path.join(a.png_out, png), bak[:-4] + '.png')
            print('saved current', name, '->', bak)

    if a.restore:
        out = {n: open(os.path.join(PREV, os.path.basename(n)), 'rb').read() for n in names}
        for name, png in TEXTURES.values():
            shutil.copyfile(os.path.join(PREV, os.path.basename(name))[:-4] + '.png', os.path.join(a.png_out, png))
    else:
        en = eg.read_en(names)
        libs, used = {}, {}
        for k in TEXTURES:
            libs[k], used[k] = eg.build(k, en)
        out = {}
        setters = {}
        for key, (name, png) in TEXTURES.items():
            style = STYLE[key]
            if style not in setters:
                setters[style] = Setter(style, libs, used[style])
                st = setters[style]
                print('%s face: %d English letters, stroke %d/%d px, track %+.2f, space %.1f, spacing rms %.2f px'
                      % (style, len(libs[style]), st.stroke, SS, st.track, st.space, st.rms))
            setter = setters[style]
            setter.drawn = set()
            # draw at the face's own size, then scale to this list's English cap height
            k = cap_height(libs[key]) / cap_height(libs[style])
            print('%s: set in the %s face, scaled x%.3f (cap %.0f -> %.0f px)'
                  % (key, style, k, cap_height(libs[style]), cap_height(libs[key])))
            if key == 'endlist':
                raw = open(os.path.join(OLD, 'endlistParts.nsp-goc.tid'), 'rb').read()
                hdr = open(os.path.join(OLD, 'endlistParts.tid'), 'rb').read()
                t = TID(raw)
                raw = hdr[:t.data_off] + raw[t.data_off:]
            else:
                raw = open(os.path.join(OLD, os.path.basename(name)), 'rb').read()
            base_img = TID(raw).image().convert('RGBA')
            img = base_img.copy()
            px = img.load()
            for ink_x, ink_r, cx0, cx1, y0, baseline, text in slots(key):
                for y in range(y0, y0 + 96):
                    for x in range(cx0, cx1):
                        px[x, y] = (255, 255, 255, 0)
            for ink_x, ink_r, cx0, cx1, y0, baseline, text in slots(key):
                text = unicodedata.normalize('NFC', text)
                mask, ox, base, track, scale = setter.fit(text, (ink_r - ink_x + 1) / k,
                                                           (baseline - y0 - 2) / k, (y0 + 94 - baseline) / k)
                if k != 1.0:
                    mask = mask.resize((max(1, round(mask.width * k)), max(1, round(mask.height * k))), Image.LANCZOS)
                    ox, base = round(ox * k), round(base * k)
                    while ink_x - ox + mask.width - 1 > ink_r and mask.width > 1:   # rounding guard
                        mask = mask.resize((mask.width - 1, mask.height), Image.LANCZOS)
                plate = Image.new('RGBA', mask.size, (255, 255, 255, 0))
                plate.putalpha(mask)
                img.alpha_composite(plate, (ink_x - ox, baseline - base))
                print('  %-36s track %+.1f scale %.3f  ink x %d..%d' % (
                    text, track, scale, ink_x, ink_x - ox + mask.width - 1))
            if key == 'movie':
                eng = TID(en[name]).image().convert('RGBA')
                for rect in CATEGORY_RECTS:
                    img.paste(eng.crop(rect), rect[:2])
                print('  category labels copied from the English build:', CATEGORY_RECTS)
            if setter.drawn:
                print('  letters not in the English atlases, drawn from Old Standard:', ''.join(sorted(setter.drawn)))
            new, changed = encode(raw, base_img, img)
            print('  %s: %d DXT5 blocks re-encoded' % (name, changed))
            out[name] = new
            dec = TID(new).image().convert('RGBA')
            dec.save(os.path.join(a.preview, os.path.basename(png)))
            # English above, Vietnamese below, same crop
            ref = TID(en[name]).image().convert('RGBA')
            box = {'bgm': (0, 0, 780, 1920), 'movie': (100, 440, 1350, 840), 'endlist': (0, 0, 1570, 2020)}[key]
            e, v = flat(ref.crop(box)), flat(dec.crop(box))
            cmp_ = Image.new('RGB', (e.width * 2 + 16, e.height), (200, 30, 30))
            cmp_.paste(e, (0, 0))
            cmp_.paste(v, (e.width + 16, 0))
            cmp_.save(os.path.join(a.preview, 'en-vs-vi_%s.png' % key))
            if not a.dry_run:
                dec.save(os.path.join(a.png_out, png))
    if a.dry_run:
        return
    for path in CPKS:
        with open(path, 'r+b') as f:
            for name in names:
                off, size = where[name]
                assert len(out[name]) == size
                f.seek(off)
                f.write(out[name])
        for name in names:
            assert read_at(path, *where[name]) == out[name]
        print('wrote', ', '.join(os.path.basename(n) for n in names), 'into', path)
    for name in names:
        print('  %s sha1 %s' % (name, hashlib.sha1(out[name]).hexdigest()[:12]))


if __name__ == '__main__':
    main()
