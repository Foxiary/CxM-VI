"""Redraw the Vietnamese titles of the BGM and Movie lists at the size of the English titles.

The list atlases (BGM/bgm_Parts.tid, MOVIE/movieParts.tid in GAME_01.cpk) hold one title per
fixed 96 px row. English titles there match Old Standard Regular at 74 px with no extra tracking,
ink between row+13 and row+91, baseline at row+70. Vietnamese titles get the same size and baseline;
only titles too wide for their column are tightened (at most 2 px per letter) and then shrunk.

Always starts from the texture saved in backup/ before the first run, so it can be re-run safely.
The new .tid is the same size as the old one, so it is written into the CPK in place.

    python3 album_fontsize.py                       # render + install into Ryujinx
    python3 album_fontsize.py --dry-run             # render previews only
    python3 album_fontsize.py --restore             # put the backed-up textures back
"""
import argparse, hashlib, os, shutil, struct, sys, unicodedata
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'work', 'album')    # game files and output, gitignored
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
from cpk import UTF
from tid import TID

FONT = os.path.join(DATA, 'fonts', 'OldStandardTT-Regular.ttf')
CPK_PATH = os.path.expanduser('~/Documents/Ryujinx/sdcard/atmosphere/contents/01002b400e9da000/romfs/CONTENTS/GAME_01.cpk')
SIZE, MIN_TRACK, SS = 74, -2.0, 4
ROW, BASELINE, TOP_MIN, BOTTOM_MAX = 96, 70, 4, 92

# (row top, ink left, ink right limit, clear x0, clear x1, text)
BGM = [(96 * r, 13, 760, 0, 768, t) for r, t in [
    (0, 'Thị trấn đơn sắc'), (5, 'Ai cũng thế'), (6, 'Hộp kín & Chìa khóa'), (7, 'Hồi ức buồn'),
    (8, 'Hồi ức yêu thương'), (9, 'Bi thủy tinh ngân vang'), (10, 'Bi thủy tinh rung rinh'),
    (11, 'Điên dại dưới ánh trăng'), (16, 'Thí nghiệm tư duy'), (17, 'Thí nghiệm giả tưởng'), (18, 'Vết đạn'),
]]
MOVIE_COLS = {'L': (141, 728, 128, 736), 'R': (746, 1330, 738, 1340)}
MOVIE = [(453 + 96 * r,) + MOVIE_COLS[c] + (t,) for r, c, t in [
    (0, 'L', 'Nhiễu lặng'), (1, 'L', 'Cảnh trong mơ'), (1, 'R', 'Vĩnh cửu kề bên'),
    (2, 'L', 'Cỏ bốn lá'), (2, 'R', 'Mèo cưng hạnh phúc'), (3, 'L', 'Ký ức khắc sâu'),
]]
TEXTURES = [('BGM/bgm_Parts.tid', 'BGM/bgm_Parts.png', BGM), ('MOVIE/movieParts.tid', 'MOVIE/movieParts.png', MOVIE)]


def render(text, size, track):
    """Coverage mask of one line; returns (mask, ink left, ink top, ink right, ink bottom) relative to origin/baseline."""
    px = int(round(size * SS))
    f = ImageFont.truetype(FONT, px)
    pad = SS * (px // SS + 1)
    base = 2 * pad
    w = int(f.getlength(text) + len(text) * max(track, 0) * SS) + 2 * pad
    im = Image.new('L', (w, 3 * pad), 0)
    d = ImageDraw.Draw(im)
    for i, ch in enumerate(text):
        d.text((pad + f.getlength(text[:i]) + i * track * SS, base), ch, font=f, fill=255, anchor='ls')
    im = im.resize((im.width // SS, im.height // SS), Image.BOX)
    bb = im.point(lambda v: 255 if v > 8 else 0).getbbox()
    im = im.crop(bb)
    return im, bb[1] - base // SS, bb[3] - base // SS


def fit(text, room):
    size, track = SIZE, 0.0
    while True:
        im, top, bottom = render(text, size, track)
        if im.width <= room and BASELINE + top >= TOP_MIN and BASELINE + bottom <= BOTTOM_MAX:
            return im, top, size, track
        if im.width > room and track > MIN_TRACK:
            track -= 0.5
        else:
            size -= 0.5


def redraw(base, cells):
    out = base.copy()
    px = out.load()
    report = []
    for y0, ink_x, ink_r, cx0, cx1, text in cells:
        text = unicodedata.normalize('NFC', text)
        for y in range(y0, y0 + ROW):
            for x in range(cx0, cx1):
                px[x, y] = (255, 255, 255, 0)
        im, top, size, track = fit(text, ink_r - ink_x + 1)
        plate = Image.new('RGBA', im.size, (255, 255, 255, 0))
        plate.putalpha(im)
        out.alpha_composite(plate, (ink_x, y0 + BASELINE + top))
        report.append((text, size, track, im.width, im.height, ink_x + im.width - 1))
    return out, report


def enc_alpha(al):
    best = None
    lo, hi = min(al), max(al)
    cands = [(hi, lo, [hi, lo] + [((7 - i) * hi + i * lo) // 7 for i in range(1, 7)])]
    mid = [a for a in al if 0 < a < 255] or [lo, hi]
    m0, m1 = min(mid), max(mid)
    cands.append((m0, m1, [m0, m1] + [((5 - i) * m0 + i * m1) // 5 for i in range(1, 5)] + [0, 255]))
    for a0, a1, pal in cands:
        idx = [min(range(8), key=lambda k: abs(pal[k] - a)) for a in al]
        err = sum(abs(pal[k] - a) for k, a in zip(idx, al))
        if best is None or err < best[0]:
            best = (err, a0, a1, idx)
    _, a0, a1, idx = best
    bits = 0
    for i, v in enumerate(idx):
        bits |= v << (3 * i)
    return bytes([a0, a1]) + bits.to_bytes(6, 'little')


WHITE = struct.pack('<HHI', 0xFFFF, 0xFFFF, 0)


def encode_changed(raw_tid, before, after):
    t = TID(raw_tid)
    assert t.fourcc == b'DXT5' and before.size == after.size == (t.width, t.height)
    payload = bytearray(t.body())
    b, a = before.load(), after.load()
    bw = t.width // 4
    changed = 0
    for by in range(t.height // 4):
        for bx in range(bw):
            pix = [a[bx * 4 + i, by * 4 + j] for j in range(4) for i in range(4)]
            if pix == [b[bx * 4 + i, by * 4 + j] for j in range(4) for i in range(4)]:
                continue
            o = (by * bw + bx) * 16
            payload[o:o + 16] = enc_alpha([p[3] for p in pix]) + WHITE
            changed += 1
    out = raw_tid[:t.data_off] + bytes(payload) + raw_tid[t.data_off + t.payload_size:]
    assert len(out) == len(raw_tid)
    return out, changed


def locate(cpk_path, names):
    with open(cpk_path, 'rb') as f:
        prefix = f.read(1 << 20)
    h = UTF(prefix, 0x10).rows[0]
    toc = UTF(prefix, h['TocOffset'] + 0x10)
    base = min(h['TocOffset'], h['ContentOffset'])
    found = {}
    for r in toc.rows:
        name = (r['DirName'] + '/' if r['DirName'] else '') + r['FileName']
        if name in names:
            assert r['FileSize'] == r['ExtractSize'], (name, 'stored compressed, cannot write in place')
            found[name] = (base + r['FileOffset'], r['FileSize'])
    assert set(found) == set(names), found
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cpk', default=CPK_PATH)
    ap.add_argument('--png-out', default=os.path.join(DATA, 'anh-sua'))
    ap.add_argument('--backup', default=os.path.join(DATA, 'backup-truoc-doi-co-chu'))
    ap.add_argument('--preview', default=os.path.join(DATA, 'preview-co-chu'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--restore', action='store_true')
    a = ap.parse_args()

    where = locate(a.cpk, [n for n, _, _ in TEXTURES])
    os.makedirs(a.backup, exist_ok=True)
    os.makedirs(a.preview, exist_ok=True)
    for name, png, cells in TEXTURES:
        off, size = where[name]
        bak = os.path.join(a.backup, os.path.basename(name))
        if not os.path.exists(bak):
            with open(a.cpk, 'rb') as f:
                f.seek(off)
                open(bak, 'wb').write(f.read(size))
            old_png = os.path.join(a.png_out, png)
            if os.path.exists(old_png):
                shutil.copyfile(old_png, os.path.join(a.backup, os.path.basename(png)))
            print('backed up', name, '->', bak)
        raw = open(bak, 'rb').read()
        assert len(raw) == size, (name, len(raw), size)

        if a.restore:
            new = raw
            bak_png = os.path.join(a.backup, os.path.basename(png))
            if os.path.exists(bak_png):
                shutil.copyfile(bak_png, os.path.join(a.png_out, png))
        else:
            before = TID(raw).image().convert('RGBA')
            after, report = redraw(before, cells)
            for text, sz, tr, w, hgt, right in report:
                print('  %-28s size %.1f track %+.1f  %dx%d  right edge %d' % (text, sz, tr, w, hgt, right))
            new, changed = encode_changed(raw, before, after)
            decoded = TID(new).image().convert('RGBA')
            decoded.save(os.path.join(a.preview, os.path.basename(png)))
            if not a.dry_run:
                os.makedirs(os.path.dirname(os.path.join(a.png_out, png)), exist_ok=True)
                decoded.save(os.path.join(a.png_out, png))
            print(name, 'dxt blocks re-encoded', changed)
        if a.dry_run:
            continue
        with open(a.cpk, 'r+b') as f:
            f.seek(off)
            f.write(new)
        with open(a.cpk, 'rb') as f:
            f.seek(off)
            back = f.read(size)
        assert back == new
        print('wrote', name, 'into', a.cpk, 'sha1', hashlib.sha1(new).hexdigest()[:12])


if __name__ == '__main__':
    main()
