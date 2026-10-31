"""English clock card (month / day / time) on both discs.

    python3 event/clock_en.py build     write work/date/out/310.CL3
    python3 event/clock_en.py install   put it in GAME_01 and GAME_02 of both mods

The card that slides in when a chapter starts - "MONTH 04 / DAY 10 /
TIME 01:05PM" in the English release, "04月 10日 PM01:05" in JP - is not the
CHANGE_DATE screen (taskChangeDateDraw, whose code is the same in all four
executables). It is the cutscene effect ADV/EFFECT/310.CL3, "310_現在時刻",
called from the scripts. The CL3 holds a CWD (the animation), its TI (sprite
table) and two textures; the one that differs is 現在時刻.tid, 2048x512: the
digit strips, 月 / 日 and AM/PM.

Aksys kept the CWD and both TIs byte for byte (checked against the English
main game) and only redrew the texture, so the English picture drops into the
JP file as is. The English main game's copy is used for both discs: the JP
build's GAME_01 and GAME_02 copies have the same CWD and TI, and the English
-Unlimited- one is an older CWD format (CWDL002) with a compressed TID. Its
texture is BC7; the JP engine is only known to take DXT5, so it is re-encoded
(event/dxt5.py), header copied from the JP file. The CL3 keeps its size, so
it is swapped in place with voice/unlsub.cmd_swap's append-and-repoint method.
"""
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 've-es', 'tools'))
sys.path.insert(0, HERE)
from cpk import CPK, UTF  # noqa: E402
from dxt5 import encode_into  # noqa: E402
from tid import TID  # noqa: E402

DATA = os.path.join(ROOT, 'work', 'date')
NAME = 'ADV/EFFECT/310.CL3'
TEX = '現在時刻.tid'
EN_CPK = os.path.expanduser('~/Documents/Game/010083E00F40E000/romfs/GAME_01.CPK')
MODS = [os.path.expanduser('~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa/romfs/CONTENTS'),
        os.path.expanduser('~/Documents/Ryujinx/sdcard/atmosphere/contents/01002b400e9da000/romfs/CONTENTS')]
OUT = os.path.join(DATA, 'out', '310.CL3')


def read_file(cpk_path, name):
    c = CPK(cpk_path)
    for _i, full, row in c.files():
        if full == name:
            return c.read(row)
    raise SystemExit('%s not in %s' % (name, cpk_path))


def members(cl3):
    """{file name: (absolute offset, size)} of the CL3 FILE_COLLECTION."""
    i = cl3.find(b'FILE_COLLECTION')
    cnt, _size, off = struct.unpack_from('<III', cl3, i + 0x20)
    out = {}
    for k in range(cnt):
        e = off + k * 0x230
        fn = cl3[e:e + 0x200].split(b'\0')[0].decode('cp932')
        _idx, o, sz = struct.unpack_from('<3I', cl3, e + 0x200)
        out[fn] = (off + o, sz)
    return out


def part(cl3, suffix):
    m = members(cl3)
    keys = [k for k in m if k.endswith(suffix)]
    if len(keys) != 1:
        raise SystemExit('no single %s in CL3: %s' % (suffix, list(m)))
    o, sz = m[keys[0]]
    return o, sz, cl3[o:o + sz]


def build():
    jp = bytearray(read_file(os.path.join(MODS[0], 'GAME_02.cpk'), NAME))
    en = read_file(EN_CPK, NAME)
    # everything but the texture has to match, or the English picture is laid out for another animation
    for suffix in ('.CWD', '現在時刻.TI', '背景デバッグ用.TI', '背景デバッグ用.tid'):
        if part(jp, suffix)[2] != part(en, suffix)[2]:
            raise SystemExit('%s differs between JP and EN 310.CL3' % suffix)
    o, sz, jp_tex = part(jp, TEX)
    en_tex = part(en, TEX)[2]
    img = TID(en_tex).image().convert('RGBA')
    w, h = img.size
    payload = encode_into(b'\0' * (w // 4 * h // 4 * 16), img, (0, 0, w, h))
    new = bytearray(jp_tex[:0x80])
    if bytes(new[0x64:0x68]) != b'DXT5' or struct.unpack_from('<II', new, 0x44) != (w, h):
        raise SystemExit('JP texture is not a %dx%d DXT5' % (w, h))
    new += payload
    if len(new) != sz:
        raise SystemExit('size %d != %d' % (len(new), sz))
    jp[o:o + sz] = new
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'wb').write(jp)
    TID(bytes(new)).image().save(os.path.join(DATA, 'out', '310_tex.png'))
    print('  %s: %s replaced with the English picture (%dx%d BC7 -> DXT5) -> %s' % (NAME, TEX, w, h, OUT))


def swap(cpk_path, blob):
    """Append blob after the content and repoint NAME's TOC row (cpk stays in place, old bytes orphaned)."""
    from patch_sub import align_up
    with open(cpk_path, 'rb') as fh:
        head = bytearray(fh.read(0x800))
        hdr = UTF(head, 0x10).rows[0]
        fh.seek(0)
        prefix = bytearray(fh.read(hdr['ContentOffset']))
        fh.seek(hdr['EtocOffset'])
        etoc = fh.read(hdr['EtocSize'])
    if hdr['EtocOffset'] + hdr['EtocSize'] != os.path.getsize(cpk_path):
        raise SystemExit('ETOC is not the last thing in %s' % cpk_path)
    toc = UTF(prefix, hdr['TocOffset'] + 0x10)
    row = [i for i, r in enumerate(toc.rows) if (r['DirName'] + '/' + r['FileName']) == NAME]
    if len(row) != 1:
        raise SystemExit('%s not found once in %s' % (NAME, cpk_path))
    end = hdr['ContentOffset'] + hdr['ContentSize']
    at = align_up(end, hdr['Align'])
    for cell, value in (('FileSize', len(blob)), ('ExtractSize', len(blob)),
                        ('FileOffset', at - hdr['TocOffset'])):
        if not toc.patch(prefix, row[0], cell, value):
            raise SystemExit('cannot patch ' + cell)
    cur = at + len(blob)
    etoc_off = align_up(cur, hdr['Align'])
    head_utf = UTF(prefix, 0x10)
    for cell, value in (('ContentSize', cur - hdr['ContentOffset']),
                        ('EnabledPackedSize', hdr['EnabledPackedSize'] + len(blob)),
                        ('EnabledDataSize', hdr['EnabledDataSize'] + len(blob)),
                        ('EtocOffset', etoc_off)):
        if not head_utf.patch(prefix, 0, cell, value):
            raise SystemExit('cannot patch ' + cell)
    with open(cpk_path, 'r+b') as fo:
        fo.seek(0)
        fo.write(prefix)
        fo.truncate(hdr['EtocOffset'])
        fo.seek(0, 2)
        fo.write(b'\0' * (at - fo.tell()))
        fo.write(blob)
        fo.write(b'\0' * (etoc_off - fo.tell()))
        fo.write(etoc)


def install():
    sys.path.insert(0, os.path.join(ROOT, 'voice'))
    blob = open(OUT, 'rb').read()
    backup = os.path.join(DATA, 'backup')
    os.makedirs(backup, exist_ok=True)
    for d in MODS:
        for g in ('GAME_01.cpk', 'GAME_02.cpk'):
            p = os.path.join(d, g)
            if read_file(p, NAME) == blob:
                print('  already in', p)
                continue
            keep = os.path.join(backup, '%s.%s.310.CL3' % (os.path.basename(os.path.dirname(os.path.dirname(d))), g))
            if not os.path.exists(keep):
                open(keep, 'wb').write(read_file(p, NAME))
            swap(p, blob)
            if read_file(p, NAME) != blob:
                raise SystemExit('read-back failed for ' + p)
            print('  ->', p)


if __name__ == '__main__':
    {'build': build, 'install': install}[sys.argv[1]]()
