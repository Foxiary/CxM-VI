"""Pull files out of the RomFS of a Switch .nsp (decryption by nsz, keys from ~/.switch/prod.keys).

    .venv/bin/python romfs_extract.py list    GAME.nsp
    .venv/bin/python romfs_extract.py extract GAME.nsp GAME_02.CPK out_dir

nsz decrypts the program NCA's RomFS section but does not parse it, so the RomFS
directory/file tables (header at the start of the last IVFC level) are walked here.
"""
import os, struct, sys
from nsz.Fs import Nsp, Nca, Type
from nsz.nut import Keys


def open_romfs(nsp):
    Keys.load_default()
    c = Nsp.Nsp()
    c.open(nsp, 'rb')
    for f in c:
        if isinstance(f, Nca.Nca) and f.header.contentType == Type.Content.PROGRAM:
            for fs in f.sectionFilesystems:
                if type(fs).__name__ == 'Rom':
                    base = [l for l in fs.ivfc.levels if l.size][-1].offset
                    return fs, base
    raise SystemExit('no RomFS in ' + nsp)


def files(rom, base):
    rom.seek(base)
    (hs, dh_off, dh_sz, dm_off, dm_sz, fh_off, fh_sz, fm_off, fm_sz, data_off) = struct.unpack('<10Q', rom.read(0x50))
    rom.seek(base + dm_off)
    dm = rom.read(dm_sz)
    rom.seek(base + fm_off)
    fm = rom.read(fm_sz)

    def dname(o):
        parent, sib, child, fil, nxt, nlen = struct.unpack_from('<6I', dm, o)
        return parent, dm[o + 0x18:o + 0x18 + nlen].decode('utf-8')

    def dpath(o):
        parts = []
        while o != 0:
            parent, n = dname(o)
            parts.append(n)
            o = parent
        return '/'.join(reversed(parts))

    o = 0
    while o < len(fm):
        parent, sib, off, size, nxt, nlen = struct.unpack_from('<IIQQII', fm, o)
        name = fm[o + 0x20:o + 0x20 + nlen].decode('utf-8')
        d = dpath(parent)
        yield (d + '/' if d else '') + name, base + data_off + off, size
        o += 0x20 + ((nlen + 3) & ~3)


def main():
    cmd, nsp = sys.argv[1], sys.argv[2]
    rom, base = open_romfs(nsp)
    if cmd == 'list':
        for name, off, size in files(rom, base):
            print('%-40s %14s' % (name, format(size, ',')))
    elif cmd == 'extract':
        want, out = sys.argv[3], sys.argv[4]
        os.makedirs(out, exist_ok=True)
        for name, off, size in files(rom, base):
            if name.lower() == want.lower() or os.path.basename(name).lower() == want.lower():
                dst = os.path.join(out, os.path.basename(name))
                rom.seek(off)
                left = size
                with open(dst, 'wb') as fh:
                    while left:
                        chunk = rom.read(min(left, 1 << 24))
                        fh.write(chunk)
                        left -= len(chunk)
                print('->', dst, format(size, ','))
                return
        raise SystemExit('not found: ' + want)


if __name__ == '__main__':
    main()
