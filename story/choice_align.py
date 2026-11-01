"""Line up the left edges of the main game's chapter 0 choice.

    python3 story/choice_align.py <STORY_01.cpk> <out .cpk>

The choice after the prologue (SCRIPT/99.DAT) offers three routes, each
centred on its black bar. The 2021 text padded the second with five spaces,
`CHƯƠNG.0　Thường     `, so it lines up with `CHƯƠNG.0　Aiji Yanagi`, while
`CHƯƠNG.0　Mở đầu` sits ~45 units further right. Widths at adv - 12 in
font_Normal: 505, 598 (508 + 5 spaces of 18), 593. Five spaces bring the first
to 595.

Its text-section block is 28 bytes and the padded line needs 30, so the line
is not grown in place: that would move every block after it. A new block is
appended at the end of the file, after the last text-section block, and the
choice instruction's first parameter (0x67988, the only reader of the old
block) is pointed at it. Nothing else moves, and the old block stays as it was.
No header field holds the file size in this script (COLLECTION_LINK + 4 is the
start of the text section). Running over its own output changes nothing.

Order of the STORY pipeline: line_fixes.py -> quotes.py -> lead_dash.py ->
choice_align.py.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'voice'))
from cpk import CPK                                             # noqa: E402
import stcm2l                                                   # noqa: E402
from visub import VI_2021                                       # noqa: E402

SCRIPT = 'SCRIPT/99.DAT'
INS = 0x67988                  # choice instruction (global call), param 0 = text
# The 2021 text spells CHƯƠNG with the code point VI_2021 gives Ộ.
OLD = 'CHƯỘNG.0　Mở đầu'
NEW = OLD + '     '


def enc(text):
    b = ''.join(VI_2021.get(ch, ch) for ch in text).encode('utf-8')
    b.decode('utf-8').encode('cp932')        # STORY text must stay in CP932
    return b


def block_text(d, hdr):
    flag, nw, one, ln = struct.unpack_from('<4I', d, hdr)
    assert one == 1 and ln == nw * 4 and hdr + 16 + ln <= len(d), hex(hdr)
    return d[hdr + 16:hdr + 16 + ln].split(b'\0')[0]


def fix_script(raw):
    """(new bytes, changed?)"""
    s = stcm2l.Script(raw)
    ins = next(i for i in s.instructions if i.off == INS)
    assert ins.global_call == 1 and len(ins.params) == 3, 'wrong instruction'
    hdr = ins.params[0][0]
    have = block_text(raw, hdr)
    if have == enc(NEW):
        return raw, False
    assert have == enc(OLD), 'unexpected text %r' % have
    readers = [i.off for i in s.instructions for p in i.params if p[0] == hdr]
    assert readers == [INS], 'block has other readers: %s' % readers

    payload = enc(NEW) + b'\0'
    payload += b'\0' * (-len(payload) % 4)
    buf = bytearray(raw)
    buf += b'\0' * (-len(buf) % 4)
    at = len(buf)
    buf += struct.pack('<4I', 0, len(payload) // 4, 1, len(payload)) + payload
    struct.pack_into('<I', buf, INS + 16, at)     # param 0, first word
    return bytes(buf), True


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    cpk = CPK(sys.argv[1])
    rows = {f: r for _i, f, r in cpk.files()}
    raw = cpk.read(rows[SCRIPT])
    new, changed = fix_script(raw)
    print('%s: %s' % (SCRIPT, 'line padded' if changed else 'already padded'))
    s = stcm2l.Script(new)
    assert s.landed
    ins = next(i for i in s.instructions if i.off == INS)
    assert block_text(new, ins.params[0][0]) == enc(NEW)
    diff = [o for o in range(len(raw)) if raw[o] != new[o]]
    assert all(INS + 16 <= o < INS + 20 for o in diff), diff
    repl = {SCRIPT: new} if changed else {}
    cpk.repack(sys.argv[2], repl)
    check = CPK(sys.argv[2])
    assert check.hdr['GtocOffset'] == cpk.hdr['GtocOffset']
    for _i, full, row in check.files():
        assert check.read(row) == repl.get(full, cpk.read(rows[full])), full
    print('  verified every file')


if __name__ == '__main__':
    main()
