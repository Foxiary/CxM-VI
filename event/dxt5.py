"""Small DXT5 encoder. Bit order is checked against Pillow's BCn decoder."""
import struct

LUT5 = [min(31, (i * 31 + 128) // 255) for i in range(256)]
LUT6 = [min(63, (i * 63 + 128) // 255) for i in range(256)]
EXP5 = [((v << 3) | (v >> 2)) for v in range(32)]
EXP6 = [((v << 2) | (v >> 4)) for v in range(64)]


def _to565(r, g, b):
    return (LUT5[r] << 11) | (LUT6[g] << 5) | LUT5[b]


def _from565(v):
    return EXP5[(v >> 11) & 31], EXP6[(v >> 5) & 63], EXP5[v & 31]


def _endpoints(colors):
    """Two RGB endpoints along the principal colour axis."""
    n = len(colors)
    sr = sg = sb = 0
    for r, g, b in colors:
        sr += r
        sg += g
        sb += b
    mr = sr / n
    mg = sg / n
    mb = sb / n
    xx = xy = xz = yy = yz = zz = 0.0
    for r, g, b in colors:
        r -= mr
        g -= mg
        b -= mb
        xx += r * r
        xy += r * g
        xz += r * b
        yy += g * g
        yz += g * b
        zz += b * b
    vx = vy = vz = 1.0
    for _ in range(5):
        nx = xx * vx + xy * vy + xz * vz
        ny = xy * vx + yy * vy + yz * vz
        nz = xz * vx + yz * vy + zz * vz
        mag = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
        vx, vy, vz = nx / mag, ny / mag, nz / mag
    lo = hi = None
    plo = 1e18
    phi = -1e18
    for r, g, b in colors:
        p = (r - mr) * vx + (g - mg) * vy + (b - mb) * vz
        if p < plo:
            plo = p
            lo = (r, g, b)
        if p > phi:
            phi = p
            hi = (r, g, b)
    return lo, hi


def _color_block(pixels):
    """8-byte DXT1 colour block. pixels: 16 (r,g,b,a)."""
    opaque = [(r, g, b) for r, g, b, a in pixels if a >= 8]
    if not opaque:
        return b'\x00' * 8
    if len(opaque) == 1 or max(opaque) == min(opaque) or (
            max(c[0] for c in opaque) - min(c[0] for c in opaque) < 2
            and max(c[1] for c in opaque) - min(c[1] for c in opaque) < 2
            and max(c[2] for c in opaque) - min(c[2] for c in opaque) < 2):
        r = sum(c[0] for c in opaque) // len(opaque)
        g = sum(c[1] for c in opaque) // len(opaque)
        b = sum(c[2] for c in opaque) // len(opaque)
        v = _to565(r, g, b)
        return struct.pack('<HHI', v, v, 0)

    lo, hi = _endpoints(opaque)
    best = None
    best_err = 1 << 62
    for inset in (0, 16):
        if inset:
            c0 = tuple(lo[i] + (hi[i] - lo[i]) // inset for i in range(3))
            c1 = tuple(hi[i] + (lo[i] - hi[i]) // inset for i in range(3))
        else:
            c0, c1 = lo, hi
        v0 = _to565(*c0)
        v1 = _to565(*c1)
        if v0 < v1:
            v0, v1 = v1, v0
        elif v0 == v1:
            # nudge so the 4-colour mode stays available
            if v0 < 0xFFFF:
                v0 += 1
            else:
                v1 -= 1
        e0 = _from565(v0)
        e1 = _from565(v1)
        pal = (
            e0,
            e1,
            tuple((2 * e0[i] + e1[i]) // 3 for i in range(3)),
            tuple((e0[i] + 2 * e1[i]) // 3 for i in range(3)),
        )
        bits = 0
        err = 0
        for i, (r, g, b, a) in enumerate(pixels):
            if a < 8:
                continue
            be = 1 << 30
            bi = 0
            for k, p in enumerate(pal):
                d = (r - p[0]) ** 2 + (g - p[1]) ** 2 + (b - p[2]) ** 2
                if d < be:
                    be = d
                    bi = k
            err += be
            bits |= bi << (2 * i)
        if err < best_err:
            best_err = err
            best = struct.pack('<HHI', v0, v1, bits)
    return best


def _alpha_mode(a0, a1, eight):
    if eight:
        pal = [
            a0, a1,
            (6 * a0 + a1) // 7,
            (5 * a0 + 2 * a1) // 7,
            (4 * a0 + 3 * a1) // 7,
            (3 * a0 + 4 * a1) // 7,
            (2 * a0 + 5 * a1) // 7,
            (a0 + 6 * a1) // 7,
        ]
    else:
        pal = [
            a0, a1,
            (4 * a0 + a1) // 5,
            (3 * a0 + 2 * a1) // 5,
            (2 * a0 + 3 * a1) // 5,
            (a0 + 4 * a1) // 5,
            0, 255,
        ]
    return pal


def _fit_alpha(alphas, a0, a1, eight):
    pal = _alpha_mode(a0, a1, eight)
    acc = 0
    err = 0
    n = 8 if eight else 8
    for i, a in enumerate(alphas):
        be = 1 << 30
        bi = 0
        for k in range(n):
            d = abs(pal[k] - a)
            if d < be:
                be = d
                bi = k
        err += be
        acc |= bi << (3 * i)
    return bytes([a0 & 255, a1 & 255]) + acc.to_bytes(6, 'little'), err


def _alpha_block(pixels):
    alphas = [a for _r, _g, _b, a in pixels]
    lo = min(alphas)
    hi = max(alphas)
    if lo == hi:
        return bytes([lo, hi]) + b'\x00' * 6
    # 8-value mode needs a0 > a1.
    cands = []
    if hi > lo:
        cands.append(_fit_alpha(alphas, hi, lo, True))
    # 6-value mode (explicit 0 and 255) when the block actually uses them.
    if lo == 0 or hi == 255:
        cands.append(_fit_alpha(alphas, lo, hi if hi != lo else min(255, lo + 1), False))
    cands.sort(key=lambda t: t[1])
    return cands[0][0]


def encode_block(pixels):
    """pixels: 16 RGBA tuples, row-major."""
    return _alpha_block(pixels) + _color_block(pixels)


def encode(image, box=None):
    """Encode an RGBA image to a DXT5 payload. box limits which blocks are new.

    Returns (payload, (x0, y0, x1, y1) block-aligned region that was encoded)
    when box is set the payload is None and the caller supplies the base via
    encode_into.
    """
    raise NotImplementedError


def encode_into(base, image, box):
    """Splice DXT5 blocks for `box` (x0,y0,x1,y1, exclusive) into `base` bytes.

    `image` is a Pillow RGBA image the same size as the texture. Only blocks
    that overlap the box are rewritten; everything else stays as it was.
    """
    w, h = image.size
    if len(base) != (w // 4) * (h // 4) * 16:
        raise ValueError('payload %d does not match %dx%d' % (len(base), w, h))
    x0, y0, x1, y1 = box
    x0 &= ~3
    y0 &= ~3
    x1 = (x1 + 3) & ~3
    y1 = (y1 + 3) & ~3
    x1 = min(x1, w)
    y1 = min(y1, h)
    bx_count = w // 4
    pix = image.load()
    out = bytearray(base)
    for by in range(y0 // 4, y1 // 4):
        for bx in range(x0 // 4, x1 // 4):
            pixels = []
            oy = by * 4
            ox = bx * 4
            for py in range(4):
                for px in range(4):
                    pixels.append(pix[ox + px, oy + py])
            block = encode_block(pixels)
            off = (by * bx_count + bx) * 16
            out[off:off + 16] = block
    return bytes(out)
