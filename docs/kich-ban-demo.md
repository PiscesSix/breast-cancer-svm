# Kịch bản demo — da2: SVM chẩn đoán ung thư vú

**Địa chỉ dịch vụ:** https://breast-cancer-svm-api-f2qq.onrender.com · tài khoản dùng thử **demo / demo123**

> Luôn nói rõ ngay từ đầu: *"Sản phẩm chỉ phục vụ mục đích giáo dục, không thay thế chẩn đoán y khoa."*

## Chuẩn bị (trước giờ trình bày 2–3 phút)

1. Gói Render Free ngủ sau khoảng 15 phút không dùng; request đầu tiên mất 30–60 giây. Mở sẵn
   `https://breast-cancer-svm-api-f2qq.onrender.com/health` cho tới khi thấy `"status": "ok"`.
2. Mở sẵn trang chủ (bảng điều khiển) và tab `/docs`.
3. (Tuỳ chọn) chạy `python scripts/smoke_test.py https://breast-cancer-svm-api-f2qq.onrender.com` — 7/7 đạt là yên tâm.

## Phút 0:00 – 1:00 — Tổng quan

1. Mở trang chủ. Chỉ vào băng màu cam: "Mọi nơi trong sản phẩm — giao diện, API, tài liệu — đều có cảnh báo giáo dục."
2. Trang **Tổng quan**: ảnh tế bào học ác tính (chỉ dòng *Nguồn: Nephron, CC BY-SA 3.0, link Wikimedia*), các thanh so
   sánh đặc trưng giữa hai nhóm, biểu đồ tròn 212 ác tính / 357 lành tính, *Đặc điểm nổi bật* và *Nhận xét* — "mọi con
   số do API tính trực tiếp từ dữ liệu".
3. Bấm **Lành tính** ở nhóm *Loại khối u* trên thanh bên: ảnh, thanh so sánh và nhận xét đổi theo nhóm.

## Phút 1:00 – 2:40 — Đăng nhập và chẩn đoán

4. Bấm **Đăng nhập** (góc phải) → `demo` / `demo123`: "Mật khẩu băm bcrypt, đăng nhập nhận JWT."
5. Bấm **Chẩn đoán SVM** → **Mẫu ác tính ngẫu nhiên**: 30 ô được điền từ một mẫu của **tập kiểm tra** (mô hình chưa từng
   thấy). Bấm **Dự đoán**: thẻ đỏ **Ác tính**, thanh xác suất có vạch ngưỡng, dòng so với nhãn thật, ảnh tế bào minh hoạ.
6. Giải thích ngưỡng: "Ngưỡng không phải 0,5 mà là ngưỡng chọn trên dữ liệu kiểm định để bắt ít nhất 97% ca ác tính,
   rồi khoá lại trước khi chạy tập kiểm tra — vì bỏ sót ung thư nguy hiểm hơn báo động nhầm."
7. Bấm **Lưu vào lịch sử**. Lặp lại với **Mẫu lành tính ngẫu nhiên** → Dự đoán → Lưu.

## Phút 2:40 – 3:30 — Lịch sử và Excel

8. Bấm **Lịch sử**: hai dự đoán vừa lưu, có nhãn thật và cột *Đúng / sai*. "Mỗi tài khoản chỉ thấy lịch sử của mình."
9. Bấm **Xuất Excel (theo bộ lọc)** → mở tệp `lich_su_du_doan_….xlsx`: header in đậm nền tím, sheet dự đoán, sheet 30 số
   đo, sheet bộ lọc.

## Phút 3:30 – 4:40 — So sánh 5 mô hình

10. Bấm **So sánh mô hình**: "Năm bộ phân loại, cùng một quy trình với mô hình chính." Chỉ vào bảng xếp hạng: Logistic
    Regression có CV cao nhất nhưng chỉ hơn SVM rất ít — nhỏ hơn độ lệch giữa các fold; sản phẩm vẫn dùng SVM theo đề bài.
11. Chỉ vào badge **Nhanh / Trung bình / Chậm**, biểu đồ ROC và hai biểu đồ thời gian: "đo bằng `perf_counter` trên máy chủ".
12. Bấm **Train lại** (khoảng 20–60 giây trên gói Free): bảng *Lịch sử huấn luyện đã lưu trong CSDL* thêm một dòng.
    Bấm **Xuất Excel** → tệp `so_sanh_mo_hinh_….xlsx`.

## Phút 4:40 – 5:40 — Điểm nổi bật: khám phá ngưỡng

13. Bấm **Phân tích nâng cao**. Ở ngưỡng đã khoá: 1 ca bỏ sót (FN), 5 ca báo nhầm (FP). Kéo thanh trượt sang phải: tới
    0,5 báo nhầm còn 2, tới 0,6 còn 1 — số bỏ sót vẫn 1; kéo tiếp tới khoảng 0,7 thì bỏ sót tăng lên 2. Điểm đỏ trên
    đường ROC trượt theo. Bấm **Ngưỡng đã khoá** để quay lại.
14. "Kéo ngưỡng trên tập test chỉ để quan sát sự đánh đổi — chọn lại ngưỡng theo tập test là rò rỉ thông tin."
    Chỉ vào PCA 2D: hai lớp tách chủ yếu theo PC1 nhưng có vùng chồng lấn.

## Phút 5:40 – 6:30 — API và kết

15. Tab `/docs` → **POST /predict** → **Try it out** → xoá dòng `"mean radius": ...` → **Execute**: **422** kèm
    `"missing": ["mean radius"]`. "NaN, chuỗi, số âm, giá trị vượt 3 lần mức lớn nhất cũng đều bị từ chối."
16. Chốt: "Một API chạy được không đồng nghĩa với một công cụ y tế sẵn sàng sử dụng — cần kiểm định ngoại bộ, hiệu chỉnh
    lại trên dữ liệu địa phương và phê duyệt chuyên môn."

## Liên kết nhanh cho trình chiếu

- Lấy mẫu ác tính và dự đoán ngay: `https://breast-cancer-svm-api-f2qq.onrender.com/?sample=malignant&auto=1`
- Lấy mẫu lành tính và dự đoán ngay: `https://breast-cancer-svm-api-f2qq.onrender.com/?sample=benign&auto=1`

## Tình huống dự phòng

| Sự cố | Xử lý |
|-------|-------|
| Trang không phản hồi / rất chậm | Dịch vụ Free đang ngủ — chờ 30–60 giây, tải lại `/health` |
| Bấm **Lưu** / **Train lại** báo "Cần đăng nhập" hoặc "Phiên đăng nhập đã hết hạn" | Dịch vụ vừa khởi động lại — đăng nhập lại `demo` / `demo123` |
| Lịch sử trống sau khi dịch vụ ngủ dậy | Gói Free không giữ ổ đĩa: CSDL SQLite được tạo lại khi khởi động. Lưu một dự đoán mới rồi mở lại |
| Render lỗi hoặc mất mạng phòng họp | Chạy cục bộ: `.\tasks.ps1 run`, demo trên `http://127.0.0.1:8000` |
| Mẫu ngẫu nhiên rơi vào ca bị dự đoán sai | Tận dụng: "Mô hình sai ở ca này — đây là lý do phải báo cáo sensitivity, specificity và không dùng một xác suất đơn lẻ" |
