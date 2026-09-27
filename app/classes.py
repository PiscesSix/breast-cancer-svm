"""The two classes shown by the dashboard: description and a credited cytology image each.

Images: Wikimedia Commons, fine-needle aspiration (FNA) smears with Pap stain — the same kind of
specimen the dataset's features were measured on. Stored under app/static/images, never hotlinked.
"""

from __future__ import annotations

CLASSES = {
    "benign": {
        "key": "benign",
        "class_id": 1,
        "label_vi": "Lành tính",
        "label_en": "Benign",
        "example": "U xơ tuyến vú (fibroadenoma)",
        "description": (
            "Nhân tế bào nhỏ, tương đối đều nhau, đường viền trơn; tế bào xếp thành mảng phẳng có trật tự. "
            "Trong dữ liệu, bán kính, chu vi, diện tích và độ lõm của nhân đều thấp hơn nhóm ác tính."
        ),
        "image_url": "/static/images/benign.jpg",
        "alt_text": "Ảnh hiển vi phết tế bào chọc hút kim nhỏ của u xơ tuyến vú, nhuộm Pap",
        "author": "Nephron",
        "license": "CC BY-SA 3.0",
        "source_url": "https://commons.wikimedia.org/wiki/File:Fibroadenoma_1_-_cytology.jpg",
    },
    "malignant": {
        "key": "malignant",
        "class_id": 0,
        "label_vi": "Ác tính",
        "label_en": "Malignant",
        "example": "Ung thư biểu mô ống tuyến vú (ductal carcinoma)",
        "description": (
            "Nhân lớn, kích thước không đều, đường viền lõm và gồ ghề; tế bào mất kết dính, xếp chồng lộn xộn. "
            "Các đặc trưng 'worst' (ba nhân bất thường nhất) tách hai lớp rõ nhất."
        ),
        "image_url": "/static/images/malignant.jpg",
        "alt_text": "Ảnh hiển vi phết tế bào chọc hút kim nhỏ của ung thư biểu mô ống tuyến vú, nhuộm Pap",
        "author": "Nephron",
        "license": "CC BY-SA 3.0",
        "source_url": "https://commons.wikimedia.org/wiki/File:Ductal_carcinoma_2_-_cytology.jpg",
    },
}
