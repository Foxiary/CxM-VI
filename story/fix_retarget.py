"""Undo the damage the Latin Extended-B retarget did outside the text.

DO NOT SHIP ITS OUTPUT. Repairing the pointers is not enough: with the text
itself re-encoded, the EVENT CG view still goes black and the Voice Recorder
reads every entry as locked. The same scripts in the 2021 encoding work. All
114 code points the 2021 patch used for Vietnamese (Greek, Cyrillic, circled
digits, curly quotes) are in CP932 and none of the Latin Extended-B
replacements are, so the engine evidently pushes script text through a
Shift-JIS path. The shipped fonts draw the old code points with the same
bitmaps as the new ones, so the 2021-encoded scripts display correctly as
they are. Kept for the record of what the retarget broke.

    python3 fix_retarget.py BEFORE.cpk RETARGETED.cpk OUT.cpk

The retarget swapped every Greek/Cyrillic UTF-8 pair for a Latin Extended-B
one by raw byte replacement over whole .DAT files. Inside text that is the
intended change. Outside it, the same two bytes are often the low half of a
little-endian word: a parameter pointing at a text block at 0x95D0 reads
`d0 95 00 00`, which is Cyrillic 'Е', and came out as `c6 b8` -> 0xB8C6. The
scripts then jump to and read from the wrong places; the EVENT gallery's CG
view going black was the first visible symptom. STORY_01 had 6,490 such bytes
in parameters plus a few in instruction headers, EXPORT_DATA and the file
header; STORY_02 had 8,262.

Every script keeps its size, so this rebuilds each one from BEFORE and copies
in from RETARGETED only the bytes that are text:
  - every data block of the text section that COLLECTION_LINK+4 points at;
  - a code-area data block longer than 4 bytes whose payload is UTF-8 text.
Code-area 4-byte blocks are numbers (40142 and 40144 side by side in 151.DAT)
and stay as BEFORE, as does everything else.

OUT is RETARGETED with the repaired scripts written over their own bytes; the
TOC is untouched. Verified on the way out: OUT differs from BEFORE only inside
the text it took, and from RETARGETED only outside it.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
sys.path.insert(0, HERE)
from cpk import CPK          # noqa: E402
from stcm import regions     # noqa: E402


def is_text(payload):
    s = payload.rstrip(b'\0')
    if not s or b'\0' in s:
        return False
    try:
        s.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


def text_spans(before):
    """[(start, end)] of the bytes the retarget was meant to change."""
    regs, _odd = regions(before)
    spans = []
    for a, b, kind in regs:
        if kind == 'tblock':
            spans.append((a, b))
        elif kind == 'block' and b - a > 4 and is_text(before[a:b]):
            spans.append((a, b))
    return spans


def repair(before, after):
    """(fixed bytes, restored byte count, text byte count)."""
    if len(before) != len(after):
        raise ValueError('size changed %d -> %d' % (len(before), len(after)))
    fixed = bytearray(before)
    taken = 0
    for a, b in text_spans(before):
        fixed[a:b] = after[a:b]
        taken += sum(1 for i in range(a, b) if before[i] != after[i])
    restored = sum(1 for x, y in zip(fixed, after) if x != y)
    return bytes(fixed), restored, taken


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    src_before, src_after, out = sys.argv[1:]
    cb, ca = CPK(src_before), CPK(src_after)
    rb = {f: r for _i, f, r in cb.files()}
    ra = {f: r for _i, f, r in ca.files()}
    if set(rb) != set(ra):
        raise SystemExit('the two CPKs hold different files')

    shutil.copyfile(src_after, out)
    total_restored = total_text = 0
    with open(out, 'r+b') as fh:
        for f in sorted(ra):
            r = ra[f]
            if r['ExtractSize'] != r['FileSize']:
                raise SystemExit('%s is compressed in %s' % (f, src_after))
            before, after = cb.read(rb[f]), ca.read(r)
            fixed, restored, taken = repair(before, after)
            total_restored += restored
            total_text += taken
            if fixed != after:
                fh.seek(ca.base + r['FileOffset'])
                fh.write(fixed)

    # Read back and prove the split.
    co = CPK(out)
    for _i, f, r in co.files():
        got = co.read(r)
        before, after = cb.read(rb[f]), ca.read(ra[f])
        want = bytearray(before)
        for a, b in text_spans(before):
            want[a:b] = after[a:b]
        if got != bytes(want):
            raise SystemExit('%s does not read back as BEFORE plus its text' % f)
    print('%s: %d text bytes kept, %d non-text bytes restored, %d scripts'
          % (out, total_text, total_restored, len(ra)))


if __name__ == '__main__':
    main()
