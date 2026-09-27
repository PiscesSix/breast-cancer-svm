# Nguồn tài nguyên (CREDITS)

Mọi hình ảnh, icon, font và thư viện đều được tải về dự án (`app/static/`, `web/public/`), không liên kết trực tiếp (hotlink)
tới máy chủ bên ngoài lúc chạy.

## Ảnh tế bào học (Wikimedia Commons)

Cả hai ảnh là phết tế bào chọc hút kim nhỏ (FNA) nhuộm Papanicolaou — cùng loại mẫu mà bộ dữ liệu đo 30 đặc trưng.
Bản dùng trong sản phẩm là ảnh thu nhỏ 960 px do Wikimedia tạo, không chỉnh sửa nội dung.

| Tệp | Nội dung | Tác giả | Giấy phép | Nguồn |
|---|---|---|---|---|
| `app/static/images/benign.jpg` | U xơ tuyến vú (fibroadenoma) — nhóm **lành tính** | Nephron | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Fibroadenoma_1_-_cytology.jpg |
| `app/static/images/malignant.jpg` | Ung thư biểu mô ống tuyến vú (ductal carcinoma) — nhóm **ác tính** | Nephron | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Ductal_carcinoma_2_-_cytology.jpg |

Giấy phép CC BY-SA 3.0: https://creativecommons.org/licenses/by-sa/3.0/ — dưới mỗi ảnh lớn trên giao diện có chú thích
"Nguồn: tác giả, giấy phép, liên kết".

## Icon, font, thư viện giao diện

| Thành phần | Nguồn | Giấy phép |
|---|---|---|
| Icon Lucide (nhúng dạng SVG trong `web/public/js/icons.js`) | https://lucide.dev | ISC — `web/public/vendor/LUCIDE_LICENSE.txt` |
| Font Be Vietnam Pro (`web/public/fonts/`) | https://fonts.google.com/specimen/Be+Vietnam+Pro | SIL Open Font License 1.1 — `web/public/fonts/OFL.txt` |
| Chart.js (`web/public/vendor/chart.umd.min.js`) | https://www.chartjs.org | MIT |

## Dữ liệu

*Breast Cancer Wisconsin (Diagnostic)* — W. H. Wolberg, W. N. Street, O. L. Mangasarian, UCI Machine Learning Repository
(https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic), CC BY 4.0; nạp qua
`sklearn.datasets.load_breast_cancer`.
