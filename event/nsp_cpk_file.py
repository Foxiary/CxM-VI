"""Pull one file out of a CPK that sits inside an NSP's RomFS, without
extracting the whole CPK.

    work/album/.venv/bin/python event/nsp_cpk_file.py GAME.nsp GAME_02.CPK ADV/EFFECT/310.CL3 out_dir

Needs the nsz venv of album/romfs_extract.py. The output is named after the
path with / replaced by __.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'album'))
sys.path.insert(0, os.path.join(ROOT, 've-es', 'tools'))
import romfs_extract  # noqa: E402
from cpk import UTF, crilayla  # noqa: E402


def main():
    nsp, cpk_name, want, out = sys.argv[1:5]
    rom, base = romfs_extract.open_romfs(nsp)
    for name, off, _size in romfs_extract.files(rom, base):
        if name.lower().endswith(cpk_name.lower()):
            break
    else:
        raise SystemExit('%s not in %s' % (cpk_name, nsp))
    rom.seek(off)
    head = bytearray(rom.read(0x800))
    hdr = UTF(head, 0x10).rows[0]
    rom.seek(off + hdr['TocOffset'])
    toc = bytearray(rom.read(hdr['TocSize'] + 0x10))
    cbase = min(hdr['TocOffset'], hdr['ContentOffset'])
    for r in UTF(toc, 0x10).rows:
        full = (r['DirName'] + '/' if r['DirName'] else '') + r['FileName']
        if full == want:
            rom.seek(off + cbase + r['FileOffset'])
            d = rom.read(r['FileSize'])
            if r['ExtractSize'] > r['FileSize'] and d[:8] == b'CRILAYLA':
                d = crilayla(d)
            os.makedirs(out, exist_ok=True)
            p = os.path.join(out, full.replace('/', '__'))
            open(p, 'wb').write(d)
            print(full, len(d), '->', p)
            return
    raise SystemExit('%s not in %s' % (want, cpk_name))


if __name__ == '__main__':
    main()
