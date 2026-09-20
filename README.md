# Deka

Đang nâng cấp từ phiên bản trước? Xem [hướng dẫn đổi tên sang Deka](docs/branding-upgrade.md)
để giữ đúng database, volume và cấu hình hiện có.

[![GitHub Repo](https://img.shields.io/badge/GitHub-Deka-blue?style=flat-square&logo=github)](https://github.com/kamusarj/Deka)
[![Python](https://img.shields.io/badge/Python-3.11+-yellow?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue?style=flat-square&logo=react)](https://reactjs.org/)

Deka là hệ thống hỗ trợ giáo viên tạo đề kiểm tra Khoa học tự nhiên theo ma trận, bản đặc tả, đáp án và rubric. **Hệ thống ưu tiên dùng dữ liệu chương trình đã kiểm soát, tài liệu giáo viên upload và RAG thay vì để AI tự crawl dữ liệu từ web.**

🔗 **GitHub Repository:** [https://github.com/kamusarj/Deka](https://github.com/kamusarj/Deka)

---

## 1. Giới thiệu

Deka giúp giáo viên THCS tạo bộ đề kiểm tra Khoa học tự nhiên hoàn chỉnh trong vài phút thay vì 2-3 giờ. Hệ thống không chỉ sinh câu hỏi mà tạo đầy đủ hồ sơ: ma trận đề, bản đặc tả, đề kiểm tra, đáp án, hướng dẫn chấm — sẵn sàng in và sử dụng.

**Nguyên tắc cốt lõi:**
- 📚 **Dữ liệu đã kiểm soát** - Local JSON curriculum, giáo viên upload, question bank
- 🤖 **AI chỉ là công cụ** - Xử lý, chuẩn hóa, sinh đề dựa trên dữ liệu đã kiểm soát
- ✅ **Duyệt có chọn lọc** - Giáo viên duyệt từng câu, chỉ tạo lại câu không ok
- 🔍 **RAG retrieval** - BM25 + vector tùy chọn, RRF, rerank và context budget

**Điểm khác biệt so với ChatGPT:**

| ChatGPT thường | Deka |
|---|---|
| Chỉ sinh câu hỏi | Sinh hồ sơ đề kiểm tra hoàn chỉnh |
| Không có ma trận | Ma trận đúng format quy định |
| Không có bản đặc tả | Bản đặc tả chi tiết |
| Không kiểm tra format | Validation tự động |
| Không export Word | Export Word ready-to-print |
| Tự bịa kiến thức | Dùng dữ liệu chương trình đã kiểm soát |
| Không kiểm soát nguồn | RAG + local JSON + giáo viên upload |

---

## 2. Mục tiêu MVP

- **Nạp dữ liệu đã kiểm soát** - Local JSON, giáo viên upload, question bank
- Nhập thông tin đề kiểm tra: lớp, môn, loại đề, thời gian, nội dung kiểm tra, tỉ lệ mức độ
- Tạo ma trận đề kiểm tra theo format Công văn 7991
- Tạo bản đặc tả đề kiểm tra chi tiết
- Tạo đề kiểm tra với 4 dạng: TNKQ, Đúng/Sai, Trả lời ngắn, Tự luận
- **Duyệt có chọn lọc** - Giáo viên duyệt từng câu, chỉ tạo lại câu không ok
- Tạo đáp án và hướng dẫn chấm
- Lưu đề đã tạo vào database
- Export Word ready-to-print

---

## 3. Tính năng chính

| Tính năng | Mô tả |
|---|---|
| **📚 Data Ingestion** | Nạp dữ liệu từ local JSON, giáo viên upload, question bank |
| **📝 Exam Info Input** | Nhập thông tin đề kiểm tra (trường, khối, môn, loại kiểm tra) |
| **📊 Matrix Builder** | Sinh ma trận đề theo format Công văn 7991 |
| **📋 Specification Generator** | Tạo bản đặc tả chi tiết từng câu hỏi |
| **❓ Question Generator** | Sinh câu hỏi theo bản đặc tả |
| **✅ Selective Review** | Duyệt từng câu, chỉ tạo lại câu không ok |
| **📝 Answer & Rubric** | Tạo đáp án và hướng dẫn chấm |
| **🔍 Validator** | Kiểm tra format, điểm, mức độ, nội dung |
| **📄 Export DOCX** | Xuất file Word ready-to-print |

---

## 4. Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DEKA                             │
│                      System Architecture                                │
│                    (Flow mới: Nạp dữ liệu + RAG)                        │
└─────────────────────────────────────────────────────────────────────────┘

User Input
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   React     │────▶│   FastAPI   │────▶│  AI Agents  │
│  Frontend   │     │   Backend   │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
                         │                    │
                         ▼                    ▼
                    ┌─────────┐         ┌─────────┐
                    │PostgreSQL│         │OpenAI   │
                    │   DB    │         │→Gemini  │
                    └─────────┘         │→DeepSeek│
                                        └─────────┘
                         │
                         ▼
                    ┌─────────┐
                    │ Export  │
                    │ Service │
                    │(Word/PDF)│
                    └─────────┘
```

**Luồng xử lý:**

1. **Agent 0: Data Ingestion** - Nạp dữ liệu từ local JSON, teacher upload, question bank
2. **Agent 1: Document Processing** - Chuẩn hóa dữ liệu về schema chung
3. **Agent 2: Retriever** - Tìm kiếm từ knowledge base / RAG
4. **Agent 3: Matrix Generator** - Tạo ma trận đề kiểm tra
5. **Agent 4: Specification Generator** - Tạo bản đặc tả
6. **Agent 5: Question Generator** - Sinh câu hỏi (KHÔNG tự bịa chương trình)
7. **Agent 6: Teacher Review** - Xử lý duyệt câu hỏi
8. **Agent 7: Answer & Rubric** - Sinh đáp án và rubric
9. **Agent 8: Validator** - Kiểm tra format và chất lượng
10. **Agent 9: Exporter** - Xuất file Word

---

## 5. Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Frontend | React, Vite, TypeScript |
| Backend | FastAPI, Python |
| Package Manager | uv |
| Database | PostgreSQL |
| Vector DB | ChromaDB tùy chọn / bounded memory cache |
| AI | OpenAI Responses API → Gemini → DeepSeek |
| Export | python-docx, reportlab |
| DevOps | Docker Compose (fe + be + postgres + chromadb) |

---

## 6. User Flow

```mermaid
flowchart TD
    A[Step 0: Nạp nguồn dữ liệu] --> B[Step 1: Chuẩn hóa dữ liệu]
    B --> C[Step 2: Giáo viên xác nhận phạm vi]
    C --> D[Step 3: Tạo ma trận đề]
    D --> E[Step 4: Tạo bản đặc tả]
    E --> F[Step 5: Sinh câu hỏi theo ma trận]
    F --> G[Step 6: Giáo viên duyệt câu hỏi]

    G -->|Câu đạt| H[Step 7: Sinh đáp án & rubric]
    G -->|Câu chưa đạt| F

    H --> I[Step 8: Kiểm tra format + validation]
    I -->|Không đạt| G
    I -->|Đạt| J[Step 9: Xác nhận cuối cùng]

    J -->|Cần sửa| C
    J -->|Đồng ý| K[Step 10: Export Word/PDF]
```

| Step | Tính năng | Mô tả |
|------|-----------|-------|
| 0 | Nạp nguồn dữ liệu | Local JSON, teacher upload, question bank |
| 1 | Chuẩn hóa dữ liệu | Chuyển đổi về schema chung |
| 2 | Giáo viên xác nhận | Xác nhận phạm vi kiểm tra |
| 3 | Tạo ma trận | AI sinh ma trận theo format Công văn 7991 |
| 4 | Tạo bản đặc tả | AI sinh bản đặc tả chi tiết |
| 5 | Sinh câu hỏi | AI sinh câu hỏi theo ma trận |
| 6 | Giáo viên duyệt | Duyệt từng câu: accepted/needs_revision/rejected |
| 7 | Sinh đáp án & rubric | Tạo đáp án và hướng dẫn chấm |
| 8 | Kiểm tra format | Validation tự động |
| 9 | Xác nhận cuối cùng | Giáo viên xác nhận trước khi export |
| 10 | Export Word/PDF | Xuất file Word ready-to-print |

---

## 7. Cấu trúc thư mục

```
deka/
├── backend/
│   ├── app/
│   │   ├── api/              # API routes
│   │   ├── agents/           # AI agents
│   │   ├── models/           # Database models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── main.py           # FastAPI entry point
│   ├── data/                 # Curriculum JSON + templates (tĩnh)
│   ├── pyproject.toml
│   ├── requirements.txt      # Dependencies (for pip users)
│   ├── Dockerfile            # Build image backend (Python 3.11-slim)
│   ├── .dockerignore
│   ├── uv.lock
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.tsx
│   ├── nginx.conf            # Cấu hình nginx (SPA + proxy /api -> backend)
│   ├── package.json
│   ├── Dockerfile            # Multi-stage: Node build -> nginx serve
│   ├── .dockerignore
│   └── .env
├── docs/                     # Tài liệu dự án
│   ├── 01-PRD.md
│   ├── 02-User-Flow.md
│   ├── 03-AI-Agents-Architecture.md
│   ├── 04-Data-Schema.md
│   ├── 05-Prompt-Design.md
│   ├── 06-Validation-Checklist.md
│   ├── 07-MVP-Scope.md
│   └── 08-Future-Features.md
├── docker-compose.yml        # Orchestrator: fe + be + postgres + chromadb + network
└── README.md
```

---

## 8. Yêu cầu môi trường

| Yêu cầu | Phiên bản |
|---|---|
| Python | 3.11–3.13 |
| uv | Mới nhất |
| Node.js | 22+ |
| npm | 10+ |
| Docker | 24+ |
| Docker Compose | 2.20+ |
| OpenAI API Key | Cần thiết để dùng API chính |

---

## 9. 🚀 Cài đặt và chạy local — từng bước

### Bước 1: Clone project

```bash
git clone https://github.com/kamusarj/Deka.git deka
cd deka
```

### Bước 2: Cấu hình biến môi trường

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Các cổng của `docker-compose.yml` chỉ bind vào `127.0.0.1` để chạy local. Triển khai ra Internet dùng [hướng dẫn production](docs/production-deployment.md). Không đặt API key hoặc secret vào biến `VITE_*` vì chúng xuất hiện trong JavaScript gửi tới trình duyệt. Xem [chính sách bảo mật](SECURITY.md).

Điền một giá trị ngẫu nhiên, đủ dài cho `.env` → `SECRET_KEY` (bắt buộc ở production/Docker; biến này override giá trị trong `backend/.env`) và một mật khẩu URL-safe cho `.env` → `POSTGRES_PASSWORD` (bắt buộc khi dùng Docker Compose). Không commit các file `.env`.

> 🔑 **Quan trọng:** Mở `backend/.env` và điền `OPENAI_API_KEY` để dùng API chính. Có thể cấu hình thêm `GEMINI_API_KEY` và `DEEPSEEK_API_KEY` làm hai tầng dự phòng. Nếu cả ba đều thiếu hoặc lỗi, sinh đề sẽ thất bại rõ ràng và không lưu nội dung giả.

### 🐳 Option nhanh: Chạy toàn bộ stack bằng Docker (khuyến nghị)

Nếu chỉ muốn **chạy thử app nhanh** mà không cần cài Python/Node trên máy, chỉ cần Docker. Một lệnh duy nhất sẽ build & khởi động cả 4 service: **Frontend + Backend + PostgreSQL + ChromaDB** trên cùng một network.

```bash
docker compose up -d --build
```

Lần đầu chạy sẽ mất ~2-3 phút để build images (cài deps Python + npm). Các lần sau chỉ mất vài giây vì có cache.

**Các service sau khi khởi động:**

| Service | Container | Port máy host | Mô tả |
|---|---|---|---|
| Frontend | `deka_frontend` | **http://localhost:8080** ⭐ | React build + nginx serve |
| Backend | `deka_backend` | http://localhost:8000 | FastAPI (Swagger: `/docs`) |
| PostgreSQL | `deka_postgres` | localhost:5432 | Database chính |
| ChromaDB | `deka_chromadb` | localhost:8001 | Vector DB cho RAG (Phase 2) |

> ⭐ **Mở trình duyệt tại http://localhost:8080** — nginx sẽ tự proxy mọi request `/api/*` tới backend, nên frontend gọi API cùng origin, không lo CORS.

Sau khi rebuild, trình duyệt xác thực lại `index.html` để nhận đúng bundle mới.
Các file có hash trong `/assets/` được cache dài hạn; file không tồn tại trả `404`
thay vì trả HTML của ứng dụng.

**Kiến trúc network:**

```
browser ──:8080──▶ nginx (frontend) ──┬─ static (React build)
                                      └─ /api/* ──▶ backend:8000 ──┬─ postgres:5432
                                                                  └─ chromadb:8000
                                                          (cùng network: deka_net)
```

**Các lệnh Docker thường dùng:**

```bash
docker compose up -d --build   # Build + khởi động (chạy nền)
docker compose ps              # Xem trạng thái container
docker compose logs -f backend # Xem log backend (realtime)
docker compose logs -f frontend# Xem log nginx/frontend
docker compose restart backend # Khởi động lại 1 service
docker compose down            # Dừng tất cả (giữ nguyên data)
docker compose down -v         # Dừng + XÓA hết data volumes (reset DB)
docker compose up -d --build   # Rebuild sau khi sửa code backend/frontend
```

> 💡 **Lưu ý về biến môi trường:** Compose tự load `backend/.env` (chứa các key OpenAI/Gemini/DeepSeek) qua `env_file`, nhưng **override** các biến network (`DATABASE_URL`, `CHROMA_HOST`, `ENV`) trong `environment` để trỏ đúng tên container (`postgres`, `chromadb`). Không cần sửa gì thêm trong `.env` khi chạy Docker.

> ⚠️ **Port 8080 bị chiếm?** Sửa port publish trong `docker-compose.yml` (ví dụ `"3000:80"`), rồi mở `http://localhost:3000`.

**Nếu chạy Docker rồi thì bỏ qua Bước 3-5 bên dưới** (chỉ dành cho ai muốn chạy từng phần local để dev).

---

### Bước 3: Khởi động Database (chỉ khi chạy local, không dùng full Docker stack)

```bash
# Chỉ khởi động PostgreSQL + ChromaDB để backend local kết nối
docker compose up -d postgres chromadb
```

> 💡 Nếu không có Docker, backend sẽ tự động fallback về **SQLite** (`backend/app/data/smart_exam.db`) — không cần cấu hình gì thêm.

Dịch vụ khởi động:
- PostgreSQL: `localhost:5432`
- ChromaDB: `localhost:8001`

### Bước 4: Chạy Backend (FastAPI)

**Dùng uv (khuyến nghị):**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Hoặc dùng pip + venv:**

```bash
cd backend
python -m venv venv
source venv/bin/activate     # Linux/Mac
# venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

✅ Backend chạy ở:
- API: **http://localhost:8000**
- Swagger Docs: **http://localhost:8000/docs**
- Health check: **http://localhost:8000/health**

### Bước 5: Chạy Frontend (React + Vite)

> Mở **terminal thứ hai**:

```bash
cd frontend
npm install
npm run dev
```

✅ Frontend chạy ở: **http://localhost:5173**

### Bước 6: 🧪 Chạy test

**Backend (223 tests):**

```bash
cd backend
source .venv/bin/activate

# Chạy toàn bộ test backend
uv run python -m pytest tests/ -v

# Chỉ chạy test agents
uv run python -m pytest tests/test_agents.py -v
```

**Frontend (23 tests, Vitest + Testing Library):**

```bash
cd frontend
npm run test:run        # chạy 1 lần
npm run test            # watch mode
npm run test:coverage   # kèm báo cáo coverage
npm run lint            # ESLint 9 flat config
```

> 🤖 **CI:** `.github/workflows/ci.yml` chạy toàn bộ các lệnh trên cho mỗi push
> và pull request — pytest (Python 3.11 + 3.13), ESLint, Vitest, `tsc -b` +
> build, `npm audit --omit=dev --audit-level=high`, và `docker compose config`.

### Bước 7: Test thử luồng chính

1. Mở **http://localhost:5173** → trang chủ
2. Nhấn **"Tạo đề mới"** → điền form → nhấn **"Tạo đề MVP"**
3. Ma trận, câu hỏi, validation hiển thị bên phải
4. Duyệt từng câu: ✅ Chấp nhận / 🔄 Cần sửa → Tạo lại
5. Vào **"Đề đã tạo"** → xem chi tiết → **Tải Word (.docx)**

---

## 10. ⚙️ Biến môi trường

### Tài khoản thử cho từng role

Tạo tài khoản demo bằng lệnh chủ động (không tự tạo khi khởi động):

```bash
docker compose exec backend python -m app.services.demo_accounts --allow-demo-accounts
# Nếu chạy backend trực tiếp:
cd backend && uv run python -m app.services.demo_accounts --allow-demo-accounts
```

| Role | Email |
| --- | --- |
| Quản trị hệ thống (`super_admin`) | `superadmin@demo.deka.test` |
| Quản trị trường (`school_admin`) | `schooladmin@demo.deka.test` |
| Giáo viên (`teacher`) | `teacher@demo.deka.test` |
| Người xem (`viewer`) | `viewer@demo.deka.test` |

Mật khẩu chung: `Demo@123456`. Ba tài khoản cấp trường thuộc **Trường THCS Demo**.
Lệnh chạy lại sẽ dùng tài khoản đã có; nếu thông tin xung đột, lệnh dừng và không
đổi mật khẩu, quyền hoặc dữ liệu của tài khoản cũ.

Để hiện 4 nút đăng nhập nhanh tại `/#/login`, đặt `VITE_ENABLE_DEMO_LOGIN=true`
trong `.env` gốc rồi chạy `docker compose up -d --build --no-deps frontend`.
Với Vite local, đặt cùng biến trong `frontend/.env` rồi khởi động lại Vite.
Đăng xuất sẽ quay về trang đăng nhập để chọn role khác.

Chế độ này mặc định tắt và dành cho môi trường thử. Đặt biến về `false` rồi
build lại để ẩn nút; thao tác đó không thu hồi quyền của tài khoản demo đã tạo.

### backend/.env

```env
# App Configuration
APP_NAME=Deka
ENV=development

# Database (PostgreSQL) — để trống để dùng SQLite
DATABASE_URL=postgresql://smart_exam:REDACTED_OLD_POSTGRES_PASSWORD@localhost:5432/smart_exam_db
USE_POSTGRES=false

# Chuỗi cố định: OpenAI chính -> Gemini -> DeepSeek
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1
AI_INTERACTIVE_REVIEW_MODE=dual
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-chat

# ChromaDB (Vector Database — chưa dùng trong Phase 1)
CHROMA_HOST=localhost
CHROMA_PORT=8001

# CORS Origins (frontend URL)
CORS_ORIGINS=["http://localhost:5173"]
```

### frontend/.env

```env
# Để trống: Vite và Docker đều dùng same-origin /api proxy
VITE_API_BASE_URL=
```

Vite dev proxy `/api/*` tới `http://localhost:8000`; Docker nginx proxy cùng
đường dẫn tới backend trên network nội bộ. Chỉ đặt URL tuyệt đối khi triển khai
frontend và API ở hai origin khác nhau, đồng thời cấu hình CORS tương ứng.

### Google OAuth

Trong Google Cloud Console → **APIs & Services → Credentials → OAuth 2.0 Client**, thêm URI callback khớp với cách chạy ứng dụng:

```text
# Docker, mở ứng dụng tại http://localhost:8080
http://localhost:8080/api/auth/callback/google

# Local development, frontend gọi trực tiếp backend :8000
http://localhost:8000/api/auth/callback/google
```

Google so khớp tuyệt đối scheme, hostname, port và path. Nếu dùng hostname hoặc port khác, thêm URI tương ứng vào **Authorized redirect URIs**.

---

## 11. ⚡ Lệnh tiện ích

### Docker (full stack)

```bash
# Khởi động cả 4 service (fe + be + db + chromadb)
docker compose up -d --build

# Xem trạng thái / log
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend

# Rebuild 1 service sau khi sửa code
docker compose up -d --build backend
docker compose up -d --build frontend

# Vào shell trong container để debug
docker compose exec backend bash
docker compose exec postgres psql -U smart_exam -d smart_exam_db

# Dừng (giữ data) / Dừng + xoá data
docker compose down
docker compose down -v
```

### Local dev

```bash
# Build frontend cho production
cd frontend && npm run build

# Kiểm tra lỗi TypeScript
cd frontend && npx tsc --noEmit

# Lint + test frontend
cd frontend && npm run lint && npm run test:run

# Kiểm tra curriculum JSON hợp lệ
cd backend && source .venv/bin/activate
python -c "
from app.services.curriculum_service import validate_all_curriculum_files
print(validate_all_curriculum_files())
"
```

---

## 12. ❓ Xử lý sự cố thường gặp

| Vấn đề | Cách xử lý |
|--------|-----------|
| Không có Docker | Backend tự fallback về SQLite — không cần làm gì thêm |
| Thiếu API key hoặc vẫn dùng placeholder | Bỏ qua provider đó và thử provider kế tiếp trong chuỗi |
| Cả ba API đều thiếu/lỗi | App vẫn mở được, nhưng sinh đề trả lỗi rõ ràng và không lưu nội dung giả |
| Port 8000 đã bị chiếm | Sửa port trong lệnh `uvicorn` và `frontend/.env` |
| Port 5173 đã bị chiếm | Vite tự chọn port khác, xem trong terminal |
| `ModuleNotFoundError: fastapi` | Chạy `source .venv/bin/activate` trước khi start backend |
| `npm: command not found` | Cài Node.js 22+ từ https://nodejs.org |
| Lỗi CORS khi gọi API | Kiểm tra `CORS_ORIGINS` trong `backend/.env` có chứa URL frontend |
| Google báo `redirect_uri_mismatch` | Thêm callback đúng origin đang mở vào Google Cloud; Docker mặc định dùng `http://localhost:8080/api/auth/callback/google` |
| Port 8080 đã bị chiếm (Docker) | Sửa `"8080:80"` trong `docker-compose.yml` thành port khác |
| `docker compose up` build chậm lần đầu | Bình thường (~2-3 phút), các lần sau có cache chỉ vài giây |
| Frontend Docker không gọi được API | Chạy `docker compose logs nginx` / `frontend`; kiểm tra container `backend` đang `healthy` |
| Backend Docker vẫn dùng SQLite | Kiểm tra `docker compose logs backend` có dòng `production mode`; đảm bảo `ENV=production` + `USE_POSTGRES=true` trong compose |
| Sửa code backend nhưng không thấy đổi | Cần `docker compose up -d --build backend` (vì code copy vào image lúc build) |

---

### 12.1 Chọn retriever cho RAG

Hệ thống có hai backend truy xuất, cùng interface `BaseRetriever.retrieve(query, k)`:

| `RAG_RETRIEVER` | Hành vi |
|---|---|
| `auto` (mặc định) | Dùng embeddings khi đã có `GEMINI_API_KEY`, không có thì BM25 |
| `bm25` | Luôn chạy BM25 offline, không gọi provider |
| `embedding` | Ưu tiên embeddings; vẫn tự fallback BM25 nếu chưa cấu hình |

Bật cache vector để không phải embed lại cùng một tài liệu:

```env
RAG_USE_CHROMA=true
RAG_CHROMA_MODE=embedded      # hoặc "http" để dùng service chromadb trong Compose
CHROMA_PERSIST_DIR=app/data/chroma
```

Response của `POST /api/rag/index` và `POST /api/rag/query` có trường `retriever`
cho biết backend nào đã trả lời. Nếu provider lỗi giữa chừng, truy xuất tự động
lùi về BM25 — việc sinh đề không bị gián đoạn.

Chi tiết: [`docs/decisions/0009-rag-embedding-retriever.md`](./docs/decisions/0009-rag-embedding-retriever.md).

### 12.2 Timeout & telemetry của provider AI

`AI_REQUEST_TIMEOUT_SECONDS` là trần ở tầng ứng dụng (giữ event loop không bị
chặn), còn `AI_CONNECT_TIMEOUT_SECONDS` / `AI_READ_TIMEOUT_SECONDS` được truyền
thẳng xuống SDK — đây mới là thứ thực sự hủy được request đang chạy dở. Giữ read
timeout **thấp hơn** trần ứng dụng để SDK báo lỗi thật thay vì bị cancel.

`AI_FAILOVER_TIMEOUT_SECONDS` là ngân sách tổng cho chuỗi tuần tự OpenAI →
Gemini → DeepSeek. Provider chưa có key được bỏ qua và chuỗi dừng ngay khi nhận
được kết quả hợp lệ.

Mỗi lần gọi provider ghi một dòng log `app.ai` gồm provider, model, outcome,
`latency_ms` và số token (tắt bằng `AI_LOG_TELEMETRY=false`).

Chi tiết: [`docs/decisions/0008-provider-transport-timeouts.md`](./docs/decisions/0008-provider-transport-timeouts.md).

---

## 13. API

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/data/ingest` | Nạp dữ liệu từ nhiều nguồn |
| POST | `/api/data/normalize` | Chuẩn hóa dữ liệu |
| POST | `/api/curriculum/confirm` | Giáo viên xác nhận phạm vi |
| POST | `/api/matrix/generate` | Tạo ma trận đề |
| POST | `/api/specification/generate` | Tạo bản đặc tả |
| POST | `/api/questions/generate` | Tạo câu hỏi |
| POST | `/api/questions/review` | Giáo viên duyệt câu hỏi |
| POST | `/api/answers/generate` | Tạo đáp án & rubric |
| POST | `/api/validate` | Kiểm tra format |
| POST | `/api/export` | Export Word/PDF |

---

## 14. Roadmap

### MVP (4 tuần)

- Nạp dữ liệu đã kiểm soát (local JSON, teacher upload)
- Tạo đề theo input thủ công
- Duyệt có chọn lọc từng câu hỏi
- Lưu đề vào database
- Export Word

### Phase 2 ✅

- Upload PDF/DOCX/XLSX/PNG/JPEG; PDF native-first và OCR trang cần thiết
- RAG (BM25 offline; embeddings + ChromaDB — xem mục 12.1)
- Question bank
- PDF export
- Lưu lịch sử đề

### Phase 3 ✅

- Multi-school support
- Admin/teacher roles, OAuth (Google/Facebook)
- Tenant authorization (owner/school scoping)

### Hoàn thiện v1.0 ✅

- Giao diện sáng/tối (dark mode) + toast, skeleton, mobile drawer
- Vitest + Testing Library cho frontend, GitHub Actions CI
- Timeout ở tầng transport cho provider AI + telemetry latency/token
- Tách `exam_service.py` thành module theo pipeline
- RAG embeddings + cache vector ChromaDB, fallback BM25

### Authoring capabilities (US-168)

- Hybrid retrieval/RRF/rerank, semantic duplicate checks trong đề và ngân hàng.
- Editor trực tiếp cả bốn dạng, version check, Save/Cancel, kiểm định lại và reuse ngân hàng.
- Rich content, KaTeX, bảng/ảnh, diagram có cấu trúc; Word OMML và PDF.
- OCR Gemini/Tesseract theo trang, fallback native, structured chunks giữ nguồn/trang.
- Trộn MCQ options và đáp án/lời giải cùng nhau; TF mapping và seed tất định.

Xem [flow hiện tại](docs/02-User-Flow.md) và [cấu hình/giới hạn](docs/product/authoring-capabilities.md).
`RAG_EMBEDDING_MODEL` mặc định là `gemini-embedding-001`; `.env` cũ chỉ định
`text-embedding-004` cần đổi sang model hỗ trợ. Cache được tách theo model.

### Còn lại

- Giữ phạm vi KHTN lớp 6–9; không mở rộng môn/khối trong initiative hiện tại
- Template system
- Reranker ngoài, ANN quy mô lớn và đánh giá chất lượng trên corpus trường học

---

## 15. Tài liệu

Xem thư mục [`docs/`](./docs/) để biết thêm chi tiết:

- [Decision records](./docs/decisions/) — vì sao contract thay đổi

- [PRD - Product Requirement Document](./docs/01-PRD.md)
- [User Flow](./docs/02-User-Flow.md)
- [AI Agents Architecture](./docs/03-AI-Agents-Architecture.md)
- [Data Schema](./docs/04-Data-Schema.md)
- [Prompt Design](./docs/05-Prompt-Design.md)
- [Validation Checklist](./docs/06-Validation-Checklist.md)
- [MVP Scope](./docs/07-MVP-Scope.md)
- [Future Features](./docs/08-Future-Features.md)

---

## 16. Liên hệ

- **GitHub:** [https://github.com/kamusarj/Deka](https://github.com/kamusarj/Deka)
- **Issues:** [https://github.com/kamusarj/Deka/issues](https://github.com/kamusarj/Deka/issues)



dùng các model của gg deepmind để check xem câu hỏi (của các môn thiên về logic) sinh ra có đúng không.

### AI usage và credit trong development

Nền tảng AI Gateway, routing, usage theo user, FREE/BASIC/PRO và credit ledger
được mô tả tại [docs/ai-architecture.md](docs/ai-architecture.md). Có API
`/api/me/subscription`, `/api/me/credits`, `/api/me/usage` và CLI development để
đổi plan/cộng credit; chưa tích hợp payment. Cấu hình mới nằm trong
`backend/.env.example`; để trống routing override sẽ giữ model hiện tại.
