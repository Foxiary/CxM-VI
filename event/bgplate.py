"""Name plates painted into the profile backgrounds (ADV/BG/881-893).

    python3 event/bgplate.py build      work/bgplate/out/<n>.tid + previews
    python3 event/bgplate.py install    write them into GAME_01 of both mods
    python3 event/bgplate.py restore    put the JP backgrounds back

Eleven ADV/BG pictures show a character on a scene with the same name plate
as their EFFECT plate already drawn into the picture, so event/nameplate.py
never reaches them:

    881 Enomoto 403    882 Sasazuka 404   883 Shiraishi 405  884 Sakuragawa 407
    885 Mochida 408    886 Saeki 409      887 Morioka 410    888 Minegishi 411
    890 Satake 413     891 Mukai 414      893 Hoshino 406

(892 has no plate: its JP and EN pictures are the same.) They are 2048x2048
DXT5 textures with the 1920x1080 picture in the top-left corner, drawn 1:1.

The plate in each picture is the JP EFFECT plate's own pixels, pasted
unscaled: wherever the JP plate texture has alpha (all 0 or 255) the
background matches it to 0.01 levels, at (1160, 544) for plates on the right,
(160, 544) on the left and (1041, 544) for 882. So the Vietnamese plate that
nameplate.py built (work/plate/out/<n>_1.CL3) goes in at the same place over
the same mask, and nothing else in the picture changes. build() checks the
JP plate is really there first, so a picture already patched, or a different
one, is refused rather than painted twice.

Only the 4 KB-aligned blocks under the plate are re-encoded; the rest of
the payload is the JP bytes. Run nameplate.py build first.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 've-es', 'tools'))
sys.path.insert(0, HERE)
from PIL import Image  # noqa: E402
from cpk import CPK  # noqa: E402
from dxt5 import encode_into  # noqa: E402
from tid import TID  # noqa: E402
import nameplate  # noqa: E402

DATA = os.path.join(ROOT, 'work', 'bgplate')
MODS = nameplate.MODS
CPK_NAME = 'GAME_01.cpk'
# background -> (EFFECT plate, x, y of the plate texture's top-left in the picture)
PLATES = {
    881: (403, 1160, 544), 882: (404, 1041, 544), 883: (405, 1160, 544),
    884: (407, 1160, 544), 885: (408, 1160, 544), 886: (409, 160, 544),
    887: (410, 1160, 544), 888: (411, 160, 544), 890: (413, 160, 544),
    891: (414, 160, 544), 893: (406, 160, 544),
}
MATCH = 3.0          # mean |JP background - JP plate| over the mask, levels; found 0.01 (882: 1.8)


def bg_name(n):
    return 'ADV/BG/%d.tid' % n


def pull():
    """The JP backgrounds, from the first mod's GAME_01, into work/bgplate/jp/."""
    d = os.path.join(DATA, 'jp')
    os.makedirs(d, exist_ok=True)
    if all(os.path.exists(os.path.join(d, '%d.tid' % n)) for n in PLATES):
        return
    want = {bg_name(n) for n in PLATES}
    c = CPK(os.path.join(MODS[0], CPK_NAME))
    for _i, f, r in c.files():
        if f in want:
            open(os.path.join(d, os.path.basename(f)), 'wb').write(c.read(r))


def plate_rgba(path):
    return nameplate.tex_of(open(path, 'rb').read()).convert('RGBA')


def build():
    pull()
    out_dir = os.path.join(DATA, 'out')
    os.makedirs(out_dir, exist_ok=True)
    previews = []
    for n, (p, x, y) in sorted(PLATES.items()):
        raw = open(os.path.join(DATA, 'jp', '%d.tid' % n), 'rb').read()
        w, h = struct.unpack_from('<II', raw, 0x44)
        if raw[0x64:0x68] != b'DXT5' or len(raw) != 0x80 + w * h:
            raise SystemExit('%d: not a %dx%d DXT5' % (n, w, h))
        pic = TID(raw).image().convert('RGBA')
        jp = plate_rgba(os.path.join(nameplate.DATA, 'jp1', '%d.CL3' % p))
        vi = plate_rgba(os.path.join(nameplate.DATA, 'out', '%d_1.CL3' % p))
        # DXT5 rounds 255 to 251-254 in places; what must agree is where the plate is
        cover = lambda im: im.getchannel('A').point(lambda a: 255 if a else 0).tobytes()  # noqa: E731
        if cover(jp) != cover(vi):
            raise SystemExit('%d: plate %d covers a different area' % (n, p))
        box = jp.getchannel('A').point(lambda a: 255 if a else 0).getbbox()
        mask = jp.getchannel('A').crop(box).point(lambda a: 255 if a else 0)
        bx, by = x + box[0], y + box[1]
        area = (bx, by, bx + mask.width, by + mask.height)
        # is the JP plate really there?
        here = pic.crop(area).convert('RGB').tobytes()
        want = jp.crop(box).convert('RGB').tobytes()
        m = mask.tobytes()
        on = [i for i in range(len(m)) if m[i]]
        diff = sum(abs(here[3 * i + k] - want[3 * i + k]) for i in on for k in range(3)) / (3 * len(on))
        if diff > MATCH:
            raise SystemExit('%d: JP plate %d not found at (%d, %d), mean diff %.1f' % (n, p, x, y, diff))
        new = pic.copy()
        new.paste(vi.crop(box), (bx, by), mask)
        payload = encode_into(raw[0x80:], new, area)
        blob = raw[:0x80] + payload
        open(os.path.join(out_dir, '%d.tid' % n), 'wb').write(blob)
        back = TID(blob).image().convert('RGB')
        previews.append((n, p, back.crop((0, 0, 1920, 1080)), pic.convert('RGB').crop((0, 0, 1920, 1080))))
        print('  %d: plate %d at (%d, %d), JP match %.2f' % (n, p, x, y, diff))
    W = 960
    S = Image.new('RGB', (2 * W, len(previews) * 540), (40, 40, 40))
    for i, (n, p, vi_im, jp_im) in enumerate(previews):
        S.paste(jp_im.resize((W, 540), Image.LANCZOS), (0, i * 540))
        S.paste(vi_im.resize((W, 540), Image.LANCZOS), (W, i * 540))
    S.save(os.path.join(out_dir, 'sheet.jpg'), quality=88)
    print('  %d backgrounds -> %s' % (len(previews), out_dir))


def install():
    sys.path.insert(0, os.path.join(ROOT, 'voice'))
    import clock_en
    for d in MODS:
        p = os.path.join(d, CPK_NAME)
        for n in sorted(PLATES):
            blob = open(os.path.join(DATA, 'out', '%d.tid' % n), 'rb').read()
            clock_en.NAME = bg_name(n)
            if clock_en.read_file(p, clock_en.NAME) != blob:
                clock_en.swap(p, blob)
                if clock_en.read_file(p, clock_en.NAME) != blob:
                    raise SystemExit('read-back failed: %d in %s' % (n, p))
        print('  ->', p)


def restore():
    sys.path.insert(0, os.path.join(ROOT, 'voice'))
    import clock_en
    for d in MODS:
        p = os.path.join(d, CPK_NAME)
        for n in sorted(PLATES):
            clock_en.NAME = bg_name(n)
            clock_en.swap(p, open(os.path.join(DATA, 'jp', '%d.tid' % n), 'rb').read())
        print('  restored', p)


if __name__ == '__main__':
    {'build': build, 'install': install, 'restore': restore}[sys.argv[1]]()
