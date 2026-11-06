"""English case-report typing and fiction disclaimer for a new game.

    python3 event/xday_en.py build     write work/xday/out/ (--all: the backgrounds again too)
    python3 event/xday_en.py install   put them into GAME_01/GAME_02 of the mod
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

The English CWDs sound each keystroke on its own: a sound key per letter,
all on cue 0 of typing_SE.acb. That bank is byte for byte the JP one, where
cue 0 is the whole typing recording (100: key_type01, 7 s) or brush_01
(111-117) - JP plays the long recording once. On the JP engine every
keystroke therefore started another 7-second recording on top of the last
(100) or a brush sound (111-117). fix_typing_se() makes cue 0 one click: it
points cue 0 at the typing recording's synth (111-117: cue 4, key_04_05) and
cuts that recording's HCA to its first frames (CLICK_FRAMES x 1024 samples,
the first keystroke and its tail; the frames after it are made silent), with
NumSamples and the cue length to match. Same bytes count, so nothing in the CL3 moves.

Before that, the new-game screen shows the fiction disclaimer. It is
ADV/BG/1.tid (a background, 2048x2048), not SYSTEM/FICTION.tid (which holds
the 2021 patch's Vietnamese credits). Both discs have their own: the main
game's in GAME_01 and -Unlimited-'s in GAME_02, both Japanese. Each is
replaced by its English counterpart (EN main GAME_01, EN -Unlimited- GAME_02,
pulled out of the NSP with nsp_cpk_file.py), BC7 -> DXT5 into the JP header.

ADV/BG/812-820 are the nine backgrounds of Yanagi's nightmare in chapter 0
(main game only): vertical lines "――人殺し", "お前さえいなければ生きられたのに" ...
on a dark strip. The English ones read "-Murderer.", "If not for you, they'd
still be alive." ...; same 2048x2048 layout, swapped the same way.
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
# Yanagi's nightmare at the start of the main game ("――人殺し" ... -> "-Murderer." ...)
FILES += [('GAME_01.cpk', 'ADV/BG/%d.tid' % n, 'en1') for n in range(812, 821)]
FILES += [('GAME_01.cpk', 'ADV/BG/%d.tid' % n, 'en1')
          for n in (7107, 7114, 7115, 7116, 7117, 827, 828, 829, 830, *range(840, 848))]
# 7115 is in both discs; the JP copies match, so disc 2 gets the English main-game picture.
FILES += [('GAME_02.cpk', 'ADV/BG/7115.tid', 'en1')]


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


CLICK_FRAMES = 4                               # 4 x 1024 samples at 44.1 kHz: one keystroke


def _utf(b, off=0):
    """CRI @UTF table at b[off]: [{column: (value, absolute offset of a per-row cell or None)}].
    Blob cells come back as (absolute start, size)."""
    types = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'Q', 7: 'q', 8: 'f', 9: 'd'}
    if b[off:off + 4] != b'@UTF':
        raise SystemExit('not @UTF at %#x' % off)
    _size, rows, stro, data, _name, ncol, _rowlen, nrow = struct.unpack_from('>IIIIIHHI', b, off + 4)
    rows &= 0xffff
    base = off + 8

    def cstr(o):
        st = base + stro + o
        return b[st:b.index(b'\0', st)].decode('utf-8', 'replace')

    def cell(t, p):
        if t == 0xa:
            return cstr(struct.unpack_from('>I', b, p)[0]), p + 4
        if t == 0xb:
            o, sz = struct.unpack_from('>II', b, p)
            return (base + data + o, sz), p + 8
        f = types[t]
        return struct.unpack_from('>' + f, b, p)[0], p + struct.calcsize(f)

    p, cols = off + 0x20, []
    for _ in range(ncol):
        flags = b[p]
        name = cstr(struct.unpack_from('>I', b, p + 1)[0])
        p += 5
        const = None
        if flags & 0xf0 == 0x30:
            const, p = cell(flags & 0x0f, p)
        cols.append((name, flags & 0x0f, flags & 0xf0, const))
    out, p = [], base + rows
    for _ in range(nrow):
        row = {}
        for name, t, storage, const in cols:
            if storage == 0x50:
                at = p
                v, p = cell(t, p)
                row[name] = (v, at, t)
            else:
                row[name] = (const, None, t)
        out.append(row)
    return out


def _put(buf, cell, value):
    v, at, t = cell
    if at is None:
        raise SystemExit('cell is not per-row')
    struct.pack_into('>' + {2: 'H', 4: 'I'}[t], buf, at, value)


def _crc16(b):
    c = 0
    for x in b:
        c ^= x << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x8005) & 0xffff if c & 0x8000 else (c << 1) & 0xffff
    return c


def fix_typing_se(cl3):
    """cue 0 of the CL3's typing_SE.acb -> one keystroke (see the docstring). In place."""
    m = clock_en.members(cl3)
    if 'typing_SE.acb' not in m:
        raise SystemExit('no typing_SE.acb')
    a0, _asz = m['typing_SE.acb']
    acb = _utf(cl3, a0)[0]
    cues = _utf(cl3, acb['CueTable'][0][0])
    names = {r['CueIndex'][0]: r['CueName'][0] for r in _utf(cl3, acb['CueNameTable'][0][0])}
    synths = _utf(cl3, acb['SynthTable'][0][0])
    waves = _utf(cl3, acb['WaveformTable'][0][0])
    key = next(i for i, n in names.items() if n.startswith('key_'))       # key_type01 / key_04_05
    if cues[key]['ReferenceType'][0] != 2 or cues[0]['ReferenceType'][0] != 2:
        raise SystemExit('cue does not point at a synth')
    # the synth of the key cue -> its waveform (one level: type 1 = waveform)
    syn = cues[key]['ReferenceIndex'][0]
    s0, ssz = synths[syn]['ReferenceItems'][0]
    items = [struct.unpack_from('>HH', cl3, s0 + i) for i in range(0, ssz, 4)]
    while items[0][0] != 1:
        s0, ssz = synths[items[0][1]]['ReferenceItems'][0]
        items = [struct.unpack_from('>HH', cl3, s0 + i) for i in range(0, ssz, 4)]
    wave = items[0][1]
    wid = waves[wave]['Id'][0]
    # the waveform's HCA inside the AWB
    w0, _wsz = acb['AwbFile'][0]
    if cl3[w0:w0 + 4] != b'AFS2':
        raise SystemExit('no AFS2')
    offsz, idsz = cl3[w0 + 5], cl3[w0 + 6]
    cnt, align = struct.unpack_from('<IH', cl3, w0 + 8)
    ids = [struct.unpack_from('<H', cl3, w0 + 0x10 + i * idsz)[0] for i in range(cnt)]
    tab = w0 + 0x10 + cnt * idsz
    k = ids.index(wid)
    h = w0 + (int.from_bytes(cl3[tab + k * offsz:tab + (k + 1) * offsz], 'little') + align - 1) // align * align
    if cl3[h:h + 3] != b'HCA':
        raise SystemExit('waveform %d is not HCA' % wid)
    hsz = struct.unpack_from('>H', cl3, h + 6)[0]
    p = h + 8
    while bytes(x & 0x7f for x in cl3[p:p + 4]) != b'fmt\0':
        p += 1
    rate = int.from_bytes(cl3[p + 5:p + 8], 'big')
    frames, delay, _pad = struct.unpack_from('>IHH', cl3, p + 8)
    q = hsz and h + 8
    while bytes(x & 0x7f for x in cl3[q:q + 4]) != b'comp':
        q += 1
    block = struct.unpack_from('>H', cl3, q + 4)[0]
    # every frame after the click becomes a silent one (sync word, all-zero body, its own CRC),
    # so a decoder that plays to the end of the data and not to the header's frame count
    # stays quiet too
    silent = bytearray(block)
    silent[0:2] = b'\xff\xff'
    struct.pack_into('>H', silent, block - 2, _crc16(silent[:block - 2]))
    for i in range(CLICK_FRAMES, frames):
        cl3[h + hsz + i * block:h + hsz + (i + 1) * block] = silent
    struct.pack_into('>IH', cl3, p + 8, CLICK_FRAMES, delay)
    struct.pack_into('>H', cl3, p + 14, 0)
    struct.pack_into('>H', cl3, h + hsz - 2, _crc16(cl3[h:h + hsz - 2]))
    samples = CLICK_FRAMES * 1024 - delay
    _put(cl3, waves[wave]['NumSamples'], samples)
    _put(cl3, cues[key]['Length'], samples * 1000 // rate)
    _put(cl3, cues[0]['ReferenceIndex'], syn)
    _put(cl3, cues[0]['Length'], samples * 1000 // rate)
    return names[key], samples


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
        out = os.path.join(DATA, 'out', out_name(cpk, name))
        if name.endswith('.tid') and os.path.exists(out) and '--all' not in sys.argv:
            continue                     # the backgrounds take minutes and do not change
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
            cue, samples = fix_typing_se(en)
            print('    typing_SE cue 0 -> %s, cut to %d samples' % (cue, samples))
            new = bytes(en)
        open(out, 'wb').write(new)
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
