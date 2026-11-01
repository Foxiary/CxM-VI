"""English case-report typing and fiction disclaimer for a new game.

    python3 event/xday_en.py build     write work/xday/out/
    python3 event/xday_en.py install   put them into GAME_01/GAME_02 of both mods
    python3 event/xday_en.py restore   put the JP files back

Starting chapter 0 of the main game plays prologue.usm (English since
movie/pro_en.py), then "X-Day 事件における経過報告書" is typed out on a white
screen. That is not a movie: it is ADV/EFFECT/100.CL3, a CWD animation with
one 2048x128 texture per keystroke. The English main game (GAME_01.CPK of
010083E00F40E000) types "Report of X-Day Incidents" with its own CWD (CWDL003,
the same version as JP, 22 keystrokes instead of 40) and its own sound bank.
The English 111-117.CL3 ("Report for April, May" ... "January 1st, 20XX")
are the same kind; they play later in the prologue and are swapped as well.

The English files are taken whole. Only their textures change: they are BC7
with format byte 0x94, which the JP engine is not known to read, so each is
re-encoded to DXT5 (same byte count, 16 bytes per 4x4 block) with the JP
header layout - format byte 0x90, +4 = total size, fourcc DXT5, flags word at
0x78 = 01 01 01 00 - as event/clock_en.py build_unl does for 310.CL3.

Before that, the new-game screen shows the fiction disclaimer. It is
ADV/BG/1.tid (a background, 2048x2048), not SYSTEM/FICTION.tid (which holds
the 2021 patch's Vietnamese credits). Both discs have their own: the main
game's in GAME_01 and -Unlimited-'s in GAME_02, both Japanese. Each is
replaced by its English counterpart (EN main GAME_01, EN -Unlimited- GAME_02,
pulled out of the NSP with nsp_cpk_file.py), BC7 -> DXT5 into the JP header.
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 've-es', 'tools'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'voice'))       # patch_sub, used by clock_en.swap
from dxt5 import encode_into  # noqa: E402
from tid import TID  # noqa: E402
import clock_en  # noqa: E402

DATA = os.path.join(ROOT, 'work', 'xday')
EN1_CPK = os.path.expanduser('~/Documents/Game/010083E00F40E000/romfs/GAME_01.CPK')
UNL_NSP = clock_en.UNL_NSP
MODS = clock_en.MODS
VENV_PY = os.path.join(ROOT, 'work', 'album', '.venv', 'bin', 'python')

# (cpk in the mod, path inside, where the English one comes from)
FILES = [('GAME_01.cpk', 'ADV/EFFECT/%d.CL3' % n, 'en1') for n in (100, 111, 112, 113, 114, 115, 116, 117)]
FILES += [('GAME_01.cpk', 'ADV/BG/1.tid', 'en1'),
          ('GAME_02.cpk', 'ADV/BG/1.tid', 'unl')]


def out_name(cpk, name):
    return '%s__%s' % (cpk.split('.')[0], name.replace('/', '__'))


def english(name, src):
    if src == 'en1':
        return clock_en.read_file(EN1_CPK, name)
    d = os.path.join(DATA, 'unl')
    p = os.path.join(d, name.replace('/', '__'))
    if not os.path.exists(p):
        subprocess.check_call([VENV_PY, os.path.join(HERE, 'nsp_cpk_file.py'), UNL_NSP, 'GAME_02.CPK', name, d],
                              stdout=subprocess.DEVNULL)
    return open(p, 'rb').read()


def bc7_image(raw):
    """RGBA of an English BC7 TID (format byte 0x90 or 0x94, payload right after the header)."""
    from PIL import Image
    if raw[:3] != b'TID' or raw[0x64:0x68] != b'BC7 ':
        raise SystemExit('not a BC7 TID: %r %r' % (raw[:4], raw[0x64:0x68]))
    w, h = struct.unpack_from('<II', raw, 0x44)
    if len(raw) != 0x80 + w * h:
        raise SystemExit('BC7 payload: %d bytes for %dx%d' % (len(raw), w, h))
    return Image.frombytes('RGBA', (w, h), bytes(raw[0x80:]), 'bcn', 7)


def to_dxt5(raw, jp_hdr):
    """The same TID as DXT5, laid out as the JP ones are."""
    img = bc7_image(raw).convert('RGBA')
    w, h = img.size
    new = bytearray(raw[:0x80])
    new[3] = jp_hdr[3]                         # 0x90
    new[0x64:0x68] = b'DXT5'
    new[0x78:0x7C] = jp_hdr[0x78:0x7C]         # 01 01 01 00
    new += encode_into(b'\0' * (w // 4 * h // 4 * 16), img, (0, 0, w, h))
    if len(new) != len(raw):
        raise SystemExit('size %d != %d' % (len(new), len(raw)))
    struct.pack_into('<I', new, 4, len(new))
    if TID(bytes(new)).image().size != (w, h):
        raise SystemExit('re-read failed')
    return bytes(new)


def build():
    os.makedirs(os.path.join(DATA, 'out'), exist_ok=True)
    os.makedirs(os.path.join(DATA, 'backup'), exist_ok=True)
    jp_hdr = None
    for cpk, name, src in FILES:
        jp = clock_en.read_file(os.path.join(MODS[0], cpk), name)
        bk = os.path.join(DATA, 'backup', out_name(cpk, name))
        if not os.path.exists(bk):
            open(bk, 'wb').write(jp)
        jp = open(bk, 'rb').read()
        en = bytearray(english(name, src))
        if name.endswith('.tid'):
            new = to_dxt5(en, jp[:0x80])
        else:
            if jp_hdr is None:
                m = clock_en.members(jp)
                o = next(m[k][0] for k in m if k.endswith('.tid'))
                jp_hdr = jp[o:o + 0x80]
            if b'CWDL003' not in clock_en.part(en, '.CWD')[2][:16]:
                raise SystemExit('%s: English CWD is not CWDL003' % name)
            for k, (o, sz) in clock_en.members(en).items():
                if k.endswith('.tid'):
                    en[o:o + sz] = to_dxt5(en[o:o + sz], jp_hdr)
            new = bytes(en)
        open(os.path.join(DATA, 'out', out_name(cpk, name)), 'wb').write(new)
        print('  %s %s: %d bytes (JP %d)' % (cpk, name, len(new), len(jp)))


def install(restore_jp=False):
    for cpk in ('GAME_01.cpk', 'GAME_02.cpk'):
        for d in MODS:
            p = os.path.join(d, cpk)
            for c, name, _src in FILES:
                if c != cpk:
                    continue
                src = os.path.join(DATA, 'backup' if restore_jp else 'out', out_name(cpk, name))
                blob = open(src, 'rb').read()
                clock_en.NAME = name
                if clock_en.read_file(p, name) != blob:
                    clock_en.swap(p, blob)
            print('  ->', p)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'build':
        build()
    elif cmd == 'install':
        install()
    elif cmd == 'restore':
        install(restore_jp=True)
    else:
        raise SystemExit(__doc__)
