# Product Requirement Document (PRD)
# Smart Exam Matrix AI

## 1. Tổng quan sản phẩm

### 1.1 Tên sản phẩm
Smart Exam Matrix AI

### 1.2 Phiên bản
MVP 2.0

### 1.3 Mô tả sản phẩm
Smart Exam Matrix AI là hệ thống hỗ trợ giáo viên THCS môn Khoa học tự nhiên tạo đề kiểm tra định kì. Hệ thống tự động sinh hồ sơ đề kiểm tra hoàn chỉnh bao gồm: Ma trận đề kiểm tra, Bản đặc tả, Đề kiểm tra, Đáp án và Hướng dẫn chấm - tuân thủ đúng format theo Thông tư 22/2021/TT-BGDĐT và Công văn 7991/BGDĐT-GDTrH.

**Nguyên tắc cốt lõi:** Hệ thống **không dùng AI như nguồn kiến thức chính**. Hệ thống ưu tiên lấy dữ liệu theo thứ tự:

1. Local curriculum JSON đã chuẩn hóa
2. Tài liệu giáo viên upload (PDF, DOCX, XLSX)
3. Ngân hàng đề cũ / ma trận mẫu / bản đặc tả mẫu
4. RAG retrieval từ kho tài liệu nội bộ
5. AI API chỉ dùng để tóm tắt/chuyển đổi/sinh nội dung, **không dùng làm nguồn kiến thức chính**

> **Lưu ý quan trọng:** AI không phải nguồn kiến thức tuyệt đối. AI chỉ là công cụ xử lý, chuẩn hóa, sinh đề và format hóa dựa trên dữ liệu đã được kiểm soát. Giáo viên luôn là người xác nhận cuối cùng.

### 1.4 Điểm khác biệt so với ChatGPT
| ChatGPT thường | Smart Exam Matrix AI |
|-----------------|---------------------|
| Chỉ sinh câu hỏi | Sinh hồ sơ đề kiểm tra hoàn chỉnh |
| Không có ma trận | Ma trận đúng format quy định |
| Không có bản đặc tả | Bản đặc tả chi tiết |
| Không kiểm tra format | Validation tự động |
| Không export Word | Export Word ready-to-print |
| Tự bịa kiến thức | Dùng dữ liệu chương trình đã kiểm soát |
| Không kiểm soát nguồn | RAG + local JSON + giáo viên upload |

---

## 2. Mục tiêu sản phẩm

### 2.1 Mục tiêu chính
- Giảm 80% thời gian tạo đề kiểm tra cho giáo viên
- Đảm bảo 100% tuân thủ format quy định
- Tự động phân bổ mức độ nhận thức (Nhận biết - Thông hiểu - Vận dụng)
- Tạo hồ sơ đề kiểm tra hoàn chỉnh, sẵn sàng in
- **Kiểm soát nguồn dữ liệu** - không để AI tự bịa kiến thức

### 2.2 Mục tiêu đo lường
| Metric | Target |
|--------|--------|
| Thời gian tạo đề | < 5 phút (thay vì 2-3 giờ) |
| Độ chính xác format | 100% |
| Tổng điểm | Luôn bằng 10 |
| Phân bổ mức độ | Đúng tỷ lệ 30-40-30 |
| Dữ liệu từ nguồn kiểm soát | 100% (không dùng AI tự bịa) |

---

## 3. Người dùng mục tiêu

### 3.1 Primary Users
- Giáo viên THCS dạy môn Khoa học tự nhiên
- Tổ trưởng chuyên môn Khoa học tự nhiên

### 3.2 Secondary Users
- Giáo viên các môn khác (mở rộng tương lai)
- Giáo viên THPT (mở rộng tương lai)

### 3.3 User Persona
**Name:** Cô Nguyễn Thị Hương  
**Role:** Giáo viên KHTN lớp 8  
**Pain points:**
- Mất 2-3 giờ để tạo một bộ đề kiểm tra hoàn chỉnh
- Hay sai format ma trận và bản đặc tả
- Khó khăn trong việc phân bổ đều mức độ nhận thức
- Phải kiểm tra lại nhiều lần trước khi nộp
- Không tin tưởng AI tự bịa kiến thức

---

## 4. Tính năng chính

### 4.1 Tính năng cốt lõi (MVP)

#### F0: Nạp nguồn dữ liệu (THAY THẾ)
Thay thế hoàn toàn tư duy "AI tự thu thập tài liệu". Hệ thống ưu tiên lấy dữ liệu theo thứ tự:
1. Local curriculum JSON đã chuẩn hóa
2. Tài liệu giáo viên upload (PDF, DOCX, XLSX)
3. Ngân hàng đề cũ / ma trận mẫu / bản đặc tả mẫu
4. RAG retrieval từ kho tài liệu nội bộ
5. AI API chỉ dùng để tóm tắt/chuyển đổi/sinh nội dung

#### F1: Chuẩn hóa dữ liệu
- Dữ liệu đầu vào từ JSON/file upload/RAG phải được chuẩn hóa về schema chung
- Schema bao gồm: grade, subject, exam_type, school_year, topics, objectives

#### F2: Giáo viên xác nhận phạm vi
- Trường, năm học, khối lớp, loại kiểm tra
- Chủ đề, số tiết, yêu cầu cần đạt
- Tỉ lệ nhận biết / thông hiểu / vận dụng
- Cấu trúc đề

#### F3: Tạo ma trận đề kiểm tra
- Tự động sinh ma trận theo format Công văn 7991
- Mapping: Chủ đề × Mức độ nhận thức
- Phân bổ điểm theo tỷ lệ 30-40-30
- Hiển thị dạng bảng trực quan

#### F4: Tạo bản đặc tả đề kiểm tra
- Tự động sinh bản đặc tả chi tiết
- Mỗi câu hỏi có đầy đủ thông tin:
  - Chủ đề/Chương
  - Nội dung/đơn vị kiến thức
  - Yêu cầu cần đạt
  - Mức độ đánh giá
  - Dạng câu hỏi
  - Điểm số

#### F5: Sinh câu hỏi theo ma trận
- Sinh câu hỏi dựa trên ma trận đã xác nhận, bản đặc tả đã xác nhận
- Dữ liệu chương trình đã chuẩn hóa
- Tài liệu retrieve từ RAG nếu có
- **Không để LLM tự nghĩ chương trình ngoài dữ liệu đã nạp**

#### F6: Giáo viên duyệt câu hỏi
- Vòng lặp duyệt: Sinh câu hỏi → Giáo viên duyệt → Sửa/loại câu chưa đạt → Duyệt lại
- Các trạng thái: `accepted`, `needs_revision`, `rejected`
- Chỉ tạo lại câu không ok, câu đã duyệt giữ nguyên

#### F7: Sinh đáp án & rubric
- Chỉ sinh đáp án/rubric sau khi câu hỏi đã được duyệt
- Bao gồm: Đáp án trắc nghiệm, tự luận, thang điểm, rubric, gợi ý lời giải

#### F8: Kiểm tra format + Validation
- Format validation
- Content validation
- Matrix validation
- Rubric validation

#### F9: Xác nhận cuối cùng
- Giáo viên preview toàn bộ: Ma trận, Bản đặc tả, Đề kiểm tra, Đáp án, Rubric
- Nếu sai thì quay lại bước tương ứng

#### F10: Export Word/PDF
- Đề kiểm tra .docx
- Đáp án .docx
- Ma trận .docx
- Bản đặc tả .docx
- Rubric .docx

---

## 5. Yêu cầu tuân thủ

### 5.1 Thông tư 22/2021/TT-BGDĐT
- Đánh giá học sinh THCS/THPT
- Các mức độ nhận thức: Nhận biết, Thông hiểu, Vận dụng
- Hình thức kiểm tra: TNKQ, Đúng/Sai, Trả lời ngắn, Tự luận

### 5.2 Công văn 7991/BGDĐT-GDTrH (17/12/2024)
- Format ma trận đề kiểm tra
- Format bản đặc tả đề kiểm tra
- Cách tính và phân bổ điểm

---

## 6. Cấu trúc dữ liệu đầu vào

### 6.1 Thông tin cơ bản
```json
{
  "school": "THCS Nguyễn Du",
  "grade": 8,
  "subject": "Khoa học tự nhiên",
  "exam_type": "Giữa học kì I",
  "duration_minutes": 45,
  "school_year": "2025-2026",
  "total_score": 10
}
```

### 6.2 Blueprint (Phân bổ)
```json
{
  "difficulty_ratio": {
    "biet": 30,
    "hieu": 40,
    "van_dung": 30
  },
  "question_types": {
    "multiple_choice": true,
    "true_false": true,
    "short_answer": true,
    "essay": true
  }
}
```

### 6.3 Nguồn dữ liệu (MỚI)
```json
{
  "data_sources": [
    {
      "source_type": "local_json",
      "source_name": "curriculum_grade8_khtn.json",
      "confidence_score": 1.0
    },
    {
      "source_type": "uploaded_file",
      "source_name": "phan_phoi_chuong_trinh.pdf",
      "source_page": 1,
      "confidence_score": 0.9
    }
  ]
}
```

---

## 7. Yêu cầu phi chức năng

### 7.1 Performance
- Thời gian sinh đề: < 60 giây
- Thời gian export: < 10 giây

### 7.2 Usability
- Giao diện đơn giản, dễ sử dụng
- Không yêu cầu kiến thức kỹ thuật
- Hướng dẫn sử dụng rõ ràng

### 7.3 Compatibility
- Web-based (responsive)
- Export Word tương thích MS Word 2016+

---

## 8. Constraints & Assumptions

### 8.1 Constraints
- Chỉ hỗ trợ môn Khoa học tự nhiên (MVP)
- Chỉ hỗ trợ khối 8 (MVP)
- Cần API key cho AI model
- Dữ liệu chương trình phải từ nguồn đã kiểm soát

### 8.2 Assumptions
- Giáo viên có máy tính/điện thoại truy cập internet
- Giáo viên đã có phân phối chương trình
- Format đề kiểm tra theo đúng quy định hiện hành
- Giáo viên sẵn sàng xác nhận phạm vi trước khi sinh đề

---

## 9. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Adoption rate | 100 giáo viên trong 3 tháng | Đăng ký |
| Time saved | 80% | Survey |
| Accuracy | 100% format compliance | Audit |
| User satisfaction | > 4.5/5 | Rating |
| Data source control | 100% từ nguồn kiểm soát | Audit log |

---

## 10. Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1: MVP | 4 weeks | Core features F0-F10 |
| Phase 2: Enhancement | 4 weeks | Upload PDF/DOCX, RAG |
| Phase 3: Scale | 4 weeks | Môn khác, khối khác |

---

## 11. Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AI sinh câu hỏi sai | Medium | High | Validation layer + human review |
| Format thay đổi | Low | High | Modular design, easy update |
| User không adopt | Medium | Medium | User training, support |
| Thiếu dữ liệu chương trình | Low | High | Local JSON + teacher upload |

---

## 12. Open Questions

1. Nên dùng AI model nào? (GPT-4, Claude, Gemini)
MVP:
- Main generator: Gemini API
- Validator: Rule-based + AI cho quality check
- Embedding/RAG: Gemini embedding (future phase)
2. Có cần lưu trữ đề đã tạo không? 
Có, cần lưu trữ. Database nên dùng PostgreSQL + JSONB.
3. Có cần tính năng chia sẻ đề không? 
Chỉ cần Export Word, Export PDF.
4. Có cần tích hợp với hệ thống trường không? 
MVP chưa tích hợp. Làm standalone web app trước.
