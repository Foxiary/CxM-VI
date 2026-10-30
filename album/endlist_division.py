"""Give the Division ending its label back and fit the long title beside it into the left column.

Atlas row 7 of ENDLIST/endlistParts.tid holds two entries: a left-column title (originally
冷たい指と悪魔のささやき, ink x 4..781) and the right-column sprite "÷ [Division]" (x 788..1208).
The Vietnamese title had been drawn at the size of the other titles, 1056 px wide, and ran over
"÷ [Divi". This puts the original sprite back, block for block, and redraws the title in the same
Old Standard Regular, tightened by up to 2 px per letter and then shrunk until its ink ends at
x 781, on the baseline it had before (y 744).

    python3 endlist_division.py              # render + install into Ryujinx
    python3 endlist_division.py --dry-run    # preview only
    python3 endlist_division.py --restore    # put the backed-up texture back
"""
import argparse, hashlib, os, shutil, unicodedata
from PIL import Image

import album_fontsize as af
from tid import TID

NAME, PNG = 'ENDLIST/endlistParts.tid', 'ENDLIST/endlistParts.png'
TITLE = 'Ngón tay lạnh lẽo & Lời của ác quỷ'
SIZE, INK_X, INK_R, BASELINE = 70, 4, 781, 744
ROW_Y0, ROW_Y1 = 670, 777            # empty rows above and below this atlas row, inclusive
SPRITE_X0, CLEAR_X1 = 782, 1320      # the right-column sprite comes back from the original from here


def fit(text):
    size, track = SIZE, 0.0
    while True:
        im, top, bottom = af.render(text, size, track)
        if im.width <= INK_R - INK_X + 1:
            assert ROW_Y0 < BASELINE + top and BASELINE + bottom < ROW_Y1, (top, bottom)
            return im, top, size, track
        if track > af.MIN_TRACK:
            track -= 0.5
        else:
            size -= 0.5


def redraw(cur, orig):
    out = cur.copy()
    px, op = out.load(), orig.load()
    for y in range(ROW_Y0, ROW_Y1 + 1):
        for x in range(0, CLEAR_X1):
            px[x, y] = op[x, y] if x >= SPRITE_X0 else (255, 255, 255, 0)
    im, top, size, track = fit(unicodedata.normalize('NFC', TITLE))
    plate = Image.new('RGBA', im.size, (255, 255, 255, 0))
    plate.putalpha(im)
    out.alpha_composite(plate, (INK_X, BASELINE + top))
    print('  %s  size %.1f track %+.1f  %dx%d  ink x %d..%d y %d..%d' % (
        TITLE, size, track, im.width, im.height, INK_X, INK_X + im.width - 1, BASELINE + top, BASELINE + top + im.height - 1))
    return out


def encode(raw_cur, raw_orig, cur, orig, new):
    """Re-encode changed blocks; a block that now equals the original game's is copied from it verbatim."""
    t, to = TID(raw_cur), TID(raw_orig)
    payload, opay = bytearray(t.body()), to.body()
    c, o, n = cur.load(), orig.load(), new.load()
    bw = t.width // 4
    copied = encoded = 0
    for by in range(t.height // 4):
        for bx in range(bw):
            cells = [(bx * 4 + i, by * 4 + j) for j in range(4) for i in range(4)]
            pix = [n[p] for p in cells]
            if pix == [c[p] for p in cells]:
                continue
            k = (by * bw + bx) * 16
            if pix == [o[p] for p in cells]:
                payload[k:k + 16] = opay[k:k + 16]
                copied += 1
            else:
                payload[k:k + 16] = af.enc_alpha([p[3] for p in pix]) + af.WHITE
                encoded += 1
    out = raw_cur[:t.data_off] + bytes(payload) + raw_cur[t.data_off + t.payload_size:]
    assert len(out) == len(raw_cur)
    print('  blocks copied from the original %d, re-encoded %d' % (copied, encoded))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cpk', default=af.CPK_PATH)
    ap.add_argument('--png-out', default=os.path.join(af.DATA, 'anh-sua'))
    ap.add_argument('--backup', default=os.path.join(af.DATA, 'backup-truoc-doi-co-chu'))
    ap.add_argument('--preview', default=os.path.join(af.DATA, 'preview-co-chu'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--restore', action='store_true')
    a = ap.parse_args()

    off, size = af.locate(a.cpk, [NAME])[NAME]
    bak = os.path.join(a.backup, 'endlistParts.tid')
    bak_png = os.path.join(a.backup, 'endlistParts.png')
    if not os.path.exists(bak):
        with open(a.cpk, 'rb') as f:
            f.seek(off)
            open(bak, 'wb').write(f.read(size))
        if os.path.exists(os.path.join(a.png_out, PNG)):
            shutil.copyfile(os.path.join(a.png_out, PNG), bak_png)
        print('backed up', NAME, '->', bak)
    raw = open(bak, 'rb').read()
    raw_orig = open(os.path.join(a.backup, 'endlistParts.nsp-goc.tid'), 'rb').read()
    assert len(raw) == len(raw_orig) == size

    if a.restore:
        new = raw
        if os.path.exists(bak_png):
            shutil.copyfile(bak_png, os.path.join(a.png_out, PNG))
    else:
        cur = TID(raw).image().convert('RGBA')
        orig = TID(raw_orig).image().convert('RGBA')
        after = redraw(cur, orig)
        new = encode(raw, raw_orig, cur, orig, after)
        decoded = TID(new).image().convert('RGBA')
        os.makedirs(a.preview, exist_ok=True)
        decoded.save(os.path.join(a.preview, 'endlistParts.png'))
        if not a.dry_run:
            decoded.save(os.path.join(a.png_out, PNG))
    if a.dry_run:
        return
    with open(a.cpk, 'r+b') as f:
        f.seek(off)
        f.write(new)
    with open(a.cpk, 'rb') as f:
        f.seek(off)
        assert f.read(size) == new
    print('wrote', NAME, 'into', a.cpk, 'sha1', hashlib.sha1(new).hexdigest()[:12])


if __name__ == '__main__':
    main()
