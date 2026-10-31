"""Put the missing spaces in the SYSTEM databases.

    python3 dot_space.py <SYSTEM.cpk> <out dir>

The 2021 translation has sentences run together, e.g. the -Unlimited- After
Story panel (dbNewMemoryAfterStory_02): `Tháng 4 năm 20XX.Những ngày...`.
A space goes in wherever a letter or digit, a '.', and a letter follow each
other - which also gives the numbered ADONIS titles their space
(`00.Điều tra Saeki` -> `00. Điều tra Saeki`; the longest grows from 422 to
440 units, under the 528 of `Shiraishi Kageyuki Normal ED`). File names
(`gk402.DAT`, `/op.usm`), `cp.1`, ellipses and a stop before `#n` stay.

The same titles end in a full-width digit stuck to the name (`Saeki１`); it
becomes a space and an ASCII digit (`Saeki 1`), as in `cp.1` / `Common.1`.
Only a Latin letter followed by a full-width digit is touched, and not the
`n` of a `#n` break, so the Japanese strings (`#n９月`, `１２月`) and
`strSystem`'s lone `０`..`９` stay.

The Interlude titles (dbNewMemoryInterlude_02) join place and person with a
full-width `／` (`Kiểm tra phòng／Yanagi`), which draws as a wide slanted bar
next to the one title that has an ASCII `/`. Between a letter and a Latin
letter it becomes `/`; `ＯＮ／ＯＦＦ` in strKeyHelp and the lone `／` in
strSystem stay.

The confirmation dialogs and save details (strSystem, strGame) pad each label
with ideographic spaces and a full-width `：` (`Tựa đề　：%s`), meant to line
up in a monospaced Japanese font; with proportional Vietnamese the colon
floats away from its word. After a Latin / borrowed-Greek-Cyrillic letter the
padding and `：` become `: ` (`Tựa đề: %s`). Japanese text keeps its `：`.

Curly double quotes get their proper side through story/quotes.py, as in the
scripts: the dictionary wrote `“Cặp Đôi Súp Miso“`, both ends opening.

Strings are UTF-8 in the 2021 encoding (borrowed Greek / Cyrillic / circled
digits count as letters), and gbnl rebuilds the pool, so a longer string is
fine. Writes each changed .gbin / .gstr into <out dir> for cpk.py repack.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 've-es', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'story'))
import gbnl                                                     # noqa: E402
from quotes import fix_quotes                                   # noqa: E402
from cpk import CPK                                             # noqa: E402

# a letter (any script) or digit . a letter; not a file extension
RUN_ON = re.compile(r'(?<=[^\W_])\.(?=[^\W\d_])(?!DAT\b|usm\b)')

# a Latin letter, then a full-width digit; not the `#n` line break
STUCK_DIGIT = re.compile(r'(?<=[A-Za-z])(?<!#n)([０-９])')

# a letter (not full-width) / a Latin letter
WIDE_SLASH = re.compile(r'(?<=[^\W\d_])(?<![Ａ-Ｚａ-ｚ])／(?=[A-Za-z])')

# a non-CJK letter, any ideographic / ASCII padding, a full-width colon
WIDE_COLON = re.compile(r'(?<=[A-Za-z\u00C0-\u04FF])[\u3000 ]*：')


def fix(text):
    text = fix_quotes(text)
    text = WIDE_COLON.sub(': ', text)
    text = WIDE_SLASH.sub('/', text)
    text = RUN_ON.sub('. ', text)
    return STUCK_DIGIT.sub(lambda m: ' ' + chr(ord(m.group(1)) - 0xFEE0), text)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    cpk = CPK(sys.argv[1])
    os.makedirs(sys.argv[2], exist_ok=True)
    for _i, full, row in cpk.files():
        if not full.startswith('DATABASE/'):
            continue
        try:
            g = gbnl.GBNL(cpk.read(row))
        except ValueError:
            continue
        repl = {t: fix(t) for t in g.strings().values() if fix(t) != t}
        if not repl:
            continue
        name = full.split('/')[-1]
        for old, new in repl.items():
            print('%s\n    %r\n -> %r' % (name, old, new))
        with open(os.path.join(sys.argv[2], name), 'wb') as fh:
            fh.write(g.build(repl))


if __name__ == '__main__':
    main()
