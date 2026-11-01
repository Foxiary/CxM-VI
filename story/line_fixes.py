"""Single-line repairs to the STORY scripts, run before quotes.py.

    python3 story/line_fixes.py <STORY_01.cpk> <STORY_02.cpk> <out dir>

Each entry replaces one whole line of text, given in readable Vietnamese and
written in the 2021 encoding (voice/visub.py VI_2021). The new text must fit
the line's data block; the rest is zero-filled, so nothing in the file moves.
Every copy of the line in the script is replaced (507.DAT has the line twice:
the text section the game reads and a stale inline block). A line already
replaced is skipped, so the script can run over its own output.

Order of the STORY pipeline: line_fixes.py -> quotes.py -> lead_dash.py.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 've-es', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'voice'))
from cpk import CPK                                             # noqa: E402
import stcm2l                                                   # noqa: E402
from visub import VI_2021                                       # noqa: E402

# 警視総監 (Takaeda's title) is "Tổng thanh tra" everywhere: the -Unlimited-
# dictionary entry, its one line in STORY_02 404 and the name plate 415 already
# say so, while the 2021 STORY_01 text called him "Cục trưởng" (46 lines) and
# STORY_02 252 "bộ trưởng". "Tổng thanh tra" is four bytes longer, so a line
# whose block has no room loses a word ("ngài", "lại", "đấy") instead.
T = 'Tổng thanh tra'


def _title(*lines):
    """Lines where the title is simply swapped."""
    return [(ln, ln.replace('Cục trưởng cục cảnh sát', T + ' cảnh sát').replace('Cục trưởng', T))
            for ln in lines]


FIXES = {
    'STORY_01.cpk': {
        # Shiraishi route: left in English by the 2021 patch.
        # JP 白石さんは扉の隣の小窓を覗き込む。
        'SCRIPT/507.DAT': [('Shiraishi peered through the window near the door.',
                            'Shiraishi-san ngó qua ô cửa sổ nhỏ cạnh cửa.')],
        'SCRIPT/158.DAT': [('...Ngài Cục trưởng.', '...' + T + '.')],
        'SCRIPT/162.DAT': _title('Cục trưởng?! Ngài làm gì ở Shinjuku vậy?!',
                                 'Xin ngài bình tĩnh, Cục trưởng.'),
        'SCRIPT/163.DAT': _title('Bây giờ vừa đúng lúc Cục trưởng Takaeda'),
        'SCRIPT/165.DAT': [('Chưa bao giờ, tôi cảm thấy ngài Cục trưởng',
                            'Chưa bao giờ tôi thấy ngài ' + T)],
        'SCRIPT/208.DAT': [('Cục trưởng?! Sao ngài lại tới đây?', T + '?! Sao ngài tới đây?'),
                           ('...Ngài Cục trưởng. Tôi hiểu lí do ngài',
                            '...' + T + '. Tôi hiểu lí do ngài')]
                          + _title('Cho phép tôi nói thẳng, ngài Cục trưởng, ngài đang ưu'),
        'SCRIPT/210.DAT': [('Nghe nói Cục trưởng cũng đến đây đấy.',
                            'Nghe nói ' + T + ' cũng đến đây.')],
        'SCRIPT/309.DAT': [('Đặc biệt là Cục trưởng Takaeda.', 'Nhất là ' + T + ' Takaeda.')],
        'SCRIPT/408.DAT': _title('Cục trưởng đến Shinjuku rồi đó.',
                                 'Hả?! Cục trưởng cục cảnh sát Takaeda á?!',
                                 'Cục trưởng cục cảnh sát',
                                 '(Cục trưởng cục cảnh sát?!)',
                                 '(Cục trưởng Takaeda đây sao...)',
                                 'Có Cục trưởng ở đây, ai ai cũng mồ hôi',
                                 'Cục trưởng nhìn một lượt quanh phòng rồi',
                                 'nhiều vấn đề khi làm Cục trưởng.',
                                 'Tôi lặng lẽ nhìn ngài Cục trưởng Takaeda',
                                 'kiến nói chuyện riêng với ngài Cục trưởng nữa.')
                          + [('Nhưng nếu đích thân Cục trưởng đến tận đây',
                              'Nhưng nếu đích thân ' + T + ' đến đây'),
                             ('Vậy đúng là ngài Cục trưởng đã đến Shinjuku.',
                              'Vậy đúng là ' + T + ' đã đến Shinjuku.'),
                             ('Chi tiết là về cách Cục trưởng Takaeda nghiêm túc',
                              'Chi tiết về cách ' + T + ' Takaeda nghiêm túc'),
                             ('Còn ngài Cục trưởng Takaeda thì chẳng thèm',
                              'Còn ' + T + ' Takaeda thì chẳng thèm'),
                             ('chỉ quan tâm đến cái chức Cục trưởng của mình.',
                              'chỉ quan tâm đến chức ' + T + ' của mình.'),
                             ('Sasazuka-san đang nói chuyện với ngài Cục trưởng.',
                              'Sasazuka-san đang nói chuyện với ' + T + '.'),
                             ('Dứt lời, ngài Cục trưởng', 'Dứt lời, ' + T),
                             ('Cục trưởng của mình thôi.', T + ' của mình.'),
                             ('Minegishi nhanh chóng theo chân ngài Cục trưởng.',
                              'Minegishi nhanh chóng theo chân ' + T + '.')],
        'SCRIPT/409.DAT': _title('năng lượng là Cục trưởng Takaeda, ông ta la hét sáng giờ.'),
        'SCRIPT/410.DAT': _title('Khi các sĩ quan đều đã vào vị trí, ngài Cục trưởng',
                                 'Ngài Cục trưởng.',
                                 'Cục trưởng Takaeda. Tôi muốn một lần nữa thảo luận',
                                 'Cục trưởng Takaeda lườm Sasazuka-san',
                                 'Cục trưởng Takaeda chắc chẳng hiểu gì,',
                                 'Ngài Cục trưởng nghĩ ngợi trong chốc lát',
                                 'Và Cục trưởng Takaeda cũng đã hứa sẽ giúp')
                          + [('Cục trưởng Takaeda, mời ngài.', 'Mời ' + T + ' Takaeda.'),
                             ('rồi nhìn về phía Cục trưởng.', 'rồi nhìn về ' + T + '.'),
                             ('Tôi cúi đầu khi ngài Cục trưởng rời đi,',
                              'Tôi cúi đầu khi ' + T + ' rời đi,'),
                             # two narration lines already among the widest; shortened
                             # so they draw narrower than before
                             ('toàn bộ những đôi mắt kinh ngạc đều hướng về Cục trưởng Takaeda.',
                              'mọi ánh mắt kinh ngạc đều hướng về ' + T + ' Takaeda.'),
                             ('tới chỗ Cục trưởng, lúc này ông ta còn đang lau mồ hôi trên trán.',
                              'tới chỗ ' + T + ', ông ta còn đang lau mồ hôi trên trán.')],
        'SCRIPT/510.DAT': _title('Tôi nhận lệnh trực tiếp từ ngài Cục trưởng.',
                                 'Nạn nhân là con trai của thủ tướng nên Cục trưởng')
                          + [('Cục trưởng sẽ chỉ huy điều tra vụ này đấy.',
                              T + ' sẽ chỉ huy điều tra vụ này.'),
                             ('chính trị nên Cục trưởng Takaeda mới đích thân điều tra.',
                              'chính trị nên ' + T + ' Takaeda mới trực tiếp điều tra.')],
    },
    'STORY_02.cpk': {
        # everyone at the table at once: one pair of quotes, not two
        'SCRIPT/509.DAT': [('““Mời cả nhà ăn cơm.””', '“Mời cả nhà ăn cơm.”')],
        # JP 警察庁や警視総監は / 警視総監の代理が来るらしい
        'SCRIPT/252.DAT': [('Vì vậy, cả sở cảnh sát trung ương và ngài bộ trưởng',
                            'Vì vậy, cả sở cảnh sát trung ương và ngài ' + T),
                           ('ngài bộ trưởng sắp đến đây rồi.', T + ' sắp đến đây rồi.')],
        'SCRIPT/404.DAT': [('là ý kiến của ngài tổng thanh tra Takaeda...',
                            'là ý kiến của ngài ' + T + ' Takaeda...')],
    },
}


def enc(text):
    b = ''.join(VI_2021.get(ch, ch) for ch in text).encode('utf-8')
    b.decode('utf-8').encode('cp932')        # STORY text must stay in CP932
    return b


def fix_script(raw, pairs):
    buf, n = bytearray(raw), 0
    for old, new in pairs:
        o, nb = enc(old), enc(new)
        found = 0
        start = 0
        while True:
            at = buf.find(o + b'\0', start)
            if at < 0:
                break
            _flag, nw, one, ln = struct.unpack_from('<4I', buf, at - 16)
            assert one == 1 and ln == nw * 4 and len(nb) < ln, hex(at)
            buf[at:at + ln] = nb.ljust(ln, b'\0')
            found += 1
            start = at + ln
        if not found:
            assert nb + b'\0' in buf, 'neither old nor new line: %r' % old
        n += found
    return bytes(buf), n


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    os.makedirs(sys.argv[3], exist_ok=True)
    for path in sys.argv[1:3]:
        name = os.path.basename(path)
        cpk = CPK(path)
        rows = {f: r for _i, f, r in cpk.files()}
        repl = {}
        for full, pairs in FIXES[name].items():
            raw = cpk.read(rows[full])
            new, n = fix_script(raw, pairs)
            if n:
                stcm2l.Script(new)
                repl[full] = new
            print('%s %s: %d line(s) replaced' % (name, full, n))
        out = os.path.join(sys.argv[3], name)
        cpk.repack(out, repl)
        check = CPK(out)
        for _i, full, row in check.files():
            assert check.read(row) == repl.get(full, cpk.read(rows[full])), full
        assert check.raw[check.content_off:min(check.base + r['FileOffset'] for _i, _f, r in check.files())] \
            == cpk.raw[cpk.content_off:min(cpk.base + r['FileOffset'] for _i, _f, r in cpk.files())]
        print('  verified every file and the tables before them')


if __name__ == '__main__':
    main()
