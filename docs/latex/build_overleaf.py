"""Đóng gói tài liệu LaTeX thành các tệp .zip kéo thả thẳng lên Overleaf.

Mỗi gói là **một project Overleaf phẳng, tự chứa**: chỉ cần Upload Project, chọn
Compiler rồi Recompile, không phải sửa gì thêm.

    da2_tai_lieu_overleaf.zip     Compiler: pdfLaTeX
        main.tex                  <- gộp sẵn metrics_data, bảng ánh xạ tiếng Việt
                                     và toàn bộ mã nguồn phụ lục
        logo.jpeg, search.png     <- ảnh trang bìa
        *.png                     <- hình được chèn, tên phẳng

    da2_slide_overleaf.zip        Compiler: XeLaTeX
        main.tex
        *.png                     <- chỉ những hình slide dùng tới

Tách làm hai gói vì tài liệu dùng `vietnam` (chỉ chạy pdfLaTeX) còn slide dùng
`fontspec` (chỉ chạy XeLaTeX) — để chung một project thì mỗi lần đổi Main document
lại phải đổi Compiler, rất dễ quên và sinh lỗi khó hiểu.

Chạy:  python docs/latex/build_overleaf.py
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

import make_listings_map

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parents[1]
BUILD = DOCS / "overleaf"

COVER_IMAGES = ["logo.jpeg", "search.png"]

PACKAGES = {
    "da2_tai_lieu_overleaf.zip": {
        "tex": "da2_tai_lieu_san_pham.tex",
        "engine": "pdfLaTeX",
    },
    "da2_tai_lieu_overleaf_gon.zip": {
        "tex": "da2_tai_lieu_san_pham.tex",
        "engine": "pdfLaTeX",
        "trim_appendix": True,
    },
    "da2_slide_overleaf.zip": {
        "tex": "da2_slide.tex",
        "engine": "XeLaTeX",
    },
}

# The compact package keeps the files the lecture shows (train.py, main.py, requirements.txt,
# render.yaml) and drops the rest of the appendix, for when Overleaf reports "compile timed out".
APPENDIX_OPTIONAL = ["evaluate.py", "schemas.py", "model_service.py", "smoke_test.py", "make_sample_request.py",
                     "test_api.py", "test_model.py", "app.js"]

TRIM_NOTE = (
    "\n\\noindent\\textit{Phần phụ lục này in nguyên văn các tệp chính. Mã nguồn đầy đủ "
    "(\\texttt{evaluate.py}, \\texttt{schemas.py}, \\texttt{model\\_service.py}, kiểm thử, giao diện) "
    "xem trong kho mã nguồn kèm theo sản phẩm.}\n"
)

GUIDE = """# Cách biên dịch trên Overleaf

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
  `code/`, không cần `\\input` tệp nào khác.
- Sửa nội dung thì sửa ở `docs/latex/da2_tai_lieu_san_pham.tex` (bản ở máy) rồi chạy lại
  `python docs/latex/build_overleaf.py` — đừng sửa thẳng `main.tex` trong gói, lần build sau sẽ mất.
- Huấn luyện lại thì chạy `python docs/latex/make_tex_data.py` trước khi đóng gói để số liệu
  trong báo cáo khớp với mô hình mới.
"""


def listing_chars(text: str) -> set[str]:
    """Tập ký tự ngoài ASCII nằm bên trong các khối lstlisting."""
    blocks = re.findall(
        r"\\begin\{lstlisting\}(?:\[[^\]]*\])?\n(.*?)\\end\{lstlisting\}", text, re.S)
    return {ch for block in blocks for ch in block if ord(ch) > 127}


def inline_inputs(text: str) -> str:
    """Thay \\input{ten} bằng nội dung thật của docs/ten.tex.

    Riêng `vietnamese_listings` được sinh lại **tối thiểu**: chỉ những ký tự thật sự
    có trong code. Bảng đầy đủ 157 mục nhân với ~36.000 ký tự code là 5,7 triệu phép
    so khớp, đủ để Overleaf báo "compile timed out".
    """
    used = listing_chars(text)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        path = DOCS / (name if name.endswith(".tex") else name + ".tex")
        if path.stem == "vietnamese_listings":
            body = make_listings_map.render(used)
            note = f" (bảng tối thiểu: {len(used)} ký tự thay vì bảng đầy đủ)"
        else:
            body = path.read_text(encoding="utf-8")
            note = ""
        return (f"% ----- gộp từ {path.name}{note} -----\n{body.rstrip()}\n"
                f"% ----- hết {path.name} -----")

    return re.sub(r"\\input\{([^}]+)\}", replace, text)


def inline_listings(text: str) -> str:
    """Thay \\lstinputlisting[tuỳ chọn]{đường dẫn} bằng khối lstlisting có sẵn mã nguồn.

    Overleaf khi đó không cần thư mục code/ — đúng kiểu một tệp main.tex tự chứa.
    """
    def replace(match: re.Match[str]) -> str:
        options, rel = match.group(1) or "", match.group(2)
        source = (DOCS / rel).resolve()
        code = source.read_text(encoding="utf-8").rstrip()
        if "\\end{lstlisting}" in code:
            raise ValueError(f"{source} chứa \\end{{lstlisting}}, không nhúng thẳng được")
        return f"\\begin{{lstlisting}}{options}\n{code}\n\\end{{lstlisting}}"

    return re.sub(r"\\lstinputlisting(\[[^\]]*\])?\{([^}]+)\}", replace, text)


def trim_appendix(text: str) -> str:
    """Bỏ các mục phụ lục không bắt buộc, giữ lại ghi chú cho người đọc biết."""
    pattern = re.compile(
        r"\\subsection\{[^}]*\}\n\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}\n")

    def drop(match: re.Match[str]) -> str:
        return "" if Path(match.group(1)).name in APPENDIX_OPTIONAL else match.group(0)

    text, n = pattern.subn(drop, text)
    anchor = "\\section{Phụ lục: mã nguồn Python}\n"
    if anchor in text:
        text = text.replace(anchor, anchor + TRIM_NOTE, 1)
    return text


def flatten_graphics(text: str) -> str:
    """Bỏ \\graphicspath: trong gói phẳng, mọi hình nằm ngay cạnh main.tex."""
    return re.sub(r"\\graphicspath\{[^\n]*\}\n", "", text)


def build(zip_name: str, tex_name: str, engine: str, trim: bool = False) -> None:
    out = BUILD / zip_name.removesuffix(".zip")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    text = (DOCS / tex_name).read_text(encoding="utf-8")
    if trim:
        text = trim_appendix(text)
    # Thứ tự bắt buộc: nhúng code trước, rồi mới gộp \input — vì bảng ánh xạ tối thiểu
    # phải nhìn thấy code đã nhúng mới biết cần những ký tự nào.
    text = flatten_graphics(inline_inputs(inline_listings(text)))
    (out / "main.tex").write_text(text, encoding="utf-8", newline="\n")

    # Chỉ chép hình thật sự được chèn, để gói không phình vì hình của tệp .tex kia
    wanted = set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text))
    sources = [ROOT / "reports" / "figures", ROOT / "docs" / "screenshots", DOCS]
    for name in sorted(wanted):
        found = next((d / name for d in sources if (d / name).exists()), None)
        if found:
            shutil.copy2(found, out / name)
        elif name in COVER_IMAGES:
            print(f"  (thiếu {name} — trang bìa sẽ không có ảnh này)")
        else:
            raise FileNotFoundError(f"{tex_name} chèn {name} nhưng không tìm thấy tệp")

    zip_path = DOCS / zip_name
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(out))

    n_files = sum(1 for p in out.rglob("*") if p.is_file())
    print(f"{zip_name:<28} {n_files:>2} tệp, "
          f"{zip_path.stat().st_size / 1_048_576:.1f} MB, Compiler: {engine}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)

    for zip_name, cfg in PACKAGES.items():
        build(zip_name, cfg["tex"], cfg["engine"], cfg.get("trim_appendix", False))

    (DOCS / "DOC_OVERLEAF.md").write_text(GUIDE, encoding="utf-8")
    print("\nKéo từng tệp .zip vào Overleaf: New Project > Upload Project")
    print("Hướng dẫn chi tiết: docs/latex/DOC_OVERLEAF.md")


if __name__ == "__main__":
    main()
