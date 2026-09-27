# Kịch bản demo 5 phút — da2: SVM chẩn đoán ung thư vú

**Địa chỉ dịch vụ:** https://breast-cancer-svm-api-f2qq.onrender.com
**Giao diện demo:** https://breast-cancer-svm-api-f2qq.onrender.com/ui

> Luôn nói rõ ngay từ đầu: *"Sản phẩm chỉ phục vụ mục đích giáo dục, không thay thế chẩn đoán y khoa."*

## Chuẩn bị (trước giờ trình bày 2–3 phút)

1. Gói Render Free ngủ sau khoảng 15 phút không dùng; request đầu tiên mất 30–60 giây. Mở sẵn
   `https://breast-cancer-svm-api-f2qq.onrender.com/health` cho tới khi thấy `"status": "ok"`.
2. Mở sẵn bốn tab: `/ui`, `/docs`, `/health`, `/metadata`.
3. (Tuỳ chọn) chạy `python scripts/smoke_test.py https://breast-cancer-svm-api-f2qq.onrender.com` — 7/7 đạt là yên tâm.

## Phút 0:00 – 0:40 — Mở đầu

1. Mở tab `/ui`. Chỉ vào băng màu cam trên cùng: "Mọi nơi trong sản phẩm — giao diện, API, tài liệu — đều có cảnh báo
   giáo dục này."
2. Chỉ vào thẻ **Mô hình đang chạy** bên phải: "Số liệu lấy trực tiếp từ `/metadata`: SVM kernel RBF, ngưỡng
   P(ác tính) đã khoá, sensitivity và specificity trên tập test."

## Phút 0:40 – 1:40 — Mẫu ác tính

3. Bấm **Mẫu ác tính ngẫu nhiên**: 30 ô được điền từ một mẫu của **tập kiểm tra** (mô hình chưa từng thấy khi huấn
   luyện). Dòng hồng ghi mã mẫu và nhãn thật.
4. Bấm **Dự đoán**. Kết quả: thẻ đỏ **Ác tính**, thanh xác suất gần đầy, vạch đen là ngưỡng.
5. Đọc dòng quy tắc: "P(ác tính) ≥ ngưỡng → Ác tính. Nhãn luôn tính từ xác suất và ngưỡng, nên hai thứ không bao giờ
   mâu thuẫn." Dòng xanh cho biết mô hình dự đoán **đúng** so với nhãn thật.

## Phút 1:40 – 2:30 — Mẫu lành tính và ý nghĩa ngưỡng

6. Bấm **Mẫu lành tính ngẫu nhiên** → **Dự đoán**: thẻ xanh dương **Lành tính**, xác suất ác tính nằm dưới vạch ngưỡng.
7. Giải thích: "Ngưỡng không phải 0,5. Nó được chọn trên dữ liệu kiểm định để bắt ít nhất 97% ca ác tính, rồi khoá lại
   trước khi chạy tập kiểm tra — vì bỏ sót ung thư nguy hiểm hơn báo động nhầm."

## Phút 2:30 – 3:30 — Dữ liệu sai bị từ chối (422)

8. Chuyển sang tab `/docs` (Swagger) → mở **POST /predict** → **Try it out**. Payload mẫu là một ca thật của tập test.
9. Xoá dòng `"mean radius": ...` → **Execute**. Kết quả **422**, cuối phản hồi có `"missing": ["mean radius"]`.
10. Đặt lại dòng đó nhưng đổi giá trị thành `"abc"` → **Execute** → 422 *Input should be a valid number*.
    Nói thêm: "NaN, vô cực, số âm, giá trị gấp hơn 3 lần mức lớn nhất trong dữ liệu huấn luyện cũng đều bị từ chối;
    và API không lặp lại dữ liệu đã gửi trong thông báo lỗi."

## Phút 3:30 – 4:20 — Health, metadata, samples

11. Tab `/health`: `"status": "ok"`, `model_loaded: true`, phiên bản mô hình, ngưỡng. "Render dùng endpoint này làm
    health check; nếu artifact lỗi nó trả 503."
12. Tab `/metadata`: cuộn qua `feature_names` (30 tên), `class_mapping` (`0 = malignant`), `threshold_malignant`,
    `calibration`, `test_metrics`, `data_hash`, `sklearn_version`, `warning`.
13. (Nếu còn thời gian) mở `/samples?n=3&label=malignant` — endpoint giao diện dùng để lấy mẫu.

## Phút 4:20 – 5:00 — Kết

14. Quay lại `/ui`: "Toàn bộ số liệu trên giao diện, trong tài liệu và slide sinh ra từ cùng một lần huấn luyện; CI trên
    GitHub huấn luyện lại từ đầu và kiểm tra kết quả giống hệt."
15. Chốt: "Một API chạy được không đồng nghĩa với một công cụ y tế sẵn sàng sử dụng — cần kiểm định ngoại bộ, hiệu chỉnh
    lại trên dữ liệu địa phương và phê duyệt chuyên môn."

## Liên kết nhanh cho trình chiếu

- Lấy mẫu ác tính và dự đoán ngay: `https://breast-cancer-svm-api-f2qq.onrender.com/ui?sample=malignant&auto=1`
- Lấy mẫu lành tính và dự đoán ngay: `https://breast-cancer-svm-api-f2qq.onrender.com/ui?sample=benign&auto=1`

## Tình huống dự phòng

| Sự cố | Xử lý |
|-------|-------|
| Trang không phản hồi / rất chậm | Dịch vụ Free đang ngủ — chờ 30–60 giây, tải lại `/health` |
| Render lỗi hoặc mất mạng phòng họp | Chạy cục bộ: `.\tasks.ps1 run` (hoặc `uvicorn app.main:app`), demo trên `http://127.0.0.1:8000/ui` |
| `/health` trả 503 | Artifact không nạp được — xem Logs trên Render (thường do lệch phiên bản scikit-learn); demo bằng bản cục bộ |
| Mẫu ngẫu nhiên rơi vào ca bị dự đoán sai | Tận dụng: "Mô hình sai ở ca này — đây là lý do phải báo cáo sensitivity, specificity và không dùng một xác suất đơn lẻ" |
