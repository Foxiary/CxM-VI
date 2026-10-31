"""Give every curly double quote its proper side, in the STORY scripts.

    python3 story/quotes.py <STORY_01.cpk> <STORY_02.cpk> <out dir>

The 2021 text uses one mark for both ends of a quotation: mostly `”` (`”...!”`,
`”#Color[3]Notice#Color[0]”`), in places `“` (`“After Story/... cp.1“`). The
fonts draw the two differently, so on screen both ends were closing (or both
opening) marks. Of 36,489 marks in the text blocks, about 15,700 were on the
wrong side.

Which side a mark is on is read from its neighbours, ignoring `#Color[..]`
style tags: after the start of the line, a space or an opening bracket it opens,
otherwise it closes; after `...` with no quotation open and a letter next
(`Tên của bọn ta là...”Adonis”`) it opens. `#Name[1]` counts as a word.
Where both sides are spaces (`mЁt #Color[0]” ⑰Δ`) it goes by
whether a quotation is already open on that line. A quotation that runs over
several lines simply opens on one and closes on another, which the neighbour
rule handles line by line.

`“` and `”` are both three bytes in UTF-8 and both in CP932, so only those bytes
of data-block payloads change, at the same length, as CLAUDE.md requires for
STCM2L text. Both the text section the game reads and the stale inline copies
are fixed. Files the 2021 patch stored compressed come out stored plain, as
cpk.py repack writes every file it replaces.
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
sys.path.insert(0, HERE)
from cpk import CPK                                             # noqa: E402
from stcm import regions                                        # noqa: E402

OPEN, CLOSE = '“', '”'
TAG = re.compile(r'#\w+\[[^\]]*\]|#n|#\w+')
OPENS_AFTER = ' \t\u3000([{「『‘―—“'
SPACE_AFTER = ' \t\u3000'
CJK = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')


def fix_quotes(text):
    # strip style tags so the neighbours are real characters; #n is a space
    plain, pos = [], []
    i = 0
    while i < len(text):
        m = TAG.match(text, i) if text[i] == '#' else None
        if m:
            if m.group() == '#n':
                plain.append(' ')
                pos.append(None)
            elif m.group().startswith('#Name'):
                plain.append('N')          # the player's name: a word
                pos.append(None)
            i = m.end()
            continue
        plain.append(text[i])
        pos.append(i)
        i += 1
    out = list(text)
    depth = 0
    for k, ch in enumerate(plain):
        if ch not in (OPEN, CLOSE):
            continue
        prev = plain[k - 1] if k else ''
        nxt = plain[k + 1] if k + 1 < len(plain) else ''
        if prev in '―—' and (nxt == '' or nxt in SPACE_AFTER):
            side = CLOSE                   # `X-Day—”`: speech cut off
        elif prev == '' or prev in OPENS_AFTER:
            side = OPEN
            if (prev == '' or prev in SPACE_AFTER) and (nxt == '' or nxt in SPACE_AFTER):
                side = CLOSE if depth else OPEN
        elif CJK.match(prev) and not depth:
            side = OPEN                    # untranslated Japanese: 事件を“X-Day事件”と
        elif prev in '.…' and nxt.isalnum() and not depth:
            side = OPEN                    # `...”Adonis”`: a pause, then a quote
        else:
            side = CLOSE
        depth = depth + 1 if side == OPEN else max(depth - 1, 0)
        out[pos[k]] = side
    return ''.join(out)


def fix_script(raw):
    """Return (new bytes, marks changed)."""
    regs, _odd = regions(raw)
    buf = bytearray(raw)
    n = 0
    for s, e, kind in regs:
        if kind not in ('block', 'tblock') or e - s <= 4:
            continue
        payload = raw[s:e]
        if b'\xe2\x80\x9c' not in payload and b'\xe2\x80\x9d' not in payload:
            continue
        body = payload.split(b'\0')[0]
        try:
            text = body.decode('utf-8')
        except UnicodeDecodeError:
            continue
        new = fix_quotes(text).encode('utf-8')
        assert len(new) == len(body)
        if new != body:
            n += sum(a != b for a, b in zip(new, body))
            buf[s:s + len(body)] = new
    return bytes(buf), n


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    os.makedirs(sys.argv[3], exist_ok=True)
    for path in sys.argv[1:3]:
        cpk = CPK(path)
        repl, total = {}, 0
        for _i, full, row in cpk.files():
            if not full.upper().endswith('.DAT'):
                continue
            raw = cpk.read(row)
            new, n = fix_script(raw)
            if n:
                # only quote bytes moved: 9c <-> 9d after e2 80
                diff = [i for i in range(len(raw)) if raw[i] != new[i]]
                assert all(raw[i - 2:i] == b'\xe2\x80' and {raw[i], new[i]} == {0x9c, 0x9d}
                           for i in diff)
                repl[full] = new
                total += n
        out = os.path.join(sys.argv[3], os.path.basename(path))
        print('%s: %d marks in %d scripts' % (os.path.basename(path), total, len(repl)))
        cpk.repack(out, repl)
        check = CPK(out)
        for _i, full, row in check.files():
            want = repl.get(full)
            if want is None:
                want = cpk.read([r for _j, f, r in cpk.files() if f == full][0])
            assert check.read(row) == want, full
        print('  verified every file of', os.path.basename(out))


if __name__ == '__main__':
    main()
