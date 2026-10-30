"""Re-break the dictionary description lines that run past their panel.

    python3 dict_rewrap.py <SYSTEM.cpk> <font_Normal.ffu> <out dir>

The description panel clips at about 1295 units of font_Normal per line once
drawer 2 steps advance + spacing / 4 (dictionary detail -12 -> -3). Three
lines of the 2021 translation are longer than that; they overflowed in 2021
too. Each one is split at the last space that keeps it under LIMIT, and the
rest is joined to the following line when the two still fit, so no stray short
line is left behind. Nothing else in the text changes.

Writes dbDictionary_01.gbin / dbDictionary_02.gbin into <out dir> for
cpk.py repack.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 've-es', 'tools'))
import gbnl                                                     # noqa: E402
from cpk import CPK                                             # noqa: E402
from ffu import FFU                                             # noqa: E402

LIMIT = 1250             # units at spacing -3; the panel clips near 1295
SPACING = -3
FILES = ('dbDictionary_01.gbin', 'dbDictionary_02.gbin')
DESC = 2                 # string cell holding the description


def width(font, text):
    return sum(font.glyphs[font.index(ch)]['adv'] + SPACING
               for ch in text if font.index(ch) is not None)


def split(font, line):
    """(head, tail) at the last space keeping head within LIMIT."""
    cut = None
    for i, ch in enumerate(line):
        if ch == ' ' and i and width(font, line[:i]) <= LIMIT:
            cut = i
    if cut is None:
        raise ValueError('no break point in %r' % line)
    return line[:cut], line[cut + 1:]


def rewrap(font, text):
    lines = text.split('#n')
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if width(font, line) <= LIMIT:
            out.append(line)
            i += 1
            continue
        head, tail = split(font, line)
        out.append(head)
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            glue = '' if tail.endswith(' ') or nxt.startswith(' ') else ' '
            if width(font, tail + glue + nxt) <= LIMIT:
                lines[i + 1] = tail + glue + nxt
                i += 1
                continue
        lines[i] = tail          # still too long or nothing to join: go again
    return '#n'.join(out)


def main():
    cpk = CPK(sys.argv[1])
    font = FFU(open(sys.argv[2], 'rb').read())
    os.makedirs(sys.argv[3], exist_ok=True)
    files = {full.split('/')[-1]: row for _i, full, row in cpk.files()}
    for name in FILES:
        raw = cpk.read(files[name])
        g = gbnl.GBNL(raw)
        repl = {}
        for r in range(g.n):
            cells = g.record(r)
            if len(cells) <= DESC:
                continue
            old = cells[DESC]
            new = rewrap(font, old)
            if new != old:
                repl[old] = new
                print('%s rec %d' % (name, r))
                for ln in new.split('#n'):
                    print('    %4d  %s' % (width(font, ln), ln))
        with open(os.path.join(sys.argv[3], name), 'wb') as fh:
            fh.write(g.build(repl))


if __name__ == '__main__':
    main()
