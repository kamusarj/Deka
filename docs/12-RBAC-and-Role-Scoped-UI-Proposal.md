# Đề xuất: Hoàn thiện phân quyền theo vai trò & UI theo vai trò

> Trạng thái: **Đã triển khai và kiểm chứng** — decision 0018; stories
> US-122 đến US-129 đã hoàn tất ngày 2026-08-17.
> Mục đích: ghi lại hiện trạng, các gap đã phát hiện, trạng thái mục tiêu và lộ trình
> để sau này scale thêm vai trò, trường học và nghiệp vụ một cách có hệ thống.
>
> Liên quan: `docs/product/permissions.md`,
> `docs/decisions/0012-admin-user-role-model.md`,
> `docs/decisions/0013-hierarchical-role-permissions.md`,
> `docs/decisions/0017-logout-token-revocation.md`,
> epic `docs/stories/epics/E05-access-control`.

## 1. Ngữ cảnh & mục tiêu

Hệ thống hiện có 4 vai trò: `super_admin`, `school_admin`, `teacher`, `viewer`.
Phân quyền nền (backend) đã khá chặt cho nhóm admin, nhưng còn các điểm sau cần
hoàn thiện để sản phẩm sẵn sàng mở rộng:

- Vai trò `viewer` chưa thực sự "chỉ xem".
- Mọi vai trò dùng chung một dashboard, không có góc nhìn riêng.
- Thiếu vòng đời tài khoản, audit log và một số nghiệp vụ vận hành.

**Mục tiêu:** mỗi vai trò có đúng quyền + đúng trải nghiệm; mọi thay đổi quyền
được mô hình hoá thành story/decision để dễ duy trì và mở rộng.

## 2. Hiện trạng (baseline)

### 2.1 Mô hình vai trò & scope dữ liệu

| Vai trò | Scope dữ liệu | Khả năng hiện tại |
| --- | --- | --- |
| `super_admin` | Toàn hệ thống | Quản lý trường + mọi tài khoản, đổi role, chọn AI provider/model, tạo đề |
| `school_admin` | Theo `school_id` | Quản lý Teacher trong trường (tạo/khóa/gỡ/gán), xem metadata AI, tạo đề |
| `teacher` | Theo `owner_user_id` | Tạo đề, tài liệu, ngân hàng câu hỏi, xem metadata AI |
| `viewer` | Theo `owner_user_id` | Hiện **có quyền ghi như teacher** (xem gap G1) |

### 2.2 Các gap đã xác minh

| ID | Gap | Mức độ |
| --- | --- | --- |
| G1 | `viewer` chưa bị chặn ghi: các endpoint tạo đề/upload/xóa ngân hàng/review chỉ dùng `get_current_user`, chưa có `require_teacher`. UI cũng không ẩn nút tạo đề cho viewer. | **Cao** |
| G2 | Dashboard (`Home.tsx`) giống hệt cho mọi role; không có thống kê hệ thống (super admin) hay thống kê trường (school admin). | Trung bình |
| G3 | School admin thấy (và có thể xóa) tài nguyên của mọi teacher trong trường, nhưng danh sách không hiển thị "người tạo" → khó kiểm soát. | Trung bình |
| G4 | Thiếu vòng đời tài khoản: không có đổi mật khẩu lần đầu (khi admin tạo teacher), không reset password/quên mật khẩu, không email verify, chỉ có khóa `is_active`. | Trung bình |
| G5 | Không có workflow chuyển trường tường minh cho teacher (chỉ có qua `update_managed_user` của super admin). | Thấp |
| G6 | Xuất Word/PDF luôn kèm đáp án + rubric; thiếu bản "đề cho học sinh" (ẩn đáp án). | Thấp |
| G7 | Thiếu audit log cho thao tác admin (đổi role, khóa tài khoản, xóa tài nguyên). | Thấp |
| G8 | Không có endpoint xóa trường; không có xóa mềm tài khoản. | Thấp |
| G9 | Exam list lọc client-side, chưa có lọc theo môn/kỳ/giáo viên và phân trang server-side. | Thấp |

## 3. Trạng thái mục tiêu (target)

### 3.1 Ma trận quyền đề xuất

Ký hiệu: ✅ = cho phép, ❌ = cấm, 👁 = chỉ xem.

| Capability | super_admin | school_admin | teacher | viewer |
| --- | --- | --- | --- | --- |
| Đọc đề/tài liệu/ngân hàng (theo scope) | ✅ toàn bộ | ✅ theo trường | ✅ của mình | 👁 của mình |
| Tạo/sửa/xóa đề, review câu hỏi | ✅ | ✅* | ✅ | ❌ |
| Upload/xóa tài liệu, thêm/xóa ngân hàng | ✅ | ✅* | ✅ | ❌ |
| Quản lý Teacher (tạo/khóa/gỡ/gán) | ✅ | ✅ (trong trường) | ❌ | ❌ |
| Quản lý trường + mọi tài khoản | ✅ | ❌ | ❌ | ❌ |
| Đổi role, gán/chuyển trường | ✅ | ❌ | ❌ | ❌ |
| Chọn AI provider/model, chạy test admin | ✅ | ❌ | ❌ | ❌ |
| Xem metadata AI | ✅ | ✅ | ✅ | ❌ |
| Dashboard | Hệ thống | Trường | Cá nhân | Cá nhân (read-only) |

`*` — cần quyết định (xem mục 7, câu hỏi mở O1): school admin có nên toàn quyền
ghi tài nguyên trong trường, hay chỉ quản lý teacher + xem thống kê?

### 3.2 UI theo vai trò

| Vai trò | Navigation đề xuất |
| --- | --- |
| `super_admin` | Dashboard hệ thống · Quản trị hệ thống (trường + tài khoản) · AI provider · Tạo đề · Đề đã tạo |
| `school_admin` | Dashboard trường · Quản lý Teacher · Tạo đề · Đề đã tạo (toàn trường, có cột người tạo) |
| `teacher` | Dashboard cá nhân · Tạo đề · Đề đã tạo · Tài liệu · Ngân hàng · AI metadata (xem) |
| `viewer` | Dashboard cá nhân (read-only) · Đề đã tạo · Tài liệu · Ngân hàng (chỉ xem, không nút ghi) |

## 4. Các sáng kiến cải tiến (initiatives)

Mỗi mục là một đơn vị triển khai độc lập, map 1:1 thành story packet.

| ID | Initiative | Giải quyết gap | Ưu tiên | Risk lane khi implement |
| --- | --- | --- | --- | --- |
| I1 | Enforce `viewer` read-only: backend thêm `require_teacher` cho endpoint ghi; frontend ẩn nút tạo/upload/xóa cho viewer | G1 | P0 | High (Authorization) |
| I2 | Dashboard riêng cho super admin & school admin (thống kê + quick actions) | G2 | P1 | Normal |
| I3 | Hiển thị "người tạo" + lọc theo môn/kỳ/giáo viên trong exam list | G3, G9 | P1 | Normal |
| I4 | Vòng đời tài khoản: đổi mật khẩu lần đầu, reset password, email verify, xóa mềm | G4, G8 | P1 | High (Auth) |
| I5 | Workflow chuyển trường teacher cho super admin (UI + endpoint tường minh) | G5 | P2 | High (Authorization) |
| I6 | Xuất 2 phiên bản: đề học sinh (ẩn đáp án) vs hồ sơ giáo viên | G6 | P2 | Normal |
| I7 | Audit log cho thao tác admin | G7 | P2 | High (Audit/security) |
| I8 | Xóa trường (có kiểm tra ràng buộc member) | G8 | P3 | High (Data model) |

## 5. Lộ trình đề xuất

| Phase | Nội dung | Initiatives |
| --- | --- | --- |
| **A — Nền tảng phân quyền** | Khóa chặt quyền ghi, phân biệt teacher/viewer, hiển thị owner | I1, I3 |
| **B — Trải nghiệm admin** | Dashboard theo role, audit log | I2, I7 |
| **C — Vận hành tài khoản** | Vòng đời tài khoản, chuyển trường, xóa trường | I4, I5, I8 |
| **D — Trải nghiệm giáo viên** | Xuất 2 phiên bản, lọc nâng cao | I6, (phần còn lại của I3) |

Phase A nên làm trước vì nó là nền tảng đảm bảo quyền; các phase sau mở rộng
trải nghiệm mà không đụng lại mô hình quyền.

## 6. Mapping sang Harness

- Mỗi initiative → 1 story packet (dùng `docs/templates/story.md`).
- Các initiative chạm Authorization/Auth/Audit/Data model (I1, I4, I5, I7, I8)
  là **high-risk** khi implement → dùng `docs/templates/high-risk-story/` và ghi
  decision tương ứng.
- Cập nhật `docs/product/permissions.md` khi ma trận quyền thay đổi.
- Ghi decision trước khi thay đổi một quy tắc đã ổn định (xem mục 7).

## 7. Câu hỏi mở & quyết định cần ghi

| ID | Câu hỏi / quyết định | Gợi ý |
| --- | --- | --- |
| O1 | School admin có quyền ghi tài nguyên của teacher trong trường không? | **Đã chốt:** chỉ xem + thống kê; sửa/xóa thuộc về chủ sở hữu hoặc Super Admin (decision 0018). |
| D1 | Hợp đồng `viewer` = read-only (cấm mọi endpoint ghi) | Ghi decision trước khi làm I1 |
| D2 | Dashboard theo role là một phần của product contract | Ghi decision khi làm I2 |
| D3 | Xuất đề có 2 phiên bản (học sinh vs giáo viên) | Ghi decision khi làm I6 |

## 8. Tiêu chí hoàn thành (Definition of Done cho toàn bộ đề xuất)

- [ ] `viewer` không thể gọi bất kỳ endpoint ghi nào (có test integration).
- [ ] Mỗi role thấy đúng navigation & dashboard theo ma trận mục 3.
- [ ] Exam list hiển thị người tạo và có lọc server-side.
- [ ] Có reset password + đổi mật khẩu lần đầu cho tài khoản do admin tạo.
- [ ] Có audit log cho thao tác admin và có thể truy vấn được.
- [ ] Xuất được 2 phiên bản đề (ẩn/đầy đủ đáp án).
- [ ] `docs/product/permissions.md` và các decision được cập nhật đồng bộ.
