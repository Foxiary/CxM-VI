"""English story-intro movies on both discs.

    python3 movie/pro_en.py build     write work/movie/MOVIE_01.cpk and MOVIE_02.cpk
    python3 movie/pro_en.py install   copy them into both installed mods

The main game opens its prologue (chapter 0) with /prologue.usm
(dbEntryMovie_01 row 1) in MOVIE_01.cpk: "X-Day 事件における経過報告" and
the case report typed out in Japanese. The English main game
(010083E00F40E000, its romfs already extracted under ~/Documents/Game) has the
same movie with the text in English: same VP9 stream size and 1350 frames;
its audio is 496 samples (10 ms) shorter, so the sample count may differ by
up to AUDIO_SLACK. Only prologue.usm is replaced in MOVIE_01 (op, ed01-05
stay JP). The rest below is about MOVIE_02.

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
MODS = [os.path.expanduser('~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa/romfs/CONTENTS')]
MOVIES = ['pro%02d.usm' % i for i in range(1, 7)]
EN1_CPK = os.path.join(GAME, '010083E00F40E000', 'romfs', 'MOVIE_01.CPK')
AUDIO_SLACK = 1024             # samples; 21 ms at 48 kHz


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


def swap(jp, en, names, out):
    """Write jp with every file in names replaced by en's copy; check and read back."""
    en_files = {f: r for _i, f, r in en.files()}
    jp_files = {f: r for _i, f, r in jp.files()}
    rep = {}
    for full in names:
        r = jp_files[full]
        new = en.read(en_files[full])
        a, b = usm_info(jp.read(r)), usm_info(new)
        if a['total_frames'] != b['total_frames'] or \
                abs(a['total_samples'] - b['total_samples']) > AUDIO_SLACK:
            raise SystemExit('%s: JP %s, EN %s - not a drop-in' % (full, a, b))
        print('  %s  %s frames, %s/%s samples  %s -> %s bytes' % (
            full, a['total_frames'], a['total_samples'], b['total_samples'],
            format(r['FileSize'], ','), format(len(new), ',')))
        rep[full] = new
    jp.repack(out, rep)
    chk = CPK(out)
    for _i, full, r in chk.files():
        assert chk.read(r) == rep.get(full, jp.read(jp_files[full])), full
    if chk.hdr.get('GtocOffset'):
        g = chk.hdr['GtocOffset']
        assert bytes(chk.raw[g:g + 4]) == b'GTOC', 'GTOC overwritten in ' + out
    print('  ok', out)


def build():
    jp = CPK(extract(JP_NSP, 'CONTENTS/MOVIE_01.cpk', os.path.join(DATA, 'jp1')))
    swap(jp, CPK(EN1_CPK), ['prologue.usm'], os.path.join(DATA, 'MOVIE_01.cpk'))
    jp = CPK(extract(JP_NSP, 'CONTENTS/MOVIE_02.cpk', os.path.join(DATA, 'jp')))
    en = CPK(extract(EN_NSP, 'MOVIE_02.CPK', os.path.join(DATA, 'en')))
    swap(jp, en, MOVIES, os.path.join(DATA, 'MOVIE_02.cpk'))


def install():
    for name in ('MOVIE_01.cpk', 'MOVIE_02.cpk'):
        src = os.path.join(DATA, name)
        for d in MODS:
            dst = os.path.join(d, name)
            shutil.copyfile(src, dst)
            print('  ->', dst)


if __name__ == '__main__':
    {'build': build, 'install': install}[sys.argv[1]]()
