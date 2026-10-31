"""Build the JP SystemData0000.sav from the two English titles' system saves.

    python3 merge_en_system.py <JP SystemData> <EN main SystemData> \
                               <EN -Unlimited- SystemData> <out>

The JP release keeps both discs in one save (title 01002B400E9DA000); the
English release is two titles, 010083E00F40E000 and 0100E3B00F412000, each with
a SystemData0000.sav of the same size and header. Copying either English file
over the JP one locks the other disc's Extra screens, and the -Unlimited- one
also lands its flags on the wrong indices. Read off the three saves:

    0x000-0x394   options              kept from the JP file
    0x394         u32 flags[1026]      [0..5] shared, then disc 1's system
                                       flags, then disc 2's. JP puts disc 2's
                                       365 flags at 76 (after disc 1's 70);
                                       English -Unlimited- has no disc 1 and
                                       starts them at 6. Index 6 + n is flag n
                                       in the order 4_iflag.DAT declares them:
                                       EN main 65-75 are hiren/clear, as in JP.
    0x139C        72-byte records      "already read" marks: disc 1's records,
                                       one 0x00 byte, disc 2's records, 0x00.
                                       Every file has both lists - EN main's
                                       second and EN -Unlimited-'s first are
                                       empty, a lone 0x00 - so -Unlimited-'s
                                       records start at 0x139D, as disc 2's do
                                       in a JP save after disc 1's.
    0x160C9C      unlock lists         CG, BGM, ending list, voice recorder...
                                       Each disc has its own lists at fixed
                                       offsets and the two never overlap, so
                                       they are OR-ed byte for byte.
"""
import struct
import sys

SIZE = 0x164DBC
FLAGS, NFLAGS = 0x394, 1026
SHARED, DISC1, DISC2_JP, DISC2_EN, NDISC2 = 6, 6, 76, 6, 365
RECS, REC, NREC = 0x139C, 72, 20000
LISTS, LISTS_END = 0x160C9C, 0x1649BC


def read_lists(b):
    """[disc 1 records, disc 2 records]; each list ends at a 0x00 byte."""
    lists, p = [], RECS
    for _disc in range(2):
        out = []
        while b[p]:
            out.append(b[p:p + REC])
            p += REC
        lists.append(out)
        p += 1
    assert not any(b[p:RECS + REC * NREC]), 'data after the second list'
    return lists


def merge(jp, en1, en2):
    for b in (jp, en1, en2):
        assert len(b) == SIZE and b[4:0x30] == jp[4:0x30], 'not a CxM SystemData'
    out = bytearray(jp)

    # flags
    f1 = struct.unpack_from('<%dI' % NFLAGS, en1, FLAGS)
    f2 = struct.unpack_from('<%dI' % NFLAGS, en2, FLAGS)
    assert not any(f1[DISC1 + 70:]), 'EN main has flags past disc 1'
    assert not any(f2[DISC2_EN + NDISC2:]), 'EN -Unlimited- has flags past disc 2'
    flags = [0] * NFLAGS
    for i in range(SHARED):
        flags[i] = max(f1[i], f2[i])
    flags[DISC1:DISC1 + 70] = f1[DISC1:DISC1 + 70]
    flags[DISC2_JP:DISC2_JP + NDISC2] = f2[DISC2_EN:DISC2_EN + NDISC2]
    struct.pack_into('<%dI' % NFLAGS, out, FLAGS, *flags)

    # read marks: disc 1 from EN main, disc 2 from EN -Unlimited-
    d1, e1 = read_lists(en1)
    e2, d2 = read_lists(en2)
    assert not e1 and not e2, 'an English save holds the other disc'
    area = b''.join(d1) + b'\0' + b''.join(d2) + b'\0'
    assert len(area) <= REC * NREC
    out[RECS:RECS + REC * NREC] = area.ljust(REC * NREC, b'\0')
    recs = d1 + d2

    # unlock lists
    for i in range(LISTS, LISTS_END):
        a, b = en1[i], en2[i]
        assert not (a and b and a != b), 'lists overlap at %#x' % i
        out[i] = a or b or jp[i]
    return bytes(out), len(recs), sum(1 for v in flags if v)


def main():
    jp, en1, en2 = (open(p, 'rb').read() for p in sys.argv[1:4])
    out, nrec, nflag = merge(jp, en1, en2)
    with open(sys.argv[4], 'wb') as fh:
        fh.write(out)
    print('%d read marks, %d flags set -> %s' % (nrec, nflag, sys.argv[4]))


if __name__ == '__main__':
    main()
