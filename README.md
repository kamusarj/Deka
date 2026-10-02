# Deka · Public demo

Bản demo tạo đề kiểm tra Khoa học tự nhiên, chạy hoàn toàn trong trình duyệt
với dữ liệu mẫu. Có thể deploy trực tiếp lên Vercel, không cần tài khoản,
API key, backend, cơ sở dữ liệu hay LLM.

## Trải nghiệm

- Tạo đề mẫu KHTN lớp 6–9 với bốn dạng câu hỏi.
- Xem ma trận, bản đặc tả, đáp án và hướng dẫn chấm.
- Duyệt câu hỏi, đổi sang câu mẫu khác và nhân bản đề.
- Xem ngân hàng câu hỏi đã duyệt và danh sách tài liệu minh hoạ.
- Lưu đề và trạng thái duyệt trên trình duyệt bằng `localStorage`.
- Giao diện hỗ trợ màn hình nhỏ và màu sáng/tối theo hệ thống.

Nội dung kiểm tra nhập vào dùng làm tên chủ đề. Câu hỏi được chọn từ bộ mẫu
có sẵn theo lớp; ứng dụng không tạo nội dung bằng AI. Tài liệu là danh sách
minh hoạ, không có tải lên hay truy xuất dữ liệu thật.

## Chạy tại máy

Yêu cầu **Node.js 24.x** và npm.

```bash
npm ci --prefix frontend
npm run dev
```

Mở địa chỉ Vite hiển thị, mặc định là `http://localhost:5173`.

## Kiểm tra và build

```bash
npm run check
npm run audit
```

`check` chạy ESLint, các bài kiểm tra luồng demo, TypeScript, Vite build và
kiểm tra bundle production. Kết quả build nằm trong `frontend/dist`.

Xem thử bản production:

```bash
npm run build
npm run preview --prefix frontend
```

## Deploy lên Vercel

Import repository **[kamusarj/Deka](https://github.com/kamusarj/Deka)** vào
Vercel. Giữ **Root Directory** ở thư mục gốc repo (`./`) và chọn **Node.js 24.x**.
`vercel.json` đã khai báo:

| Thiết lập             | Giá trị                           |
| --------------------- | --------------------------------- |
| Framework             | Vite                              |
| Install Command       | `npm ci --prefix frontend`        |
| Build Command         | `npm run build --prefix frontend` |
| Output Directory      | `frontend/dist`                   |
| Environment Variables | Không cần                         |

Hướng dẫn từng bước: **[Deploy Vercel](docs/deploy-vercel.md)**.

## Cấu trúc mã nguồn

```text
frontend/
  src/
    demo/
      components/       # Khung trang và nút điều hướng dùng chung
      pages/            # Các màn hình demo
      data.ts           # Câu hỏi, đáp án và tài liệu mẫu
      storage.ts        # Kiểm tra dữ liệu đã lưu
      useDemoExams.ts   # Tạo, cập nhật, nhân bản và lưu đề
      DemoApp.tsx       # Định tuyến
    components/         # Biểu trưng Deka
    styles/             # Màu sắc và font
  public/fonts/         # Font phục vụ từ cùng website và giấy phép
  scripts/              # Kiểm tra bundle production
docs/deploy-vercel.md
vercel.json
.github/workflows/ci.yml
```

Repo này chỉ chứa demo tĩnh. Các dependency backend, LLM, proxy và cấu hình
Docker đã được bỏ khỏi phiên bản hiện tại.

## Dữ liệu demo

Dữ liệu được lưu riêng trên mỗi trình duyệt tại key `deka-public-demo-v1`.
Không có đồng bộ giữa thiết bị. Nếu trình duyệt chặn lưu trữ, ứng dụng thông
báo rằng thay đổi sẽ mất khi tải lại trang.

Để khôi phục bộ mẫu ban đầu, xoá dữ liệu website trong trình duyệt hoặc xoá
key trên trong Developer Tools → Application → Local Storage rồi tải lại.
