# Plan: Giai đoạn cuối — Topbar, User Dropdown & Landing Page

> Mục tiêu: Gỡ bỏ sidebar trái, chuyển điều hướng lên thanh ngang (topbar); gom
> "Quản lý AI" + "Tài khoản" vào dropdown user; tạo Landing page kiểu Lumen
> (https://53c5.aaisee.me/); chuẩn bị sẵn sàng để triển khai (deploy).

---

## 1. Thay đổi cấu trúc routing

Hiện tại dùng `HashRouter` (React Router). Các route hiện tại:

| Route            | Trang            |
| ---------------- | ---------------- |
| `/`              | Home (dashboard) |
| `/create`        | CreateExam       |
| `/exams`         | ExamList         |
| `/exams/:id`     | ExamDetail       |
| `/documents`     | Documents        |
| `/question-bank` | QuestionBank     |
| `/account`       | Account          |
| `/ai-settings`   | AiSettings       |

**Đề xuất mới:**

- `/` → **Landing** (trang chào, không có navbar app)
- `/dashboard` → **Home** (dashboard cũ, giờ nằm dưới Layout có topbar)
- Giữ nguyên `/create`, `/exams`, `/documents`, `/question-bank`, `/account`, `/ai-settings` (nằm dưới Layout)
- Fallback `*` → Landing

**File:** `frontend/src/App.tsx`
- Thêm `import Landing from "./pages/Landing";`
- Tách route: `<Route path="/" element={<Landing />} />` ngoài Layout; các route app nằm trong `<Route element={<Layout />}>` với Home dời sang `path="/dashboard"`.

---

## 2. Topbar (thay thế sidebar) — `frontend/src/components/Layout.tsx`

Chuyển từ `<aside className="sidebar">` sang `<header className="topbar">` dọc ngang:

- **Brand** (trái): logo ✦ + "Deka / AI workspace".
- **Nav ngang** (giữa): các nút có icon + label:
  - Tổng quan → `/dashboard` (exact match)
  - Tạo đề → `/create`
  - Đề đã tạo → `/exams`
  - Tài liệu → `/documents`
  - Ngân hàng → `/question-bank`
- **Actions** (phải):
  - Nút nhỏ "Tạo đề" (primary pill) → `/create`
  - **Icon user** mở dropdown.
- **User dropdown** (click icon):
  - Head: "Tài khoản / Quản lý workspace của bạn"
  - Mục "⚙️ Quản lý AI" → `/ai-settings`
  - Mục "👤 Tài khoản" → `/account`
  - Foot: "← Về tổng quan" → `/dashboard`
  - Đóng khi click ra ngoài (dùng `useRef` + listener `mousedown` trên `document`).

Giữ nguyên các icon SVG inline (overview, create, exams, documents, bank, settings, user) đã có sẵn.

---

## 3. Landing page kiểu Lumen — `frontend/src/pages/Landing.tsx`

Thiết kế theo mẫu: gradient mesh hero, Inter font, glassmorphism, pill buttons,
semantic color tokens (đã có trong `:root` của `styles.css`).

**Các section:**

1. **Nav tối giản** — brand trái; link neo (#tinh-nang, #quy-trinh, #cam-ket) giữa;
   "Đăng nhập" (ghost) + "Vào workspace →" (primary) phải.
2. **Hero** — gradient mesh background (radial-gradients), eyebrow, H1 lớn với
   đoạn highlight gradient ("đáng tin cậy"), subtext, 2 CTA lớn, dải trust badges
   (Bám ma trận 7991 · Dùng tài liệu của bạn · Xuất Word & PDF), và một mockup
   preview thẻ "AI đang chuẩn bị đề".
3. **Stats** — 3–4 thẻ (Đề đã tạo, Câu hỏi, Câu trong ngân hàng, Đề đạt validation)
   lấy số liệu tĩnh hoặc placeholder.
4. **Tính năng** (`#tinh-nang`) — grid 6 tính năng (Ma trận 7991, Kiểm tra câu hỏi,
   4 dạng câu hỏi, Tài liệu & RAG, Ngân hàng câu hỏi, Export Word/PDF) dạng glass card
   có hover-lift.
5. **Quy trình** (`#quy-trinh`) — 3 bước (Tạo đề → Thêm tài liệu → Khai thác ngân hàng)
   theo style "step card".
6. **CTA cuối** — section nền gradient, headline + nút "Bắt đầu tạo đề →".
7. **Footer** — brand, link nhóm, copyright.

**File:** `frontend/src/components/index.ts` — thêm `export { default as Landing } from "./Landing";`

---

## 4. CSS — `frontend/src/styles.css`

- Đổi `.app-layout` thành `flex-direction: column` (topbar trên, main dưới).
- **Thay thế** khối CSS `.sidebar` + `.mobile-topbar` + `.mobile-nav` (dòng ~154–369)
  bằng khối mới:
  - `.topbar` (sticky, glass, border-bottom)
  - `.topbar-brand`, override `.brand-name` sang màu tối (vì nền sáng)
  - `.topnav` (flex row, gap), `.topnav-link` (pill, hover, `.current` = primary),
    `.topnav-icon`
  - `.topbar-actions`, `.topbar-cta`
  - `.user-menu` (relative), `.user-menu-trigger`, `.user-avatar` (circle),
    `.user-menu-dropdown` (absolute right, glass card, shadow, appear animation),
    `.user-menu-head`, `.user-menu-item` + icon, `.user-menu-foot`
  - Khối `.landing-*` lớn: nav, hero, mesh, eyebrow, `.grad-text`, sub, actions,
    trust, preview, stats, section, feature cards, steps, cta, footer.
- **Responsive** (dòng ~2994+):
  - Bỏ ẩn/hiện `.sidebar`/`.mobile-topbar`/`.mobile-nav` (đã không còn).
  - `@media (max-width:1024px)`: `.topnav` cho phép cuộn ngang; ẩn `.landing-nav-links`.
  - `@media (max-width:768px)`: topbar giảm padding; landing hero giảm padding,
    ẩn preview; grid landing về 1 cột.
- Tôn trọng `prefers-reduced-motion` (đã có rule chung).

---

## 5. Chuẩn bị triển khai (deploy)

- `cd frontend && npm run build` — đảm bảo `tsc -b` + `vite build` pass.
- `docker compose up --build -d backend frontend` — rebuild image.
- Kiểm tra:
  - Frontend phục vụ `dist/` tĩnh (HashRouter không cần SPA fallback).
  - `GET /api/ai/models`, `POST /api/ai/model`, SSE `generate-full-exam/stream` vẫn ok.
- (Tùy chọn) Cập nhật `README` hướng dẫn deploy — chỉ làm nếu anh yêu cầu.

---

## Thứ tự thực hiện

1. `App.tsx` (routing) → 2. `Layout.tsx` (topbar + dropdown) →
3. `Landing.tsx` + `index.ts` → 4. `styles.css` (topbar + landing + responsive) →
5. Build + Docker + verify.

## Rủi ro / lưu ý

- Link nội bộ trong `Home.tsx` trỏ `/create`, `/exams`, `/question-bank`,
  `/documents`, `/ai-settings`, `/account` — **giữ nguyên** (không đổi path).
  Chỉ "Tổng quan" đổi thành `/dashboard`.
- Landing dùng neo `#...` (scroll trong trang), không phải route.
- Không đẩy file `.env` / `.ai-log/*` lên git.
