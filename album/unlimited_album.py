"""Vietnamese text for the Collar x Malice -Unlimited- extras, in the letters of the English BGM / Movie titles.

    python3 unlimited_album.py               # render + write into both GAME_02.cpk copies
    python3 unlimited_album.py --dry-run     # previews only (unl/preview/)
    python3 unlimited_album.py --restore     # put GAME_02.cpk back exactly as it was

WHAT IS CHANGED (all in GAME_02.cpk, which the patch never touched)
    VOICERECORDER/voiceRecorderParts.tid   NUMBER column (16 names + numbers) copied from the
                                           English -Unlimited- build; the 13 question titles in
                                           Vietnamese
    BGM/bgm_Parts.tid                      the 13 Japanese track names; 11 are the Collar x Malice
                                           tracks and reuse their Vietnamese names, 2 are new
    MOVIE/movieParts.tid                   the 6 Japanese titles (same as Collar x Malice) and the
                                           CATEGORY labels, copied from the English build
    CHAPTERLIST/chapterListParts1.tid      route tabs - copied block for block from the
    SITUATION/parts.tid                    OK / Tro ve buttons   Vietnamese GAME_01 versions,
                                                                 whose atlases have the same layout

HOW IT IS WRITTEN
    Every file in GAME_02.cpk is CRILAYLA-compressed and there is no compressor here, so the new
    textures are stored uncompressed and cannot go back in place. They are appended where the
    ETOC table was, the ETOC is moved after them, and only numeric cells are patched: FileOffset /
    FileSize / ExtractSize of the five TOC rows and EtocOffset / ContentSize in the header. No
    other byte of the 3.7 GB file moves. The first run saves the header block and the old tail
    (unl/backup/); every run restores them first, so re-running is idempotent and --restore gives
    back the original file bit for bit (checked against its saved SHA-1).
"""
import argparse, hashlib, json, os, unicodedata
from PIL import Image

import album_en_letters as ae
import en_glyphs as eg
from cpk import UTF, crilayla
from tid import TID

DATA = ae.DATA
UNL = os.path.join(DATA, 'unl')
ORIG = os.path.join(UNL, 'orig')              # decompressed originals, saved on first contact
BACKUP = os.path.join(UNL, 'backup')
PREVIEW = os.path.join(UNL, 'preview')
PNG_OUT = os.path.join(DATA, 'anh-sua', 'UNLIMITED')
CPKS = [os.path.expanduser('~/Documents/Ryujinx/sdcard/atmosphere/contents/01002b400e9da000/romfs/CONTENTS/GAME_02.cpk'),
        os.path.expanduser('~/Documents/Game/01002B400E9DA000/PatchVietHoa/romfs/CONTENTS/GAME_02.cpk'),
        # Ryujinx also loads this mod folder (games/01002b400e9da000/mods.json), so it must match
        os.path.expanduser('~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa/romfs/CONTENTS/GAME_02.cpk')]

VR, BGM, MOV, CHAP, SIT = ('VOICERECORDER/voiceRecorderParts.tid', 'BGM/bgm_Parts.tid', 'MOVIE/movieParts.tid',
                           'CHAPTERLIST/chapterListParts1.tid', 'SITUATION/parts.tid')
NAMES = [VR, BGM, MOV, CHAP, SIT]

# ---------------------------------------------------------------- text

# Voice Recorder: rows of 64 px from y 128. The NUMBER column (name x 0..150 + number sprite
# x 150..226) is taken whole from the English -Unlimited- build (0100E3B00F412000), whose atlas
# has the same rows: "Aiji 01" ... "Isshiki", all names at one size (cap ~28 px). It was pulled
# out of the NSP with `.venv/bin/python romfs_extract.py` (see unl/en/); the English names run
# up to x 152 (Sakuragawa, Minegishi), so the copied strip is x 0..228.
EN_VR = os.path.join(UNL, 'en', 'VOICERECORDER__voiceRecorderParts.tid')
VR_NUMBER_RECT = (0, 128, 228, 1152)
# The five heroes are called by family name, as everywhere else in this patch, instead of the
# English build's given names. Same size and place as the English names: cap 28 px, baseline
# row + 43, centred on x 78, inside x 0..150 (the number sprite starts at 150).
VR_SURNAMES = ['Yanagi', 'Okazaki', 'Enomoto', 'Sasazuka', 'Shiraishi']
VR_NAME_CAP, VR_NAME_BASE, VR_NAME_CENTRE, VR_NAME_RECT_W = 28, 43, 78, 150
# Titles: the number sprite ("01".."10", x 150..225) is kept; the text part starts at x 233.
VR_TITLES = ['Điều anh thích ở cô ấy',            # 彼女の好きなところ
             'Điều muốn cô ấy thay đổi',          # 彼女に直してほしいところ
             'Điều muốn làm cùng cô ấy',          # 彼女としたいこと
             'Về gia đình',                       # 家族について
             'Về các mối quan hệ',                # 交友関係について
             'Mùa và nơi yêu thích',              # 好きな季節・場所
             'Điều luôn để tâm',                  # こだわっているもの
             'Điều thầm bận tâm',                 # 密かに気にしていること
             'Điều giữ bí mật',                   # 秘密にしていること
             'Đôi lời gửi cô ấy',                 # 彼女に一言
             'Tự giới thiệu',                     # 自己紹介
             'Thứ yêu thích & không thể nhường',  # 好きなもの・譲れないもの
             'Đôi lời gửi nữ chính']              # 主人公に一言
VR_TEXT_X, VR_TEXT_R = 233, 792                 # Japanese text start / widest Japanese title
VR_SIDE_X = 233                                 # rows 10-12 have no number; start where the others do
# Rows are only 64 px. The number sprites are 44 px tall (baseline row + 54), but a Vietnamese
# line needs 62/57 cap above the baseline for stacked marks (Đ, Ể) and 25/57 below for g/y, so
# cap 38 with the baseline at row + 43 is the largest that keeps every mark and descender in its
# own row (58 px of 64).
VR_CAP, VR_BASE = 38, 43

# BGM: rows of 96 px, baseline row + 69, as in Collar x Malice. Right column ends at x 1470,
# where the scroll-bar sprite starts; both columns keep the width the CxM BGM screen shows (717).
BGM_L = [(1, 'Hai nhịp tim'),                   # ふたつの心音 (new in Unlimited)
         (3, 'Tình yêu vô hình'),               # 形のない恋 (new in Unlimited)
         (10, 'Thị trấn đơn sắc'), (15, 'Ai cũng thế'), (16, 'Hộp kín & Chìa khóa'),
         (17, 'Hồi ức buồn'), (18, 'Hồi ức yêu thương'),
         (19, 'Bi thủy tinh ngân vang'), (20, 'Bi thủy tinh rung rinh')]
BGM_R = [(0, 'Điên dại dưới ánh trăng'), (5, 'Thí nghiệm tư duy'), (6, 'Thí nghiệm giả tưởng'), (7, 'Vết đạn')]
BGM_W = 717

CHAP_RECT = (0, 64, 672, 192)                   # the six route tabs
SIT_RECT = (560, 1340, 1000, 1472)              # OK / B Tro ve


# ---------------------------------------------------------------- CPK I/O

def read_toc(path):
    with open(path, 'rb') as f:
        h = UTF(f.read(1 << 20), 0x10).rows[0]
        head = bytearray(open(path, 'rb').read(h['ContentOffset']))
    hu = UTF(head, 0x10)
    toc = UTF(head, hu.rows[0]['TocOffset'] + 0x10)
    rows = {}
    for i, r in enumerate(toc.rows):
        rows[(r['DirName'] + '/' if r['DirName'] else '') + r['FileName']] = (i, r)
    return head, hu, toc, rows


def read_file(path, name):
    head, hu, toc, rows = read_toc(path)
    h = hu.rows[0]
    base = min(h['TocOffset'], h['ContentOffset'])
    _i, r = rows[name]
    with open(path, 'rb') as f:
        f.seek(base + r['FileOffset'])
        d = f.read(r['FileSize'])
    return crilayla(d) if r['ExtractSize'] > r['FileSize'] else d


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 24), b''):
            h.update(chunk)
    return h.hexdigest()


def backup_paths(path):
    tag = 'ryujinx-mods' if '/Ryujinx/mods/' in path else 'ryujinx' if '/Ryujinx/' in path else 'mod'
    return {k: os.path.join(BACKUP, '%s.%s' % (tag, k)) for k in ('head', 'tail', 'json')}


def save_backup(path):
    b = backup_paths(path)
    if os.path.exists(b['json']):
        return
    os.makedirs(BACKUP, exist_ok=True)
    head, hu, toc, rows = read_toc(path)
    h = hu.rows[0]
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        f.seek(h['EtocOffset'])
        tail = f.read()
    open(b['head'], 'wb').write(head)
    open(b['tail'], 'wb').write(tail)
    print('  hashing', path, '(first run only) ...')
    json.dump({'size': size, 'etoc': h['EtocOffset'], 'sha1': sha1_file(path)}, open(b['json'], 'w'))
    print('  saved header block and tail of', path)


def matches_backup(path):
    """True if path is still the file the backup was taken from (plus only this script's appends).

    Anything else - another tool rebuilding GAME_02.cpk, adding files - moves the TOC, and
    writing the saved header/tail back over such a file would destroy it.
    """
    b = backup_paths(path)
    if not os.path.exists(b['json']):
        return False
    orig = open(b['head'], 'rb').read()
    ho = UTF(orig, 0x10).rows[0]
    to = UTF(orig, ho['TocOffset'] + 0x10)
    head, hu, toc, rows = read_toc(path)
    if len(toc.rows) != len(to.rows):
        return False
    for ro, rn in zip(to.rows, toc.rows):
        n = (ro['DirName'] + '/' if ro['DirName'] else '') + ro['FileName']
        if n in NAMES:
            continue
        if (ro['FileOffset'], ro['FileSize'], ro['ExtractSize']) != (rn['FileOffset'], rn['FileSize'], rn['ExtractSize']):
            return False
    return True


def restore(path, verify=False):
    b = backup_paths(path)
    meta = json.load(open(b['json']))
    if not matches_backup(path):
        raise SystemExit('%s has been rebuilt since the backup was taken (its TOC no longer matches);\n'
                         'refusing to write the old header over it.' % path)
    with open(path, 'r+b') as f:
        f.seek(0)
        f.write(open(b['head'], 'rb').read())
        f.truncate(meta['etoc'])
        f.seek(meta['etoc'])
        f.write(open(b['tail'], 'rb').read())
    assert os.path.getsize(path) == meta['size']
    if verify:
        assert sha1_file(path) == meta['sha1'], 'restore did not reproduce the original'
        print('  restored', path, 'bit for bit (sha1 %s)' % meta['sha1'][:12])


def append_replace(path, repl):
    """Write repl {name: bytes} uncompressed after the content, move the ETOC behind them."""
    head, hu, toc, rows = read_toc(path)
    h = hu.rows[0]
    base = min(h['TocOffset'], h['ContentOffset'])
    align = h['Align'] or 2048
    etoc_off, etoc_size = h['EtocOffset'], h['EtocSize']
    with open(path, 'rb') as f:
        f.seek(etoc_off)
        etoc = f.read(etoc_size)
    assert etoc[:4] == b'ETOC'
    # If our own files already sit at the end (an earlier run on a file another tool rebuilt),
    # write over them instead of appending again, so re-runs do not grow the file.
    ends = sorted((base + r['FileOffset'], base + r['FileOffset'] + r['FileSize'], n) for n, (i, r) in rows.items())
    others_end = max(e for o, e, n in ends if n not in repl)
    ours = [o for o, e, n in ends if n in repl]
    pos = etoc_off
    if ours and min(ours) >= others_end:
        pos = others_end                 # reclaim our old copies and any gap they left
    with open(path, 'r+b') as f:
        for name, data in repl.items():
            i, r = rows[name]
            pos += (-pos) % align
            f.seek(pos)
            f.write(data)
            for col, v in (('FileOffset', pos - base), ('FileSize', len(data)), ('ExtractSize', len(data))):
                assert toc.patch(head, i, col, v), col
            pos += len(data)
        content_end = pos
        pos += (-pos) % align
        f.seek(pos)
        f.write(etoc)
        f.truncate(pos + etoc_size)
        assert hu.patch(head, 0, 'EtocOffset', pos)
        need = content_end - h['ContentOffset']
        if need > h['ContentSize']:
            assert hu.patch(head, 0, 'ContentSize', need)
        f.seek(0)
        f.write(head)
    # read every replaced file back through a fresh parse
    for name, data in repl.items():
        assert read_file(path, name) == data, name
    print('  appended %d files (%s bytes) to %s, ETOC now at %d'
          % (len(repl), format(sum(map(len, repl.values())), ','), path, pos))


# ---------------------------------------------------------------- drawing

def original(name):
    p = os.path.join(ORIG, name.replace('/', '__'))
    if not os.path.exists(p):
        os.makedirs(ORIG, exist_ok=True)
        open(p, 'wb').write(read_file(CPKS[0], name))
    return open(p, 'rb').read()


def clear(img, rect):
    px = img.load()
    for y in range(rect[1], rect[3]):
        for x in range(rect[0], rect[2]):
            px[x, y] = (255, 255, 255, 0)


def place(img, setter, text, ink_x, ink_r, baseline, top, bottom, k, centre=None, shrink=True):
    """Set text at scale k of the BGM face (cap 57). Returns ink x range."""
    text = unicodedata.normalize('NFC', text)
    if shrink:
        mask, ox, base, track, scale = setter.fit(text, (ink_r - ink_x + 1) / k, top / k, bottom / k)
    else:
        mask, ox, base = setter.line(text, 0.0)
        scale = 1.0
    if k != 1.0:
        mask = mask.resize((max(1, round(mask.width * k)), max(1, round(mask.height * k))), Image.LANCZOS)
        ox, base = round(ox * k), round(base * k)
    bb = mask.point(lambda v: 255 if v > 8 else 0).getbbox()
    if centre is not None:
        left = round(centre - (bb[2] - bb[0]) / 2) - bb[0]
    else:
        left = ink_x - ox
        while left + bb[2] - 1 > ink_r and mask.width > 1:          # rounding guard
            mask = mask.resize((mask.width - 1, mask.height), Image.LANCZOS)
            bb = mask.point(lambda v: 255 if v > 8 else 0).getbbox()
    plate = Image.new('RGBA', mask.size, (255, 255, 255, 0))
    plate.putalpha(mask)
    img.alpha_composite(plate, (left, baseline - base))
    return left + bb[0], left + bb[2] - 1, scale


def copy_blocks(raw_dst, raw_src, rect):
    """Copy the DXT5 blocks of rect verbatim from one texture to another of the same layout."""
    td, ts = TID(raw_dst), TID(raw_src)
    assert (td.width, td.height, td.fourcc) == (ts.width, ts.height, ts.fourcc) == (td.width, td.height, b'DXT5')
    assert all(v % 4 == 0 for v in rect)
    out = bytearray(raw_dst)
    bw = td.width // 4
    for by in range(rect[1] // 4, rect[3] // 4):
        for bx in range(rect[0] // 4, rect[2] // 4):
            o = (by * bw + bx) * 16
            out[td.data_off + o:td.data_off + o + 16] = raw_src[ts.data_off + o:ts.data_off + o + 16]
    return bytes(out)


def build():
    en = eg.read_en([v[0] for v in ae.TEXTURES.values()])
    libs, used = {}, {}
    for k in ae.TEXTURES:
        libs[k], used[k] = eg.build(k, en)
    setter = ae.Setter('bgm', libs, used['bgm'])
    cap57 = ae.cap_height(libs['bgm'])
    out = {}

    # Voice Recorder
    raw = original(VR)
    base_img = TID(raw).image().convert('RGBA')
    img = base_img.copy()
    k_title = VR_CAP / cap57
    if not os.path.exists(EN_VR):
        raise SystemExit('missing %s - extract it from the English -Unlimited- NSP first' % EN_VR)
    eng_vr = TID(open(EN_VR, 'rb').read()).image().convert('RGBA')
    for r in range(13):
        clear(img, (226, 128 + 64 * r, 1024, 192 + 64 * r))
    img.paste(eng_vr.crop(VR_NUMBER_RECT), VR_NUMBER_RECT[:2])
    print('Voice Recorder NUMBER column copied from the English build:', VR_NUMBER_RECT)
    k_name = VR_NAME_CAP / cap57
    for r, n in enumerate(VR_SURNAMES):
        y0 = 128 + 64 * r
        clear(img, (0, y0, VR_NAME_RECT_W, y0 + 64))
        a, b, _ = place(img, setter, n, 0, VR_NAME_RECT_W - 1, y0 + VR_NAME_BASE, VR_NAME_BASE - 1,
                        63 - VR_NAME_BASE, k_name, centre=VR_NAME_CENTRE, shrink=False)
        assert 2 <= a and b <= VR_NAME_RECT_W - 2, (n, a, b)
        print('  VR name %-10s ink x %d..%d' % (n, a, b))
    for r, t in enumerate(VR_TITLES):
        y0 = 128 + 64 * r
        x0 = VR_TEXT_X if r < 10 else VR_SIDE_X
        a, b, s = place(img, setter, t, x0, VR_TEXT_R, y0 + VR_BASE, VR_BASE, 64 - VR_BASE, k_title)
        print('  VR %-34s ink x %d..%d  scale %.3f' % (t, a, b, s))
    out[VR] = (raw, base_img, img)

    # BGM
    raw = original(BGM)
    base_img = TID(raw).image().convert('RGBA')
    img = base_img.copy()
    for r, t in BGM_L:
        clear(img, (0, 96 * r, 740, 96 * r + 96))
    for r, t in BGM_R:
        clear(img, (740, 96 * r, 1470, 96 * r + 96))
    for col, rows, x0, x1 in (('L', BGM_L, 12, 12 + BGM_W), ('R', BGM_R, 749, 749 + BGM_W)):
        for r, t in rows:
            a, b, s = place(img, setter, t, x0, x1, 96 * r + 69, 67, 25, 1.0)
            print('  BGM %s %-30s ink x %d..%d  scale %.3f' % (col, t, a, b, s))
    out[BGM] = (raw, base_img, img)

    # Movie: titles as in Collar x Malice, categories from the English build
    raw = original(MOV)
    base_img = TID(raw).image().convert('RGBA')
    img = base_img.copy()
    msetter = ae.Setter('movie', libs, used['movie'])
    slots = ae.slots('movie')
    for ink_x, ink_r, cx0, cx1, y0, baseline, text in slots:
        clear(img, (cx0, y0, cx1, y0 + 96))
    for ink_x, ink_r, cx0, cx1, y0, baseline, text in slots:
        a, b, s = place(img, msetter, text, ink_x, ink_r, baseline, baseline - y0 - 2, y0 + 94 - baseline, 1.0)
        print('  MOVIE %-28s ink x %d..%d  scale %.3f' % (text, a, b, s))
    eng = TID(en[MOV]).image().convert('RGBA')
    for rect in ae.CATEGORY_RECTS:
        img.paste(eng.crop(rect), rect[:2])
    out[MOV] = (raw, base_img, img)

    final = {}
    for name, (raw, base_img, img) in out.items():
        new, changed = ae.encode(raw, base_img, img)
        print('  %s: %d DXT5 blocks re-encoded' % (name, changed))
        final[name] = new

    # Chapter tabs and Situation buttons: verbatim blocks from the Vietnamese GAME_01
    for name, rect in ((CHAP, CHAP_RECT), (SIT, SIT_RECT)):
        final[name] = copy_blocks(original(name), read_file(ae.CPKS[0], name), rect)
        print('  %s: blocks of %s copied from GAME_01' % (name, rect))
    return final, en


def flat(im, bg=(28, 28, 44, 255)):
    out = Image.new('RGBA', im.size, bg)
    out.alpha_composite(im)
    return out.convert('RGB')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--restore', action='store_true')
    a = ap.parse_args()

    if a.restore:
        for p in CPKS:
            restore(p, verify=True)
        return

    for n in NAMES:
        original(n)                      # make sure the pristine textures are saved first
    final, en = build()
    os.makedirs(PREVIEW, exist_ok=True)
    for name, data in final.items():
        before = TID(original(name)).image().convert('RGBA')
        after = TID(data).image().convert('RGBA')
        stem = name.replace('/', '__')[:-4]
        after.save(os.path.join(PREVIEW, stem + '.png'))
        b, c = flat(before), flat(after)
        cmp_ = Image.new('RGB', (b.width * 2 + 16, b.height), (200, 30, 30))
        cmp_.paste(b, (0, 0))
        cmp_.paste(c, (b.width + 16, 0))
        cmp_.save(os.path.join(PREVIEW, 'truoc-sau_' + stem + '.png'))
    if a.dry_run:
        return

    for p in CPKS:
        save_backup(p)
        if matches_backup(p):
            restore(p)                   # start from the original file: re-runs do not pile up
        else:
            print('  %s was rebuilt by another tool; appending to it as it is' % p)
        append_replace(p, final)
    os.makedirs(PNG_OUT, exist_ok=True)
    for name, data in final.items():
        TID(read_file(CPKS[0], name)).image().convert('RGBA').save(
            os.path.join(PNG_OUT, name.replace('/', '__')[:-4] + '.png'))
    for name in NAMES:
        print('  %s sha1 %s' % (name, hashlib.sha1(final[name]).hexdigest()[:12]))


if __name__ == '__main__':
    main()
