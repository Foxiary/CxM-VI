"""Give the message window its per-speaker colour back, on both discs.

    python3 name_colour.py <SYSTEM.cpk> <out dir> [<STORY_01.cpk> <STORY_02.cpk>]

Writes dbCharaNameInfo_01.gbin and dbCharaNameInfo_02.gbin into <out dir> for
cpk.py repack. With the STORY cpks it also counts how many speaker names in
the scripts find a colour, before and after.

WHY THE 2021 PATCH LOST IT
    The window colour comes from the speaker name. The name instruction's
    handler (JP main 0x3FFD0) calls 0x906E0, which strcmps the name string
    against field 0 of every row of dbCharaNameInfo_01 (dbCharaNameInfo_02 on
    -Unlimited-; the disc global picks, 0x90658) and stores the first match's
    +132 into the window at +552. No match gives 7, the neutral window.

    The table holds each lead three times - full-width space, ASCII space,
    no space - all in Japanese. The 2021 patch writes every speaker on both
    discs in English, family name first ("Yanagi Aiji", "Hoshino #Name[1]"),
    so no line found a colour.

WHERE THE NAME THE GAME READS IS
    Not in the name instruction's own data block. The 2021 scripts moved
    their text into a section after the code, and the instruction's first
    parameter points there; the inline block still holds an older string
    ("Aiji Yanagi" in STORY_01, Japanese in 3000-3004.DAT and in STORY_02)
    that nothing reads. In stock JP the parameter points at the inline
    block. A first version of this script counted the inline strings and
    wrote "Aiji Yanagi" into the table - which matches nothing on screen.
    `speaker_counts` follows the parameter.

THE FIX
    Rows 0-5, the full-width-space spelling, which no script uses, get the
    names the scripts use. The other fields (+128, +132 colour, +136) stay,
    so each lead keeps the colour Japanese gives them. Bare given names,
    side characters and "A & B" stay neutral, as in Japanese.
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 've-es', 'tools'))
from cpk import CPK                                             # noqa: E402

FILES = ['dbCharaNameInfo_01.gbin', 'dbCharaNameInfo_02.gbin']
STRIDE, NAME_LEN, ROWS = 140, 128, 18
# row -> (Japanese it replaces, the speaker string the 2021 scripts use)
NEW = {
    0: ('星野　#Name[1]', 'Hoshino #Name[1]'),
    1: ('柳　愛時', 'Yanagi Aiji'),
    2: ('岡崎　契', 'Okazaki Kei'),
    3: ('榎本　峰雄', 'Enomoto Mineo'),
    4: ('笹塚　尊', 'Sasazuka Takeru'),
    5: ('白石　景之', 'Shiraishi Kageyuki'),
}
# what the first version of this script wrote, so it can be run over its output
OLD_FIX = {0: '#Name[1] Hoshino', 1: 'Aiji Yanagi', 2: 'Kei Okazaki',
           3: 'Mineo Enomoto', 4: 'Takeru Sasazuka', 5: 'Kageyuki Shiraishi'}
# global_call targets of the name instruction (the opcode is an address, so
# it moves with each file's layout): STORY_01, STORY_02
NAME_OPS = {64444, 64460, 64476, 56856, 58188}


def names(raw):
    return [raw[r * STRIDE:r * STRIDE + NAME_LEN].split(b'\0')[0].decode('utf-8')
            for r in range(ROWS)]


def build(raw):
    assert len(raw) >= ROWS * STRIDE
    out = bytearray(raw)
    for r, (old, new) in NEW.items():
        cur = names(raw)[r]
        if cur == new:
            continue
        assert cur in (old, OLD_FIX[r]), 'row %d holds %r, expected %r' % (r, cur, old)
        b = new.encode('utf-8')
        assert len(b) < NAME_LEN
        out[r * STRIDE:r * STRIDE + NAME_LEN] = b.ljust(NAME_LEN, b'\0')
    # nothing but the six name fields may change
    for r in range(ROWS):
        lo = r * STRIDE + (NAME_LEN if r in NEW else 0)
        assert out[lo:(r + 1) * STRIDE] == raw[lo:(r + 1) * STRIDE], r
    assert out[ROWS * STRIDE:] == raw[ROWS * STRIDE:]
    return bytes(out)


def speaker_counts(story_cpk):
    """Counter of the speaker strings the game reads, via the parameter."""
    import stcm2l
    c = collections.Counter()
    cpk = CPK(story_cpk)
    for _i, full, row in cpk.files():
        if not full.upper().endswith('.DAT'):
            continue
        raw = cpk.read(row)
        try:
            script = stcm2l.Script(raw)
        except ValueError:
            continue                       # STORY_02 1307.DAT does not walk
        for ins in script.instructions:
            if ins.global_call == 1 and ins.opcode in NAME_OPS and len(ins.blocks) == 1:
                p = ins.params[0][0]
                _flag, _nw, one, ln = struct.unpack_from('<4I', raw, p)
                assert one == 1, (full, hex(p))
                c[raw[p + 16:p + 16 + ln].split(b'\0')[0].decode('utf-8', 'replace')] += 1
    return c


def main():
    if len(sys.argv) not in (3, 5):
        raise SystemExit(__doc__)
    cpk = CPK(sys.argv[1])
    files = {full.split('/')[-1]: row for _i, full, row in cpk.files()}
    os.makedirs(sys.argv[2], exist_ok=True)
    for disc, name in enumerate(FILES):
        raw = cpk.read(files[name])
        out = build(raw)
        with open(os.path.join(sys.argv[2], name), 'wb') as fh:
            fh.write(out)
        print(name)
        if len(sys.argv) == 5:
            c = speaker_counts(sys.argv[3 + disc])
            total = sum(c.values())
            for label, data in (('before', raw), ('after', out)):
                hit = sum(c[n] for n in set(names(data)))
                print('  %-6s %6d of %d speaker names find a colour' % (label, hit, total))
        for r in NEW:
            print('  row %d  colour %d  %s' % (r, struct.unpack_from('<I', out, r * STRIDE + 132)[0],
                                              names(out)[r]))


if __name__ == '__main__':
    main()
