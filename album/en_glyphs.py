"""Cut the English build's own title letters out of its list atlases.

The USA release (title 010083E00F40E000) draws every BGM / Movie / Ending List title
into BC7 atlases in GAME_01.CPK. Each known English line is split into one bitmap per
character: strong pixels (alpha > SEED) form the seeds, i-dots and question-mark dots
are merged into the letter they sit over, and every faint anti-aliased pixel is handed
to the nearest seed. A line whose piece count disagrees with its text is skipped, so a
touching pair never yields a wrong letter.
"""
import os, sys, unicodedata
from collections import deque
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
from cpk import UTF, crilayla
from tid import TID

EN_CPK = os.path.expanduser('~/Documents/Game/010083E00F40E000/romfs/GAME_01.CPK')
SEED = 96
BASE_SET = set('abcdefhiklmnorstuvwxzABCDEFGHIKLMNOPRSTUVWXYZ')

# (atlas, [(text, (x0, y0, x1, y1)), ...]) - rectangles hold exactly one English line.
BGM_LINES = [(t, (0, 96 * r, 770, 96 * r + 96)) for r, t in enumerate([
    'The Monochrome City', 'Breakfast Time', 'Lunch Time', 'Supper Time', 'Dinner Time',
    'Everyone All Around', 'A Closed Box and A Key', 'Reminiscence of Sadness', 'Reminiscence of Love',
    'Playing Marbles', 'Swerving Marble', None, 'Drunkard', 'Premonition', 'Suspicion',
    'Garnet Vs. Adamantite', 'Thought Experiment', 'Virtual Experiment', 'Gunshot Wound', "Noah's Ark"]) if t]
MOVIE_LINES = [(t, (x0, 453 + 96 * r, x1, 453 + 96 * r + 96)) for r, (x0, x1), t in [
    (0, (120, 735), 'Silent Noise'), (0, (735, 1340), 'Premonition'),
    (1, (120, 735), 'Scene in a Dream'), (1, (735, 1340), 'Next to Eternity'),
    (2, (120, 735), 'Four-leaf Clover'), (2, (735, 1340), 'Happy Pet Cat'),
    (3, (120, 735), 'Indelible Memories')]]
_E = [  # (text, ocr x0, y0, x1, y1) read off the USA endlistParts
    ('A test of resolve', 0, 22, 358, 83), ('Abandoned cat', 786, 30, 1126, 80),
    ('Prison of malice', 0, 220, 357, 270), ('Let me hear your voice', 785, 217, 1294, 291),
    ('Failure as a fan', 0, 318, 335, 367), ('Doll with closed eyes', 789, 304, 1255, 382),
    ("You're such a strange person", 0, 406, 628, 479), ('Trick of the imagination', 789, 408, 1329, 479),
    ("You weren't the one", 0, 508, 450, 557), ('A dying wish', 0, 604, 296, 667),
    ("Icy hand and demon's whispers", 0, 696, 684, 764), ('Ally of Justice', 0, 890, 318, 953),
    ('Obtained Freedom', 4, 984, 423, 1038), ("Who's sin is it anyway?", 0, 1082, 516, 1144),
    ('Bunny stained in red', 0, 1179, 463, 1242), ('Public murder', 0, 1276, 326, 1325),
    ('False justice', 0, 1373, 269, 1432), ('A dim glimmer', 3, 1565, 349, 1628),
    ('Bloodstained lamentation', 786, 604, 1351, 653), ('Desperate defeat', 786, 896, 1157, 954),
    ('In a world of enduring sorrow', 784, 973, 1445, 1057), ('Bound by love', 785, 1080, 1109, 1147),
    ('Erase it in my place', 784, 1170, 1224, 1245), ('The city...without you', 786, 1276, 1285, 1339),
    ('Resonance of the Executors', 786, 1466, 1391, 1520), ("God's true colors", 4, 1661, 379, 1710),
    ('Protection in the line of fire', 0, 1754, 613, 1803), ('Critical hit', 4, 1849, 256, 1901),
    ("I'm sorry", 0, 1944, 207, 2013)]
END_LINES = [(t, (max(0, x0 - 4), y0 - 6, x1 + 4, y1 + 6)) for t, x0, y0, x1, y1 in _E] + [
    ("Mull over it in hell, m'kay?", (782, 790, 1390, 866)),
    ('We would like to announce X-Day - [Subtraction]', (0, 117, 1147, 200)),
    ('HAPPY END', (782, 497, 1108, 560))]

ATLASES = {
    'bgm': ('BGM/bgm_Parts.tid', BGM_LINES),
    'movie': ('MOVIE/movieParts.tid', MOVIE_LINES),
    'endlist': ('ENDLIST/endlistParts.tid', END_LINES),
}


def read_en(names, cpk_path=EN_CPK):
    with open(cpk_path, 'rb') as f:
        pre = f.read(1 << 20)
        h = UTF(pre, 0x10).rows[0]
        f.seek(h['TocOffset'])
        toc = UTF(f.read(h['TocSize'] + 0x10), 0x10)
        base = min(h['TocOffset'], h['ContentOffset'])
        out = {}
        for r in toc.rows:
            n = (r['DirName'] + '/' if r['DirName'] else '') + r['FileName']
            if n in names:
                f.seek(base + r['FileOffset'])
                d = f.read(r['FileSize'])
                out[n] = crilayla(d) if r['ExtractSize'] > r['FileSize'] else d
    return out


def seeds(A, box):
    x0, y0, x1, y1 = box
    px = A.load()
    seen, comps = set(), []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[x, y] > SEED and (x, y) not in seen:
                st, pts = [(x, y)], []
                seen.add((x, y))
                while st:
                    a, b = st.pop()
                    pts.append((a, b))
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            c, d = a + dx, b + dy
                            if x0 <= c < x1 and y0 <= d < y1 and (c, d) not in seen and px[c, d] > SEED:
                                seen.add((c, d))
                                st.append((c, d))
                comps.append(pts)
    return comps


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def merge_stacked(comps):
    """Fold a piece into the one it sits directly above or below (i/j dots, ?, !, :, ;)."""
    comps = sorted(comps, key=lambda c: bbox(c)[0])
    changed = True
    while changed:
        changed = False
        for i in range(len(comps)):
            for j in range(len(comps)):
                if i == j:
                    continue
                a, b = bbox(comps[i]), bbox(comps[j])
                ov = min(a[2], b[2]) - max(a[0], b[0]) + 1
                small = min(a[2] - a[0], b[2] - b[0]) + 1
                apart = a[3] < b[1] or b[3] < a[1]
                if ov >= 0.5 * small and apart:
                    comps[i] = comps[i] + comps[j]
                    del comps[j]
                    changed = True
                    break
            if changed:
                break
    return sorted(comps, key=lambda c: bbox(c)[0])


def split_line(A, text, box):
    comps = merge_stacked(seeds(A, box))
    chars = [c for c in text if c != ' ']
    # '...' style runs and quotes are single pieces per character; count must match
    if len(comps) != len(chars):
        return None
    x0, y0, x1, y1 = box
    px = A.load()
    label = {}
    q = deque()
    for k, pts in enumerate(comps):
        for p in pts:
            label[p] = k
            q.append(p)
    while q:  # hand every faint pixel to the nearest strong piece
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
        l, t, r, b = bbox(pts)
        im = Image.new('L', (r - l + 1, b - t + 1), 0)
        ip = im.load()
        for (x, y) in pts:
            ip[x - l, y - t] = px[x, y]
        strong = bbox([p for p in pts if px[p] > SEED])
        out.append((ch, im, l, t, strong))
    bottoms = sorted(s[3] for ch, im, l, t, s in out if ch in BASE_SET)
    baseline = bottoms[len(bottoms) // 2] + 1 if bottoms else None
    # word starts, for measuring the space
    words, k = [], 0
    for w in text.split(' '):
        words.append(k)
        k += len(w)
    return out, baseline, words


def build(atlas_key, en_cache=None):
    """{char: (alpha image, top relative to baseline)}, plus raw per-line pieces for fitting."""
    name, lines = ATLASES[atlas_key]
    raw = (en_cache or read_en([name]))[name]
    A = TID(raw).image().convert('RGBA').getchannel('A')
    lib, samples, used = {}, {}, []
    for text, box in lines:
        res = split_line(A, text, box)
        if res is None or res[1] is None:
            print('  [%s] skipped line %r' % (atlas_key, text))
            continue
        pieces, baseline, words = res
        used.append((text, pieces, baseline))
        for ch, im, l, t, strong in pieces:
            samples.setdefault(ch, []).append((im, t - baseline, strong[1] - baseline, strong[3] - baseline))
    for ch, ss in samples.items():
        ss.sort(key=lambda s: (s[0].width, s[0].height))
        im, top, stop, sbot = ss[len(ss) // 2]
        lib[ch] = (im, top)
    return lib, used


if __name__ == '__main__':
    names = [v[0] for v in ATLASES.values()]
    cache = read_en(names)
    for k in ATLASES:
        lib, used = build(k, cache)
        print(k, len(used), 'lines,', len(lib), 'glyphs:', ''.join(sorted(lib)))
