"""Move .rodata, .data and .bss of an NSO up by whole pages so .text can grow.

    import nsoshift
    text, rodata, data, head, layout = nsoshift.shift(nso_bytes, 0x1000)
    nsoshift.verify(old_nso_bytes, new_nso_bytes, 0x1000)

.text is the only executable segment, and the emulator runs nothing past the
.text size the NSO header declares, so the only way to add code beyond the
page padding is to move everything after .text. The code itself does not
move, so every reference from or into the moved segments is rebased:

    ADRP in .text            page += D when the target page moved
    jump tables (.rodata)    clang's `ldrsw xT, [xB, xI, lsl #2]; add xT, xT, xB;
                             br xT` stores target - table: entry -= D. An earlier
                             attempt missed these and broke every switch.
    RELA (.rela.dyn/.plt)    r_offset and addend += D when they moved
    .dynamic                 address-valued tags += D
    .dynsym                  st_value += D when it moved
    MOD0                     offsets relative to MOD0 (in .text) += D
    .eh_frame_hdr            function start, relative to the header: -= D
    .eh_frame                FDE pc_begin, pcrel into .text: -= D
    NSO header               .rodata / .data memory offsets += D

Nothing else here refers across the boundary: in the JP Collar x Malice main
there are no ADR or literal loads from .text into .rodata, no RELR and no TLS
relocations, and every absolute address carries a RELA entry. verify()
decodes each kind of reference in both files and checks they agree.
"""
import struct

PAGE = 0x1000

R_ABS64, R_GLOB_DAT, R_JUMP_SLOT, R_RELATIVE = 257, 1025, 1026, 1027
DT_ADDR_TAGS = {
    3, 4, 5, 6, 7,          # PLTGOT, HASH, STRTAB, SYMTAB, RELA
    12, 13,                 # INIT, FINI (in .text, so never moved)
    23, 25, 26, 32,         # JMPREL, INIT_ARRAY, FINI_ARRAY, PREINIT_ARRAY
    0x6FFFFEF5,             # GNU_HASH
    0x6FFFFFF0, 0x6FFFFFFC, 0x6FFFFFFE,   # VERSYM, VERDEF, VERNEED
}
DT_OTHER_TAGS = {1, 2, 8, 9, 10, 11, 14, 20, 21, 27, 28, 30,
                 0x6FFFFFF9, 0x6FFFFFFB, 0x6FFFFFFD, 0x6FFFFFFF}
PTR_SIZE = {0x0: 8, 0x2: 2, 0x3: 4, 0x4: 8, 0xA: 2, 0xB: 4, 0xC: 8}


def sx(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def adrp_target(op, pc):
    if (op & 0x9F000000) != 0x90000000:
        return None
    imm = sx((((op >> 5) & 0x7FFFF) << 2) | ((op >> 29) & 3), 21)
    return (pc & ~0xFFF) + (imm << 12)


def encode_adrp(op, pc, page):
    imm = (page - (pc & ~0xFFF)) >> 12
    if not -(1 << 20) <= imm < (1 << 20):
        raise ValueError('adrp out of range at %#x' % pc)
    imm &= (1 << 21) - 1
    return (op & 0x9F00001F) | ((imm & 3) << 29) | (((imm >> 2) & 0x7FFFF) << 5)


def uleb(b, p):
    v = s = 0
    while True:
        c = b[p]
        p += 1
        v |= (c & 0x7F) << s
        s += 7
        if not c & 0x80:
            return v, p


class Image:
    """The three segments of an NSO at their virtual addresses."""

    def __init__(self, nso):
        from exefs import nso_segments
        segs = nso_segments(nso)
        self.text, self.rodata, self.data = (bytearray(b) for _n, b in segs)
        self.ro_va = struct.unpack_from('<I', nso, 0x24)[0]
        self.data_va = struct.unpack_from('<I', nso, 0x34)[0]
        self.bss = struct.unpack_from('<I', nso, 0x3C)[0]
        self.mod0 = struct.unpack_from('<I', self.text, 4)[0]
        if self.text[self.mod0:self.mod0 + 4] != b'MOD0':
            raise ValueError('no MOD0')

    def seg(self, va):
        """(buffer, offset) holding va."""
        for buf, base in ((self.text, 0), (self.rodata, self.ro_va),
                          (self.data, self.data_va)):
            if base <= va < base + len(buf):
                return buf, va - base
        raise ValueError('%#x is in no segment' % va)

    def read(self, va, n):
        b, o = self.seg(va)
        return bytes(b[o:o + n])

    def u32(self, va):
        return struct.unpack('<I', self.read(va, 4))[0]

    def i32(self, va):
        return struct.unpack('<i', self.read(va, 4))[0]

    def mod0_fields(self):
        f = struct.unpack_from('<6i', self.text, self.mod0 + 4)
        return dict(zip(('dynamic', 'bss_start', 'bss_end', 'eh_start', 'eh_end', 'module'),
                        (self.mod0 + v for v in f)))

    def dynamic(self):
        """[(va of the entry, tag, value)]."""
        va = self.mod0_fields()['dynamic']
        out = []
        while True:
            tag, val = struct.unpack('<qQ', self.read(va, 16))
            if tag == 0:
                return out
            out.append((va, tag, val))
            va += 16

    def dyn(self, tag, default=None):
        for _va, t, v in self.dynamic():
            if t == tag:
                return v
        return default

    def relas(self):
        """[(va of the entry, r_offset, r_info, r_addend)]."""
        out = []
        for start, size in ((self.dyn(7), self.dyn(8, 0)), (self.dyn(23), self.dyn(2, 0))):
            if not start:
                continue
            for va in range(start, start + size, 24):
                out.append((va,) + struct.unpack('<QQq', self.read(va, 24)))
        return out

    def symbols(self):
        """[va of st_value] of every .dynsym entry, counted by DT_HASH."""
        nchain = self.u32(self.dyn(4) + 4)
        return [self.dyn(6) + 24 * i + 8 for i in range(nchain)]

    def eh_hdr(self):
        """(header va, .eh_frame va, entry count)."""
        start = self.mod0_fields()['eh_start']
        if self.read(start, 4) != bytes((1, 0x1B, 0x03, 0x3B)):
            raise ValueError('unexpected .eh_frame_hdr encoding')
        return start, start + 4 + self.i32(start + 4), self.u32(start + 8)

    def fdes(self):
        """[(va of the pc_begin field, pc_begin)] of every FDE in .eh_frame."""
        hdr, va0, _n = self.eh_hdr()
        b, o0 = self.seg(va0)
        end = len(b) if va0 > hdr else o0 + (hdr - va0)
        cies, out, p = {}, [], o0
        while p + 4 <= end:
            length = struct.unpack_from('<I', b, p)[0]
            if length == 0:
                break
            if length == 0xFFFFFFFF:
                raise ValueError('64-bit .eh_frame')
            cid_at = p + 4
            cid = struct.unpack_from('<I', b, cid_at)[0]
            if cid == 0:
                q = cid_at + 5
                aug_end = b.index(b'\0', q)
                aug = bytes(b[q:aug_end]).decode()
                _ca, q = uleb(b, aug_end + 1)
                _da, q = uleb(b, q)
                q += 1                              # return register, CIE v1
                enc = None
                if aug.startswith('z'):
                    _alen, q = uleb(b, q)
                    for ch in aug[1:]:
                        if ch == 'R':
                            enc = b[q]
                            q += 1
                        elif ch == 'L':
                            q += 1
                        elif ch == 'P':
                            q += 1 + PTR_SIZE[b[q] & 0x0F]
                cies[p] = enc
            else:
                if cies.get(cid_at - cid) != 0x1B:
                    raise ValueError('FDE at %#x: pointer encoding %r'
                                     % (va0 + p - o0, cies.get(cid_at - cid)))
                field = va0 + (cid_at + 4 - o0)
                out.append((field, field + self.i32(field)))
            p += 4 + length
        return out

    def jump_tables(self):
        """{table va: [targets]} for every `ldrsw; add; br` switch in .text."""
        import bisect
        t = self.text
        ops = struct.unpack_from('<%dI' % (len(t) // 4), t, 0)
        starts = sorted(set(pc for _v, pc in self.fdes()))
        self._into = {}                                   # block start -> branches into it
        for k, o in enumerate(ops):
            if (o & 0xFF000010) == 0x54000000 or (o & 0x7E000000) == 0x34000000:
                tgt = 4 * k + sx((o >> 5) & 0x7FFFF, 19) * 4     # b.cond, cbz/cbnz
            elif (o & 0x7E000000) == 0x36000000:
                tgt = 4 * k + sx((o >> 5) & 0x3FFF, 14) * 4      # tbz/tbnz
            elif (o & 0xFC000000) == 0x14000000:
                tgt = 4 * k + sx(o & 0x3FFFFFF, 26) * 4          # b
            else:
                continue
            self._into.setdefault(tgt, []).append(k)
        tables = {}
        for i, op in enumerate(ops):
            site = self._switch(ops, i)
            if site is None:
                continue
            rn, rm = site
            f = bisect.bisect_right(starts, 4 * i) - 1
            fn_start = starts[f]
            fn_end = starts[f + 1] if f + 1 < len(starts) else len(t)
            base = self._table_base(ops, i, rn, fn_start)
            if not self.ro_va <= base < self.data_va:
                raise ValueError('switch at %#x: table %#x is not in .rodata' % (4 * i, base))
            count = self._table_count(ops, i, rm)
            targets = [base + self.i32(base + 4 * e) for e in range(count)]
            if not all(fn_start <= x < fn_end for x in targets):
                raise ValueError('switch at %#x: table %#x points outside its function'
                                 % (4 * i, base))
            if base in tables and len(tables[base]) != count:
                raise ValueError('table %#x is read with two sizes' % base)
            tables[base] = targets
        return tables

    @staticmethod
    def _switch(ops, i):
        """(table register, index register) if i is a switch's table load.

        A switch is `ldrsw Xt, [Xn, Xm, lsl #2]` with `add Xd, Xt, Xn` after it,
        the sum going to a `br`. Either gap can be long: 11 instructions from
        the ldrsw to the add at 0x197188, and 0x10D96C's add is followed by
        argument moves for a while before its br - matching from the br
        missed that one, and the game crashed in that switch. So this matches
        from the ldrsw and does not look for the br at all; the targets are
        checked to land inside the function instead."""
        op = ops[i]
        if (op & 0xFFE0FC00) != 0xB8A07800:              # ldrsw Xt, [Xn, Xm, lsl #2]
            return None
        rt, rn, rm = op & 31, (op >> 5) & 31, (op >> 16) & 31
        for a in range(i + 1, min(len(ops), i + 24)):
            o = ops[a]
            if (o & 0xFFE0FC00) == 0x8B000000 and \
                    {(o >> 5) & 31, (o >> 16) & 31} == {rt, rn} and rt != rn:
                return rn, rm                              # add Xd, Xt, Xn
            if (o & 31) in (rt, rn) and not (o & 0xFF000010) == 0x54000000:
                return None                                # either one rewritten first
        return None

    @staticmethod
    def _table_base(ops, i, rn, start):
        """The `adrp Xn; add Xn, Xn, #lo` nearest above i in its function.

        Usually right above the ldrsw, but a switch inside a loop gets its
        table address hoisted to the function's prologue (0x10D67C)."""
        for j in range(i - 1, start // 4 - 1, -1):
            o = ops[j]
            if (o & 0xFFE0FFE0) == 0xAA0003E0 and (o & 31) == rn:    # mov Xd, Xm (0x1FC4EC)
                rn = (o >> 16) & 31
                continue
            if (o & 0xFF800000) == 0x91000000 and (o & 31) == rn and ((o >> 5) & 31) == rn:
                lo = (o >> 10) & 0xFFF
                for k in range(j - 1, max(start // 4, j - 32) - 1, -1):
                    if (ops[k] & 0x9F00001F) == (0x90000000 | rn):
                        return adrp_target(ops[k], 4 * k) + lo
        raise ValueError('cannot find the table of the switch at %#x' % (4 * i))

    # entries for a guard `cmp Rn, #imm` and the branch that keeps the switch
    # out of range: falling through a b.hi / b.hs, or taking a b.ls / b.lo
    SKIP = {0x8: 1, 0x2: 0}           # hi, hs: not taken
    ENTER = {0x9: 1, 0x3: 0}          # ls, lo: taken

    def _table_count(self, ops, i, rm):
        n = self._walk(ops, i, rm, None, 0)
        if n is None:
            # The guard may test a copy made separately: 0x4488C indexes with
            # `and x10, x21, #0x7fffffff` and compares `and w8, w21, ...`. Take
            # the nearest guard on any register, which is where clang puts it.
            n = self._walk(ops, i, None, None, 0)
        if n is None:
            raise ValueError('cannot size the switch at %#x' % (4 * i))
        return n

    def _walk(self, ops, i, reg, cond, depth):
        """Walk back from i to the `cmp` on reg; cond is a b.hi/b.hs passed on
        the way (the guard's flags can be set in an earlier block, 0x429A4).
        At a block reached only by branches, follow each one in: a b.ls/b.lo
        there is the guard itself (0x157C08)."""
        j = i - 1
        while j >= max(0, i - 64):
            o = ops[j]
            if reg is not None and (o & 0x7FE0FFE0) == 0x2A0003E0 and (o & 31) == reg:   # mov Wd, Wm
                reg = (o >> 16) & 31
            elif (o & 0xFF000010) == 0x54000000 and cond is None and (o & 0xF) in self.SKIP:
                cond = o & 0xF
            else:
                imm = None
                if (o & 0x7F80001F) == 0x7100001F and reg in (None, (o >> 5) & 31):   # cmp #imm
                    imm = ((o >> 10) & 0xFFF) << (12 if o & (1 << 22) else 0)
                elif (o & 0x7FE00C10) == 0x7A400800 and reg in (None, (o >> 5) & 31):  # ccmp #imm
                    imm = (o >> 16) & 31
                if imm is not None:
                    return imm + self.SKIP[cond] if cond is not None else None
                if o == 0xD65F03C0 or (o & 0xFC000000) == 0x14000000 or \
                        (o & 0xFFFFFC1F) == 0xD61F0000:
                    # j + 1 is reached only by branching to it
                    preds = self._into.get(4 * (j + 1), [])
                    if not preds or depth > 3:
                        return None
                    counts = [self._enter(ops, k, reg, cond, depth) for k in preds]
                    return max(counts) if counts and None not in counts else None
            j -= 1
        return None

    def _enter(self, ops, k, reg, cond, depth):
        c = ops[k]
        if (c & 0xFF000010) == 0x54000000 and (c & 0xF) in self.ENTER and cond is None:
            for j in range(k - 1, max(0, k - 8), -1):
                o = ops[j]
                if (o & 0x7F80001F) == 0x7100001F and reg in (None, (o >> 5) & 31):
                    imm = ((o >> 10) & 0xFFF) << (12 if o & (1 << 22) else 0)
                    return imm + self.ENTER[c & 0xF]
            return None
        return self._walk(ops, k, reg, cond, depth + 1)


def shift(nso, delta):
    """(text, rodata, data, header, layout) with everything after .text moved up."""
    if delta % PAGE:
        raise ValueError('delta must be whole pages')
    img = Image(nso)
    lo = img.ro_va
    hi = img.data_va + len(img.data) + img.bss + PAGE

    def moved(va):
        return lo <= va < hi

    def mv(va):
        return va + delta if moved(va) else va

    tables = img.jump_tables()
    relas = img.relas()
    dyn = img.dynamic()
    syms = img.symbols()
    eh_start, _eh_frame, eh_count = img.eh_hdr()
    fdes = img.fdes()
    m0 = img.mod0_fields()
    text, rodata, data = bytearray(img.text), bytearray(img.rodata), bytearray(img.data)

    def w(va, fmt, *values):
        """Write at an address of the OLD layout."""
        if img.ro_va <= va < img.ro_va + len(rodata):
            struct.pack_into(fmt, rodata, va - img.ro_va, *values)
        elif img.data_va <= va < img.data_va + len(data):
            struct.pack_into(fmt, data, va - img.data_va, *values)
        else:
            raise ValueError('write outside .rodata/.data at %#x' % va)

    for pc in range(0, len(text), 4):
        op = struct.unpack_from('<I', text, pc)[0]
        page = adrp_target(op, pc)
        if page is not None and moved(page):
            struct.pack_into('<I', text, pc, encode_adrp(op, pc, page + delta))
    for k, name in enumerate(('dynamic', 'bss_start', 'bss_end', 'eh_start', 'eh_end', 'module')):
        struct.pack_into('<i', text, img.mod0 + 4 + 4 * k, mv(m0[name]) - img.mod0)
    for base, targets in tables.items():
        for e, tgt in enumerate(targets):
            w(base + 4 * e, '<i', tgt - (base + delta))
    for va, off, info, add in relas:
        typ = info & 0xFFFFFFFF
        if typ not in (R_ABS64, R_GLOB_DAT, R_JUMP_SLOT, R_RELATIVE):
            raise ValueError('relocation type %d at %#x' % (typ, va))
        if typ == R_ABS64 and add:
            raise ValueError('ABS64 with an addend at %#x' % va)
        w(va, '<QQq', mv(off), info, mv(add) if typ == R_RELATIVE else add)
    for va, tag, val in dyn:
        if tag not in DT_ADDR_TAGS | DT_OTHER_TAGS:
            raise ValueError('unknown dynamic tag %#x' % tag)
        if tag in DT_ADDR_TAGS:
            w(va + 8, '<Q', mv(val))
    for va in syms:
        v = struct.unpack('<Q', img.read(va, 8))[0]
        if moved(v):
            w(va, '<Q', v + delta)
    for k in range(eh_count):
        va = eh_start + 12 + 8 * k
        loc = img.i32(va)
        if not moved(eh_start + loc):
            w(va, '<i', loc - delta)
    for va, pc in fdes:
        if not moved(pc):
            w(va, '<i', pc - (va + delta))

    head = bytearray(nso[:0x100])
    struct.pack_into('<I', head, 0x24, img.ro_va + delta)
    struct.pack_into('<I', head, 0x34, img.data_va + delta)
    layout = {'ro_va': img.ro_va + delta, 'ro_end': img.ro_va + delta + len(rodata),
              'data_va': img.data_va + delta, 'bss_end': m0['bss_end'] + delta,
              'tables': len(tables), 'relas': len(relas), 'fdes': len(fdes)}
    return bytes(text), bytes(rodata), bytes(data), bytes(head), layout


def verify(old_nso, new_nso, delta, text_end):
    """Decode every cross-segment reference in both files and check they agree.

    text_end is the old .text size: bytes past it (the cave) are not compared.
    Words that are neither ADRP nor MOD0 may differ only where hooks point
    into the cave; the caller lists those as `hooks`."""
    a, b = Image(old_nso), Image(new_nso)
    lo, hi = a.ro_va, a.data_va + len(a.data) + a.bss + PAGE

    def mv(va):
        return va + delta if lo <= va < hi else va

    if (b.ro_va, b.data_va, b.bss) != (a.ro_va + delta, a.data_va + delta, a.bss):
        raise AssertionError('segment layout')
    other = []
    for pc in range(0, text_end, 4):
        oa = struct.unpack_from('<I', a.text, pc)[0]
        ob = struct.unpack_from('<I', b.text, pc)[0]
        ta = adrp_target(oa, pc)
        if ta is not None and adrp_target(ob, pc) == mv(ta):
            continue
        if oa != ob and not a.mod0 <= pc < a.mod0 + 28:
            other.append(pc)
    ma, mb = a.mod0_fields(), b.mod0_fields()
    if any(mb[k] != mv(ma[k]) for k in ma):
        raise AssertionError('MOD0')
    ta, tb = a.jump_tables(), b.jump_tables()
    if sorted(mv(k) for k in ta) != sorted(tb) or any(ta[k] != tb[mv(k)] for k in ta):
        raise AssertionError('jump tables decode differently')
    ra, rb = a.relas(), b.relas()
    for x, y in zip(ra, rb):
        rel = (x[2] & 0xFFFFFFFF) == R_RELATIVE
        if (y[1], y[2], y[3]) != (mv(x[1]), x[2], mv(x[3]) if rel else x[3]):
            raise AssertionError('relocation at %#x' % x[0])
    if len(ra) != len(rb):
        raise AssertionError('relocation count')
    if [pc for _v, pc in a.fdes()] != [pc for _v, pc in b.fdes()]:
        raise AssertionError('FDE pc_begin')
    ha, hb = a.eh_hdr(), b.eh_hdr()
    for k in range(ha[2]):
        la = ha[0] + a.i32(ha[0] + 12 + 8 * k)
        lb = hb[0] + b.i32(hb[0] + 12 + 8 * k)
        if mv(la) != lb:
            raise AssertionError('eh_frame_hdr entry %d' % k)
    for x, y in zip(a.symbols(), b.symbols()):
        if struct.unpack('<Q', b.read(y, 8))[0] != mv(struct.unpack('<Q', a.read(x, 8))[0]):
            raise AssertionError('symbol at %#x' % x)
    for (_x, t1, v1), (_y, t2, v2) in zip(a.dynamic(), b.dynamic()):
        if t1 != t2 or v2 != (mv(v1) if t1 in DT_ADDR_TAGS else v1):
            raise AssertionError('dynamic tag %#x' % t1)
    return {'tables': len(ta), 'relas': len(ra), 'fdes': len(a.fdes()),
            'eh': ha[2], 'other_text_words': other}
