# Cách biên dịch trên Overleaf

Mỗi tệp .zip là một project riêng, **tự chứa** — không phải sửa gì sau khi up.

| Tệp zip | Compiler cần chọn |
|---|---|
| `da2_tai_lieu_overleaf.zip` — tài liệu sản phẩm | **pdfLaTeX** |
| `da2_slide_overleaf.zip` — slide trình chiếu | **XeLaTeX** |

Các bước (làm riêng cho từng gói):

1. https://www.overleaf.com → **New Project** → **Upload Project** → kéo thả tệp zip.
2. **Menu** (góc trên bên trái) → **Compiler** → chọn theo bảng trên.
3. **Recompile**.

`main.tex` trong mỗi gói được Overleaf tự nhận làm Main document nên không phải chọn tay.

## Vì sao hai gói dùng hai bộ máy khác nhau

- Tài liệu dùng gói `vietnam` (vntex) theo mẫu của trường — gói **8-bit**, chỉ chạy với
  **pdfLaTeX**. Chọn XeLaTeX sẽ lỗi bảng mã.
- Slide dùng `fontspec`, chỉ chạy với **XeLaTeX**. Chọn pdfLaTeX sẽ báo
  *"Fatal Package fontspec Error: The fontspec package requires either XeTeX or LuaTeX"*.

## Lưu ý

- `main.tex` của tài liệu đã **gộp sẵn** số liệu (`metrics_data`), bảng ánh xạ tiếng Việt
  cho phần code (`vietnamese_listings`) và toàn bộ mã nguồn phụ lục. Không cần thư mục
  `code/`, không cần `\input` tệp nào khác.
- Sửa nội dung thì sửa ở `docs/latex/da2_tai_lieu_san_pham.tex` (bản ở máy) rồi chạy lại
  `python docs/latex/build_overleaf.py` — đừng sửa thẳng `main.tex` trong gói, lần build sau sẽ mất.
- Huấn luyện lại thì chạy `python docs/latex/make_tex_data.py` trước khi đóng gói để số liệu
  trong báo cáo khớp với mô hình mới.
