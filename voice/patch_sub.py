"""Add English voice-recorder subtitles to the JP build.

The JP executable never loads VOICERECORDER/SUBTITLE/%02u.tid. This shifts
.rodata and .data up by one page so a hook fits at the end of .text, and
appends the 25 subtitle textures to GAME_01.cpk.
"""
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'work', 'voice')    # game files and output, gitignored
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'event'))

from cpk import CPK, UTF
from dxt5 import encode_into
from exefs import nso_segments
from tid import TID

DELTA = 0x1000
OLD_RO = 0x273000
OLD_DATA = 0x330000
NEW_RO = OLD_RO + DELTA
NEW_DATA = OLD_DATA + DELTA
TEXT_END = 0x274000          # new text size, page-aligned, cave lives in the gap
CAVE_AT = 0x2729F0
HOOK_AT = 0xC7BE8
FMT = b'/VOICERECORDER/SUBTITLE/%02u.tid\x00'
# rodata offset of the format string = old rodata size
FMT_OFF = 773352
FMT_VA = NEW_RO + FMT_OFF    # 0x330CE8
GLOBAL_OFF = 82200           # appended to .data
GLOBAL_VA = NEW_DATA + GLOBAL_OFF  # 0x345118
MOVED_LO = OLD_RO
MOVED_HI = 0x1600000

JP_EXE = os.path.join(DATA, 'jp-exefs', 'main')
CAVE = os.path.join(DATA, 'cave.bin')
EN_CPK = os.path.expanduser('~/Documents/Game/010083E00F40E000/romfs/GAME_01.CPK')
JP_CPK = os.path.expanduser('~/Documents/Game/01002B400E9DA000/PatchVietHoa/romfs/CONTENTS/GAME_01.cpk')
OUT_EXE = os.path.join(DATA, 'main')
OUT_CPK = JP_CPK + '.new'

HEADER = 0x100
FLAG_COMPRESSED = 0b111
HASH_OFF = (0xA0, 0xC0, 0xE0)
SEG_HDR = (0x10, 0x20, 0x30)


def align_up(n, a=2048):
    return (n + a - 1) & ~(a - 1)


def adrp_target(op, pc):
    if (op & 0x9F000000) != 0x90000000:
        return None
    immlo = (op >> 29) & 3
    immhi = (op >> 5) & 0x7FFFF
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm -= 1 << 21
    return (pc & ~0xFFF) + (imm << 12)


def encode_adrp(rd, pc, page):
    imm = ((page - (pc & ~0xFFF)) >> 12)
    if not -(1 << 20) <= imm < (1 << 20):
        raise ValueError('adrp out of range pc=%#x page=%#x' % (pc, page))
    imm &= (1 << 21) - 1
    immlo = imm & 3
    immhi = (imm >> 2) & 0x7FFFF
    return 0x90000000 | (immlo << 29) | (immhi << 5) | (rd & 31)


def shift_adrp(text):
    out = bytearray(text)
    n = 0
    for i in range(0, len(text) - 4, 4):
        op = struct.unpack_from('<I', text, i)[0]
        page = adrp_target(op, i)
        if page is None or page < OLD_RO:
            continue
        rd = op & 31
        struct.pack_into('<I', out, i, encode_adrp(rd, i, page + DELTA))
        n += 1
    return bytes(out), n


def shift_va(v):
    if MOVED_LO <= v < MOVED_HI:
        return v + DELTA
    return v


def shift_rela(buf, va, size):
    off = va - OLD_RO
    n = size // 24
    moved = 0
    for i in range(n):
        p = off + i * 24
        r_off, r_info, r_add = struct.unpack_from('<QQq', buf, p)
        n_off = shift_va(r_off)
        n_add = r_add + DELTA if r_add >= MOVED_LO and r_add < MOVED_HI else r_add
        if n_off != r_off or n_add != r_add:
            struct.pack_into('<QQq', buf, p, n_off, r_info, n_add)
            moved += 1
    return moved


def shift_dynamic(data):
    """Add DELTA to every dynamic-table value that is a moved VA."""
    dyn = 0x340048 - OLD_DATA
    p = dyn
    n = 0
    while p + 16 <= len(data):
        tag, val = struct.unpack_from('<qQ', data, p)
        if tag == 0:
            break
        nv = shift_va(val)
        if nv != val:
            struct.pack_into('<Q', data, p + 8, nv)
            n += 1
        p += 16
    return n


def shift_symbols(rod):
    """st_value fields that point into the moved segments."""
    base = 0x291F70 - OLD_RO
    count = (0x2935F0 - 0x291F70) // 24
    n = 0
    for i in range(count):
        p = base + i * 24 + 8
        val = struct.unpack_from('<Q', rod, p)[0]
        nv = shift_va(val)
        if nv != val:
            struct.pack_into('<Q', rod, p, nv)
            n += 1
    return n


def shift_eh_table(rod):
    """eh_frame_hdr binary-search table: function addresses are pcrel into .text."""
    hdr = 0x2CBD08 - OLD_RO
    if rod[hdr] != 1 or rod[hdr + 1] != 0x1B or rod[hdr + 3] != 0x3B:
        raise ValueError('unexpected eh_frame_hdr encoding')
    count = struct.unpack_from('<I', rod, hdr + 8)[0]
    p = hdr + 12
    for _ in range(count):
        loc = struct.unpack_from('<i', rod, p)[0]
        struct.pack_into('<i', rod, p, loc - DELTA)
        p += 8
    return count


def build_nso(text, rodata, data, original):
    head = bytearray(original[:HEADER])
    flags = struct.unpack_from('<I', head, 0x0C)[0]
    struct.pack_into('<I', head, 0x0C, flags & ~FLAG_COMPRESSED)
    mem = (0, NEW_RO, NEW_DATA)
    segs = (text, rodata, data)
    body = bytearray()
    for i, (blob, moff) in enumerate(zip(segs, mem)):
        hdr = SEG_HDR[i]
        struct.pack_into('<I', head, hdr, HEADER + len(body))
        struct.pack_into('<I', head, hdr + 4, moff)
        struct.pack_into('<I', head, hdr + 8, len(blob))
        struct.pack_into('<I', head, 0x60 + 4 * i, len(blob))
        struct.pack_into('32s', head, HASH_OFF[i], hashlib.sha256(blob).digest())
        body += blob
    return bytes(head) + bytes(body)


def shift_mod0(text):
    """MOD0 lives at the start of .text. Its offsets are relative to VA 8."""
    text = bytearray(text)
    for rel in (4, 8, 12, 16, 20, 24):
        v = struct.unpack_from('<i', text, 8 + rel)[0]
        if 8 + v >= OLD_RO:
            struct.pack_into('<i', text, 8 + rel, v + DELTA)
    return bytes(text)


def utf_header(buf, off):
    tsize, rows_off, str_off, data_off, name_off, ncols, rowlen, nrows = \
        struct.unpack_from('>IIIIIHHI', buf, off + 4)
    return {
        'off': off, 'tsize': tsize, 'rows': rows_off, 'str': str_off,
        'data': data_off, 'name': name_off, 'ncols': ncols,
        'rowlen': rowlen, 'nrows': nrows, 'base': off + 8,
    }


def rebuild_rows(packet, new_rows, extra_strings=b''):
    """packet is a full @UTF blob. new_rows is the raw row section. Strings append."""
    h = utf_header(packet, 0)
    base = 8
    schema_end = base + h['rows']
    old_rows_end = base + h['str']
    # strings run until data, or until the end of the table if data is at the end
    table_end = 8 + h['tsize']
    str_end = base + h['data'] if h['data'] > h['str'] else table_end
    old_strings = packet[base + h['str']:str_end]
    old_data = packet[str_end:table_end]
    new_str_off = h['rows'] + len(new_rows)
    new_data_off = new_str_off + len(old_strings) + len(extra_strings)
    body = bytearray(packet[base:schema_end])
    body += new_rows
    body += old_strings
    body += extra_strings
    body += old_data
    # header fields live at the start of body (rows/str/data/name/ncols/rowlen/nrows)
    struct.pack_into('>I', body, 0, new_str_off and h['rows'])  # rows offset unchanged
    struct.pack_into('>I', body, 0, h['rows'])
    struct.pack_into('>I', body, 4, new_str_off)
    struct.pack_into('>I', body, 8, new_data_off if old_data or h['data'] else new_data_off)
    struct.pack_into('>I', body, 20, len(new_rows) // h['rowlen'])
    out = bytearray(b'@UTF') + struct.pack('>I', len(body)) + body
    return bytes(out)


def make_subtitles():
    en = CPK(EN_CPK)
    out = []
    for i in range(25):
        name = 'VOICERECORDER/SUBTITLE/%02d.tid' % i
        raw = None
        for _i, full, row in en.files():
            if full == name:
                raw = en.read(row)
                break
        if raw is None:
            raise SystemExit('missing ' + name)
        t = TID(raw)
        img = t.image().convert('RGBA')
        payload = encode_into(b'\x00' * (img.size[0] // 4 * img.size[1] // 4 * 16),
                               img, (0, 0, img.size[0], img.size[1]))
        tid = bytearray(raw[:0x80])
        tid[0x64:0x68] = b'DXT5'
        tid += payload
        # total size at 0x04 and payload size at 0x58 already match: same byte count
        if struct.unpack_from('<I', tid, 0x58)[0] != len(payload):
            raise SystemExit('payload size mismatch %s' % name)
        struct.pack_into('<I', tid, 0x04, len(tid))
        out.append(bytes(tid))
        print('  encoded', name, len(tid))
    return out


def patch_cpk(tids):
    c = CPK(JP_CPK)
    raw = c.raw
    # --- TOC ---
    toc_at = raw.find(b'@UTF', c.toc_off, c.toc_off + 32)
    th = utf_header(raw, toc_at)
    if th['rowlen'] != 28:
        raise SystemExit('unexpected toc row length %d' % th['rowlen'])
    rows = bytearray(raw[th['base'] + th['rows']:th['base'] + th['str']])
    if len(rows) != th['nrows'] * 28:
        raise SystemExit('toc rows size')
    # round-trip check on the first row's filename via the existing parser
    insert_at = 1813
    pool = bytearray()
    # existing pool is copied by rebuild; extra strings are appended, so offsets
    # of old strings stay valid. New offsets are len(old pool) + offset in extra.
    old_pool_len = (th['base'] + (th['data'] if th['data'] > th['str'] else th['tsize'])
                    ) - (th['base'] + th['str'])
    # compute old pool length from the packet
    packet = bytes(raw[toc_at:toc_at + 8 + th['tsize']])
    ph = utf_header(packet, 0)
    str_end = 8 + (ph['data'] if ph['data'] > ph['str'] else ph['tsize'])
    old_pool = packet[8 + ph['str']:str_end]
    extra = bytearray()
    dir_off = len(old_pool) + len(extra)
    extra += b'VOICERECORDER/SUBTITLE\x00'
    name_offs = []
    for i in range(25):
        name_offs.append(len(old_pool) + len(extra))
        extra += b'%02d.tid\x00' % i
    new_rows = bytearray()
    # rows before the insertion
    new_rows += rows[:insert_at * 28]
    base = c.base
    content_end = c.content_off + c.hdr['ContentSize']
    cursor = align_up(content_end)
    placed = []
    max_id = max(r['ID'] for r in c.toc.rows)
    for i, tid in enumerate(tids):
        cursor = align_up(cursor)
        file_off = cursor - base
        rec = struct.pack('>IIIII', dir_off, name_offs[i],
                           len(tid), len(tid), 0)  # placeholder, FileOffset is u64
        # DirName u32, FileName u32, FileSize u32, ExtractSize u32, FileOffset u64, ID u32
        rec = struct.pack('>IIIIQI', dir_off, name_offs[i], len(tid), len(tid),
                           file_off, max_id + 1 + i)
        if len(rec) != 28:
            raise SystemExit('row %d' % len(rec))
        new_rows += rec
        placed.append((cursor, tid))
        cursor += len(tid)
    new_rows += rows[insert_at * 28:]
    new_toc = rebuild_rows(packet, new_rows, bytes(extra))
    # confirm it parses and the new names resolve
    nt = UTF(new_toc, 0)
    if nt.nrows != c.toc.nrows + 25:
        raise SystemExit('nrows %d' % nt.nrows)
    got = nt.rows[insert_at]['DirName'] + '/' + nt.rows[insert_at]['FileName']
    if got != 'VOICERECORDER/SUBTITLE/00.tid':
        raise SystemExit('bad name %r' % got)
    if nt.rows[insert_at + 25]['FileName'] != 'voiceRecorderBg.tid':
        raise SystemExit('shifted row wrong %r' % nt.rows[insert_at + 25])
    # old names still resolve
    if nt.rows[0]['FileName'] != c.toc.rows[0]['FileName']:
        raise SystemExit('first row changed')

    # --- Fdata tree ---
    gtoc_at = raw.find(b'@UTF', c.hdr['GtocOffset'], c.hdr['GtocOffset'] + 32)
    gh = utf_header(raw, gtoc_at)
    grow = gh['base'] + gh['rows']
    # blobs: three, F is the middle one
    f_off, f_size = struct.unpack_from('>II', raw, grow + 12 + 8)
    data_base = gh['base'] + gh['data']
    fpacket = bytes(raw[data_base + f_off:data_base + f_off + f_size])
    fh = utf_header(fpacket, 0)
    if fh['rowlen'] != 12 or fh['nrows'] != 1816:
        raise SystemExit('fdata %d x %d' % (fh['rowlen'], fh['nrows']))
    frows = [struct.unpack_from('>iii', fpacket, 8 + fh['rows'] + i * 12)
             for i in range(fh['nrows'])]
    nodes = list(frows)
    # node 0 SortFlink -> new last node; node 1813 Next stays 1814 (first subtitle)
    nodes[0] = (nodes[0][0], nodes[0][1], 1840)
    fresh = []
    for i in range(1814, 1839):          # 25 subtitle nodes
        nxt = i + 1
        fresh.append((-1 if False else nxt, i - 1, i))
    # last subtitle's next is the shifted bg node
    fresh[-1] = (1839, 1837, 1838)
    bg = (1840, 1838, 1839)              # old node 1814
    parts = (0, 1839, 1840)              # old node 1815, Next 0 = end
    new_nodes = nodes[:1814] + fresh + [bg, parts]
    if len(new_nodes) != 1841:
        raise SystemExit('nodes %d' % len(new_nodes))
    raw_rows = b''.join(struct.pack('>iii', *n) for n in new_nodes)
    new_f = rebuild_rows(fpacket, raw_rows)
    nf = UTF(new_f, 0)
    if nf.nrows != 1841:
        raise SystemExit('fdata nrows')
    if nf.rows[1814]['Next'] != 1815 or nf.rows[0]['SortFlink'] != 1840:
        raise SystemExit('tree link check %s %s' % (nf.rows[0], nf.rows[1814]))

    # splice Fdata into gtoc data section and update the size/offset of AttrData
    g_off, g_size = struct.unpack_from('>II', raw, grow + 12)
    a_off, a_size = struct.unpack_from('>II', raw, grow + 12 + 16)
    gblob = bytes(raw[data_base + g_off:data_base + g_off + g_size])
    ablob = bytes(raw[data_base + a_off:data_base + a_off + a_size])
    new_data = gblob + new_f + ablob
    # rewrite the three blob descriptors
    gtoc_packet = bytearray(raw[gtoc_at:gtoc_at + 8 + gh['tsize']])
    # row is inside this packet
    rel_row = (grow - gtoc_at)
    struct.pack_into('>i', gtoc_packet, rel_row + 4, 1841)  # Flink
    struct.pack_into('>II', gtoc_packet, rel_row + 12, 0, len(gblob))
    struct.pack_into('>II', gtoc_packet, rel_row + 20, len(gblob), len(new_f))
    struct.pack_into('>II', gtoc_packet, rel_row + 28,
                     len(gblob) + len(new_f), len(ablob))
    # rebuild gtoc packet with the same rows (already patched) but a new data section
    # easier to swap the data bytes if the new data is longer: update tsize and data
    old_data_len = g_size + f_size + a_size
    if gh['base'] + gh['data'] + old_data_len != gtoc_at + 8 + gh['tsize']:
        # data may not run to the end; check
        print('  gtoc data end', gh['base'] + gh['data'] + old_data_len,
              'table end', gtoc_at + 8 + gh['tsize'])
    # replace data section and fix tsize
    new_gtoc_body_data_off = gh['data']
    prefix = bytearray(gtoc_packet[:8 + new_gtoc_body_data_off])
    # prefix includes @UTF + tsize + fields up through the byte before data.
    # gtoc_packet starts at @UTF. data begins at (base - gtoc_at) + data_off = 8 + data_off
    new_gtoc = prefix + new_data
    struct.pack_into('>I', new_gtoc, 4, len(new_gtoc) - 8)
    # parse check
    ng = UTF(bytes(new_gtoc), 0)
    if ng.rows[0]['Flink'] != 1841:
        raise SystemExit('flink')
    f2 = UTF(ng.rows[0]['Fdata'], 0)
    if f2.nrows != 1841:
        raise SystemExit('nested nrows')

    # fit into the prefix
    new_toc_size = 16 + len(new_toc)   # 'TOC ' + 12 pad + utf? current layout:
    # toc_off points at 'TOC ', @UTF is 16 bytes later
    if raw[c.toc_off:c.toc_off + 4] != b'TOC ':
        raise SystemExit('no TOC magic')
    toc_total = (toc_at - c.toc_off) + len(new_toc)
    gtoc_total = (gtoc_at - c.hdr['GtocOffset']) + len(new_gtoc)
    print('  toc bytes', toc_total, 'limit', c.hdr['GtocOffset'] - c.toc_off)
    print('  gtoc bytes', gtoc_total, 'limit', c.content_off - c.hdr['GtocOffset'])
    if c.toc_off + toc_total > c.hdr['GtocOffset']:
        raise SystemExit('toc overlaps gtoc')
    if c.hdr['GtocOffset'] + gtoc_total > c.content_off:
        raise SystemExit('gtoc overlaps content')

    prefix = bytearray(raw[:c.content_off])
    prefix[toc_at:toc_at + len(new_toc)] = new_toc
    prefix[gtoc_at:gtoc_at + len(new_gtoc)] = new_gtoc

    # content: old payloads, then the new files at the offsets already stored
    content = bytearray(raw[c.content_off:c.content_off + c.hdr['ContentSize']])
    # placed cursors are absolute. content[0] is at c.content_off.
    for abs_off, tid in placed:
        rel = abs_off - c.content_off
        if rel < len(content):
            raise SystemExit('new file overlaps old content')
        if rel > len(content):
            content += b'\x00' * (rel - len(content))
        content += tid
    etoc_at = align_up(c.content_off + len(content))
    pad = etoc_at - (c.content_off + len(content))
    content += b'\x00' * pad
    etoc = bytes(raw[c.hdr['EtocOffset']:c.hdr['EtocOffset'] + c.hdr['EtocSize']])
    out = prefix + content + etoc

    # header fields. patch() writes into `out` using offsets from the original header.
    def setf(name, value):
        if not c.head.patch(out, 0, name, value):
            raise SystemExit('cannot patch ' + name)
    setf('TocSize', toc_total)
    setf('GtocSize', gtoc_total)
    setf('Files', c.hdr['Files'] + 25)
    setf('ContentSize', len(content) - pad)
    setf('EnabledPackedSize', len(content) - pad)
    setf('EnabledDataSize', len(content) - pad)
    setf('EtocOffset', etoc_at)
    with open(OUT_CPK, 'wb') as fh:
        fh.write(out)
    print('  wrote', OUT_CPK, len(out))
    return placed


def main():
    print('subtitles')
    tids = make_subtitles()
    print('cpk')
    patch_cpk(tids)
    # verify
    c = CPK(OUT_CPK)
    for i in (0, 12, 24):
        name = 'VOICERECORDER/SUBTITLE/%02d.tid' % i
        found = False
        for _i, full, row in c.files():
            if full == name:
                data = c.read(row)
                t = TID(data)
                print(' ', name, t.width, t.height, t.fourcc, len(data))
                found = True
                break
        if not found:
            raise SystemExit('not found ' + name)
    # old file still there
    for _i, full, row in c.files():
        if full == 'EVENT/event_Parts.tid':
            print('  event parts', row['FileSize'])
            break

    print('executable')
    original = open(JP_EXE, 'rb').read()
    text, rodata, data = [b for _n, b in nso_segments(original)]
    text, nadrp = shift_adrp(text)
    cave = open(CAVE, 'rb').read()
    if CAVE_AT != len(text):
        raise SystemExit('cave va %#x but text ends %#x' % (CAVE_AT, len(text)))
    text = bytearray(text)
    text += cave
    text += b'\x00' * (TEXT_END - len(text))
    # hook
    imm = (CAVE_AT - HOOK_AT) >> 2
    bl = 0x94000000 | (imm & 0x3FFFFFF)
    struct.pack_into('<I', text, HOOK_AT, bl)
    text = shift_mod0(text)

    rodata = bytearray(rodata) + FMT
    shift_rela(rodata, 0x273050, 0x1D370)
    shift_rela(rodata, 0x2903C0, 0x13B0)
    syms = shift_symbols(rodata)
    eh = shift_eh_table(rodata)
    data = bytearray(data) + b'\x00' * 8 + b'\xff\xff\xff\xff' + b'\x00' * 4
    ndyn = shift_dynamic(data)
    print('  adrp', nadrp, 'symbols', syms, 'eh entries', eh, 'dyn', ndyn)

    blob = build_nso(bytes(text), bytes(rodata), bytes(data), original)
    open(OUT_EXE, 'wb').write(blob)
    # read back
    got = dict(nso_segments(blob))
    if got['text'][HOOK_AT:HOOK_AT + 4] != struct.pack('<I', bl):
        raise SystemExit('hook missing')
    # format string
    if got['rodata'][FMT_OFF:FMT_OFF + len(FMT)] != FMT:
        raise SystemExit('format string missing')
    # a known string survived the shift: voiceRecorderParts path at old rodata off
    old_off = 0x299FA1 - OLD_RO
    if b'voiceRecorderParts.tid' not in got['rodata'][old_off:old_off + 40]:
        raise SystemExit('parts path lost')
    # hashes
    head = blob[:HEADER]
    for i, name in enumerate(('text', 'rodata', 'data')):
        digest = hashlib.sha256(got[name]).digest()
        if head[HASH_OFF[i]:HASH_OFF[i] + 32] != digest:
            raise SystemExit('hash ' + name)
    flags = struct.unpack_from('<I', head, 0x0C)[0]
    if flags & FLAG_COMPRESSED:
        raise SystemExit('still compressed')
    print('  exe', len(blob), 'flags', hex(flags))
    print('ok')


if __name__ == '__main__':
    main()
