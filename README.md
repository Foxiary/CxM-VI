# CxM-VI

Công cụ dựng bản Việt hoá cho **Collar×Malice** và **Collar×Malice -Unlimited-**
trên Switch (bản Nhật, title `01002B400E9DA000`), làm tiếp trên PatchVietHoa 2021.

Những gì repo này thêm vào game:

- Phụ đề tiếng Anh cho Voice Recorder của game chính và -Unlimited-, giống bản USA.
- Phụ đề cho câu nhân vật nói ở màn Extra của -Unlimited-.
- Khoảng cách chữ đều ở mọi màn hình, kể cả danh sách Load/Save.
- Danh sách Dictionary cắt tên ở cuối thanh đỏ và cho chữ chạy khi chọn.
- Chữ trên texture của màn Extra / Album / BGM / danh sách ending.

Repo chỉ chứa mã. Không có file nào của game ở đây.

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `voice/` | Sửa `exefs/main`: phụ đề, marquee Dictionary, dời segment. `voicesub.py` là lệnh build |
| `save/` | File `.ips` cho khoảng cách chữ và danh sách Load/Save; ngắt dòng Dictionary |
| `album/` | Texture màn Extra / Album / BGM / ending và font của chúng |
| `story/` | Sửa kịch bản STORY |
| `event/` | Bộ nén DXT5 nhỏ mà các thư mục khác dùng |
| `ve-es/` | Submodule [VE-ES](https://github.com/Foxiary/VE-ES): bộ đọc/ghi `.cpk`, `.tid`, `.ffu`, `.gbin`, NSO dùng chung |
| `work/` | Dữ liệu game và mọi file sinh ra. Bị gitignore, mỗi máy tự chuẩn bị |

Ghi chú kỹ thuật (định dạng, địa chỉ, những bẫy đã gặp) nằm trong `CLAUDE.md`.

## Chuẩn bị

```bash
git clone --recursive https://github.com/Foxiary/CxM-VI.git
```

Nếu đã clone mà chưa có `ve-es/`:

```bash
git submodule update --init
```

Cần có:

- Python 3, Pillow, `etcpak` (để nén texture DXT5).
- LLVM (`brew install llvm`): `voicesub.py` gọi `clang` và `ld.lld` trong `/opt/homebrew/bin`.
- `prod.keys` để trích file từ NSP.

Dữ liệu cần đặt vào `work/` trước khi build:

| Đường dẫn | Lấy từ |
|---|---|
| `work/voice/jp-exefs/main` | `exefs/main` của bản Nhật gốc |
| `work/voice/en-unl/main` | `exefs/main` của bản USA -Unlimited- (`0100E3B00F412000` v0) |
| `work/voice/en-unl/sysfont.ffu` | `SYSTEM.CPK` → `WINDOW/FONT/` của bản USA -Unlimited- |
| `work/voice/en-unl/voiceRecorderParts.tid`, `extra_charParts.tid` | `GAME_02.CPK` của bản USA -Unlimited- |
| `work/voice/en-unl/jp_template.tid` | Một file `.tid` DXT5 bất kỳ của bản Nhật, chỉ để lấy header |

## Lệnh thường dùng

Dựng `exefs/main` và cài vào Ryujinx:

```bash
python3 voice/voicesub.py exe --install ~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa
```

Vẽ texture phụ đề -Unlimited-:

```bash
python3 voice/unlsub.py tex work/voice/unlsub/tex
```

Thêm texture phụ đề -Unlimited- vào một GAME_02.cpk (GAME_02.cpk gốc phải chưa có chúng):

```bash
python3 voice/unlsub.py cpk GAME_02.cpk work/voice/GAME_02.new.cpk work/voice/unlsub/tex
```

Tạo file `.ips` cho khoảng cách chữ và danh sách Load/Save:

```bash
python3 save/savelist_ips.py work/voice/jp-exefs/main ~/Documents/Ryujinx/mods/contents/01002b400e9da000/PatchVietHoa/exefs
```

Sau khi build, chép GAME_02.cpk mới vào cả hai thư mục mod (`mods/.../PatchVietHoa` và
`sdcard/atmosphere/...`). Hai bản phải giống hệt nhau.
