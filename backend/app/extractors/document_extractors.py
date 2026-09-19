"""Trích xuất text thuần từ tài liệu giáo viên upload (PDF/DOCX/XLSX).

Tất cả hàm ở đây là hàm thuần: nhận `bytes`, trả về dict
`{"text": str, "parsed_data": dict}` — không gọi AI, không chạm DB/filesystem.
"""

from io import BytesIO
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}


class UnsupportedDocumentError(ValueError):
    """File không thuộc loại được hỗ trợ (pdf/docx/xlsx)."""


class InvalidDocumentError(ValueError):
    """Supported extension, but unreadable or invalid document content."""


def _join_parts(parts: list[tuple[dict, str]]) -> tuple[str, list[dict]]:
    """Join extracted parts while retaining lightweight character spans."""
    output: list[str] = []
    spans: list[dict] = []
    cursor = 0
    for metadata, raw_text in parts:
        text = (raw_text or "").strip()
        if not text:
            continue
        if output:
            output.append("\n\n")
            cursor += 2
        start = cursor
        output.append(text)
        cursor += len(text)
        spans.append({**metadata, "start": start, "end": cursor})
    return "".join(output), spans


def resolve_file_type(filename: str) -> str:
    """Suy ra loại file từ phần mở rộng, raise nếu không hỗ trợ."""
    extension = Path(filename or "").suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(extension)
    if not file_type:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedDocumentError(
            f"Loại file '{extension or 'không rõ'}' không được hỗ trợ. Chỉ nhận: {supported}."
        )
    return file_type


def extract_pdf(data: bytes) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    from app.core.config import settings
    if len(reader.pages) > settings.DOCUMENT_MAX_PAGES:
        raise InvalidDocumentError("PDF quá nhiều trang. Hãy chia nhỏ tài liệu trước khi tải lên.")
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            content = page.extract_text() or ""
        except (ValueError, TypeError, KeyError):
            # A damaged text layer should not hide an otherwise renderable page.
            content = ""
        pages.append(({"page": index}, content))
    text, page_spans = _join_parts(pages)
    return {
        "text": text,
        "parsed_data": {"page_count": len(reader.pages), "page_spans": page_spans, "pages": [{**metadata, "text": value} for metadata, value in pages]},
    }


def extract_docx(data: bytes) -> dict:
    from docx import Document

    document = Document(BytesIO(data))
    from docx.oxml.ns import qn
    math_count = sum(1 for _ in document.element.iter(qn("m:oMath")))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    paragraphs = [line for line in paragraphs if line]

    tables = []
    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        tables.append(rows)

    parts = [
        ({"kind": "paragraph", "paragraph": index}, value)
        for index, value in enumerate(paragraphs, start=1)
    ]
    for table_index, table in enumerate(tables, start=1):
        for row_index, row in enumerate(table, start=1):
            parts.append(
                (
                    {"kind": "table", "table": table_index, "row": row_index},
                    " | ".join(cell for cell in row),
                )
            )
    text, block_spans = _join_parts(parts)
    return {
        "text": text,
        "parsed_data": {
            "extraction_warnings": ([f"DOCX chứa {math_count} công thức Office Math chưa được native extractor chuyển đổi. Hãy dùng PDF/ảnh và OCR để giữ công thức."] if math_count else []),
            "paragraph_count": len(paragraphs),
            "tables": tables,
            "block_spans": block_spans,
        },
    }


def extract_xlsx(data: bytes) -> dict:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except OSError as error:
        # The reader operates on in-memory bytes; openpyxl uses OSError when
        # the Office archive has no valid workbook part.
        raise InvalidDocumentError("Tệp XLSX không chứa bảng tính hợp lệ. Vui lòng kiểm tra và tải lại.") from error
    sheets = []
    sheet_parts = []
    try:
        for worksheet in workbook.worksheets:
            rows = []
            if worksheet.max_row and worksheet.max_column and worksheet.max_row * worksheet.max_column > 200000:
                raise InvalidDocumentError("Bảng tính vượt giới hạn 200.000 ô.")
            for raw_row in worksheet.iter_rows(values_only=True):
                cells = ["" if value is None else str(value) for value in raw_row]
                if not any(cell.strip() for cell in cells):
                    continue
                rows.append(cells)
            sheets.append({"name": worksheet.title, "rows": rows})
            sheet_parts.append(
                ({"sheet": worksheet.title}, "\n".join("\t".join(row) for row in rows))
            )
    finally:
        workbook.close()
    text, sheet_spans = _join_parts(sheet_parts)
    return {
        "text": text,
        "parsed_data": {"sheets": sheets, "sheet_spans": sheet_spans},
    }


_EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "xlsx": extract_xlsx,
}


def extract_document(filename: str, data: bytes) -> dict:
    """Dispatch trích xuất theo loại file. Trả về dict gồm file_type, text, parsed_data."""
    from zipfile import BadZipFile

    from lxml.etree import XMLSyntaxError
    from openpyxl.utils.exceptions import InvalidFileException
    from pypdf.errors import FileNotDecryptedError, ParseError, PdfReadError

    file_type = resolve_file_type(filename)
    validate_container(file_type, data)
    try:
        extracted = _EXTRACTORS[file_type](data)
    except InvalidDocumentError:
        raise
    except FileNotDecryptedError as error:
        raise InvalidDocumentError("PDF được bảo vệ bằng mật khẩu. Vui lòng tải lên bản đã bỏ mật khẩu.") from error
    except (BadZipFile, XMLSyntaxError, InvalidFileException, PdfReadError, ParseError, KeyError, ValueError) as error:
        raise InvalidDocumentError(
            "Không đọc được tài liệu. Tệp có thể bị hỏng hoặc không đúng định dạng PDF, DOCX, XLSX. Vui lòng kiểm tra và tải lại."
        ) from error
    return {
        "file_type": file_type,
        "text": extracted["text"],
        "parsed_data": extracted["parsed_data"],
    }


def validate_container(file_type, data):
    """Bound Office decompression before handing bytes to XML/Office parsers."""
    if file_type == 'pdf':
        if not data.lstrip().startswith(b'%PDF-'):
            raise InvalidDocumentError('Nội dung tệp không phải PDF hợp lệ.')
        return
    if file_type not in {'docx', 'xlsx'}:
        return
    from zipfile import ZipFile, BadZipFile
    from pathlib import PurePosixPath
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(item.file_size for item in entries) > 100 * 1024 * 1024:
                raise InvalidDocumentError('Tài liệu giải nén vượt giới hạn tài nguyên.')
            names = set()
            for entry in entries:
                path = PurePosixPath(entry.filename.replace('\\', '/'))
                if (path.is_absolute() or '..' in path.parts or ':' in entry.filename
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000
                    or entry.file_size > 20 * 1024 * 1024
                    or entry.file_size > max(1, entry.compress_size) * 200):
                    raise InvalidDocumentError('Tài liệu nén chứa entry không an toàn hoặc quá lớn.')
                if entry.filename.lower().endswith(('.xml', '.rels')):
                    from defusedxml.ElementTree import fromstring
                    from defusedxml.common import DefusedXmlException
                    from xml.etree.ElementTree import ParseError
                    try:
                        fromstring(archive.read(entry), forbid_dtd=True, forbid_entities=True, forbid_external=True)
                    except (DefusedXmlException, ParseError) as error:
                        raise InvalidDocumentError('XML không hợp lệ hoặc chứa DTD/entity không được phép.') from error
                names.add(entry.filename)
            marker = 'word/document.xml' if file_type == 'docx' else 'xl/workbook.xml'
            if marker not in names:
                raise InvalidDocumentError('Nội dung tệp không khớp định dạng Office.')
    except BadZipFile as error:
        raise InvalidDocumentError('Không đọc được cấu trúc tệp Office.') from error
