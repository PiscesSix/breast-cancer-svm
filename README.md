# Triển khai mô hình SVM chẩn đoán ung thư vú (da2)

> ⚠️ **Chỉ phục vụ mục đích giáo dục.** Kết quả không thay thế bác sĩ, xét nghiệm đã thẩm định hay chẩn đoán y khoa.
> Không gửi tên, mã bệnh nhân hay bất kỳ dữ liệu định danh nào lên API.

Mô hình SVM (kernel RBF) phân loại khối u vú **lành tính / ác tính** từ 30 đặc trưng tế bào của bộ dữ liệu
*Breast Cancer Wisconsin Diagnostic* (`sklearn.datasets.load_breast_cancer`), phục vụ qua REST API FastAPI kèm giao
diện web demo, triển khai trên Render.

- **Demo trực tuyến:** https://breast-cancer-svm-api-f2qq.onrender.com/ui (Render Free: lần mở đầu sau khi dịch vụ ngủ
  có thể mất 30–60 giây)
- **Swagger:** `/docs` · **Giao diện demo:** `/ui` (hoặc mở `/` bằng trình duyệt)

## Điểm chính

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

Chi tiết (ma trận nhầm lẫn, ROC/PR, đường hiệu chỉnh, phân phối xác suất): `reports/metrics.json` và
`reports/figures/`. Phân tích đầy đủ trong tài liệu sản phẩm `docs/latex/`.

## Chạy nhanh (Windows PowerShell)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python scripts/train.py; python scripts/evaluate.py      # hoặc: .\tasks.ps1 train; .\tasks.ps1 evaluate
python -m pytest                                          # .\tasks.ps1 test
uvicorn app.main:app --reload                             # mở http://127.0.0.1:8000/ui
```

Linux/macOS: `make install train evaluate test run`. Kiểm tra sau deploy: `make smoke URL=https://...`
(Windows: `.\tasks.ps1 smoke -Url https://...`).

## Các endpoint

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/` | Thông tin dịch vụ (JSON); trình duyệt được chuyển sang giao diện demo |
| GET | `/ui` | Giao diện demo |
| GET | `/health` | 200 khi artifact đã nạp, 503 nếu lỗi (Render dùng làm health check) |
| GET | `/metadata` | Phiên bản, 30 tên đặc trưng + miền hợp lệ, ánh xạ nhãn, ngưỡng, metric test, cảnh báo |
| POST | `/predict` | Một bản ghi: 30 đặc trưng dạng phẳng hoặc `{"features": {...}}` |
| POST | `/predict/batch` | `{"items": [...]}`, 1–100 bản ghi |
| GET | `/samples?n=5&label=malignant\|benign&seed=` | Mẫu ngẫu nhiên từ tập **test**, kèm nhãn thật |
| GET | `/docs` | Swagger UI |

```bash
curl -X POST "http://127.0.0.1:8000/predict" -H "Content-Type: application/json" -d @sample_request.json
```

Mã lỗi: **422** dữ liệu sai (kèm danh sách `missing` / `extra` hoặc `out_of_range`), **503** mô hình chưa nạp được.
Log chỉ ghi `request_id`, đường dẫn, mã trạng thái, độ trễ và nhãn dự đoán — không bao giờ ghi giá trị xét nghiệm.

## Cấu trúc thư mục

```
breast-cancer-svm/
├── app/                  main.py (FastAPI, lifespan), schemas.py (30 trường), model_service.py, static/ (UI)
├── artifacts/            breast_cancer_svm.joblib, metadata.json, test_samples.json  (được commit)
├── scripts/              train.py, evaluate.py, make_sample_request.py, smoke_test.py
├── tests/                test_api.py (ma trận kiểm thử), test_model.py (hồi quy mô hình)
├── reports/              metrics.json, train_report.json, figures/*.png
├── docs/                 latex/ (tài liệu sản phẩm + slide Beamer), model-card.md, kich-ban-demo.md, screenshots/
├── .github/workflows/    ci.yml (ruff, pytest, train lại, pytest lại, smoke test)
├── render.yaml           Render Blueprint (PYTHON_VERSION 3.12.10)
├── Makefile / tasks.ps1  lệnh tắt cho Linux / Windows
└── requirements*.txt     phiên bản đã khoá
```

## Triển khai trên Render

1. Đẩy repo lên GitHub (artifact trong `artifacts/` **phải** được commit).
2. Render → **New → Blueprint** → chọn repo → Apply (đọc `render.yaml`).
3. Chờ build xong và health check `/health` chuyển xanh; mở `https://breast-cancer-svm-api-f2qq.onrender.com/ui`.
4. Chạy `python scripts/smoke_test.py https://breast-cancer-svm-api-f2qq.onrender.com` — 7 bước kiểm tra của bài giảng.

Gói Free ngủ sau khoảng 15 phút không dùng; request đầu tiên mất 30–60 giây. Dịch vụ phục vụ đúng artifact đã commit
(không train lại lúc build), và kiểm tra lúc khởi động rằng phiên bản scikit-learn trùng với lúc huấn luyện.

## Tài liệu

- Tài liệu sản phẩm (LaTeX) và slide (Beamer): `docs/latex/` — gói Overleaf `docs/latex/*_overleaf.zip`
- Model card: `docs/model-card.md` · Kịch bản demo 5 phút: `docs/kich-ban-demo.md`

Dữ liệu: W. H. Wolberg, W. N. Street, O. L. Mangasarian, *Breast Cancer Wisconsin (Diagnostic)*, UCI Machine Learning
Repository, phân phối kèm scikit-learn.
