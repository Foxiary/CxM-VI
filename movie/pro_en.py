"""English route-intro movies on -Unlimited-.

    python3 movie/pro_en.py build     extract both MOVIE_02, write work/movie/MOVIE_02.cpk
    python3 movie/pro_en.py install   copy it into both installed mods

Each route of -Unlimited- opens its first chapter with a movie,
dbEntryMovie_02 rows 7-12 (柳PRO ... アドニスPRO -> /pro01.usm ... /pro06.usm),
in MOVIE_02.cpk. The JP ones carry vertical Japanese text burned into the
picture; the English -Unlimited- (0100E3B00F412000) has the same cuts with the
text in English. Both are VP9 1920x1080 at 29.97 fps with one 48 kHz stereo
track, and each pair has the same total_frames and total_samples, so the
English .usm replaces the JP one as is - no re-encode, no database change.
The English files are about half the size (lower bitrate).

MOVIE_02 is otherwise untouched (op, ed01-06 stay JP). The English CPK is
aligned to 16, the JP one to 2048; cpk.repack keeps the JP alignment.
Inputs come straight out of the two NSPs through album/romfs_extract.py, run
with the venv in work/album/.venv (nsz, ~/.switch/prod.keys).
"""
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 've-es', 'tools'))
from cpk import CPK, UTF  # noqa: E402

DATA = os.path.join(ROOT, 'work', 'movie')
GAME = os.path.expanduser('~/Documents/Game')
JP_NSP = os.path.join(GAME, 'Collar×Malice for Nintendo Switch [01002B400E9DA000][v0][Base].nsp')
EN_NSP = os.path.join(GAME, 'Collar X Malice -Unlimited [0100E3B00F412000] [USA] [v0].nsp')
VENV_PY = os.path.join(ROOT, 'work', 'album', '.venv', 'bin', 'python')
MODS = [os.path.expanduser('~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa/romfs/CONTENTS'),
        os.path.expanduser('~/Documents/Ryujinx/sdcard/atmosphere/contents/01002b400e9da000/romfs/CONTENTS')]
MOVIES = ['pro%02d.usm' % i for i in range(1, 7)]


def extract(nsp, name, out):
    dst = os.path.join(out, os.path.basename(name))
    if not os.path.exists(dst):
        subprocess.check_call([VENV_PY, os.path.join(ROOT, 'album', 'romfs_extract.py'),
                               'extract', nsp, name, out], stdout=subprocess.DEVNULL)
    return dst


def usm_info(data):
    """total_frames of the video stream and total_samples of the audio stream."""
    info, o = {}, 0
    while o < len(data) and len(info) < 2:
        sig = data[o:o + 4]
        size = struct.unpack_from('>I', data, o + 4)[0]
        hoff, pad = data[o + 9], struct.unpack_from('>H', data, o + 10)[0]
        body = data[o + 8 + hoff:o + 8 + size - pad]
        if sig in (b'@SFV', b'@SFA') and body[:4] == b'@UTF':
            row = UTF(body, 0).rows[0]
            for k in ('total_frames', 'total_samples'):
                if k in row:
                    info[k] = row[k]
        o += 8 + size
    return info


def build():
    jp = CPK(extract(JP_NSP, 'CONTENTS/MOVIE_02.cpk', os.path.join(DATA, 'jp')))
    en = CPK(extract(EN_NSP, 'MOVIE_02.CPK', os.path.join(DATA, 'en')))
    en_files = {f: r for _i, f, r in en.files()}
    rep = {}
    for _i, full, r in jp.files():
        if full not in MOVIES:
            continue
        new = en.read(en_files[full])
        a, b = usm_info(jp.read(r)), usm_info(new)
        if a != b:
            raise SystemExit('%s: JP %s, EN %s - not a drop-in' % (full, a, b))
        print('  %s  %s frames, %s samples  %s -> %s bytes' % (
            full, a['total_frames'], a['total_samples'],
            format(r['FileSize'], ','), format(len(new), ',')))
        rep[full] = new
    out = os.path.join(DATA, 'MOVIE_02.cpk')
    jp.repack(out, rep)
    # read back: every file is where the TOC says and the swapped ones are EN
    chk = CPK(out)
    for _i, full, r in chk.files():
        want = rep[full] if full in rep else jp.read(dict((f, x) for _j, f, x in jp.files())[full])
        assert chk.read(r) == want, full
    print('  ok', out)


def install():
    src = os.path.join(DATA, 'MOVIE_02.cpk')
    for d in MODS:
        dst = os.path.join(d, 'MOVIE_02.cpk')
        shutil.copyfile(src, dst)
        print('  ->', dst)


if __name__ == '__main__':
    {'build': build, 'install': install}[sys.argv[1]]()
