"""Spell out the two dictionary terms the 2021 patch abbreviated.

    python3 dict_names.py <SYSTEM.cpk> <out dir>

Both sit in dbDictionary_01 (main game) and were shortened to fit the bytes
of the Japanese name, not the screen:

    12  Giết ng quá gi.hạn phòng vệ  ->  Giết người quá giới hạn phòng vệ
    37  Ban p.chống t.phạm cn cao    ->  Ban phòng chống tội phạm công nghệ cao

The text is in the 2021 Greek/Cyrillic encoding like the rest of SYSTEM, so
each new name is built only from words the file already spells: the
description of 37 opens with the full name, 12's description carries
"giới hạn phòng vệ" and 38 "Xúi giục giết người" the word "người".

Writes dbDictionary_01.gbin into <out dir> for cpk.py repack.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 've-es', 'tools'))
import gbnl                                                     # noqa: E402
from cpk import CPK                                             # noqa: E402

FILE = 'dbDictionary_01.gbin'
NAME, DESC = 0, 2        # string cells: name, description


def names(g):
    rec = [g.record(r) for r in range(g.n)]
    nguoi = rec[38][NAME].split()[-1]                   # người
    gioi = rec[12][DESC].replace('#n', ' ').split()     # ... giới hạn ...
    phong = rec[12][NAME].split()[-2]                   # phòng, twice in it
    i = len(gioi) - 1 - gioi[::-1].index(phong)
    full_12 = ' '.join([rec[12][NAME].split()[0], nguoi,
                        rec[12][NAME].split()[2]] + gioi[i - 2:i + 2])
    full_37 = rec[37][DESC].split('#n')[0]
    return {12: full_12, 37: full_37}


def main():
    cpk = CPK(sys.argv[1])
    os.makedirs(sys.argv[2], exist_ok=True)
    files = {full.split('/')[-1]: row for _i, full, row in cpk.files()}
    g = gbnl.GBNL(cpk.read(files[FILE]))
    repl = {}
    for r, new in names(g).items():
        old = g.record(r)[NAME]
        print('rec %d  %s  ->  %s' % (r, old, new))
        repl[old] = new
    out = g.build(repl)
    check = gbnl.GBNL(out)
    for r, new in names(g).items():
        assert check.record(r)[NAME] == new, r
    with open(os.path.join(sys.argv[2], FILE), 'wb') as fh:
        fh.write(out)


if __name__ == '__main__':
    main()
