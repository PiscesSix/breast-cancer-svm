"""Sinh bảng ánh xạ ký tự cho gói `listings` → docs/vietnamese_listings.tex.

Tài liệu biên dịch bằng **pdfLaTeX** (gói `vietnam`/vntex, bảng mã T5). pdfLaTeX không
đọc được UTF-8 bên trong môi trường `lstlisting`, mà mã nguồn Python của dự án lại có
chuỗi tiếng Việt (log của `train.py`, thông báo lỗi của `app.py`…). Không có bảng ánh xạ
thì phần phụ lục mã nguồn sẽ lỗi hoặc mất dấu.

Script tách ký tự bằng NFD rồi dựng lại đúng lệnh đặt dấu, nên giữ nguyên dấu thanh —
khác với bảng viết tay thường gộp `ắ` thành `á`.

**Bảng càng dài thì biên dịch càng chậm**: listings so khớp từng mục với từng ký tự trong
mọi khối code. `docs/build_overleaf.py` vì thế gọi `render()` để sinh bảng *tối thiểu*
chỉ gồm ký tự thật sự xuất hiện, thay vì nhúng cả bảng đầy đủ.

Chạy:  python docs/make_listings_map.py
"""

from __future__ import annotations

import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path

OUT = Path(__file__).resolve().parent / "vietnamese_listings.tex"

TONES = {
    "\u0301": r"\'",   # dấu sắc
    "\u0300": r"\`",   # dấu huyền
    "\u0309": r"\h",   # dấu hỏi
    "\u0303": r"\~",   # dấu ngã
    "\u0323": r"\d",   # dấu nặng
}
HORN, BREVE, CIRCUMFLEX = "\u031b", "\u0306", "\u0302"
BASES = "aeiouyAEIOUY"
HORNED = {"o": r"\ohorn", "O": r"\OHORN", "u": r"\uhorn", "U": r"\UHORN"}

# Ký tự không tách được bằng NFD, hoặc không phải chữ cái tiếng Việt nhưng vẫn
# xuất hiện trong mã nguồn (dấu ± trong log của train.py, gạch dài trong docstring).
SPECIAL: dict[str, tuple[str, int]] = {
    "\u0111": (r"\dj", 1),        # đ
    "\u0110": (r"\DJ", 1),        # Đ
    "\u00b1": (r"$\pm$", 1),      # ±
    "\u2013": ("--", 2),          # – gạch nối dài
    "\u2014": ("---", 3),         # — gạch ngang
    # Ký hiệu trong mã của phần mở rộng (tiêu đề cột Excel, log của train_regression.py).
    "\u00b2": (r"$^2$", 1),       # ² (R²)
    "\u2212": (r"$-$", 1),        # − dấu trừ
    "\u2260": (r"$\neq$", 1),     # ≠
    "\u2714": (r"$\checkmark$", 1),  # ✔ (cần amssymb)
    # Ký hiệu trong mã của da2 (log của train.py / evaluate.py / smoke_test.py).
    "\u2265": (r"$\geq$", 1),     # greater-or-equal
    "\u2264": (r"$\leq$", 1),     # less-or-equal
    "\u2192": (r"$\rightarrow$", 2),  # right arrow
    "\u00b7": (r"$\cdot$", 1),    # middle dot
    "\u03b3": (r"$\gamma$", 1),   # gamma
    "\u00d7": (r"$\times$", 1),   # multiplication sign
    "\u221e": (r"$\infty$", 1),   # infinity
    "\u201c": ("``", 1),          # left double quote
    "\u201d": ("''", 1),          # right double quote
    "\u2026": (r"\dots", 3),      # ellipsis
    "\u00b5": (r"$\mu$", 1),      # micro sign (µs)
}

HEADER = r"""% =============================================================================
%  Tệp sinh tự động bởi docs/make_listings_map.py — KHÔNG sửa tay.
%
%  pdfLaTeX không đọc được UTF-8 bên trong lstlisting, nên mọi ký tự có dấu trong
%  mã nguồn Python phải được ánh xạ sang lệnh đặt dấu của bảng mã T5 (gói vietnam).
% =============================================================================
"""


def latex_for(ch: str) -> tuple[str, int] | None:
    """Trả về (lệnh LaTeX dựng lại ký tự, bề rộng), hoặc None nếu không ánh xạ được."""
    if ch in SPECIAL:
        return SPECIAL[ch]

    parts = unicodedata.normalize("NFD", ch)
    base, marks = parts[0], parts[1:]
    if base not in BASES or not marks:
        return None

    tone, inner = None, base
    for mark in marks:
        if mark in TONES:
            tone = TONES[mark]
        elif mark == HORN:
            inner = HORNED[base]
        elif mark == BREVE:
            inner = "\\u{%s}" % base
        elif mark == CIRCUMFLEX:
            inner = "\\^{%s}" % base
        else:
            return None  # dấu lạ: bỏ qua cho an toàn

    return ("%s{%s}" % (tone, inner) if tone else inner), 1


def render(chars: Iterable[str]) -> str:
    """Dựng khối \\lstset{literate=...} cho đúng tập ký tự được truyền vào."""
    entries = []
    for ch in sorted(set(chars)):
        mapped = latex_for(ch)
        if mapped is None:
            raise ValueError(
                f"không ánh xạ được U+{ord(ch):04X} {ch!r} "
                f"({unicodedata.name(ch, 'không rõ')}) — pdfLaTeX sẽ lỗi ở ký tự này"
            )
        command, width = mapped
        entries.append("{%s}{{%s}}%d" % (ch, command, width))

    rows = ["    " + " ".join(entries[i:i + 4]) for i in range(0, len(entries), 4)]
    return "\\lstset{literate=%\n" + " %\n".join(rows) + "\n}\n"


def all_vietnamese_chars() -> list[str]:
    """Toàn bộ ký tự ánh xạ được trong khoảng Latin mở rộng, cộng các ký tự đặc biệt."""
    chars = list(SPECIAL)
    for codepoint in range(0x80, 0x1F00):
        ch = chr(codepoint)
        try:
            unicodedata.name(ch)
        except ValueError:
            continue  # codepoint chưa gán
        if ch not in SPECIAL and latex_for(ch):
            chars.append(ch)
    return chars


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    chars = all_vietnamese_chars()
    OUT.write_text(HEADER + render(chars), encoding="utf-8")
    print(f"Đã ghi {OUT} ({len(chars)} ký tự — bảng đầy đủ)")
    print("Gói Overleaf dùng bảng tối thiểu sinh từ nội dung thật, xem build_overleaf.py")


if __name__ == "__main__":
    main()
