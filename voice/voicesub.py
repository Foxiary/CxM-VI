"""Show the English voice-recorder subtitles in the JP build.

    python3 voicesub.py exe [--install DIR]     build exefs/main from voicesub.s
    python3 voicesub.py cpk SRC DST             add SUBTITLE/00..24.tid to a GAME_01.cpk

The English build draws VOICERECORDER/SUBTITLE/%02u.tid next to the recorder
while a clip plays; the JP executable has no such code. voicesub.s adds it to
the main game's recorder (draw 0xC5160) - not the -Unlimited- one at 0xC7AB0,
which was hooked first and never runs in the main game - at the end of .text.

The cave first lived in the 1.5 KB of page padding before .rodata, with no
segment moving. It filled up, and JP .text has no dead code to reuse (every
function an FDE lists is referenced), so the build now moves .rodata, .data
and .bss up by SHIFT and grows .text into the gap - nsoshift.py, which
rebases every reference across the boundary and checks each one against
stock. An earlier attempt at that missed the jump tables (`ldrsw; add; br`,
e.g. 0xC8CF8, whose entries are relative to the table in .rodata) and broke
every switch; nsoshift rebases all 440.

The installed exefs/ also holds 35A63D73...ACD.ips (save/savelist_ips.py),
which patches the save list and every letter-spacing
constant on top of this main by build ID. Only the hook words below may differ
from stock, so those instructions stay as the .ips expects; `--install`
replaces main alone and leaves the .ips alone.

The same cave carries marquee.s: the Dictionary word lists cut each name at
the end of its red bar and scroll the selected one when it is longer (hooks
0x663FC, 0x6A1A8, 0x127134; state at MQ), and the detail title is kept clear
of the vertical "Dictionary" label (0x63E2C, 0x67CD0).

The textures are the English ones re-encoded BC7 -> DXT5 (the JP build ships
no BC7) by patch_sub.make_subtitles(); `cpk` reuses its TOC/GTOC insertion.

unlsub.s does the same for -Unlimited-, from textures unlsub.py adds to
GAME_02: the voice recorder (hooks 0xC6888, 0xC652C, 0xC7A3C, 0xC7FEC; state
at US) and the character's line on the Extra screen (0xC162C, 0xC1758,
0xC19F8, 0xC3298, 0xC22A4; state at UR). Its .rodata sections are linked
into the page padding after .rodata (RODATA_END..DATA_VA, moved), and that
segment grows by their size.

clock.s moves the time cells of the chapter-start clock card (EFFECT 310,
texture 現在時刻) the way the English -Unlimited- player does (hook
0x111484).
"""
import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'work', 'voice')    # game files and output, gitignored
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
from exefs import nso_segments  # noqa: E402

STOCK = os.path.join(DATA, 'jp-exefs', 'main')
SOURCE = os.path.join(HERE, 'voicesub.s')
MARQUEE = os.path.join(HERE, 'marquee.s')
UNLSUB = os.path.join(HERE, 'unlsub.s')
CLOCK = os.path.join(HERE, 'clock.s')
OUT = os.path.join(DATA, 'voicesub', 'main')

# Every address below is in the STOCK layout. The build moves .rodata, .data
# and .bss up by SHIFT (nsoshift.py) to give the cave room, and moved() maps
# a stock address to where it ends up.
TEXT_END = 0x2729F0            # stock .text size; the cave starts here
RODATA_VA = 0x273000
RODATA_END = 0x32FCE8          # stock .rodata end; cave data goes here
DATA_VA = 0x330000
SHIFT = 0x1000                 # the cave runs to RODATA_VA + SHIFT
# Only bytes inside the .text size the NSO header declares are executable
# under the emulator: an .ips that wrote a cave past it (0x272FC0) crashed the
# Dictionary screen. That is why this cave grows .text instead of hiding in
# the page padding, and why .rodata has to move for it to grow past 1.5 KB.
BSS_END = 0x157B3D8            # MOD0 bss_end
MODULE_END = 0x157C000
STATE = 0x157B3E0              # 24 bytes of cave state, see voicesub.s
MQ = 0x157B400                 # 28 bytes of marquee state, see marquee.s
US = 0x157B420                 # 32 bytes of -Unlimited- subtitle state, see unlsub.s
UR = 0x157B440                 # 16 bytes of Extra screen subtitle state, see unlsub.s

SYMBOLS = {
    'G': STATE,
    'MQ': MQ,
    'US': US,
    'UR': UR,
    'DRAW_TEXT': 0x39990,      # (text object, x, y, ..., colour, [sp] alpha)
    'GLYPH_FLAT': 0x126F28,    # glyph loop: emit the quad untransformed
    'GLYPH_MATRIX': 0x127138,  #             transform the quad, then emit
    'GLYPH_SKIP': 0x1273A0,    #             next glyph
    'TEXT_BOUNDS': 0x1274E0,   # (text object, &min, &max), origin included
    'DISC_GOT': 0x340960,      # GOT slot of the disc index, as at 0xC596C
    'SNPRINTF': 0x141220,
    'TEX_LOAD': 0x108060,      # (archive, path, 0, 2, 0, 1, 0) -> texture
    'TEX_FREE': 0x107D60,
    'TEX_DRAW': 0xE0580,       # (texture, x, y, 0, alpha)
    'TEX_SUBDRAW': 0xE0B70,    # the draw function's tail call
    'TEX_QUAD': 0xE0940,       # (texture, x, y, z, u, v, w, h, r, [sp] g, b, a)
    'DRAW_UREC': 0xC7AB0,      # -Unlimited- recorder: draw (recorder, alpha)
    'LIST_NAV': 0xC6D50,       #                       list cursor input
    'PLAY_VOICE': 0x14D90,     # (voice id, 1, 0)
    'IS_PLAYING': 0x150B0,     # a voice is still playing
    'PAD_GOT': 0x342428,       # GOT slot of the pad array, as at 0x169740
    'DRAW_XPARTS': 0xC2CC0,    # -Unlimited- Extra screen: last part of its draw
    'MEMCMP': 0x272040,        # PLT stub
    'CK_SEND': 0x106BA0,       # the CWD player's call after a quad is laid out
}

# site -> (stock instruction, cave entry, link). Each stock word is checked
# before it is replaced, so a different build of `main` is refused, not
# corrupted. All four are in the main game's recorder.
HOOKS = {
    0xC4258: (0x39044268, 'vs_play', True),      # strb w8, [x19, #272]
    0xC52F0: (0xF9400A73, 'vs_save', True),      # ldr  x19, [x19, #16]
    # The draw function's tail call: the subtitle goes after it, on top of
    # everything, the way the English build draws it last.
    0xC5408: (0x14006DDA, 'vs_tail', False),     # b    0xE0B70
    0xC55A4: (0xF9408E60, 'vs_release', True),   # ldr  x0, [x19, #280]
    # Dictionary word lists, both discs: the row name's draw, and the text
    # drawer's glyph loop where the quad is still in local units.
    0x663FC: (0x97FF4D65, 'mq_draw', True),      # bl   0x39990
    0x6A1A8: (0x97FF3DFA, 'mq_draw', True),      # bl   0x39990
    0x127134: (0xB4FFEFB4, 'mq_glyph', False),   # cbz  x20, 0x126F28
    # The detail title on both discs.
    0x63E2C: (0x97FF56D9, 'mq_title', True),     # bl   0x39990
    0x67CD0: (0x97FF4730, 'mq_title', True),     # bl   0x39990
    # The -Unlimited- recorder: a clip starts, the list reads its cursor,
    # the screen draws, the screen closes.
    0xC6888: (0x97FD3942, 'us_play', True),      # bl   0x14D90
    0xC652C: (0x94000209, 'us_nav', True),       # bl   0xC6D50
    0xC7A3C: (0x9400001D, 'us_draw', True),      # bl   0xC7AB0
    0xC7FEC: (0xF9400660, 'us_release', True),   # ldr  x0, [x19, #8]
    # The -Unlimited- Extra screen: its three greetings, its draw, its close.
    0xC162C: (0x97FD4DD9, 'ur_play', True),      # bl   0x14D90
    0xC1758: (0x97FD4D8E, 'ur_play', True),      # bl   0x14D90
    0xC19F8: (0x97FD4CE6, 'ur_play', True),      # bl   0x14D90
    0xC3298: (0x97FFFE8A, 'ur_draw', True),      # bl   0xC2CC0
    0xC22A4: (0x940116AF, 'ur_release', True),   # bl   0x107D60
    # The CWD player's sprite loop, once a quad's corners are on the stack:
    # the clock card's AM/PM goes after the minutes (clock.s).
    0x111484: (0x97FFD5C7, 'ck_draw', True),     # bl   0x106BA0
}

def moved(va):
    """Where a stock address lands once everything after .text moves up."""
    return va + SHIFT if va >= RODATA_VA else va


HEADER = 0x100
FLAG_COMPRESSED = 0b111
HASH_OFF = (0xA0, 0xC0, 0xE0)
SEG_HDR = (0x10, 0x20, 0x30)
LLVM = '/opt/homebrew/bin'


def assemble():
    """(cave bytes, rodata bytes, {symbol: address}): the cave linked at
    TEXT_END, its .rodata sections at RODATA_END."""
    tmp = tempfile.mkdtemp()
    elf, raw, ro = (os.path.join(tmp, n) for n in ('c.elf', 'c.bin', 'r.bin'))
    objs = []
    for i, src in enumerate((SOURCE, MARQUEE, UNLSUB, CLOCK)):
        objs.append(os.path.join(tmp, 'c%d.o' % i))
        subprocess.run([os.path.join(LLVM, 'clang'), '-target', 'aarch64-none-elf',
                        '-c', src, '-o', objs[-1]], check=True)
    defs = ['--defsym=%s=%#x' % (k, moved(v)) for k, v in SYMBOLS.items()]
    subprocess.run([os.path.join(LLVM, 'ld.lld'), '-static', '--no-relax',
                    '-e', 'vs_tail', '--section-start=.text=%#x' % TEXT_END,
                    '--section-start=.rodata=%#x' % moved(RODATA_END),
                    *defs, *objs, '-o', elf], check=True)
    for section, out in (('.text', raw), ('.rodata', ro)):
        subprocess.run([os.path.join(LLVM, 'llvm-objcopy'), '-O', 'binary',
                        '--only-section=' + section, elf, out], check=True)
    nm = subprocess.run([os.path.join(LLVM, 'llvm-nm'), elf], check=True,
                        capture_output=True, text=True).stdout
    syms = {}
    for line in nm.splitlines():
        addr, _kind, name = line.split()
        syms[name] = int(addr, 16)
    cave = open(raw, 'rb').read()
    cave_ro = open(ro, 'rb').read() if os.path.exists(ro) else b''
    shutil.rmtree(tmp)
    return cave, cave_ro, syms


def branch(src, dst, link=True):
    off = (dst - src) >> 2
    if not -(1 << 25) <= off < (1 << 25):
        raise ValueError('branch out of range %#x -> %#x' % (src, dst))
    return (0x94000000 if link else 0x14000000) | (off & 0x3FFFFFF)


def build_nso(segs, original):
    head = bytearray(original[:HEADER])
    flags = struct.unpack_from('<I', head, 0x0C)[0]
    struct.pack_into('<I', head, 0x0C, flags & ~FLAG_COMPRESSED)
    body = bytearray()
    for i, blob in enumerate(segs):
        hdr = SEG_HDR[i]
        struct.pack_into('<I', head, hdr, HEADER + len(body))
        struct.pack_into('<I', head, hdr + 8, len(blob))
        struct.pack_into('<I', head, 0x60 + 4 * i, len(blob))
        struct.pack_into('32s', head, HASH_OFF[i], hashlib.sha256(blob).digest())
        body += blob
    return bytes(head) + bytes(body)


def build_exe():
    import nsoshift
    original = open(STOCK, 'rb').read()
    stock = [b for _n, b in nso_segments(original)]
    if len(stock[0]) != TEXT_END:
        raise SystemExit('stock .text is %#x, expected %#x' % (len(stock[0]), TEXT_END))
    for i, name in enumerate(('text', 'rodata', 'data')):
        if original[HASH_OFF[i]:HASH_OFF[i] + 32] != hashlib.sha256(stock[i]).digest():
            raise SystemExit('stock %s does not match its hash' % name)
    if RODATA_VA + len(stock[1]) != RODATA_END:
        raise SystemExit('stock .rodata ends at %#x, expected %#x'
                         % (RODATA_VA + len(stock[1]), RODATA_END))
    text, rodata, data, head, _layout = nsoshift.shift(original, SHIFT)

    cave, cave_ro, syms = assemble()
    if TEXT_END + len(cave) > moved(RODATA_VA):
        raise SystemExit('cave runs into .rodata')
    if RODATA_END + len(cave_ro) > DATA_VA:
        raise SystemExit('cave data runs into .data')
    if not (BSS_END <= STATE and STATE + 24 <= MQ and MQ + 28 <= US
            and US + 32 <= UR and UR + 16 <= MODULE_END):
        raise SystemExit('state outside the slack after bss')

    new = bytearray(text) + cave
    new += b'\x00' * (-len(new) % 4)
    for site, (word, entry, link) in HOOKS.items():
        got = struct.unpack_from('<I', new, site)[0]
        if got != word:
            raise SystemExit('%#x holds %#010x, expected %#010x' % (site, got, word))
        struct.pack_into('<I', new, site, branch(site, syms[entry], link))
    new_ro = rodata + cave_ro

    blob = build_nso((bytes(new), new_ro, data), head + original[HEADER:])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'wb') as fh:
        fh.write(blob)

    # Read the file back the way a loader would.
    after = dict(nso_segments(open(OUT, 'rb').read()))
    assert after['rodata'] == new_ro and after['data'] == data
    restored = bytearray(after['text'][:TEXT_END])
    for site, (word, _entry, _link) in HOOKS.items():
        struct.pack_into('<I', restored, site, word)
    assert restored == text, 'text differs outside the hooks'
    assert after['text'][TEXT_END:TEXT_END + len(cave)] == cave
    for i, name in enumerate(('text', 'rodata', 'data')):
        assert blob[HASH_OFF[i]:HASH_OFF[i] + 32] == hashlib.sha256(after[name]).digest()
    for site, (_word, entry, link) in HOOKS.items():
        assert struct.unpack_from('<I', after['text'], site)[0] == branch(site, syms[entry], link)
    # Against stock: every cross-segment reference decodes to the same place,
    # and the only other .text words that changed are the hooks.
    check = nsoshift.verify(original, blob, SHIFT, TEXT_END)
    if check['other_text_words'] != sorted(HOOKS):
        raise SystemExit('unexpected .text changes: %s'
                         % [hex(x) for x in check['other_text_words']])

    print('moved .rodata/.data/.bss up %#x: %d jump tables, %d relocations, %d FDEs'
          % (SHIFT, check['tables'], check['relas'], check['fdes']))
    print('cave %#x..%#x (%d bytes), %d free before .rodata'
          % (TEXT_END, TEXT_END + len(cave), len(cave),
             moved(RODATA_VA) - TEXT_END - len(cave)))
    print('cave data %#x..%#x (%d bytes), %d free before .data'
          % (moved(RODATA_END), moved(RODATA_END) + len(cave_ro), len(cave_ro),
             DATA_VA - RODATA_END - len(cave_ro)))
    for site, (_word, entry, link) in sorted(HOOKS.items()):
        print('  %#x -> %s %s @ %#x' % (site, 'bl' if link else 'b', entry, syms[entry]))
    print('wrote', OUT, len(blob))
    return OUT


def fdata_rows(toc):
    """The GTOC file tree a stock CPK carries for this TOC, as (Next, Child, SortFlink).

    Node n (1..N) is the file with ID n-1 and Child is its TOC row; SortFlink
    of node k is the node of TOC row k-1, so it walks the files in name
    order. Node 0 has SortFlink N. Every node of the stock GAME_01 and
    GAME_02 matches this exactly. patch_sub.patch_cpk() numbered the new
    tail nodes by row instead, which leaves IDs 1813-1839 on the wrong files.
    """
    n = len(toc)
    row_of_id = {r['ID']: i for i, r in enumerate(toc)}
    rows = [(-1, -1, n)]
    for k in range(1, n + 1):
        rows.append((k + 1 if k < n else 0, row_of_id[k - 1], toc[k - 1]['ID'] + 1))
    return rows


def _tables(path):
    """(header row, TOC rows, GTOC offset, prefix) from the bytes before content."""
    from cpk import UTF
    with open(path, 'rb') as fh:
        head = fh.read(0x800)
        hdr = UTF(bytearray(head), 0x10).rows[0]
        fh.seek(0)
        prefix = bytearray(fh.read(hdr['ContentOffset']))
    toc = UTF(prefix, hdr['TocOffset'] + 0x10).rows
    gat = prefix.find(b'@UTF', hdr['GtocOffset'], hdr['GtocOffset'] + 32)
    return hdr, toc, gat, prefix


def fix_fdata(path):
    """Rewrite the GTOC Fdata rows of `path` in place; their count is unchanged."""
    from cpk import UTF
    _hdr, toc, gat, prefix = _tables(path)
    blob = bytes(UTF(prefix[gat:], 0).rows[0]['Fdata'])
    at = prefix.find(blob, gat)
    if at < 0 or prefix.find(blob, at + 1) >= 0:
        raise SystemExit('cannot place the Fdata blob')
    rows_off, = struct.unpack_from('>I', blob, 8)
    rowlen, nrows = struct.unpack_from('>HI', blob, 26)
    want = fdata_rows(toc)
    if rowlen != 12 or nrows != len(want):
        raise SystemExit('Fdata %d x %d, expected 12 x %d' % (rowlen, nrows, len(want)))
    body = b''.join(struct.pack('>iii', *r) for r in want)
    with open(path, 'r+b') as fh:
        fh.seek(at + 8 + rows_off)
        fh.write(body)
    _hdr, _toc, gat, prefix = _tables(path)
    got = UTF(bytes(UTF(prefix[gat:], 0).rows[0]['Fdata']), 0).rows
    if [(r['Next'], r['Child'], r['SortFlink']) for r in got] != want:
        raise SystemExit('Fdata did not read back')


def build_cpk(src, dst):
    import patch_sub
    from cpk import CPK
    c = CPK(src)
    if any(full.startswith('VOICERECORDER/SUBTITLE/') for _i, full, _r in c.files()):
        raise SystemExit('%s already carries the subtitles' % src)
    patch_sub.JP_CPK = src
    patch_sub.OUT_CPK = dst
    patch_sub.patch_cpk(patch_sub.make_subtitles())
    fix_fdata(dst)


def main():
    global SOURCE, OUT
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('exe')
    e.add_argument('--install', metavar='MOD_DIR',
                   help='copy to MOD_DIR/exefs/main')
    e.add_argument('--source', default=SOURCE,
                   help='cave assembly to link instead of voicesub.s')
    e.add_argument('--out', default=OUT)
    k = sub.add_parser('cpk')
    k.add_argument('src')
    k.add_argument('dst')
    f = sub.add_parser('fixgtoc', help='repair the Fdata tree of a built CPK')
    f.add_argument('cpk')
    a = ap.parse_args()
    if a.cmd == 'fixgtoc':
        fix_fdata(a.cpk)
        print('Fdata rewritten in', a.cpk)
        return
    if a.cmd == 'exe':
        SOURCE, OUT = a.source, a.out
        out = build_exe()
        if a.install:
            dst = os.path.join(a.install, 'exefs', 'main')
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(out, dst)
            print('installed', dst)
    else:
        build_cpk(a.src, a.dst)


if __name__ == '__main__':
    main()
