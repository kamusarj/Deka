"""Xuất đề kiểm tra ra PDF (Phase 2) bằng reportlab.

Dùng font Unicode DejaVuSans (đính kèm trong app/assets/fonts) để render dấu
tiếng Việt. Xuất từng tài liệu riêng như bản Word và tái dùng dict từ
`ExamService._to_full_response`. Phần đề bài KHÔNG lộ đáp án (mirror docx).
"""

from app.services.exam.export_document import DOCUMENT_TITLES, require_export_document, select_export_data
from app.services.rich_export import pdf_paragraph, pdf_blocks

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
_FONT_NORMAL = "DejaVuSans"
_FONT_BOLD = "DejaVuSans-Bold"
_fonts_registered = False


def _ensure_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont(_FONT_NORMAL, str(_FONT_DIR / "DejaVuSans.ttf")))
    bold_path = _FONT_DIR / "DejaVuSans-Bold.ttf"
    if bold_path.exists():
        pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(bold_path)))
        pdfmetrics.registerFontFamily(_FONT_NORMAL, normal=_FONT_NORMAL, bold=_FONT_BOLD)
    _fonts_registered = True


class PdfExportService:
    """Tạo file PDF hồ sơ đề, sẵn sàng in."""

    DIFFICULTY_LABELS = {
        "nhan_biet": "Nhận biết",
        "thong_hieu": "Thông hiểu",
        "van_dung": "Vận dụng",
    }
    QUESTION_TYPE_LABELS = {
        "multiple_choice": "Trắc nghiệm",
        "true_false": "Đúng/Sai",
        "short_answer": "Trả lời ngắn",
        "essay": "Tự luận",
    }

    def __init__(self):
        _ensure_fonts()
        self.styles = self._build_styles()

    def _build_styles(self) -> dict:
        base = getSampleStyleSheet()
        normal = ParagraphStyle(
            "VnBody", parent=base["Normal"], fontName=_FONT_NORMAL, fontSize=11, leading=15
        )
        bold_font = _FONT_BOLD if (_FONT_DIR / "DejaVuSans-Bold.ttf").exists() else _FONT_NORMAL
        return {
            "title": ParagraphStyle(
                "VnTitle", parent=normal, fontName=bold_font, fontSize=18,
                leading=22, alignment=TA_CENTER, spaceAfter=10,
            ),
            "h1": ParagraphStyle("VnH1", parent=normal, fontName=bold_font, fontSize=14, leading=18, spaceBefore=8, spaceAfter=6),
            "h2": ParagraphStyle("VnH2", parent=normal, fontName=bold_font, fontSize=12, leading=16, spaceBefore=6, spaceAfter=4),
            "h3": ParagraphStyle("VnH3", parent=normal, fontName=bold_font, fontSize=11, leading=14, spaceBefore=4, spaceAfter=2),
            "body": normal,
            "cell": ParagraphStyle("VnCell", parent=normal, fontSize=9, leading=12),
        }

    def create_full_pdf(self, exam_data: dict, *, include_answers: bool = True,
                        document: str = "exam", variant_code: str | None = None) -> bytes:
        require_export_document(document, include_answers)
        data = select_export_data(exam_data, variant_code)
        buffer = BytesIO()
        pdf = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
            title=DOCUMENT_TITLES[document],
        )
        story = []
        self._header(story, data["exam_info"], DOCUMENT_TITLES[document])
        story.append(self._p(f"Mã đề {variant_code}" if variant_code else "Bản gốc", "h2"))
        if document == "exam":
            self._questions(story, data["questions"], heading=None)
        elif document == "matrix":
            self._matrix(story, data["matrix"], data["summary"])
        elif document == "specification":
            self._specification(story, data["specification"])
        else:
            self._answers(story, data["answer_key"], heading=None)
            self._rubric(story, data["rubric"])
        pdf.build(story)
        return buffer.getvalue()

    # ── Sections ────────────────────────────────────────────────

    def _header(self, story: list, info: dict, title: str) -> None:
        story.append(self._p(title.upper(), "title"))
        story.append(self._p(f"Trường: {info['school']}", "body"))
        story.append(self._p(f"Môn: {info['subject']} - Lớp {info['grade']}", "body"))
        story.append(self._p(f"Loại kiểm tra: {info['exam_type']}", "body"))
        story.append(
            self._p(
                f"Năm học: {info['school_year']} - Thời gian: {info['duration_minutes']} phút",
                "body",
            )
        )

    def _matrix(self, story: list, matrix, summary) -> None:
        rows = [["Nội dung", "Nhận biết", "Thông hiểu", "Vận dụng", "Tổng câu", "Tổng điểm"]]
        for row in matrix:
            total_count = (
                row["nhan_biet"]["count"] + row["thong_hieu"]["count"] + row["van_dung"]["count"]
            )
            rows.append([
                row["lesson_name"],
                self._cell_text(row["nhan_biet"]),
                self._cell_text(row["thong_hieu"]),
                self._cell_text(row["van_dung"]),
                str(total_count),
                str(row["total_score"]),
            ])
        story.append(self._table(rows, col_widths=[4.5 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm, 1.8 * cm, 1.8 * cm]))
        story.append(Spacer(1, 6))
        story.append(
            self._p(
                f"Tổng điểm: {summary['total_score']} - Tổng số câu: {summary['total_questions']}",
                "body",
            )
        )

    def _specification(self, story: list, specification) -> None:
        rows = [["Câu", "Nội dung", "Yêu cầu cần đạt", "Mức độ", "Dạng câu", "Điểm"]]
        for spec in specification:
            rows.append([
                str(spec["question_number"]),
                spec["knowledge_unit"],
                spec["achievement"],
                self._difficulty_text(spec["difficulty"]),
                self._question_type_text(spec["question_type"]),
                str(spec["score"]),
            ])
        story.append(self._table(rows, col_widths=[1.2 * cm, 3.6 * cm, 5.0 * cm, 2.2 * cm, 2.2 * cm, 1.3 * cm]))

    def _questions(self, story: list, questions, *, heading: str | None) -> None:
        if heading:
            story.append(PageBreak())
            story.append(self._p(heading, "h1"))
        for question in questions:
            story.append(
                self._p(
                    f"Câu {question['number']} ({question['score']} điểm). {question['content']}",
                    "body",
                )
            )
            story.extend(pdf_blocks(question.get("rich_content"), self.styles["body"]))
            if question["type"] == "multiple_choice":
                for key, value in question.get("options", {}).items():
                    story.append(self._p(f"{key}. {value}", "body"))
            if question["type"] == "true_false":
                for statement in question.get("statements", []):
                    story.append(self._p(f"- {statement.get('content', '')}", "body"))
            if question["type"] == "essay":
                for sub_question in question.get("sub_questions") or []:
                    story.append(
                        self._p(f"- {sub_question['content']} ({sub_question['score']} điểm)", "body")
                    )
            story.append(Spacer(1, 4))

    def _answers(self, story: list, answer_key, *, heading: str | None) -> None:
        if heading:
            story.append(PageBreak())
            story.append(self._p(heading, "h1"))
        for answer in answer_key:
            prefix = f"Câu {answer.get('question_number', '')}: "
            answer_type = answer.get("type")
            if answer_type == "multiple_choice":
                story.append(self._p(prefix + (answer.get("correct_answer") or ""), "body"))
            elif answer_type == "true_false":
                values = ["Đ" if item.get("is_true") else "S" for item in answer.get("answers", [])]
                story.append(self._p(prefix + ", ".join(values), "body"))
            elif answer_type == "short_answer":
                story.append(self._p(prefix + (answer.get("correct_answer") or ""), "body"))
            else:
                story.append(self._p(prefix + (answer.get("model_answer") or "Xem hướng dẫn chấm."), "body"))

    def _rubric(self, story: list, rubric) -> None:
        story.append(PageBreak())
        story.append(self._p("HƯỚNG DẪN CHẤM", "h1"))
        for item in rubric:
            story.append(self._p(f"Câu {item['question_number']} ({item['total_score']} điểm)", "h3"))
            for criterion in item["criteria"]:
                story.append(self._p(f"{criterion['name']}: tối đa {criterion['max_score']} điểm", "body"))
                for level in criterion["levels"]:
                    story.append(self._p(f"- {level['score']} điểm: {level['description']}", "body"))

    # ── Helpers ─────────────────────────────────────────────────

    def _p(self, text, style_key: str) -> Paragraph:
        return pdf_paragraph(text, self.styles[style_key])

    def _table(self, rows, *, col_widths) -> Table:
        data = [[self._p(cell, "cell") for cell in row] for row in rows]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, -1), _FONT_NORMAL),
            ])
        )
        return table

    def _cell_text(self, cell) -> str:
        if cell["count"] == 0:
            return "-"
        return f"{cell['count']} câu / {cell['score']} điểm"

    def _difficulty_text(self, value: str) -> str:
        return self.DIFFICULTY_LABELS.get(value, value)

    def _question_type_text(self, value: str) -> str:
        return self.QUESTION_TYPE_LABELS.get(value, value)
