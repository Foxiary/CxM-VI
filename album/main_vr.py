"""Collar x Malice (main game) Voice Recorder: the five question titles, in the English letters.

The main game's English Voice Recorder (GAME_01 VOICERECORDER/voiceRecorderParts.tid) is set in
the same face as the BGM / Movie lists - stem/cap 0.085 against 0.086, unlike -Unlimited-, whose
Voice Recorder uses a heavier face. The patch's Vietnamese titles there were drawn in a system
font. This redraws them with the letters of this very atlas - cut out of the five English titles
and the "Aiji 01".."Kageyuki 01" names by vr_letters.VRSetter, which also snaps every letter onto
one baseline and borrows only what the English lacks (N, h, the Vietnamese marks) from the BGM
letters - at the size and baseline of the English titles, with new wording:

    Basic info          -> Lý lịch trích ngang
    Hobbies/Skills      -> Sở thích/Kỹ năng
    Likes               -> Những thứ anh thích
    Dislikes            -> Những thứ anh ghét
    Your type of woman  -> Mẫu phụ nữ anh thích

    ~/Documents/GitHub/CxM-VI/work/album/.venv/bin/python main_vr.py --dry-run
    ~/Documents/GitHub/CxM-VI/work/album/.venv/bin/python main_vr.py

The texture is stored uncompressed in GAME_01.cpk, so it is written in place, same size, into
every copy the game loads. The first run keeps the texture it replaces in
work/album/backup-truoc-chu-en/voiceRecorderParts.tid (--restore puts it back).
"""
import argparse, os, unicodedata


from PIL import Image                                         # noqa: E402
import album_en_letters as ae                                 # noqa: E402
import album_fontsize as af                                   # noqa: E402
import en_glyphs as eg                                        # noqa: E402
import unlimited_album as ua                                  # noqa: E402
import vr_letters as vl                                       # noqa: E402
from tid import TID                                           # noqa: E402

NAME = 'VOICERECORDER/voiceRecorderParts.tid'
CPKS = ae.CPKS + [os.path.expanduser(
    '~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa/romfs/CONTENTS/GAME_01.cpk')]
BACKUP = os.path.join(ae.DATA, 'backup-truoc-chu-en', 'voiceRecorderParts.tid')
PREVIEW = os.path.join(ae.DATA, 'preview-chu-en')
PNG_OUT = os.path.join(ae.DATA, 'anh-sua', 'VOICERECORDER', 'voiceRecorderParts.png')

TITLES = ['Lý lịch trích ngang', 'Sở thích/Kỹ năng', 'Những thứ anh thích', 'Những thứ anh ghét',
          'Mẫu phụ nữ anh thích']
# Measured off the English atlas: rows of 64 px from y 128; the title text starts at x 962-964
# (after the "Aiji 05"-style number sprites, which end at 940-956); capitals 44-48 px tall,
# baseline row + 52/53; the widest English title ends at x 1430.
ROW0, ROW_H = 128, 64
INK_X, INK_R = 963, 1430
CLEAR_X0 = 958
# Baseline: the English titles and the NUMBER column ("Aiji 01") both stand on row + 52 (flat
# letters end on row 51, round ones on 52). The earlier version set the titles at + 44 with
# a smaller BGM cap to make room for the marks, and they read 8 px higher than the numbers.
# Here the letters are the atlas's own, at the English size, on the English baseline; marks
# keep the 3 px gap this atlas has between the dot of i and its stem.
BASE = 52
# This atlas's x-height letters are tall (26 px for a 44-50 px cap), so a dot below under a, u
# reaches row + 65 at the English baseline; the dot is tucked to MARK_GAP_BELOW under the letter.
MARK_GAP_BELOW = 1
EN_ATLAS_ROWS = [('Basic info', 0), ('Hobbies/Skills', 1), ('Likes', 2), ('Dislikes', 3), ('Your type of woman', 4)]
EN_NAMES = [('Aiji', 0), ('Kei', 1), ('Mineo', 2), ('Takeru', 3), ('Kageyuki', 4)]


def english_atlas():
    """Alpha of the main game's English Voice Recorder and the boxes of its English lines."""
    en = eg.read_en([NAME])
    A = TID(en[NAME]).image().convert('RGBA').getchannel('A')
    jobs = [(t, (962, ROW0 + ROW_H * r, 1472, ROW0 + ROW_H * (r + 1))) for t, r in EN_ATLAS_ROWS]
    jobs += [(n, (0, ROW0 + ROW_H * r, 140, ROW0 + ROW_H * (r + 1))) for n, r in EN_NAMES]
    return A, jobs, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--restore', action='store_true')
    a = ap.parse_args()

    off, size = af.locate(CPKS[0], [NAME])[NAME]
    for p in CPKS[1:]:
        assert af.locate(p, [NAME])[NAME] == (off, size), p
    if not os.path.exists(BACKUP):
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        open(BACKUP, 'wb').write(ae.read_at(CPKS[0], off, size))
        print('saved current texture ->', BACKUP)
    raw = open(BACKUP, 'rb').read()
    assert len(raw) == size

    if a.restore:
        new = raw
    else:
        en = eg.read_en([v[0] for v in ae.TEXTURES.values()])
        libs, used = {}, {}
        for k in ae.TEXTURES:
            libs[k], used[k] = eg.build(k, en)
        vl.MARK_GAP = 3
        setter = vl.VRSetter(libs, used, atlas=english_atlas())
        setter.gap_below = MARK_GAP_BELOW
        print('English main-game Voice Recorder: %d lines, letters %s; cap %.0f px, stem %.1f px'
              % (len(setter.vr_lines), ''.join(sorted(c for c, v in setter.vr_src.items() if v == 'vr')),
                 setter.vr_cap, setter.target_stem))
        k = 1.0
        base_img = TID(raw).image().convert('RGBA')
        img = base_img.copy()
        for r, t in enumerate(TITLES):
            y0 = ROW0 + ROW_H * r
            ua.clear(img, (CLEAR_X0, y0, img.width, y0 + ROW_H))
            x0, x1, s = ua.place(img, setter, unicodedata.normalize('NFC', t), INK_X, INK_R, y0 + BASE,
                                 BASE, ROW_H - BASE, k)
            bb = img.getchannel('A').crop((CLEAR_X0, y0, img.width, y0 + ROW_H)).point(
                lambda v: 255 if v > 8 else 0).getbbox()
            print('  %-22s ink x %d..%d  y %d..%d  scale %.3f' % (t, x0, x1, bb[1], bb[3] - 1, s))
            assert bb[1] > 0 and bb[3] < ROW_H, ('marks or descenders leave the row', t)
        if setter.drawn:
            print('  letters from Old Standard:', ''.join(sorted(setter.drawn)))
        new, changed = ae.encode(raw, base_img, img)
        print('  %d DXT5 blocks re-encoded' % changed)
        os.makedirs(PREVIEW, exist_ok=True)
        dec = TID(new).image().convert('RGBA')
        dec.save(os.path.join(PREVIEW, 'voiceRecorderParts.png'))
        if a.dry_run:
            return
        os.makedirs(os.path.dirname(PNG_OUT), exist_ok=True)
        dec.save(PNG_OUT)
    for p in CPKS:
        with open(p, 'r+b') as f:
            f.seek(off)
            f.write(new)
        assert ae.read_at(p, off, size) == new
        print('wrote', NAME, 'into', p)


if __name__ == '__main__':
    main()
