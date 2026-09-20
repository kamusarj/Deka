# Nâng cấp sang Deka

Tên sản phẩm, giao diện, email hệ thống, nhãn thiết lập MFA và file xuất đề đã
đổi thành **Deka**. Repository: https://github.com/kamusarj/Deka.

## Cài đặt mới

Làm theo README và các file `.env.example`. Project Compose mới dùng `deka`;
image phát hành dùng tiền tố `deka-`. Các mẫu systemd nằm trong
`deploy/deka-*.service.example` và `deploy/deka-*.timer.example`.

## Nâng cấp bản đang chạy

- Giữ nguyên file môi trường và giá trị `COMPOSE_PROJECT_NAME` đang dùng. Nếu
  chưa đặt biến này, Compose vẫn dùng tên project cũ `smart-exam-ai` để nối
  đúng các volume hiện có. Không thay bằng `.env.example` của cài đặt mới.
- Nếu đã cấu hình `APP_NAME`, cập nhật riêng giá trị này thành `Deka`. Cập nhật
  các tag image và đường dẫn systemd theo vị trí cài đặt thực tế trước khi
  triển khai; không chạy thêm bộ timer mới cạnh bộ backup cũ.
- Database/user PostgreSQL `smart_exam`/`smart_exam_db`, file SQLite
  `smart_exam.db`, cookie và các khóa browser storage vẫn giữ định danh cũ.
  Đây là định danh tương thích dữ liệu, không phải tên hiển thị. Phiên đăng
  nhập, bản nháp, tùy chọn giao diện và dữ liệu không cần chuyển đổi.
- Tài khoản demo được tạo mới bằng lệnh provisioning hiện có sẽ dùng miền
  `demo.deka.test`, khớp các nút demo trên giao diện. Với môi trường demo cũ,
  chạy lại lệnh opt-in trong README để tạo các địa chỉ mới. Các tài khoản cũ
  không bị đổi email, xóa hoặc reset mật khẩu tự động.
- Nhãn MFA mới là Deka. Tài khoản MFA đã cài trên điện thoại vẫn dùng secret
  hiện có; có thể đổi nhãn hiển thị ngay trong ứng dụng xác thực.

Các chuỗi tương thích này được giữ cùng regression test tương ứng. Không thay
thế hàng loạt chúng khi cập nhật thương hiệu vì có thể tách dữ liệu đang dùng
hoặc làm mất trạng thái trên trình duyệt.
