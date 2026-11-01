"""Text of the character name plates (ADV/EFFECT/401-434), as the mod writes it.

NAMES: family name first, the way the 2021 scripts name every speaker
("Yanagi Aiji", not the English "Aiji Yanagi"). Spellings follow the speaker
names in STORY_01/STORY_02 (Sanjou, Souda, Kenzou, Yuusaku); ages are the
English plates' own (disc 2 remakes 426-434 are a year or two older, and 417
says 26 on disc 1, 24 on disc 2 - kept as each disc has it).

TITLES: the plates' title line in the mod's own Vietnamese terms (see the
comments for where each comes from). One entry per line of the plate.
"""

# plate -> (family, given, age on disc 1, age on disc 2)
NAMES = {
    401: ('Yanagi', 'Aiji', 28, 28),
    402: ('Okazaki', 'Kei', 26, 26),
    403: ('Enomoto', 'Mineo', 23, 23),
    404: ('Sasazuka', 'Takeru', 24, 24),
    405: ('Shiraishi', 'Kageyuki', 29, 29),
    406: ('Hoshino', 'Kazuki', 18, 18),
    407: ('Sakuragawa', 'Kotoho', 27, 27),
    408: ('Mochida', 'Masanobu', 32, 32),
    409: ('Saeki', 'Yuzuru', 23, 23),
    410: ('Morioka', 'Hajime', 38, 38),
    411: ('Minegishi', 'Seiji', 32, 32),
    412: ('Yoshinari', 'Hideaki', 24, 24),
    413: ('Satake', 'Kenzou', 53, 53),
    414: ('Mukai', 'Eriko', 27, 27),
    415: ('Takaeda', 'Yuusaku', 58, 58),
    416: ('Isshiki', 'Yasuhiro', 25, 25),
    417: ('Mikuni', 'Rei', 26, 24),
    418: ('Sanjou', 'Keisuke', 29, 29),
    421: ('Souda', 'Manabu', 20, 20),
    422: ('Sugawara', 'Rika', 25, 25),
    423: ('Sera', 'Akito', 18, 18),
    424: ('Kobayashi', 'Hanako', 20, 20),
    425: ('Ogata', 'Tomoki', 34, 34),
    # disc 2 only
    426: ('Someya', 'Yuka', None, 18),
    427: ('Tachibana', 'Chisato', None, 27),
    428: ('Yanagi', 'Yuji', None, 35),
    429: ('Sakuragawa', 'Kotoho', None, 28),
    430: ('Mochida', 'Masanobu', None, 33),
    431: ('Morioka', 'Hajime', None, 40),
    432: ('Minegishi', 'Seiji', None, 33),
    433: ('Yoshinari', 'Hideaki', None, 25),
    434: ('Mukai', 'Eriko', None, 29),
}

# plate -> (English as on the plate, Vietnamese lines). The Vietnamese is the
# mod's own wording, found in the 2021 STORY text and dbDictionary (installed
# SYSTEM/STORY cpk, read back through VI_2021); the source line is noted for
# each. Japanese plate text in brackets.
#   警視庁 -> "Sở cảnh sát Tokyo" (Okazaki's file: "Phòng An ninh trực thuộc Sở
#     cảnh sát Tokyo - SP"; Minegishi: "phòng điều tra tội phạm sở cảnh sát Tokyo")
#   新宿署 -> "Đồn Shinjuku" (dictionary title; "đồn Shinjuku" in the script)
TITLES = {
    # 元・警視庁捜査一課; "Tôi là Yanagi Aiji. Cựu cảnh sát từ Ban Điều tra số 1."
    401: ('(formerly) Police HQ, / Investigations Section 1',
          ['(cựu) Sở cảnh sát Tokyo,', 'Ban Điều tra số 1']),
    # 警視庁 警備部警護課; "Phòng An ninh trực thuộc Sở cảnh sát Tokyo - SP."
    402: ('Police HQ, Security Police Division',
          ['Sở cảnh sát Tokyo,', 'Phòng An ninh (SP)']),
    # 元・新宿署第二機動捜査隊; "Cựu cảnh sát cơ động Đội 2.", dictionary "Đội cơ động 2"
    403: ('(formerly) Shinjuku Station, / Field Ops Team 2',
          ['(cựu) Đồn Shinjuku,', 'Đội cơ động 2']),
    # 元・警視庁サイバー犯罪対策課; "Tôi từng ở Ban phòng chống tội phạm công nghệ cao."
    404: ('(formerly) Police HQ, / Cybercrime Prevention',
          ['(cựu) Sở cảnh sát Tokyo,', 'Ban phòng chống tội phạm công nghệ cao']),
    # 警視庁 科学捜査研究所 / 新宿署 機動捜査支援; "Tôi là Shiraishi Kageyuki, đến từ phòng
    # nghiên cứu tội phạm."; "Tôi là Shiraishi Kageyuki, làm ở đội hỗ trợ cơ động"
    405: ('Police HQ, Crime Lab / Shinjuku Station, Field Ops Research',
          ['Sở cảnh sát Tokyo,', 'Phòng nghiên cứu tội phạm', 'Đồn Shinjuku, Đội hỗ trợ cơ động']),
    # 琴嶺学園 三年生; "Hoshino Kazuki. Học năm ba trường trung học Kotomine."
    406: ('Kotomine Academy, 3rd year student',
          ['Trường trung học Kotomine,', 'học sinh năm ba']),
    # 新宿署鑑識課; "Tên cô ấy là Sakuragawa Kotoho, đang làm việc tại ban giám định."
    407: ('Shinjuku Station, Forensics',
          ['Đồn Shinjuku, Ban giám định']),
    # 地域課 特殊地域防犯対策室; Morioka: "Mochida Masanobu và Hoshino Ichika từ Đặc nhiệm
    # Phòng chống Tội phạm khu vực."; "đội đặc nhiệm chống tội phạm khu vực, cơ quan cảnh sát địa phương"
    408: ('Local Station, / Special Regions Crime Prevention Office',
          ['Cảnh sát địa phương,', 'Đặc nhiệm Phòng chống Tội phạm khu vực']),
    # 地域課 交番勤務; 交番 is "bốt cảnh sát" in the script ("ai từ bên bốt cảnh sát đến cả")
    409: ('Local Station, police box',
          ['Cảnh sát địa phương, bốt cảnh sát']),
    # 警視庁 捜査一課; "Trưởng Ban điều tra số 1, Morioka Hajime"
    410: ('Police HQ, Investigations Section 1',
          ['Sở cảnh sát Tokyo,', 'Ban Điều tra số 1']),
    # "Tôi là Chánh thanh tra Minegishi Seiji từ ban điều tra số 1."
    411: ('Police HQ, Investigations Section 1',
          ['Sở cảnh sát Tokyo,', 'Ban Điều tra số 1']),
    412: ('Police HQ, Security Police Division',
          ['Sở cảnh sát Tokyo,', 'Phòng An ninh (SP)']),
    # 新宿署 第二機動捜査隊; "Satake-san giống như ông bố của cả đội cơ động."
    413: ('Shinjuku Station, Field Ops Team 2',
          ['Đồn Shinjuku, Đội cơ động 2']),
    # same units as 405; "Mukai-san ở đội hỗ trợ cơ động"
    414: ('Police HQ, Crime Lab / Shinjuku Station, Field Ops Support',
          ['Sở cảnh sát Tokyo,', 'Phòng nghiên cứu tội phạm', 'Đồn Shinjuku, Đội hỗ trợ cơ động']),
    # 警視総監; dictionary title "Tổng thanh tra" = "Giám đốc sở cảnh sát Tokyo";
    # "chỉ sau mỗi Tổng thanh tra cảnh sát". The script calls him "Cục trưởng Takaeda".
    415: ('Superintendent General, / Metropolitan Police',
          ['Tổng thanh tra', 'Sở cảnh sát Tokyo']),
    # ミュージシャン; "trở thành nhạc sĩ"
    416: ('Musician',
          ['Nhạc sĩ']),
    # 衆議院議員; "Mikuni Rei, thành viên quốc hội."
    417: ('Member of the Lower House',
          ['Thành viên quốc hội']),
    # 元・警視庁 交通機動隊; "Anh ta được bổ nhiệm vào đội cảnh sát giao thông."
    418: ('(formerly) Police HQ, / Mobile Traffic Team',
          ['(cựu) Sở cảnh sát Tokyo,', 'Đội cảnh sát giao thông']),
    # 無職; "Nạn nhân, Tanaka Satoru. Một kẻ thất nghiệp."
    421: ('Unemployed',
          ['Thất nghiệp']),
    # 会社員; "Sugawara Rika, một nhân viên văn phòng, 25 tuổi..."
    422: ('Office worker',
          ['Nhân viên văn phòng']),
    423: ('Kotomine Academy, 3rd year student',
          ['Trường trung học Kotomine,', 'học sinh năm ba']),
    # フリーター; no word for it in the mod ("Làm việc trong một cửa hàng bán quần áo."),
    # wording chosen by the translator
    424: ('Part-timer',
          ['Nhân viên bán thời gian']),
    # 会社員; "Ogata, một nhân viên văn phòng"
    425: ('Office worker',
          ['Nhân viên văn phòng']),
    # 女子高校生; "nữ sinh cấp ba"
    426: ('High School Student',
          ['Nữ sinh cấp ba']),
    # 依頼人; the speaker label "Người ủy thác", and "anh là người ủy thác đến để nói chuyện ạ?"
    427: ('Client',
          ['Người ủy thác']),
    # 会社員 in JP (English "Corporate Executive"); the mod's word for 会社員 as on 422/425
    428: ('Corporate Executive',
          ['Nhân viên văn phòng']),
    429: ('Forensics, Shinjuku Station',
          ['Ban giám định, Đồn Shinjuku']),
    430: ('Special Regions Crime Prevention Office',
          ['Đặc nhiệm Phòng chống Tội phạm khu vực']),
    431: ('Investigations Division 1, Police HQ',
          ['Ban Điều tra số 1,', 'Sở cảnh sát Tokyo']),
    432: ('Investigations Division 1, Police HQ',
          ['Ban Điều tra số 1,', 'Sở cảnh sát Tokyo']),
    433: ('Security Police Division, Police HQ',
          ['Phòng An ninh (SP),', 'Sở cảnh sát Tokyo']),
    # 警視庁 科学捜査研究所
    434: ('NRIPS, Police HQ',
          ['Phòng nghiên cứu tội phạm,', 'Sở cảnh sát Tokyo']),
}
