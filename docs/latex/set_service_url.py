"""Thay địa chỉ dịch vụ Render trong toàn bộ tài liệu bằng một lệnh.

URL nằm nguyên văn trong các tệp (macro LaTeX không mở rộng trong \\url{} và lstlisting), nên
sau khi Render cấp địa chỉ thật, chạy:

    python docs/latex/set_service_url.py https://ten-that.onrender.com

rồi chạy lại docs/latex/build_overleaf.py để đóng gói Overleaf.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parents[1]
FILES = [
    ROOT / "README.md",
    ROOT / "docs" / "kich-ban-demo.md",
    DOCS / "da2_tai_lieu_san_pham.tex",
    DOCS / "da2_slide.tex",
]
PLACEHOLDERS = [r"https://<ten-dich-vu>\.onrender\.com", r"https://[a-z0-9-]+\.onrender\.com"]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2 or not re.fullmatch(r"https://[a-z0-9-]+\.onrender\.com", sys.argv[1].rstrip("/")):
        print("Cách dùng: python docs/latex/set_service_url.py https://<ten-dich-vu>.onrender.com")
        return 2
    url = sys.argv[1].rstrip("/")
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        new, total = text, 0
        for pattern in PLACEHOLDERS:
            new, n = re.subn(pattern, url, new)
            total += n
        if new != text:
            path.write_text(new, encoding="utf-8")
        print(f"{path.relative_to(ROOT)}: {total} chỗ")
    print(f"Đã đổi sang {url}. Chạy tiếp: python docs/latex/build_overleaf.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
