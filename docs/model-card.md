# Model card — breast-cancer-svm-rbf v1.0.0

> ⚠️ **Chỉ phục vụ mục đích giáo dục; không thay thế chẩn đoán y khoa.** Mô hình chưa từng được kiểm định lâm sàng
> hay phê duyệt như thiết bị y tế.

## Mục đích

- **Dùng cho:** minh hoạ quy trình học máy và triển khai API trong môn học — từ dữ liệu, huấn luyện, chọn ngưỡng
  theo chi phí lâm sàng tới vận hành trực tuyến.
- **Không dùng cho:** chẩn đoán, sàng lọc hay ra quyết định điều trị cho người thật; không dùng một xác suất đơn lẻ
  để kết luận.

## Mô hình

| Thành phần | Giá trị |
|---|---|
| Kiến trúc | `Pipeline(StandardScaler, SVC(kernel="rbf", class_weight="balanced"))` |
| Siêu tham số | chọn bằng `GridSearchCV` (StratifiedKFold 5, `recall_macro`) trên C ∈ {0,1; 1; 10; 100}, gamma ∈ {scale; 0,001; 0,01; 0,1} — xem `artifacts/metadata.json` |
| Xác suất | `CalibratedClassifierCV(method="sigmoid", ensemble=False)`, chọn theo Brier score out-of-fold trong 4 cách |
| Quy tắc quyết định | ác tính nếu P(ác tính) ≥ `threshold_malignant` (trong `metadata.json`); ngưỡng chọn để sensitivity out-of-fold ≥ 0,97 rồi khoá lại |
| Thư viện | scikit-learn 1.9.1, numpy 2.5.3, Python 3.12.10 |

## Dữ liệu

- `sklearn.datasets.load_breast_cancer`: 569 mẫu, 30 đặc trưng số (mean / error / worst của 10 đại lượng hình thái
  nhân tế bào đo trên ảnh chọc hút kim nhỏ), 212 ác tính (nhãn 0) và 357 lành tính (nhãn 1).
- Chia 80/20 có phân tầng (`random_state=42`): 455 mẫu train, 114 mẫu test. Mọi lựa chọn (siêu tham số, cách hiệu
  chỉnh, ngưỡng) chỉ dùng tập train; tập test chỉ được đánh giá một lần.
- Không có giá trị thiếu. Sáu đặc trưng concavity / concave points bằng đúng 0 ở 13 mẫu.

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

## Giới hạn

- **Một cơ sở, một bộ dữ liệu nhỏ** (569 ca, Wisconsin, đầu thập niên 1990). Chưa kiểm định ngoại bộ trên quần thể,
  thiết bị hay quy trình nhuộm khác; tập test chỉ có 42 ca ác tính nên mỗi ca bỏ sót làm sensitivity giảm khoảng 2,4 điểm.
- Dữ liệu không có mã bệnh nhân nên không thể chia theo bệnh nhân hay theo thời gian như dữ liệu bệnh viện thật cần.
- Đầu vào là 30 số đo đã trích xuất sẵn; mô hình không đọc ảnh và không kiểm tra được chất lượng phép đo.
- Xác suất đã hiệu chỉnh trên dữ liệu này, nhưng không có gì bảo đảm vẫn đúng trên dữ liệu khác.

## Rủi ro và biện pháp

| Rủi ro | Biện pháp trong sản phẩm |
|---|---|
| Bỏ sót ca ác tính (false negative) | Ngưỡng hạ thấp theo sensitivity mục tiêu; báo cáo rõ số FN trên test |
| Báo động nhầm (false positive) | Báo cáo specificity và precision; UI hiển thị xác suất và ngưỡng, không chỉ nhãn |
| Dữ liệu nhập sai / ngoài miền | Schema chặt: 422 cho thiếu / thừa trường, sai kiểu, NaN, ∞, âm, vượt 3× max tập train |
| Lộ dữ liệu y tế | API không nhận thông tin định danh; log không ghi payload; lỗi 422 không trả lại dữ liệu đã gửi |
| Lệch phiên bản thư viện | Phiên bản khoá trong `requirements.txt` và `render.yaml`; API từ chối nạp artifact nếu scikit-learn khác bản đã train (`/health` trả 503) |
| Diễn giải sai nhãn 0/1 | Luôn đọc `target_names`; API trả nhãn chữ (`malignant` / `benign`, `Ác tính` / `Lành tính`) |

## Trước khi dùng thật (ngoài phạm vi sản phẩm này)

Đánh giá ngoại bộ đa cơ sở, hiệu chỉnh lại trên dữ liệu địa phương, giám sát trôi dữ liệu và sai lệch theo nhóm,
quy trình phê duyệt chuyên môn và pháp lý, quản trị phiên bản mô hình và kế hoạch rollback.
