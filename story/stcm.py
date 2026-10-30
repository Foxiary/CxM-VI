"""Minimal STCM2L walker for Collar x Malice scripts.

regions(d) -> sorted [(start, end, kind)] covering the file:
  head (up to the code), header/param/blockhdr/block/pad per instruction,
  exports (EXPORT_DATA..text section), thdr/tblock/tpad in the text section
  that COLLECTION_LINK+4 points at.
"""
import struct

def _blocks(d, q, lim, out, hk, bk, pk):
    while q + 16 <= lim:
        flag, nw, one, bl = struct.unpack_from('<4I', d, q)
        if one == 1 and bl == nw * 4 and bl > 0 and q + 16 + bl <= lim:
            out.append((q, q + 16, hk)); out.append((q + 16, q + 16 + bl, bk))
            q += 16 + ((bl + 3) & ~3)
        else:
            out.append((q, q + 4, pk)); q += 4
    return q

def regions(d):
    at = d.find(b'CODE_START_'); p = at + 12
    end = d.find(b'EXPORT_DATA', p)
    out = [(0, p, 'head')]; odd = []
    while p < end:
        g, op, npar, ln = struct.unpack_from('<4I', d, p)
        out.append((p, p + 16, 'header'))
        q = p + 16; out.append((q, q + 12 * npar, 'param')); q += 12 * npar
        if ln % 4 or ln < 16 or p + ln > end:
            # A length the stream does not agree with: take the blocks that
            # are actually there and resume after them.
            odd.append((p, ln))
            lim = q
            while lim + 16 <= end:
                flag, nw, one, bl = struct.unpack_from('<4I', d, lim)
                if one == 1 and bl == nw * 4 and bl > 0:
                    lim += 16 + ((bl + 3) & ~3)
                else:
                    break
        else:
            lim = p + ln
        _blocks(d, q, lim, out, 'blockhdr', 'block', 'pad')
        p = lim
    coll = struct.unpack_from('<I', d, 0x2C)[0]
    text = struct.unpack_from('<I', d, coll + 4)[0] if coll + 8 <= len(d) else len(d)
    if not end < text <= len(d):
        text = len(d)
    out.append((end, text, 'exports'))
    _blocks(d, text, len(d), out, 'thdr', 'tblock', 'tpad')
    return sorted(out), odd
