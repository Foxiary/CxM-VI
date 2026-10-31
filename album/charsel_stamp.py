"""The "調査完了" stamp on the -Unlimited- character select thumbnails, in Vietnamese.

GAME_02 CHAR_SELECT/char_selthum0..9.tid each hold three versions of one card,
left to right: normal, selected (larger), and investigated. Only the third
carries the red stamp, painted into the art at its own place and angle.

The third card is the first one re-graded (a per-channel affine colour map,
fitted at 1.6-2.5 levels mean error) and shifted by a whole number of pixels
(FRAME_SHIFT), so the paper under the stamp can be rebuilt exactly from the
first card. The stamp's own border is kept; only the inside of the border is
rebuilt and re-lettered, in the stamp's red and at its angle.

Called from unlimited_album.py, which writes the textures into GAME_02.cpk.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'event'))
from dxt5 import encode_into                                    # noqa: E402

TEXT = 'Đã điều tra'
FONT = os.path.expanduser('~/Downloads/MTO CHANEY.TTF')
NAMES = ['CHAR_SELECT/char_selthum%d.tid' % i for i in range(10)]
# third card = first card moved by (dx, dy), measured on every thumbnail
FRAME_SHIFT = {0: (1025, 1), 1: (1024, 0), 2: (896, 0), 3: (960, 0), 4: (704, 0),
               5: (1024, 0), 6: (768, 0), 7: (1024, 0), 8: (1024, 0), 9: (1024, 0)}
# the region where the third card differs from the first: the stamp
STAMP_BOX = {0: (1088, 52, 1330, 139), 1: (1246, 212, 1490, 296), 2: (919, 293, 1163, 356),
             3: (1154, 276, 1408, 364), 4: (744, 275, 1003, 409), 5: (1058, 50, 1302, 135),
             6: (826, 337, 1079, 420), 7: (1224, 49, 1467, 139), 8: (1081, 227, 1324, 304),
             9: (1216, 101, 1459, 177)}
PAD = 14
STAMP_H = 46            # border centre to border centre, measured on the clean ones
BORDER_IN = 16          # half height of the inside of the border
END_IN = 9              # from the end strokes of the border to the inside
SS = 4


def _isred(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r > 110) & (r > g + 50) & (r > b + 50)


def analyse(img, i):
    """Background prediction, stamp colour and geometry for thumbnail i."""
    A = np.asarray(img).astype(float)
    dx, dy = FRAME_SHIFT[i]
    a, b, c, d = STAMP_BOX[i]
    a, b, c, d = a - PAD, b - PAD, c + PAD, d + PAD
    T = A[b:d + 1, a:c + 1]
    S = A[b - dy:d + 1 - dy, a - dx:c + 1 - dx]
    # colour map first card -> third card, fitted over the whole third card minus red
    fx0, fx1 = max(a - 60, dx), min(c + 60, A.shape[1] - 1)
    fy0, fy1 = max(b - 60, dy), min(d + 60, A.shape[0] - 1)
    FT, FS = A[fy0:fy1, fx0:fx1], A[fy0 - dy:fy1 - dy, fx0 - dx:fx1 - dx]
    ok = (FT[..., 3] > 250) & (FS[..., 3] > 250) & ~_isred(FT[..., :3])
    X = np.c_[FS[..., :3][ok], np.ones(ok.sum())]
    coef, *_ = np.linalg.lstsq(X, FT[..., :3][ok], rcond=None)
    P = (np.c_[S[..., :3].reshape(-1, 3), np.ones(S[..., 0].size)] @ coef).reshape(T.shape[0], T.shape[1], 3)
    P = np.dstack([np.clip(P, 0, 255), S[..., 3]])
    red = _isred(T[..., :3]) & (np.abs(T[..., :3] - P[..., :3]).sum(-1) > 150)
    C = np.median(T[..., :3][red], axis=0)
    al = np.clip(((T[..., :3] - P[..., :3]) * (C - P[..., :3])).sum(-1)
                 / np.maximum(((C - P[..., :3]) ** 2).sum(-1), 1), 0, 1)
    out = S[..., 3] < 128
    al[out] = T[..., 3][out] / 255
    ys, xs = np.where(al > 0.5)
    cx, cy = xs.mean(), ys.mean()
    _w, v = np.linalg.eigh(np.cov(np.vstack([xs - cx, ys - cy])))
    m = v[:, 1] if v[0, 1] > 0 else -v[:, 1]
    u = (xs - cx) * m[0] + (ys - cy) * m[1]
    t = -(xs - cx) * m[1] + (ys - cy) * m[0]
    U0, U1 = np.percentile(u, [0.3, 99.7])
    T0, T1 = np.percentile(t, [0.3, 99.7])
    if T1 - T0 > STAMP_H + 2:            # a faint top border: trust the bottom one
        T0 = T1 - STAMP_H
    return dict(box=(a, b, c, d), T=T, P=P, C=C, cx=cx, cy=cy, m=m,
                U=(U0, U1), Tr=(T0, T1), coef_err=float(np.abs(X @ coef - FT[..., :3][ok]).mean()))


def render(img, i, text=TEXT, font_path=FONT):
    """Return img with the stamp of thumbnail i re-lettered, and the changed box."""
    g = analyse(img, i)
    a, b, c, d = g['box']
    T, P, C, m = g['T'], g['P'], g['C'], g['m']
    cx, cy = g['cx'], g['cy']
    U0, U1 = g['U']
    T0, T1 = g['Tr']
    H, W = T.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    uu = (xx - cx) * m[0] + (yy - cy) * m[1]
    tt = -(xx - cx) * m[1] + (yy - cy) * m[0]
    tm = (T0 + T1) / 2
    # inside of the border: rebuilt from the first card
    inner = (uu > U0 + END_IN) & (uu < U1 - END_IN) & (np.abs(tt - tm) < BORDER_IN)
    soft = np.asarray(Image.fromarray((inner * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))) / 255.0
    new = T.copy()
    new[..., :3] = T[..., :3] * (1 - soft[..., None]) + P[..., :3] * soft[..., None]

    # letters: fitted to the inside, upright in stamp space, then rotated
    room_w = (U1 - U0) - 2 * END_IN - 10
    room_h = 2 * BORDER_IN - 7
    font_size, mask = 10, None
    while True:
        f = ImageFont.truetype(font_path, font_size * SS)
        bb = f.getbbox(text)
        w, h = (bb[2] - bb[0]) / SS, (bb[3] - bb[1]) / SS
        if w > room_w or h > room_h:
            break
        best = (font_size, f, bb)
        font_size += 1
    font_size, f, bb = best
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    canvas = Image.new('L', (tw + 8 * SS, th + 8 * SS), 0)
    ImageDraw.Draw(canvas).text((4 * SS - bb[0], 4 * SS - bb[1]), text, font=f, fill=255)
    ang = math.degrees(math.atan2(m[1], m[0]))
    rot = canvas.rotate(-ang, resample=Image.BICUBIC, expand=True)
    rot = rot.resize((max(1, round(rot.width / SS)), max(1, round(rot.height / SS))), Image.LANCZOS)
    # centre of the inside, in box pixels
    uc = (U0 + U1) / 2
    px_c, py_c = cx + uc * m[0] - tm * m[1], cy + uc * m[1] + tm * m[0]
    ox, oy = round(px_c - rot.width / 2), round(py_c - rot.height / 2)
    ink = np.zeros((H, W))
    r = np.asarray(rot) / 255.0
    y0, x0 = max(0, oy), max(0, ox)
    y1, x1 = min(H, oy + rot.height), min(W, ox + rot.width)
    ink[y0:y1, x0:x1] = r[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    ink *= 0.92                         # the stamp ink is not fully opaque on the paper
    new[..., :3] = new[..., :3] * (1 - ink[..., None]) + C * ink[..., None]
    out = img.copy()
    out.paste(Image.fromarray(np.clip(new, 0, 255).round().astype(np.uint8), 'RGBA'), (a, b))
    return out, (a, b, c + 1, d + 1), dict(size=font_size, angle=ang, err=g['coef_err'],
                                           inside=(round(room_w), room_h))


def build(raw_by_name):
    """{name: tid bytes} -> ({name: new tid bytes}, {name: (before, after) images})."""
    from tid import TID
    out, views = {}, {}
    for i, name in enumerate(NAMES):
        raw = raw_by_name[name]
        t = TID(raw)
        assert t.fourcc == b'DXT5'
        img = t.image().convert('RGBA')
        new, box, info = render(img, i)
        payload = encode_into(t.body(), new, box)
        data = raw[:t.data_off] + payload + raw[t.data_off + t.payload_size:]
        assert len(data) == len(raw)
        out[name] = data
        views[name] = (img.crop(box), TID(data).image().convert('RGBA').crop(box))
        print('  %s: font %d px, angle %+.1f, inside %s, colour map err %.1f'
              % (name, info['size'], info['angle'], info['inside'], info['err']))
    return out, views
