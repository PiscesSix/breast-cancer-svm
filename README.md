# Triển khai mô hình SVM chẩn đoán ung thư vú (da2)

> ⚠️ **Chỉ phục vụ mục đích giáo dục.** Kết quả không thay thế bác sĩ, xét nghiệm đã thẩm định hay chẩn đoán y khoa.
> Không gửi tên, mã bệnh nhân hay bất kỳ dữ liệu định danh nào lên API.

Mô hình SVM (kernel RBF) phân loại khối u vú **lành tính / ác tính** từ 30 đặc trưng tế bào của bộ dữ liệu
*Breast Cancer Wisconsin Diagnostic* (`sklearn.datasets.load_breast_cancer`), phục vụ qua REST API FastAPI, kèm bảng
điều khiển web có đăng nhập, lịch sử dự đoán, so sánh 5 mô hình và xuất Excel; triển khai trên Render.

- **Demo trực tuyến:** https://breast-cancer-svm-api-f2qq.onrender.com (Render Free: lần mở đầu sau khi dịch vụ ngủ
  có thể mất 30–60 giây) · tài khoản dùng thử **demo / demo123**
- **Swagger:** `/docs` · **API CSDL:** `/db/docs`
- Link demo nhanh: `/?sample=malignant&auto=1` (lấy một mẫu ác tính của tập test và dự đoán ngay)

## Chức năng

| Trang | Nội dung |
|---|---|
| **Tổng quan** | Ảnh tế bào học của từng loại khối u (có ghi nguồn), so sánh đặc trưng giữa hai nhóm, tỷ lệ lớp, thống kê, đặc điểm nổi bật và nhận xét — mọi số tính từ dữ liệu |
| **Chẩn đoán SVM** | Lấy mẫu ngẫu nhiên từ tập test hoặc nhập 30 đặc trưng; **thanh trượt ngưỡng** (0,30–0,70, mặc định = ngưỡng đã khoá, nút về mặc định): nhãn, màu thẻ kết quả, donut xác suất, 4 chỉ số trên tập test và badge *Mục tiêu sensitivity* đổi ngay trong trình duyệt, không gọi lại `/predict`; thời gian suy luận phía server; so với nhãn thật, ảnh minh hoạ; **lưu vào lịch sử** (lưu nhãn và ngưỡng đang chọn) |
| **So sánh mô hình** | 5 bộ phân loại (SVM RBF, SVM tuyến tính, Logistic Regression, KNN, Random Forest) cùng một quy trình: bảng xếp hạng, sensitivity/specificity, đường ROC, thời gian train/predict có badge *Nhanh / Trung bình / Chậm*, **Train lại** (lưu vào CSDL), **Xuất Excel** |
| **Lịch sử** | Dự đoán của riêng tài khoản đang đăng nhập; lọc theo ngày và mô hình, phân trang, ghi nhãn thật, đúng/sai, **xuất Excel** |
| **Dữ liệu SQL** | Chỉ tài khoản `admin` (mật khẩu = biến `ADMIN_PASSWORD`; `demo` bị từ chối): xem các bảng (`wdbc` 569 mẫu WDBC kèm cột train/test, `users` không có `password_hash`, `predictions`, `training_runs`, `model_runs`), tự làm mới, chạy câu `SELECT`/`WITH` chỉ đọc (một câu, tối đa 500 dòng, dừng sau 5 giây) |
| **Điểm nổi bật · Phân tích nâng cao** | *Khám phá ngưỡng* (dùng chung giá trị với trang Chẩn đoán): ma trận nhầm lẫn, sensitivity/specificity/precision/F1, histogram xác suất, đường các chỉ số theo ngưỡng, điểm vận hành trên đường ROC và Precision–Recall thay đổi tức thì trên 114 mẫu test; **permutation importance** của 30 đặc trưng (SVC RBF không có `coef_` / `feature_importances_`); PCA 2D |
| **Đăng nhập / Đăng ký** | Mật khẩu băm bcrypt, đăng nhập bằng JWT |

## Kiến trúc: 3 module

```
Trình duyệt ── Web (web/, :8080) ──┬── API mô hình (app/, :8000): SVM, 5 mô hình, dữ liệu, ảnh
                                   └── API CSDL (db_api/, :8001): tài khoản, lịch sử, lần train, Excel ── SQLite
```

- **Web** chỉ gọi hai API qua HTTP (địa chỉ lấy từ `/config.js`), không nạp mô hình, không mở CSDL.
- **API mô hình** nạp artifact một lần (`lifespan`), dự đoán theo ngưỡng, so sánh 5 mô hình; chỉ *xác minh* JWT (dùng chung
  `JWT_SECRET`) để khoá chức năng train lại.
- **API CSDL** phát JWT, lưu lịch sử và bảng đánh giá mỗi lần train (`training_runs` + `model_runs`), xuất Excel bằng
  openpyxl, phục vụ trang *Dữ liệu SQL* chỉ đọc (`db_api/explorer.py`). Lược đồ tạo bằng migration đánh số trong
  `db_api/migrations/` (`002_wdbc.sql`: bảng dữ liệu WDBC, cột theo tên Kaggle/UCI `radius_mean` … `fractal_dimension_worst`).
- Trên Render (`SERVICE_MODE=single`) một tiến trình chạy cả ba: API mô hình ở `/`, API CSDL ở `/db`, web ở `/`. Ổ đĩa gói
  Free không bền nên SQLite được tạo lại mỗi lần khởi động; `seed.py` tạo lại tài khoản demo, tài khoản admin (khi có
  `ADMIN_PASSWORD`), 569 dòng của bảng `wdbc` và lần so sánh đầu tiên.

## Mô hình chính

- `Pipeline(StandardScaler → SVC(kernel="rbf", class_weight="balanced"))`, `GridSearchCV` + `StratifiedKFold(5)`
  chỉ trên tập train (80/20, `stratify`, `random_state=42`).
- **Ngưỡng quyết định không phải 0,5**: chọn trên xác suất *out-of-fold* của tập train sao cho sensitivity ác tính
  ≥ 0,97, khoá lại rồi mới đánh giá trên tập test. API trả nhãn theo `P(ác tính) >= threshold`, nên nhãn và xác
  suất luôn nhất quán.
- **Hiệu chỉnh xác suất**: so sánh 4 cách bằng Brier score out-of-fold; chọn
  `CalibratedClassifierCV(method="sigmoid", ensemble=False)` — cách scikit-learn khuyên dùng thay
  `SVC(probability=True)` (đã deprecated từ 1.9, bị xoá ở 1.11).
- Schema 30 trường tường minh: từ chối thiếu / thừa trường, chuỗi, `null`, `NaN`, `∞`, giá trị âm và giá trị vượt 3 lần
  mức lớn nhất của tập train (đều 422). Sáu đặc trưng *concavity / concave points* được phép bằng 0 vì 13 mẫu thật có
  giá trị 0.

## Kết quả

<!-- metrics:start -->
_Sinh tự động bởi `scripts/evaluate.py` từ `reports/metrics.json` (mô hình v1.0.0, train lúc 2026-09-26T12:35:51+00:00). Lớp dương = ác tính._

| Tập | Ngưỡng | Sensitivity | Specificity | Precision ác tính | F1 ác tính | ROC-AUC | PR-AUC | Brier | FN | FP |
|---|---|---|---|---|---|---|---|---|---|---|
| Train (fit trên chính tập train) | 0,3993 | 0,9824 | 0,9895 | 0,9824 | 0,9824 | 0,9983 | 0,9978 | 0,0095 | 3 | 3 |
| CV out-of-fold (tập train) | 0,3993 | 0,9706 | 0,9789 | 0,9649 | 0,9677 | 0,9955 | 0,9946 | 0,0190 | 5 | 6 |
| **Test** | 0,3993 | 0,9762 | 0,9306 | 0,8913 | 0,9318 | 0,9967 | 0,9952 | 0,0235 | 1 | 5 |
| Test, ngưỡng mặc định 0,5 (tham khảo) | 0,5000 | 0,9762 | 0,9722 | 0,9535 | 0,9647 | 0,9967 | 0,9952 | 0,0235 | 1 | 2 |
<!-- metrics:end -->

### So sánh 5 mô hình

<!-- comparison:start -->
_Sinh tự động từ `reports/comparison.json` (train lúc 2026-09-27T06:34:11+00:00). Ngưỡng mỗi mô hình chọn cho sensitivity out-of-fold ≥ 0,97; xếp theo CV recall_macro._

| Mô hình | CV recall_macro | Sensitivity | Specificity | ROC-AUC | Ngưỡng | FN / FP | Train (ms) | Predict (µs/mẫu) |
|---|---|---|---|---|---|---|---|---|
| **Logistic Regression** | 0,9760 ± 0,0116 | 0,9762 | 0,9861 | 0,9954 | 0,5783 | 1 / 1 | 9,7 | 4,3 |
| SVM (RBF) | 0,9753 ± 0,0162 | 0,9762 | 0,9306 | 0,9967 | 0,3993 | 1 / 5 | 45,9 | 21,7 |
| SVM tuyến tính | 0,9724 ± 0,0108 | 0,9762 | 0,9444 | 0,9960 | 0,3920 | 1 / 4 | 47,8 | 19,0 |
| Random Forest | 0,9613 ± 0,0114 | 0,9524 | 0,9444 | 0,9945 | 0,4900 | 2 / 4 | 153,5 | 82,4 |
| K láng giềng gần (KNN) | 0,9577 ± 0,0170 | 0,9762 | 0,8889 | 0,9944 | 0,3333 | 1 / 8 | 1,9 | 53,5 |
<!-- comparison:end -->

Chi tiết: `reports/metrics.json`, `reports/comparison.json`, `reports/figures/`. Phân tích đầy đủ trong tài liệu sản phẩm
`docs/latex/`.

## Chạy trên máy (Windows PowerShell)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
.\tasks.ps1 run          # 1 tiến trình như Render: http://127.0.0.1:8000  (demo / demo123)
.\tasks.ps1 run-split    # 3 module 3 cổng: web :8080, API mô hình :8000, API CSDL :8001
.\tasks.ps1 test         # pytest
```

Huấn luyện lại từ đầu: `.\tasks.ps1 train; .\tasks.ps1 compare; .\tasks.ps1 evaluate` (Linux/macOS: `make train compare
evaluate`). Kiểm tra sau deploy: `.\tasks.ps1 smoke -Url https://...` (Linux: `make smoke URL=https://...`).
`run` / `run-split` / `seed` tự tạo `.env` từ `.env.example` với `JWT_SECRET` và `ADMIN_PASSWORD` ngẫu nhiên ở lần đầu (mật
khẩu admin in ra màn hình, nằm trong `.env`; không commit `.env`).

## Các endpoint

**API mô hình**

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/` | Thông tin dịch vụ (JSON); trình duyệt được trả bảng điều khiển |
| GET | `/health` | 200 khi artifact đã nạp, 503 nếu lỗi (Render dùng làm health check) |
| GET | `/metadata` | Phiên bản, 30 tên đặc trưng + miền hợp lệ, ánh xạ nhãn, ngưỡng, metric test, cảnh báo |
| POST | `/predict` | Một bản ghi: 30 đặc trưng dạng phẳng hoặc `{"features": {...}}`; trả thêm `inference_ms` |
| POST | `/predict/batch` | `{"items": [...]}`, 1–100 bản ghi |
| GET | `/samples?n=5&label=malignant\|benign&seed=` | Mẫu ngẫu nhiên từ tập **test**, kèm nhãn thật |
| GET | `/classes` | Hai loại khối u: mô tả, ảnh tế bào học, tác giả, giấy phép, nguồn |
| GET | `/dataset/summary`, `/dataset/pca` | Thống kê theo lớp; PCA 2D của 569 mẫu |
| GET | `/models/metrics` | Bảng so sánh 5 mô hình |
| POST | `/models/train` | Train lại 5 mô hình (cần JWT) |
| GET | `/analysis/test-scores` | Ngưỡng mặc định, mục tiêu sensitivity, nhãn thật và P(ác tính) của 114 mẫu test (thanh trượt ngưỡng) |
| GET | `/analysis/permutation-importance` | Mức giảm ROC-AUC trên tập test khi xáo trộn từng đặc trưng (10 lần lặp) |
| GET | `/ui` | Địa chỉ demo cũ, chuyển sang trang Chẩn đoán |

**API CSDL** (trên Render có tiền tố `/db`)

| Method | Đường dẫn | Mô tả |
|---|---|---|
| POST | `/auth/register`, `/auth/login` | Đăng ký, đăng nhập; trả JWT |
| GET | `/auth/me` | Thông tin tài khoản |
| POST / GET | `/predictions` | Lưu / đọc lịch sử của chính người dùng (lọc ngày, mô hình, phân trang) |
| PATCH | `/predictions/{id}` | Ghi nhãn thật đã xác nhận |
| POST / GET | `/model-runs` | Lưu / đọc bảng đánh giá các lần train |
| GET | `/export/predictions.xlsx`, `/export/model-runs.xlsx` | Xuất Excel (header đậm có màu, cột tự giãn, mỗi loại một sheet, tên có thời gian) |
| GET | `/sql/tables`, `/sql/tables/{name}` | Danh sách bảng và dòng của một bảng (chỉ `admin`) |
| POST | `/sql/query` | Một câu `SELECT` / `WITH` chỉ đọc, tối đa 500 dòng (chỉ `admin`) |

```bash
curl -X POST "https://breast-cancer-svm-api-f2qq.onrender.com/predict" -H "Content-Type: application/json" -d @sample_request.json
```

Log chỉ ghi `request_id`, đường dẫn, mã trạng thái, độ trễ và nhãn dự đoán — không bao giờ ghi giá trị xét nghiệm.

## Cấu trúc thư mục

```
breast-cancer-svm/
├── app/                  API mô hình: main.py, schemas.py (30 trường), model_service.py, comparison.py,
│                         dashboard_api.py, classes.py, static/images (ảnh tế bào học)
├── db_api/               API CSDL: main.py, auth.py, history.py, runs.py, export.py, explorer.py, db.py, migrations/
├── web/                  module web: server.py (+ /config.js), public/ (index.html, css, js, fonts, vendor)
├── settings.py, security.py, seed.py   cấu hình (.env), bcrypt + JWT, dữ liệu khởi tạo
├── artifacts/            breast_cancer_svm.joblib, metadata.json, test_samples.json  (được commit)
├── scripts/              train.py, train_comparison.py, evaluate.py, make_sample_request.py, smoke_test.py
├── tests/                test_api.py, test_model.py, test_auth.py, test_history.py, test_export.py, test_dashboard.py,
│                         test_sql_explorer.py
├── reports/              metrics.json, comparison.json, train_report.json, figures/*.png
├── docs/                 latex/ (tài liệu sản phẩm + slide), model-card.md, kich-ban-demo.md, screenshots/
├── .github/workflows/    ci.yml (ruff, pytest, train lại, pytest lại, smoke test)
├── render.yaml, Makefile, tasks.ps1, .env.example, CREDITS.md
└── requirements*.txt     phiên bản đã khoá
```

## Triển khai trên Render

1. Đẩy repo lên GitHub (thư mục `artifacts/` và `reports/comparison.json` **phải** được commit).
2. Render → **New → Blueprint** → chọn repo → Apply (đọc `render.yaml`: `SERVICE_MODE=single`, `JWT_SECRET` và
   `ADMIN_PASSWORD` do Render tự sinh, `PYTHON_VERSION=3.12.10`). Mật khẩu admin của trang *Dữ liệu SQL* xem ở tab
   Environment của service.
3. Chờ health check `/health` chuyển xanh, mở địa chỉ dịch vụ, đăng nhập `demo / demo123`.
4. `python scripts/smoke_test.py https://<ten-dich-vu>.onrender.com` — 7 bước kiểm tra của bài giảng.

## Tài liệu và nguồn

- Tài liệu sản phẩm (LaTeX) và slide (Beamer): `docs/latex/` — gói Overleaf `docs/latex/*_overleaf.zip`
- Model card: `docs/model-card.md` · Kịch bản demo: `docs/kich-ban-demo.md`
- Nguồn ảnh, icon, font, thư viện, dữ liệu: `CREDITS.md`
