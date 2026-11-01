"""Spell out the two dictionary terms the 2021 patch abbreviated.

    python3 dict_names.py <SYSTEM.cpk> <out dir>

Both sit in dbDictionary_01 (main game) and were shortened to fit the bytes
of the Japanese name, not the screen:

    12  Giết ng quá gi.hạn phòng vệ  ->  Giết người quá giới hạn phòng vệ
    37  Ban p.chống t.phạm cn cao    ->  Ban phòng chống tội phạm công nghệ cao

and one renamed so the title reads the same everywhere:

    27  Bộ trưởng                    ->  Tổng thanh tra

27 is 警視総監, Takaeda's title. -Unlimited-'s dictionary (dbDictionary_02
record 51), the name plate 415 and the STORY lines (story/line_fixes.py) all
call it "Tổng thanh tra"; the main game's entry said "Bộ trưởng". The name
is copied from that -Unlimited- record, already in the 2021 encoding.

The text is in the 2021 Greek/Cyrillic encoding like the rest of SYSTEM, so
each new name is built only from words the file already spells: the
description of 37 opens with the full name, 12's description carries
"giới hạn phòng vệ" and 38 "Xúi giục giết người" the word "người".

Running it again over its own output gives the same file.

Writes dbDictionary_01.gbin into <out dir> for cpk.py repack.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 've-es', 'tools'))
import gbnl                                                     # noqa: E402
from cpk import CPK                                             # noqa: E402

FILE = 'dbDictionary_01.gbin'
TITLE_FROM = ('dbDictionary_02.gbin', 51)   # "Tổng thanh tra", 2021 encoding
NAME, DESC = 0, 2        # string cells: name, description


def names(g, g2):
    rec = [g.record(r) for r in range(g.n)]
    nguoi = rec[38][NAME].split()[-1]                   # người
    gioi = rec[12][DESC].replace('#n', ' ').split()     # ... giới hạn ...
    phong = rec[12][NAME].split()[-2]                   # phòng, twice in it
    i = len(gioi) - 1 - gioi[::-1].index(phong)
    full_12 = ' '.join([rec[12][NAME].split()[0], nguoi,
                        rec[12][NAME].split()[2]] + gioi[i - 2:i + 2])
    full_37 = rec[37][DESC].split('#n')[0]
    return {12: full_12, 37: full_37, 27: g2.record(TITLE_FROM[1])[NAME]}


def main():
    cpk = CPK(sys.argv[1])
    os.makedirs(sys.argv[2], exist_ok=True)
    files = {full.split('/')[-1]: row for _i, full, row in cpk.files()}
    g = gbnl.GBNL(cpk.read(files[FILE]))
    g2 = gbnl.GBNL(cpk.read(files[TITLE_FROM[0]]))
    new_names = names(g, g2)
    repl = {}
    for r, new in new_names.items():
        old = g.record(r)[NAME]
        print('rec %d  %s  ->  %s' % (r, old, new))
        repl[old] = new
    out = g.build(repl)
    check = gbnl.GBNL(out)
    for r in range(g.n):                # replaced by text: nothing else may change
        want = g.record(r)
        if r in new_names:
            want[NAME] = new_names[r]
        assert check.record(r) == want, r
    with open(os.path.join(sys.argv[2], FILE), 'wb') as fh:
        fh.write(out)


if __name__ == '__main__':
    main()
