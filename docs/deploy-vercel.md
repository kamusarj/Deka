# Deploy demo Deka lên Vercel

Bản public chạy với dữ liệu mẫu trong trình duyệt. Không cần backend, API key,
LLM, tài khoản đăng nhập hay biến môi trường.

Tham khảo chính thức: [cấu hình build](https://vercel.com/docs/builds/configure-a-build)
và [Node.js 24 trên Vercel](https://vercel.com/changelog/node-js-24-lts-is-now-generally-available-for-builds-and-functions).

## 1. Kiểm tra trước khi deploy

Dùng Node.js **24.x**, mở thư mục gốc repo và chạy:

```bash
npm ci --prefix frontend
npm run check
npm run audit
```

Sau khi kiểm tra thành công, có thể xem thử bản production:

```bash
npm run preview --prefix frontend
```

Mở địa chỉ Vite hiển thị. `npm run check` đã tạo `frontend/dist`.

## 2. Import repo vào Vercel

1. Đăng nhập [Vercel](https://vercel.com) bằng tài khoản GitHub.
2. Chọn **Add New → Project**.
3. Import repository **kamusarj/Deka**. Nếu repo chưa hiện, cấp quyền truy cập
   cho Vercel trong phần kết nối GitHub.
4. Chọn branch **main**.
5. Giữ **Root Directory** là thư mục gốc repo (`./`), không chọn `frontend`.
6. Chọn **Node.js Version: 24.x** trong cấu hình project.
7. Kiểm tra các giá trị bên dưới rồi chọn **Deploy**.

`vercel.json` ở thư mục gốc đã cấu hình các giá trị này:

| Thiết lập             | Giá trị                           |
| --------------------- | --------------------------------- |
| Framework Preset      | Vite                              |
| Install Command       | `npm ci --prefix frontend`        |
| Build Command         | `npm run build --prefix frontend` |
| Output Directory      | `frontend/dist`                   |
| Environment Variables | Để trống                          |

Nếu đã tạo project từ trước, mở **Settings → Build and Deployment** để cập nhật
Root Directory và các lệnh trên; sau đó redeploy commit mới nhất trên `main`.
Tên mục trong giao diện Vercel có thể thay đổi, nhưng các giá trị phải khớp
`vercel.json`.

## 3. Kiểm tra website sau deploy

Mở URL do Vercel cấp và thử:

1. Ở trang giới thiệu, chọn **Thử tạo đề mẫu**.
2. Chọn lớp, loại kiểm tra, thời gian rồi chọn **Tạo bộ đề mẫu**.
3. Xem các tab **Câu hỏi**, **Ma trận**, **Bản đặc tả**, **Đáp án & rubric**.
4. Duyệt một câu hỏi, mở **Ngân hàng câu hỏi** để xem câu vừa duyệt.
5. Nhân bản đề và thử **Tạo lại bản mẫu** ở bản sao.
6. Tải lại trang để kiểm tra đề và trạng thái duyệt vẫn còn.
7. Kiểm tra trên điện thoại và thử **In bản xem trước** trong tab đáp án.

Ứng dụng dùng đường dẫn có dấu `#`, ví dụ `/#/create`. Có thể chia sẻ trực tiếp
đường dẫn này và tải lại trang bình thường.

## 4. Các lỗi cấu hình thường gặp

| Hiện tượng                             | Cách xử lý                                                                                   |
| -------------------------------------- | -------------------------------------------------------------------------------------------- |
| Không tìm thấy `frontend/package.json` | Đặt Root Directory về gốc repo (`./`).                                                       |
| Không tìm thấy thư mục build           | Đặt Output Directory là `frontend/dist`.                                                     |
| Build dùng Node không phù hợp          | Chọn Node.js 24.x rồi redeploy.                                                              |
| Website vẫn hiển thị bản cũ            | Kiểm tra deployment đang dùng commit mới nhất trên branch `main`.                            |
| Đề mẫu mất khi tải lại                 | Cho phép website dùng bộ nhớ trình duyệt; chế độ riêng tư có thể xoá dữ liệu khi đóng phiên. |

Xem lỗi build cụ thể trong **Deployments → deployment tương ứng → Build Logs**.

## 5. Dữ liệu và kết nối

- Câu hỏi và tài liệu minh hoạ nằm trong `frontend/src/demo/data.ts`.
- Nội dung nhập vào là tên chủ đề; câu hỏi mẫu được chọn theo lớp.
- Đề và trạng thái duyệt lưu tại key `deka-public-demo-v1` trong `localStorage`.
- Dữ liệu không được gửi lên máy chủ và không đồng bộ giữa thiết bị.
- Font được phục vụ cùng website, không cần CDN.
- Header `connect-src 'none'` trong `vercel.json` chặn kết nối API.

Để bắt đầu lại, xoá dữ liệu website hoặc key `deka-public-demo-v1` trong
Developer Tools → Application → Local Storage rồi tải lại trang.
