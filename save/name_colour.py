"""Give the message window its per-speaker colour back in the main game.

    python3 name_colour.py <SYSTEM.cpk> <out dir> [<STORY_01.cpk>]

Writes dbCharaNameInfo_01.gbin into <out dir> for cpk.py repack. With
STORY_01.cpk it also counts how many speaker names in the scripts each row
matches, before and after.

WHY THE 2021 PATCH LOST IT
    The window colour comes from the speaker name. The name instruction's
    handler (JP main 0x3FFD0) calls 0x906E0, which strcmps the name string
    against field 0 of every row of dbCharaNameInfo_01 (dbCharaNameInfo_02 on
    -Unlimited-; the disc global picks, 0x90658) and stores the first match's
    +132 into the window at +552. No match gives 7, the neutral window.

    The table holds each lead three times - full-width space, ASCII space,
    no space - all in Japanese. The 2021 patch writes the speakers in English
    ("Aiji Yanagi", "#Name[1] Hoshino"), so in STORY_01 only the 148 names
    3000-3004.DAT still carry in Japanese (`柳 愛時`, the ASCII-space rows)
    match, and every other line falls back to 7.

THE FIX
    Rows 0-5, the full-width-space spelling, which no STORY_01 script uses,
    get the names the scripts use - the same strings the English build keeps
    in its own dbCharaNameInfo_01. The other fields (+128, +132 colour, +136)
    stay, so each lead keeps the colour Japanese gives them. Rows 6-17 stay
    Japanese for 3000-3004.DAT. A bare surname ("Yanagi") or two speakers
    ("... & Mineo Enomoto") stay neutral, as `柳` and `星野 #Name[1]＆榎本 峰雄`
    do in Japanese. -Unlimited-'s scripts and its _02 table are both still
    Japanese and already match, so _02 is left alone.
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 've-es', 'tools'))
from cpk import CPK                                             # noqa: E402

FILE = 'dbCharaNameInfo_01.gbin'
STRIDE, NAME_LEN, ROWS = 140, 128, 18
# row -> (Japanese it replaces, the speaker string the 2021 STORY_01 uses)
NEW = {
    0: ('星野　#Name[1]', '#Name[1] Hoshino'),
    1: ('柳　愛時', 'Aiji Yanagi'),
    2: ('岡崎　契', 'Kei Okazaki'),
    3: ('榎本　峰雄', 'Mineo Enomoto'),
    4: ('笹塚　尊', 'Takeru Sasazuka'),
    5: ('白石　景之', 'Kageyuki Shiraishi'),
}
# global_call targets of the name instruction in the 2021 STORY_01 (the
# opcode is an address, so it moves with each file's layout)
NAME_OPS = {64444, 64460, 64476, 56856}


def names(raw):
    return [raw[r * STRIDE:r * STRIDE + NAME_LEN].split(b'\0')[0].decode('utf-8')
            for r in range(ROWS)]


def build(raw):
    assert names(raw) and len(raw) >= ROWS * STRIDE
    out = bytearray(raw)
    for r, (old, new) in NEW.items():
        cur = names(raw)[r]
        if cur == new:
            continue
        assert cur == old, 'row %d holds %r, expected %r' % (r, cur, old)
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
    import stcm2l
    c = collections.Counter()
    cpk = CPK(story_cpk)
    for _i, full, row in cpk.files():
        if not full.upper().endswith('.DAT'):
            continue
        for ins in stcm2l.Script(cpk.read(row)).instructions:
            if ins.global_call == 1 and ins.opcode in NAME_OPS and len(ins.blocks) == 1:
                c[ins.blocks[0].raw.split(b'\0')[0].decode('utf-8', 'replace')] += 1
    return c


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cpk = CPK(sys.argv[1])
    files = {full.split('/')[-1]: row for _i, full, row in cpk.files()}
    raw = cpk.read(files[FILE])
    out = build(raw)
    os.makedirs(sys.argv[2], exist_ok=True)
    with open(os.path.join(sys.argv[2], FILE), 'wb') as fh:
        fh.write(out)
    if len(sys.argv) > 3:
        c = speaker_counts(sys.argv[3])
        total = sum(c.values())
        for label, data in (('before', raw), ('after', out)):
            hit = sum(c[n] for n in set(names(data)))
            print('%-6s %6d of %d speaker names find a colour' % (label, hit, total))
    for r, n in enumerate(names(out)):
        print('  row %2d  colour %d  %s' % (r, struct.unpack_from('<I', out, r * STRIDE + 132)[0], n))


if __name__ == '__main__':
    main()
