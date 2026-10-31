"""Single-line repairs to the STORY scripts, run before quotes.py.

    python3 story/line_fixes.py <STORY_01.cpk> <STORY_02.cpk> <out dir>

Each entry replaces one whole line of text, given in readable Vietnamese and
written in the 2021 encoding (voice/visub.py VI_2021). The new text must fit
the line's data block; the rest is zero-filled, so nothing in the file moves.
Every copy of the line in the script is replaced (507.DAT has the line twice:
the text section the game reads and a stale inline block). A line already
replaced is skipped, so the script can run over its own output.

Order of the STORY pipeline: line_fixes.py -> quotes.py -> lead_dash.py.
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

FIXES = {
    'STORY_01.cpk': {
        # Shiraishi route: left in English by the 2021 patch.
        # JP 白石さんは扉の隣の小窓を覗き込む。
        'SCRIPT/507.DAT': [('Shiraishi peered through the window near the door.',
                            'Shiraishi-san ngó qua ô cửa sổ nhỏ cạnh cửa.')],
    },
    'STORY_02.cpk': {
        # everyone at the table at once: one pair of quotes, not two
        'SCRIPT/509.DAT': [('““Mời cả nhà ăn cơm.””', '“Mời cả nhà ăn cơm.”')],
    },
}


def enc(text):
    b = ''.join(VI_2021.get(ch, ch) for ch in text).encode('utf-8')
    b.decode('utf-8').encode('cp932')        # STORY text must stay in CP932
    return b


def fix_script(raw, pairs):
    buf, n = bytearray(raw), 0
    for old, new in pairs:
        o, nb = enc(old), enc(new)
        found = 0
        start = 0
        while True:
            at = buf.find(o + b'\0', start)
            if at < 0:
                break
            _flag, nw, one, ln = struct.unpack_from('<4I', buf, at - 16)
            assert one == 1 and ln == nw * 4 and len(nb) < ln, hex(at)
            buf[at:at + ln] = nb.ljust(ln, b'\0')
            found += 1
            start = at + ln
        if not found:
            assert nb + b'\0' in buf, 'neither old nor new line: %r' % old
        n += found
    return bytes(buf), n


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    os.makedirs(sys.argv[3], exist_ok=True)
    for path in sys.argv[1:3]:
        name = os.path.basename(path)
        cpk = CPK(path)
        rows = {f: r for _i, f, r in cpk.files()}
        repl = {}
        for full, pairs in FIXES[name].items():
            raw = cpk.read(rows[full])
            new, n = fix_script(raw, pairs)
            if n:
                stcm2l.Script(new)
                repl[full] = new
            print('%s %s: %d line(s) replaced' % (name, full, n))
        out = os.path.join(sys.argv[3], name)
        cpk.repack(out, repl)
        check = CPK(out)
        for _i, full, row in check.files():
            assert check.read(row) == repl.get(full, cpk.read(rows[full])), full
        assert check.raw[check.content_off:min(check.base + r['FileOffset'] for _i, _f, r in check.files())] \
            == cpk.raw[cpk.content_off:min(cpk.base + r['FileOffset'] for _i, _f, r in cpk.files())]
        print('  verified every file and the tables before them')


if __name__ == '__main__':
    main()
