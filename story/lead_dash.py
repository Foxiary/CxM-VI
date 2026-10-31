"""Drop the dash that opens a message box, in the STORY scripts.

    python3 story/lead_dash.py <STORY_01.cpk> <STORY_02.cpk> <out dir>

The Japanese text opens many lines with `――`, a pause or a scene beat, and the
2021 translation kept it as `-`, `--`, `—` or `――` in front of the first word
of a box (`-Tôi có thể thấu hiểu nỗi hoài nghi đó.`, `——Vài ngày sau.`,
`“—Hả!?!? Em...”`). In Vietnamese it reads as a stray mark, so it goes.

Only the first line of a box: a text instruction (one parameter pointing at a
text block, not the speaker name) whose previous instruction is not one. Lines
further down a box keep their dash, as do:
  - lines where no letter follows the dash (`——?`, `————、——————！`);
  - `“—san đang chờ đấy.”`, where the dash stands for a name;
  - untranslated Japanese (the 9xx scripts of STORY_02).
A space after the dash goes with it. The text shrinks inside its own data
block and the rest is zero-filled, so nothing in the file moves and the 2021
encoding is untouched. Scripts that do not walk (STORY_02 1307.DAT) are left.
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'save'))
from cpk import CPK                                             # noqa: E402
import stcm2l                                                   # noqa: E402
from name_colour import NAME_OPS                                # noqa: E402

LEAD = re.compile(r'^([“"]?)[-—―]+[ \u3000]*(?=\w)')
JP = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')


def block_text(raw, v):
    """(payload offset, length, text) of the data block at v, or None."""
    if not 0 <= v <= len(raw) - 16:
        return None
    _flag, nw, one, ln = struct.unpack_from('<4I', raw, v)
    if one != 1 or ln != nw * 4 or ln <= 4:
        return None
    body = raw[v + 16:v + 16 + ln].split(b'\0')[0]
    try:
        return v + 16, ln, body.decode('utf-8')
    except UnicodeDecodeError:
        return None


def fix(text):
    if JP.search(text):
        return text
    m = LEAD.match(text)
    if not m or text[m.end():].startswith('san'):
        return text
    return m.group(1) + text[m.end():]


def fix_script(raw):
    """Return (new bytes, [(old, new)])."""
    try:
        ins = stcm2l.Script(raw).instructions
    except ValueError:
        return raw, []

    def text_of(i):
        if i.global_call != 1 or len(i.params) != 1 or i.opcode in NAME_OPS:
            return None
        return block_text(raw, i.params[0][0])

    buf, done, changes = bytearray(raw), set(), []
    for k, i in enumerate(ins):
        t = text_of(i)
        if t is None or (k and text_of(ins[k - 1]) is not None):
            continue
        off, ln, text = t
        new = fix(text)
        if new == text or off in done:
            continue
        b = new.encode('utf-8')
        assert len(b) < ln
        buf[off:off + ln] = b.ljust(ln, b'\0')
        done.add(off)
        changes.append((text, new))
    return bytes(buf), changes


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    os.makedirs(sys.argv[3], exist_ok=True)
    for path in sys.argv[1:3]:
        cpk = CPK(path)
        repl, n = {}, 0
        for _i, full, row in cpk.files():
            if not full.upper().endswith('.DAT'):
                continue
            raw = cpk.read(row)
            new, changes = fix_script(raw)
            if changes:
                stcm2l.Script(new)
                repl[full] = new
                n += len(changes)
        out = os.path.join(sys.argv[3], os.path.basename(path))
        print('%s: %d lines in %d scripts' % (os.path.basename(path), n, len(repl)))
        cpk.repack(out, repl)
        check = CPK(out)
        rows = {f: r for _i, f, r in cpk.files()}
        for _i, full, row in check.files():
            assert check.read(row) == repl.get(full, cpk.read(rows[full])), full
        print('  verified every file of', os.path.basename(out))


if __name__ == '__main__':
    main()
