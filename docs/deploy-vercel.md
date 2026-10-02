# Deploy bản demo Deka lên Vercel

Bản public là một website React/Vite tĩnh. Tất cả dữ liệu đều là dữ liệu mẫu
trong trình duyệt; không cần backend, database, đăng nhập hoặc dịch vụ AI.

Repo đang dùng: [kamusarj/Deka](https://github.com/kamusarj/Deka), nhánh `main`.
Các thay đổi demo hiện cần được commit và push trước khi import trên Vercel.

## Kiểm tra tại máy

Sử dụng Node.js 24.x. Từ thư mục gốc repo:

```bash
cd /home/linh/smart-exam-ai-public
node -v
npm ci --prefix frontend
npm run check
```

`node -v` cần hiển thị `v24.x.x`. Nếu máy dùng nvm, có thể chuyển phiên bản bằng
`nvm install 24` rồi `nvm use 24`.

Lệnh `check` chạy lint, toàn bộ test và build, sau đó mở bundle production trong
DOM mô phỏng để thử tạo đề, duyệt, ngân hàng câu hỏi, ma trận, bản đặc tả, in và
nhân bản đề. Bước này kiểm tra JavaScript và asset; không kiểm tra bố cục bằng
trình duyệt thật.

Để mở bản build tại máy:

```bash
cd frontend
npm run preview
```

## Deploy từ GitHub

### 1. Đẩy bản demo lên GitHub

Chạy từ thư mục gốc repo:

```bash
cd /home/linh/smart-exam-ai-public
git add -- .github/workflows/ci.yml .gitignore README.md \
  frontend/index.html frontend/package.json frontend/package-lock.json \
  frontend/src/main.tsx frontend/src/demo frontend/scripts/check-public-demo.mjs \
  .vercelignore docs/deploy-vercel.md package.json package-lock.json vercel.json
git commit -m "feat: add public mock demo for Vercel"
git push origin main
```

Mở repo GitHub và xác nhận nhánh `main` đã có `vercel.json` và
`frontend/src/demo/DemoApp.tsx` trong commit mới.

### 2. Import repo trên Vercel

1. Mở [Vercel New Project](https://vercel.com/new), đăng nhập bằng GitHub.
2. Chọn **Import** bên cạnh repo **kamusarj/Deka**. Nếu repo chưa xuất hiện,
   dùng **Adjust GitHub App Permissions** để cấp quyền truy cập repo này.
3. Đặt **Project Name** là `deka-demo` hoặc một tên bạn muốn dùng.
4. Giữ **Root Directory** là thư mục gốc (`.` hoặc `./`), không chọn `frontend`.
5. Kiểm tra các giá trị dưới đây. File `vercel.json` đã khai báo sẵn nên bạn chỉ
   cần giữ nguyên nếu Vercel đã đọc đúng:

| Thiết lập | Giá trị |
| --- | --- |
| Framework Preset | `Vite` |
| Root Directory | `.` |
| Install Command | `npm ci --prefix frontend` |
| Build Command | `npm run build --prefix frontend` |
| Output Directory | `frontend/dist` |
| Node.js Version | `24.x` |
| Environment Variables | Để trống |

Manifest `package.json` ở root đã khai báo `engines.node = 24.x`. Nếu cần kiểm
tra lại phiên bản trong dashboard, vào **Settings → Build and Deployment →
Node.js Version**.

6. Chọn **Deploy**, chờ deployment có trạng thái **Ready**, rồi mở domain
   production Vercel cung cấp, chẳng hạn `https://deka-demo.vercel.app`.

### 3. Kiểm tra website vừa deploy

Sau khi deploy, mở URL Vercel và thử tạo đề, duyệt câu hỏi, chuyển sang ngân hàng
câu hỏi rồi tải lại trang. Câu hỏi đã duyệt phải được giữ lại trên cùng trình duyệt.

Thử thêm các bước sau:

- Chuyển giữa Câu hỏi, Ma trận, Bản đặc tả và Đáp án & rubric.
- Nhân bản một đề và kiểm tra đề gốc vẫn giữ nội dung cũ.
- Mở website trên điện thoại để kiểm tra menu và bảng dữ liệu.
- Mở domain production bằng cửa sổ ẩn danh để xác nhận người xem công khai có
  thể vào bản demo. Dữ liệu demo ở cửa sổ này bắt đầu từ bộ mẫu riêng.

### 4. Cập nhật các lần sau

Commit và push thay đổi lên nhánh `main`; Vercel sẽ build lại. Theo dõi kết quả
ở tab **Deployments** của project.

Vercel đọc [cấu hình build](https://vercel.com/docs/project-configuration/vercel-json)
từ `vercel.json`. Khi repo đã được liên kết, các lần push tiếp theo sẽ tạo deployment mới.
Phiên bản Node có thể được khai báo trong
[package.json theo hướng dẫn của Vercel](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions).

## Khi deploy báo lỗi

| Thông báo hoặc hiện tượng | Cách xử lí |
| --- | --- |
| `frontend/package.json` không tồn tại | Root Directory phải là `.`; sửa lại trong project settings. |
| Không tìm thấy Output Directory | Giữ Build Command và Output Directory đúng bảng trên. |
| Lỗi phiên bản Node hoặc `EBADENGINE` | Chọn Node 24.x rồi Redeploy. |
| Vẫn hiển thị phiên bản cũ | Kiểm tra commit mới đã được push lên `main` và deployment đang dùng đúng commit. |
| Trang trắng | Mở Console và xem Build Logs trong Deployments để lấy thông báo lỗi cụ thể. |

## Deploy bằng CLI

Nếu máy đã đăng nhập Vercel, chạy từ thư mục gốc repo:

```bash
npx vercel --prod
```

Chọn project mới hoặc project demo đã có. Khi được hỏi thư mục source, chọn `.`.

## Phạm vi bản demo

- Tạo đề ghép bốn câu hỏi từ bộ mẫu theo lớp; không sinh câu hỏi bằng AI.
- “Tạo lại bản mẫu” chuyển giữa hai cách hỏi có sẵn và yêu cầu duyệt lại.
- Mỗi câu mẫu có 2,5 điểm. Ma trận lấy số câu theo mức độ từ đề đang xem.
- Duyệt câu hỏi sẽ đưa câu vào ngân hàng câu hỏi của bản demo.
- Nhân bản đề, thông tin đề và trạng thái duyệt được lưu tại key
  `deka-public-demo-v1` trong `localStorage`.
- Nếu trình duyệt chặn đọc hoặc ghi dữ liệu, demo vẫn chạy và hiển thị thông báo
  rằng các thay đổi sẽ mất khi tải lại trang.
- Tài liệu chỉ là danh sách minh hoạ; không tải tệp lên máy chủ.
- “In bản xem trước” dùng chức năng in của trình duyệt, có thể chọn Save as PDF.
- File `.vercelignore` loại các thư mục backend, dữ liệu runtime và environment
  khỏi upload bằng CLI. Deployment chỉ phục vụ thư mục `frontend/dist`.
- Header `connect-src 'none'` trên Vercel chặn kết nối API từ bản demo.

Để trở về trạng thái ban đầu, xoá dữ liệu website trong trình duyệt hoặc xoá key
`deka-public-demo-v1` trong Developer Tools → Application → Local Storage.
