"""Kiểm tra nhanh hai tệp .tex trước khi gửi lên Overleaf.

Không thay thế việc biên dịch thật, nhưng bắt được các lỗi phổ biến nhất:
  1. Macro dùng trong .tex nhưng chưa được sinh trong metrics_data.tex
  2. Số cột của macro bảng không khớp số cột khai báo trong \\begin{tabular}
  3. Tệp hình / mã nguồn được tham chiếu nhưng không tồn tại
  4. Môi trường begin/end không cân bằng

Chạy:  python docs/latex/check_tex.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parents[1]
TEX_FILES = ["da2_tai_lieu_san_pham.tex", "da2_slide.tex"]

problems: list[str] = []
notes: list[str] = []

# Mỗi tệp .tex dùng một bộ máy biên dịch riêng — chọn nhầm là lỗi "fontspec
# requires XeTeX" hoặc "Unicode character not set up for use with LaTeX".
ENGINES = {
    "da2_tai_lieu_san_pham.tex": ("pdfLaTeX", "vietnam", "fontspec"),
    "da2_slide.tex": ("XeLaTeX", "fontspec", "vietnam"),
}


def load_macros() -> tuple[dict[str, set[int]], set[str]]:
    """Trả về (macro bảng -> số ô mỗi dòng, tất cả tên macro đã định nghĩa)."""
    text = (DOCS / "metrics_data.tex").read_text(encoding="utf-8")
    names = set(re.findall(r"\\newcommand\{\\(\w+)\}", text))
    tables: dict[str, set[int]] = {}
    for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{%\n(.*?)\n\}\n", text, re.S):
        rows = [r for r in m.group(2).split("\n") if "&" in r]
        if rows:
            tables[m.group(1)] = {r.count("&") + 1 for r in rows}
    return tables, names


def count_columns(spec: str) -> int:
    spec = re.sub(r"@\{[^}]*\}", "", spec)
    spec = re.sub(r"p\{[^}]*\}", "p", spec)
    return len(re.findall(r"[lrcp]", spec))


def check_file(name: str, tables: dict[str, set[int]], defined: set[str]) -> None:
    path = DOCS / name
    text = path.read_text(encoding="utf-8")

    # 1. Macro chưa định nghĩa (chỉ xét các macro viết hoa kiểu \AccTest, \KernelRows)
    used = set(re.findall(r"\\([A-Z][A-Za-z]+)(?:\{\}|\b)", text))
    builtin = {
        "LaTeX", "TeX", "Large", "Huge", "Recompile", "Menu", "Rightarrow",
        "Upload", "New", "Iris", "Compiler", "Main", "Try", "Execute",
        # lệnh của gói dùng trong preamble / trang bìa
        "AtBeginEnvironment", "AtEndEnvironment", "IfFileExists",
        "NewDocumentEnvironment", "HRule", "OHORN", "UHORN", "DJ",
    }
    for macro in sorted(used - defined - builtin):
        if macro in {"Acc", "CV"}:
            continue
        if re.search(rf"\\newcommand\{{\\{macro}\}}", text):
            continue
        # bỏ qua lệnh LaTeX chuẩn bắt đầu bằng chữ hoa
        if macro in {"Large", "LARGE", "Huge", "Alph", "Roman"}:
            continue
        problems.append(f"{name}: dùng \\{macro} nhưng không có trong metrics_data.tex")

    # 2. Số cột bảng
    table_re = r"\\begin\{tabular\}\{((?:[^{}]|\{[^{}]*\})*)\}(.*?)\\end\{tabular\}"
    for m in re.finditer(table_re, text, re.S):
        cols = count_columns(m.group(1))
        for macro, widths in tables.items():
            if re.search(rf"\\{macro}(?![A-Za-z])", m.group(2)) and widths != {cols}:
                problems.append(
                    f"{name}: bảng {cols} cột nhưng \\{macro} sinh dòng {sorted(widths)} ô"
                )

    # 3. Tệp được tham chiếu
    # Hình bọc trong \IfFileExists{...} là tuỳ chọn (trang bìa vẫn build khi thiếu)
    optional = set(re.findall(r"\\IfFileExists\{([^}]+)\}", text))
    for inc in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
        candidates = [
            ROOT / "reports" / "figures" / inc,
            ROOT / "docs" / "screenshots" / inc,
            DOCS / "figures" / inc,
            DOCS / inc,
        ]
        if any(c.exists() for c in candidates):
            continue
        if inc in optional:
            notes.append(f"{name}: chưa có hình tuỳ chọn {inc} — bìa vẫn biên dịch được")
        else:
            problems.append(f"{name}: không tìm thấy hình {inc}")

    for inc in re.findall(r"\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}", text):
        if not (DOCS / inc).resolve().exists():
            problems.append(f"{name}: không tìm thấy tệp mã nguồn {inc}")

    for inc in re.findall(r"\\input\{([^}]+)\}", text):
        target = DOCS / (inc if inc.endswith(".tex") else inc + ".tex")
        if not target.exists():
            problems.append(f"{name}: không tìm thấy tệp \\input {target.name}")

    # 3b. Bộ máy biên dịch: đúng gói tiếng Việt, không lẫn gói của bộ máy kia
    engine, required, forbidden = ENGINES[name]
    if not re.search(rf"\\usepackage(?:\[[^\]]*\])?\{{{required}\}}", text):
        problems.append(f"{name}: thiếu gói {required} (tệp này build bằng {engine})")
    if re.search(rf"\\usepackage(?:\[[^\]]*\])?\{{{forbidden}\}}", text):
        problems.append(f"{name}: có gói {forbidden} — không dùng được với {engine}")

    # 4. begin/end cân bằng
    begins = re.findall(r"\\begin\{(\w+\*?)\}", text)
    ends = re.findall(r"\\end\{(\w+\*?)\}", text)
    for env in set(begins) | set(ends):
        if begins.count(env) != ends.count(env):
            problems.append(
                f"{name}: môi trường {env} lệch — {begins.count(env)} begin / {ends.count(env)} end"
            )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    tables, defined = load_macros()
    print(f"metrics_data.tex: {len(defined)} macro, {len(tables)} macro bảng")
    for name in TEX_FILES:
        check_file(name, tables, defined)

    for name, (engine, _, _) in ENGINES.items():
        print(f"{name}: biên dịch bằng {engine}")

    if notes:
        print(f"\n{len(notes)} ghi chú (không chặn biên dịch):")
        for n in notes:
            print(f"  - {n}")

    if problems:
        print(f"\nTìm thấy {len(problems)} vấn đề:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("\nKhông phát hiện vấn đề nào.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
