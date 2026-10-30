"""Show the English -Unlimited- subtitles in the JP build.

    python3 unlsub.py tex OUTDIR          render every texture from work/voice/en-unl/
    python3 unlsub.py cpk SRC DST TEXDIR  add them to a GAME_02.cpk as SUBDIR/*.tid
    python3 unlsub.py swap SRC DST TEXDIR replace the ones that changed in a GAME_02
                                          that already has them

The code half is unlsub.s, linked into exefs/main by voicesub.py.

WHERE THE ENGLISH TEXT IS
    Not in a texture, unlike the main game's 25 SUBTITLE/%02u.tid. The English
    -Unlimited- executable (0100E3B00F412000, build 2390EB2E...) keeps it in
    .data as two tables of C-string pointers:

      0x3442D8  83 x (voice id, question, answer) - the voice recorder, one per
                row of dbLibVoiceRecorder_02, but NOT in its order: rows 0..49
                (the five leads) agree, the 33 others are listed in a
                different character order. The game knows a clip by its
                database row, so en_tables() reorders this table by the
                database's voice ids (JP and EN databases list the same ones,
                in the same order). Taking the table's own order put Kotoho's
                answers under Mochida's questions.
      0x3434C8  225 x (voice id, line) - what a character says on the Extra
                screen (ALBUM / VOICE RECORDER / ...), looked up by the voice
                id being played

    Aksys grew the recorder object by ~37 KB for line buffers, text windows and
    a scrollbar, and added a message box to EXTRA/extra_charParts.tid. None of
    that exists in the JP build.

WHAT THIS DRAWS INSTEAD
    DXT5 textures at 2 texels per unit of the engine's 960x540 screen (the
    scale the parts atlases use too), text in the English build's own
    sysfont.ffu scaled 1.57 - measured off screenshots of the English build,
    where the recorder's question, its answer and the Extra screen's line all
    come out at that scale.

    Recorder, 00.tid..82.tid by database row, 1584 texels wide:
        rows   0..894   the English panel art, with the question baked into
                        its red bar and the scroll track baked in when the
                        answer runs past 16 lines
        rows 900..1026  the scrollbar thumb, at x 1544
        rows 904..      the answer, one line every 44 texels
    Panel at (125, 75), question centred in the 585-unit box at x 285, answer
    at x 265, scroll track at (876, 135). unlsub.s keeps each row's line count
    in us_lines; `tex` checks that table against the text.

    Extra screen, <voice id>.tid (11117.tid ...), 1220x264: the English message
    box (extra_charParts 810,512 1220x262, drawn at (350, 400)) with the line
    centred on x 655.5 as the English window does. One line has its ink top
    at y 458.9; each extra line raises the first by 8 units, as the English
    code's (932 - 16 * lines) / 2 does, and lines are 21.82 units apart.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'work', 'voice')    # game files and output, gitignored
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
from exefs import nso_segments  # noqa: E402

EN = os.path.join(DATA, 'en-unl')
EN_MAIN = os.path.join(EN, 'main')                 # exefs/main of 0100E3B00F412000 v0
EN_FONT = os.path.join(EN, 'sysfont.ffu')          # SYSTEM.CPK WINDOW/FONT/sysfont.ffu
EN_PARTS = os.path.join(EN, 'voiceRecorderParts.tid')   # GAME_02.CPK VOICERECORDER/
EN_CHARPARTS = os.path.join(EN, 'extra_charParts.tid')  # GAME_02.CPK EXTRA/
TEMPLATE = os.path.join(EN, 'jp_template.tid')     # any JP DXT5 .tid, for its header
EN_DB = os.path.join(EN, 'dbLibVoiceRecorder_02.gbin')  # SYSTEM.CPK DATABASE/

EN_BUILD = '2390EB2E1E1C4134A69C88398D784AD84E4EE9AF'
EN_RO = 0x26C000
ROWS_VA, ROWS = 0x3442D8, 83                       # (id, question, answer) x 83
LINES_VA, LINES = 0x3434C8, 225                    # (id, line) x 225
R_AARCH64_RELATIVE = 0x403

WIDTH = 1584
PANEL = (718, 1154, 1582, 894)        # texels in the English atlas: (125, 75) 791x447
TRACK = (584, 1230, 42, 744)          # (876, 135) 21x372, arrows included
THUMB = (544, 1214, 32, 126)          # 16x63 units, white bar 548..569 x 1231..1332
TRACK_AT = (2 * (876 - 125), 2 * (135 - 75))
THUMB_AT = (1544, 900)
BAR_BOX = (2 * (285 - 125), 2 * (95 - 75), 2 * 585, 72)   # question, centred
BODY_TOP = 904
PITCH = 44
VISIBLE = 16
SCALE = 1.57
INK_TOP = 6                           # first ink row of a line inside its slot

BOX = (810, 512, 1220, 262)           # English extra_charParts: (350, 400) 610x131
BOX_SIZE = (1220, 264)
LINE_CENTRE = 2 * (655.5 - 350)       # the English window: x 361, 589 wide
LINE_TOP = 2 * (458.9 - 400)          # ink top of a lone line
LINE_RISE = 2 * 8                     # per extra line
LINE_PITCH = 2 * 21.82
LINE_ROOM = 2 * 589


def en_tables():
    """(recorder rows, Extra lines) read out of the English executable."""
    nso = open(EN_MAIN, 'rb').read()
    if nso[0x40:0x54].hex().upper() != EN_BUILD:
        raise SystemExit('%s is not the English -Unlimited- v0 main' % EN_MAIN)
    ro = dict(nso_segments(nso))['rodata']
    rel = {}
    for i in range(0, len(ro) - 24, 8):
        off, info, add = struct.unpack_from('<QQq', ro, i)
        if info == R_AARCH64_RELATIVE:
            rel[off] = add

    def cstr(va):
        o = va - EN_RO
        return ro[o:ro.index(b'\0', o)].decode('utf-8')

    def table(va, rows, width):
        return [tuple(cstr(rel[va + 8 * (width * k + j)]) for j in range(width))
                for k in range(rows)]

    recorder, lines = table(ROWS_VA, ROWS, 3), table(LINES_VA, LINES, 2)
    if not all(r[0].isdigit() and r[1].startswith(('Q', '1:', '2:', '3:')) for r in recorder):
        raise SystemExit('the recorder table is not where it was')
    if not all(r[0].isdigit() for r in lines) or len({r[0] for r in lines}) != LINES:
        raise SystemExit('the Extra line table is not where it was')
    by_voice = {int(r[0]): r for r in recorder}
    order = db_voices()
    if sorted(order) != sorted(by_voice):
        raise SystemExit('dbLibVoiceRecorder_02 and the English table list different voices')
    return [by_voice[v] for v in order], lines


def db_voices():
    """The voice id of each row of dbLibVoiceRecorder_02 (u32 at +12)."""
    import gbnl
    g = gbnl.GBNL(open(EN_DB, 'rb').read())
    if g.n != ROWS or g.stride != 24:
        raise SystemExit('%s: %d rows of %d bytes' % (EN_DB, g.n, g.stride))
    return [struct.unpack_from('<I', g.raw, g.tbl + i * g.stride + 12)[0] for i in range(g.n)]


def asm_lines():
    """The us_lines table of unlsub.s."""
    src = open(os.path.join(HERE, 'unlsub.s')).read()
    body = src[src.index('us_lines:'):].split('.balign')[0]
    return [int(v) for line in body.splitlines() if '.byte' in line
            for v in line.split('.byte')[1].split(',')]


def lines_of(answer):
    lines = answer.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines


class Font:
    """sysfont.ffu rendered the way the English build draws it."""

    def __init__(self, path):
        from ffu import FFU
        self.f = FFU(open(path, 'rb').read())
        self.alpha = [a for _r, _g, _b, a in self.f.palettes[0]]
        self.cell = self.f._rA & 0xff
        self.cache = {}

    def glyph(self, ch):
        from PIL import Image
        if ch not in self.cache:
            gi = self.f.index(ch)
            if gi is None:
                raise SystemExit('sysfont has no %r' % ch)
            w, h, rows = self.f.bitmap(gi)
            im = Image.new('L', (max(w, 1), max(h, 1)), 0)
            if w and h:
                im.putdata([self.alpha[v] for r in rows for v in r])
            self.cache[ch] = (self.f.glyphs[gi]['adv'], im)
        return self.cache[ch]

    def line(self, text):
        """Coverage image of one line at SCALE, cell rows included."""
        from PIL import Image
        width = sum(self.glyph(c)[0] for c in text)
        im = Image.new('L', (max(width, 1), self.cell), 0)
        x = 0
        for c in text:
            adv, g = self.glyph(c)
            im.paste(g, (x, 0), g)
            x += adv
        return im.resize((round(im.width * SCALE), round(im.height * SCALE)),
                         Image.LANCZOS)

    def cap_top(self):
        """First ink row of a capital, at SCALE."""
        return self.line('I').point(lambda v: 255 if v > 128 else 0).getbbox()[1]


def white(coverage):
    from PIL import Image
    im = Image.new('RGBA', coverage.size, (255, 255, 255, 0))
    im.putalpha(coverage)
    return im


def render(font, atlas, question, answer):
    from PIL import Image
    lines = lines_of(answer)
    n = len(lines)
    tex = Image.new('RGBA', (WIDTH, BODY_TOP + PITCH * n + 8), (255, 255, 255, 0))
    x, y, w, h = PANEL
    tex.alpha_composite(atlas.crop((x, y, x + w, y + h)), (0, 0))
    if n > VISIBLE:
        x, y, w, h = TRACK
        tex.alpha_composite(atlas.crop((x, y, x + w, y + h)), TRACK_AT)
        x, y, w, h = THUMB
        tex.alpha_composite(atlas.crop((x, y, x + w, y + h)), THUMB_AT)

    ink_top = round(INK_TOP * SCALE)
    q = font.line(question)
    bx, by, bw, bh = BAR_BOX
    ink_h = round((font.cell - 1 - INK_TOP) * SCALE)
    tex.alpha_composite(white(q), (bx + (bw - q.width) // 2,
                                   by + (bh - ink_h) // 2 - ink_top))
    widest = 0
    for i, text in enumerate(lines):
        ln = font.line(text)
        widest = max(widest, ln.width)
        tex.alpha_composite(white(ln), (0, BODY_TOP + PITCH * i + INK_TOP - ink_top))
    return tex, n, widest


def render_line(font, box, text):
    from PIL import Image
    tex = Image.new('RGBA', BOX_SIZE, (255, 255, 255, 0))
    tex.alpha_composite(box, (0, 0))
    lines = text.split('\n')
    cap = font.cap_top()
    widest = 0
    for i, s in enumerate(lines):
        ln = font.line(s)
        widest = max(widest, ln.width)
        y = LINE_TOP - LINE_RISE * (len(lines) - 1) + LINE_PITCH * i - cap
        tex.alpha_composite(white(ln), (round(LINE_CENTRE - ln.width / 2), round(y)))
    return tex, widest


def tid_bytes(img, name):
    """A JP-style DXT5 .tid around img, header copied from TEMPLATE."""
    import etcpak
    w, h = img.size
    if w % 4 or h % 4:
        raise SystemExit('%s is %dx%d, not a multiple of 4' % (name, w, h))
    payload = etcpak.compress_bc3(img.tobytes(), w, h)
    if len(payload) != w * h:
        raise SystemExit('DXT5 payload %d, expected %d' % (len(payload), w * h))
    head = bytearray(open(TEMPLATE, 'rb').read()[:0x80])
    if head[0x64:0x68] != b'DXT5' or struct.unpack_from('<I', head, 0x5C)[0] != 0x80:
        raise SystemExit('template is not a DXT5 .tid')
    head[0x20:0x40] = name.encode('ascii').ljust(32, b'\0')[:32]
    struct.pack_into('<I', head, 0x04, 0x80 + len(payload))
    struct.pack_into('<II', head, 0x44, w, h)
    struct.pack_into('<I', head, 0x58, len(payload))
    return bytes(head) + payload


def check_encoder():
    """etcpak's channel order, checked against Pillow's BC3 decoder."""
    from PIL import Image
    import etcpak
    img = Image.new('RGBA', (8, 4), (200, 40, 10, 255))
    img.paste((10, 40, 200, 128), (4, 0, 8, 4))
    back = Image.frombytes('RGBA', (8, 4), etcpak.compress_bc3(img.tobytes(), 8, 4),
                           'bcn', (3,))
    for x in (1, 6):
        got, want = back.getpixel((x, 1)), img.getpixel((x, 1))
        if max(abs(a - b) for a, b in zip(got, want)) > 12:
            raise SystemExit('etcpak channel order: %r for %r' % (got, want))


def cmd_tex(out):
    from tid import TID
    check_encoder()
    atlas = TID(open(EN_PARTS, 'rb').read()).image().convert('RGBA')
    charparts = TID(open(EN_CHARPARTS, 'rb').read()).image().convert('RGBA')
    x, y, w, h = BOX
    box = charparts.crop((x, y, x + w, y + h))
    font = Font(EN_FONT)
    os.makedirs(out, exist_ok=True)
    recorder, extra = en_tables()

    meta = []
    for k, (vid, question, answer) in enumerate(recorder):
        img, n, widest = render(font, atlas, question, answer)
        # The scroll track starts at x 876; without one the panel's inner
        # edge is at ~897. Row 59's "Even if it's an empty truth..." is 1259.
        room = 2 * ((876 if n > VISIBLE else 897) - 265)
        if widest > room:
            raise SystemExit('row %d: a line is %d texels, %d fit' % (k, widest, room))
        name = '%02d.tid' % k
        with open(os.path.join(out, name), 'wb') as fh:
            fh.write(tid_bytes(img, name))
        meta.append({'row': k, 'voice': int(vid), 'lines': n, 'question': question})
        if k == 0:
            img.save(os.path.join(out, 'preview00.png'))
    if asm_lines() != [m['lines'] for m in meta]:
        raise SystemExit('us_lines in unlsub.s does not match the text: %r'
                         % [m['lines'] for m in meta])

    widest = (0, '')
    for vid, text in extra:
        img, w = render_line(font, box, text)
        widest = max(widest, (w, text))
        name = '%d.tid' % int(vid)
        with open(os.path.join(out, name), 'wb') as fh:
            fh.write(tid_bytes(img, name))
        if vid == '011120':
            img.save(os.path.join(out, 'preview_line.png'))
    if widest[0] > LINE_ROOM:
        raise SystemExit('Extra line %r is %d texels, the window is %d'
                         % (widest[1], widest[0], LINE_ROOM))

    with open(os.path.join(out, 'rows.json'), 'w') as fh:
        json.dump({'recorder': meta, 'extra': [int(v) for v, _t in extra]},
                  fh, ensure_ascii=False, indent=1)
    print('%d recorder textures (%d scroll), %d Extra lines (widest %d of %d) -> %s'
          % (len(meta), sum(1 for m in meta if m['lines'] > VISIBLE), len(extra),
             widest[0], LINE_ROOM, out))


# --- GAME_02.cpk -----------------------------------------------------------

SUBDIR = 'VOICERECORDER/SUBTITLE'
SPARE = 0x4000                        # left between the GTOC and the content


def grow_gtoc(prefix, hdr, toc_rows):
    """New GTOC packet with one Fdata node per row of toc_rows.

    The GTOC is one row of (Glink, Flink, Attr, Gdata, Fdata, AttrData); the
    three blobs sit back to back in its data section in that order. Fdata is
    the file tree voicesub.fdata_rows() describes, one node per file plus the
    root, and Flink is its node count.
    """
    from cpk import UTF
    from patch_sub import utf_header, rebuild_rows
    import voicesub
    at = prefix.find(b'@UTF', hdr['GtocOffset'], hdr['GtocOffset'] + 32)
    gh = utf_header(prefix, at)
    g = UTF(bytes(prefix[at:at + 8 + gh['tsize']]), 0)
    if g.nrows != 1 or [c[0] for c in g.cols] != \
            ['Glink', 'Flink', 'Attr', 'Gdata', 'Fdata', 'AttrData']:
        raise SystemExit('unexpected GTOC columns')
    row, meta = g.rows[0], g.meta[0]
    blobs = [bytes(row[k]) for k in ('Gdata', 'Fdata', 'AttrData')]
    cells = [struct.unpack_from('>II', g.b, meta[k][0]) for k in ('Gdata', 'Fdata', 'AttrData')]
    if cells != [(0, len(blobs[0])), (len(blobs[0]), len(blobs[1])),
                 (len(blobs[0]) + len(blobs[1]), len(blobs[2]))]:
        raise SystemExit('GTOC blobs are not back to back: %r' % cells)
    if 8 + gh['data'] + sum(len(b) for b in blobs) != 8 + gh['tsize']:
        raise SystemExit('GTOC data section does not end the table')

    nodes = voicesub.fdata_rows(toc_rows)
    fdata = rebuild_rows(blobs[1], b''.join(struct.pack('>iii', *n) for n in nodes))
    packet = bytearray(g.b[:8 + gh['data']])
    struct.pack_into('>I', packet, meta['Flink'][0], len(nodes))
    struct.pack_into('>II', packet, meta['Fdata'][0], len(blobs[0]), len(fdata))
    struct.pack_into('>II', packet, meta['AttrData'][0],
                     len(blobs[0]) + len(fdata), len(blobs[2]))
    packet += blobs[0] + fdata + blobs[2]
    struct.pack_into('>I', packet, 4, len(packet) - 8)
    check = UTF(bytes(packet), 0).rows[0]
    got = UTF(bytes(check['Fdata']), 0).rows
    if check['Flink'] != len(nodes) or \
            [(r['Next'], r['Child'], r['SortFlink']) for r in got] != nodes:
        raise SystemExit('new GTOC does not read back')
    return bytes(packet)


def cmd_cpk(src, dst, texdir):
    """Write src plus SUBDIR/<every .tid in texdir> to dst.

    Rows go where CRI's case-insensitive order puts them, between
    VOICERECORDER/IMAGE/17.tid and VOICERECORDER/voiceRecorderBg.tid, with new
    IDs; the Fdata tree is regenerated from the TOC (voicesub.fdata_rows); file
    names reuse the string pool where it already has them.

    The stock TOC has 2,896 bytes of slack - enough for the 83 recorder rows,
    not for 225 more. So the GTOC and the content move down: TocOffset stays,
    the GTOC follows the new TOC, the content follows the GTOC (plus SPARE),
    and every FileOffset - relative to TocOffset - grows by the same amount.
    The content is copied byte for byte; the new files follow it, then the
    ETOC as before.
    """
    import shutil
    from cpk import UTF
    from patch_sub import utf_header, rebuild_rows, align_up
    import voicesub

    names = sorted((n for n in os.listdir(texdir) if n.endswith('.tid') and n[:-4].isdigit()),
                   key=lambda n: (SUBDIR + '/' + n).upper())
    blobs = [open(os.path.join(texdir, n), 'rb').read() for n in names]

    with open(src, 'rb') as fh:
        head = bytearray(fh.read(0x800))
        hdr = UTF(head, 0x10).rows[0]
        fh.seek(0)
        prefix = bytearray(fh.read(hdr['ContentOffset']))
        fh.seek(hdr['EtocOffset'])
        etoc = fh.read(hdr['EtocSize'])
    if hdr['EtocOffset'] + hdr['EtocSize'] != os.path.getsize(src):
        raise SystemExit('ETOC is not the last thing in %s' % src)
    if not hdr['TocOffset'] < hdr['GtocOffset'] < hdr['ContentOffset']:
        raise SystemExit('unexpected CPK layout')
    align = hdr['Align']
    toc = UTF(prefix, hdr['TocOffset'] + 0x10).rows
    if any(r['DirName'] == SUBDIR for r in toc):
        raise SystemExit('%s already carries %s' % (src, SUBDIR))

    toc_at = prefix.find(b'@UTF', hdr['TocOffset'], hdr['TocOffset'] + 32)
    gtoc_at = prefix.find(b'@UTF', hdr['GtocOffset'], hdr['GtocOffset'] + 32)
    th = utf_header(prefix, toc_at)
    if th['rowlen'] != 28 or th['nrows'] != len(toc):
        raise SystemExit('unexpected TOC layout')
    packet = bytes(prefix[toc_at:toc_at + 8 + th['tsize']])
    ph = utf_header(packet, 0)
    str_end = 8 + (ph['data'] if ph['data'] > ph['str'] else ph['tsize'])
    pool = packet[8 + ph['str']:str_end]
    extra = bytearray()

    def string(s):
        b = s.encode() + b'\0'
        i = pool.find(b)
        while i > 0 and pool[i - 1] != 0:
            i = pool.find(b, i + 1)
        if i < 0:
            i = len(pool) + len(extra)
            extra.extend(b)
        return i

    full = [(r['DirName'] + '/' if r['DirName'] else '') + r['FileName'] for r in toc]
    at = next(i for i, f in enumerate(full) if f.upper() > (SUBDIR + '/').upper())
    dir_off = string(SUBDIR)
    name_off = [string(n) for n in names]
    first_id = max(r['ID'] for r in toc) + 1

    def build_toc(delta, starts):
        rows = bytearray(packet[8 + ph['rows']:8 + ph['str']])
        for i in range(len(toc)):
            off = struct.unpack_from('>Q', rows, 28 * i + 16)[0]
            struct.pack_into('>Q', rows, 28 * i + 16, off + delta)
        new = b''.join(struct.pack('>IIIIQI', dir_off, name_off[k], len(blobs[k]),
                                   len(blobs[k]), starts[k] - hdr['TocOffset'], first_id + k)
                       for k in range(len(names)))
        rows[28 * at:28 * at] = new
        return rebuild_rows(packet, bytes(rows), bytes(extra))

    # sizes do not depend on the offsets, so lay out once with zeros
    probe = build_toc(0, [hdr['TocOffset']] * len(names))
    rows_new = UTF(probe, 0).rows
    new_gtoc = grow_gtoc(prefix, hdr, rows_new)
    toc_head = toc_at - hdr['TocOffset']
    gtoc_head = gtoc_at - hdr['GtocOffset']
    gtoc_off = max(hdr['GtocOffset'], align_up(hdr['TocOffset'] + toc_head + len(probe), align))
    content_off = max(hdr['ContentOffset'],
                      align_up(gtoc_off + gtoc_head + len(new_gtoc) + SPARE, align))
    delta = content_off - hdr['ContentOffset']
    old_end = hdr['ContentOffset'] + hdr['ContentSize']
    cursor = align_up(old_end + delta, align)
    starts = []
    for blob in blobs:
        cursor = align_up(cursor, align)
        starts.append(cursor)
        cursor += len(blob)
    content_end = cursor
    etoc_off = align_up(content_end, align)
    new_toc = build_toc(delta, starts)
    if len(new_toc) != len(probe):
        raise SystemExit('TOC size changed with its offsets')

    nt = UTF(new_toc, 0).rows
    nfull = [(r['DirName'] + '/' if r['DirName'] else '') + r['FileName'] for r in nt]
    if nfull != sorted(nfull, key=str.upper) or len(nt) != len(toc) + len(names):
        raise SystemExit('new TOC is not in CRI order')
    old_by ={(r['DirName'], r['FileName']): r for r in toc}
    for r in nt:
        o = old_by.get((r['DirName'], r['FileName']))
        if o is not None and (r['FileOffset'] - o['FileOffset'], r['FileSize'], r['ID']) != \
                (delta, o['FileSize'], o['ID']):
            raise SystemExit('row %s moved wrongly' % r['FileName'])

    # header
    head_utf = UTF(prefix, 0x10)
    out_head = bytearray(prefix[:hdr['TocOffset']])
    added = sum(len(b) for b in blobs)
    for name, value in (('TocSize', toc_head + len(new_toc)),
                        ('GtocOffset', gtoc_off), ('GtocSize', gtoc_head + len(new_gtoc)),
                        ('ContentOffset', content_off),
                        ('ContentSize', content_end - content_off),
                        ('EnabledPackedSize', hdr['EnabledPackedSize'] + added),
                        ('EnabledDataSize', hdr['EnabledDataSize'] + added),
                        ('EtocOffset', etoc_off),
                        ('Files', hdr['Files'] + len(names))):
        if not head_utf.patch(out_head, 0, name, value):
            raise SystemExit('cannot patch ' + name)

    tmp = dst + '.part'
    with open(src, 'rb') as fi, open(tmp, 'wb') as fo:
        fo.write(out_head)
        chunk = bytearray(prefix[hdr['TocOffset']:toc_at]) + new_toc
        struct.pack_into('<I', chunk, 8, len(new_toc))
        fo.write(chunk)
        fo.write(b'\0' * (gtoc_off - fo.tell()))
        chunk = bytearray(prefix[hdr['GtocOffset']:gtoc_at]) + new_gtoc
        struct.pack_into('<I', chunk, 8, len(new_gtoc))
        fo.write(chunk)
        fo.write(b'\0' * (content_off - fo.tell()))
        fi.seek(hdr['ContentOffset'])
        left = hdr['EtocOffset'] - hdr['ContentOffset']     # content and its padding
        while left:
            buf = fi.read(min(left, 64 << 20))
            fo.write(buf)
            left -= len(buf)
        for off, blob in zip(starts, blobs):
            fo.write(b'\0' * (off - fo.tell()))
            fo.write(blob)
        fo.write(b'\0' * (etoc_off - fo.tell()))
        fo.write(etoc)
    voicesub.fix_fdata(tmp)          # rewrites what grow_gtoc laid out; must agree
    shutil.move(tmp, dst)
    print('added %d files (%d bytes) at row %d; content moved %d bytes; TOC %d, GTOC %d -> %s'
          % (len(names), added, at, delta, toc_head + len(new_toc),
             gtoc_head + len(new_gtoc), dst))


def cmd_swap(src, dst, texdir):
    """Write src to dst with every SUBDIR file that differs from texdir replaced.

    For a CPK that already carries the subtitles and has been edited since -
    someone repacking its atlases - so rebuilding it from an older source with
    `cpk` would undo their work. The new bytes are appended after the content
    and only numeric cells change: each replaced row's FileSize, ExtractSize
    and FileOffset, and the header's ContentSize, EtocOffset and the two
    Enabled sizes. The old bytes stay behind, unreferenced. dst starts as an
    APFS clone of src.
    """
    import shutil
    import subprocess
    from cpk import UTF
    from patch_sub import align_up

    with open(src, 'rb') as fh:
        head = bytearray(fh.read(0x800))
        hdr = UTF(head, 0x10).rows[0]
        fh.seek(0)
        prefix = bytearray(fh.read(hdr['ContentOffset']))
        fh.seek(hdr['EtocOffset'])
        etoc = fh.read(hdr['EtocSize'])
        if hdr['EtocOffset'] + hdr['EtocSize'] != os.path.getsize(src):
            raise SystemExit('ETOC is not the last thing in %s' % src)
        toc_utf = UTF(prefix, hdr['TocOffset'] + 0x10)
        swaps = []
        for i, r in enumerate(toc_utf.rows):
            if r['DirName'] != SUBDIR:
                continue
            path = os.path.join(texdir, r['FileName'])
            if not os.path.exists(path):
                raise SystemExit('%s has no %s' % (texdir, r['FileName']))
            blob = open(path, 'rb').read()
            fh.seek(hdr['TocOffset'] + r['FileOffset'])
            if r['FileSize'] != len(blob) or fh.read(r['FileSize']) != blob:
                swaps.append((i, r['FileName'], blob))
    if not swaps:
        print('nothing differs')
        return

    end = hdr['ContentOffset'] + hdr['ContentSize']
    cursor = align_up(end, hdr['Align'])
    placed = []
    for i, name, blob in swaps:
        cursor = align_up(cursor, hdr['Align'])
        for cell, value in (('FileSize', len(blob)), ('ExtractSize', len(blob)),
                            ('FileOffset', cursor - hdr['TocOffset'])):
            if not toc_utf.patch(prefix, i, cell, value):
                raise SystemExit('cannot patch %s of %s' % (cell, name))
        placed.append((cursor, blob))
        cursor += len(blob)
    etoc_off = align_up(cursor, hdr['Align'])
    added = sum(len(b) for _i, _n, b in swaps)
    head_utf = UTF(prefix, 0x10)
    for cell, value in (('ContentSize', cursor - hdr['ContentOffset']),
                        ('EnabledPackedSize', hdr['EnabledPackedSize'] + added),
                        ('EnabledDataSize', hdr['EnabledDataSize'] + added),
                        ('EtocOffset', etoc_off)):
        if not head_utf.patch(prefix, 0, cell, value):
            raise SystemExit('cannot patch ' + cell)

    tmp = dst + '.part'
    if os.path.exists(tmp):
        os.remove(tmp)
    subprocess.run(['cp', '-c', src, tmp], check=True)
    with open(tmp, 'r+b') as fo:
        fo.seek(0)
        fo.write(prefix)
        fo.truncate(hdr['EtocOffset'])
        fo.seek(0, 2)
        for off, blob in placed:
            fo.write(b'\0' * (off - fo.tell()))
            fo.write(blob)
        fo.write(b'\0' * (etoc_off - fo.tell()))
        fo.write(etoc)
    shutil.move(tmp, dst)
    print('replaced %d files (%s ... %s), %d bytes appended -> %s'
          % (len(swaps), swaps[0][1], swaps[-1][1], added, dst))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'tex' and len(sys.argv) == 3:
        cmd_tex(sys.argv[2])
    elif cmd == 'cpk' and len(sys.argv) == 5:
        cmd_cpk(*sys.argv[2:5])
    elif cmd == 'swap' and len(sys.argv) == 5:
        cmd_swap(*sys.argv[2:5])
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
