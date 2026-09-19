"""Native-first document processing with selective, bounded OCR and provenance."""
from abc import ABC, abstractmethod
from io import BytesIO
import re
import time
import unicodedata
from threading import Lock

from PIL import Image, ImageOps

from app.core.config import settings
from app.services.resource_capacity import bounded_parser
from app.extractors.document_extractors import extract_document, resolve_file_type, InvalidDocumentError, _join_parts
from app.extractors.ocr import OCRProvider, create_ocr_provider

_pdf_lock = Lock()  # PDFium is not thread-safe across document instances.
_DEFAULT = object()


def normalize_content(text: str) -> str:
    text = unicodedata.normalize('NFC', text or '').replace('\r\n', '\n').replace('\r', '\n')
    text = ''.join(c for c in text if c in '\n\t' or not unicodedata.category(c).startswith('C'))
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def extraction_quality(text: str) -> dict:
    compact = re.sub(r'\s', '', text or '')
    reasons = []
    if len(compact) < settings.OCR_NATIVE_MIN_CHARS:
        reasons.append('sparse_text')
    if '\ufffd' in compact or '(cid:' in compact or '[không đọc rõ]' in text:
        reasons.append('broken_encoding')
    if compact and sum(c.isalnum() for c in compact) / len(compact) < settings.OCR_NATIVE_MIN_ALNUM_RATIO:
        reasons.append('unreadable_layout')
    return {'needs_ocr': bool(reasons), 'reasons': reasons, 'native_characters': len(compact)}


def structured_blocks(text: str, *, page: int | None, metadata: dict | None = None) -> list[dict]:
    """Preserve tables and formula delimiters; never split their rows/tokens."""
    text = normalize_content(text)
    output, pending, kind = [], [], 'text'
    formula_open = False
    def flush():
        nonlocal pending
        if pending:
            content = '\n'.join(pending).strip()
            output.append({'id': f'b{len(output)}', 'page_number': page, 'content_type': kind, 'text': content, 'normalized_text': normalize_content(content), 'metadata': dict(metadata or {})})
        pending = []
    for line in text.splitlines():
        stripped = line.strip()
        if formula_open:
            pending.append(line)
            if '$$' in line or r'\]' in line:
                formula_open = False
                flush()
            continue
        if not stripped:
            flush()
            continue
        next_kind = 'heading' if stripped.startswith('#') else 'table' if '|' in stripped or '\t' in line else 'formula' if stripped.startswith(('$$', r'\[')) else 'caption' if re.match(r'^(Hình|Figure|Bảng)\s+\d', stripped, re.I) else 'text'
        if next_kind != kind or next_kind in {'heading', 'caption', 'formula'}:
            flush()
            kind = next_kind
        pending.append(line)
        if kind == 'formula':
            formula_open = (stripped.startswith('$$') and stripped.count('$$') == 1) or (stripped.startswith(r'\[') and r'\]' not in stripped)
            if not formula_open:
                flush()
    flush()
    return output


class DocumentExtractor(ABC):
    @abstractmethod
    def extract(self, filename: str, data: bytes) -> dict:
        raise NotImplementedError


class NativeDocumentExtractor(DocumentExtractor):
    def extract(self, filename: str, data: bytes) -> dict:
        return extract_document(filename, data)


def image_for_ocr(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in {'PNG', 'JPEG'} or source.width * source.height > settings.OCR_MAX_IMAGE_PIXELS:
                raise ValueError('Ảnh vượt giới hạn kích thước hoặc không phải PNG/JPEG.')
            image = ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((settings.OCR_RENDER_MAX_SIDE, settings.OCR_RENDER_MAX_SIDE))
            output = BytesIO()
            image.save(output, format='PNG')
            return output.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise InvalidDocumentError('Không đọc được ảnh PNG/JPEG hoặc ảnh quá lớn.') from error


def render_pdf_page(data: bytes, page_number: int) -> bytes:
    import pypdfium2 as pdfium
    with _pdf_lock:
        document = pdfium.PdfDocument(data)
        try:
            page = document[page_number - 1]
            try:
                width, height = page.get_size()
                scale = min(settings.OCR_RENDER_DPI / 72, settings.OCR_RENDER_MAX_SIDE / max(width, height))
                bitmap = page.render(scale=scale)
                try:
                    output = BytesIO()
                    bitmap.to_pil().save(output, format='PNG')
                    return output.getvalue()
                finally:
                    bitmap.close()
            finally:
                page.close()
        finally:
            document.close()


class DocumentProcessor:
    def __init__(self, extractor: DocumentExtractor | None = None, ocr: OCRProvider | None = _DEFAULT):
        self.extractor = extractor or NativeDocumentExtractor()
        self.ocr = create_ocr_provider() if ocr is _DEFAULT else ocr

    @bounded_parser
    def process(self, filename: str, data: bytes, *, ocr_mode: str = 'auto') -> dict:
        if ocr_mode not in {'auto', 'native', 'ocr'}:
            raise InvalidDocumentError('Chế độ đọc tài liệu không hợp lệ.')
        file_type = resolve_file_type(filename)
        if file_type == 'image':
            image = image_for_ocr(data)
            extracted = {'file_type': file_type, 'text': '', 'parsed_data': {'page_count': 1}}
            pages = [{'page': 1, 'text': ''}]
        else:
            extracted = self.extractor.extract(filename, data)
            pages = extracted['parsed_data'].get('pages', [])
        parsed = extracted['parsed_data']
        warnings, blocks, parts, assessments = list(parsed.get("extraction_warnings") or []), [], [], []
        attempted, deadline = 0, time.monotonic() + settings.OCR_DOCUMENT_TIMEOUT_SECONDS
        for page in pages:
            number, text = page['page'], page['text']
            quality = extraction_quality(text)
            method, provider = 'native', None
            needs_ocr = ocr_mode == 'ocr' or quality['needs_ocr'] or file_type == 'image'
            if needs_ocr and ocr_mode != 'native':
                if self.ocr is None:
                    warnings.append(f'Trang {number}: chưa cấu hình OCR; chỉ giữ nội dung đọc trực tiếp được.')
                elif attempted >= settings.OCR_MAX_PAGES or time.monotonic() >= deadline:
                    warnings.append(f'Trang {number}: vượt giới hạn OCR; hãy chia nhỏ tài liệu.')
                else:
                    attempted += 1
                    try:
                        raster = image if file_type == 'image' else render_pdf_page(data, number)
                        result = self.ocr.recognize(raster)
                        recognized = normalize_content(result.text)
                        if not recognized or 'broken_encoding' in extraction_quality(recognized)['reasons']:
                            raise ValueError('Empty/unreadable OCR result')
                        text, method, provider = recognized, 'ocr', result.provider
                        if not result.preserves_math:
                            warnings.append(f'Trang {number}: OCR văn bản; cần kiểm tra lại công thức và bố cục.')
                    except Exception:
                        warnings.append(f'Trang {number}: OCR không thành công; chỉ giữ phần đọc trực tiếp được.')
            assessments.append({'page_number': number, **quality, 'method': method, 'ocr_provider': provider})
            parts.append(({'page': number}, normalize_content(text)))
            blocks.extend(structured_blocks(text, page=number, metadata={'extraction_method': method, 'ocr_provider': provider}))
        if pages:
            extracted['text'], parsed['page_spans'] = _join_parts(parts)
            parsed.pop('pages', None)
        else:
            spans = parsed.get('block_spans') or parsed.get('sheet_spans') or [{'start': 0, 'end': len(extracted['text'])}]
            from itertools import groupby
            def group_key(span):
                return ('table', span['table']) if span.get('kind') == 'table' else ('span', span['start'])
            for _, group in groupby(spans, key=group_key):
                members = list(group)
                first = members[0]
                text = '\n'.join(extracted['text'][span['start']:span['end']] for span in members)
                metadata = {'extraction_method': 'native', **{k: v for k, v in first.items() if k not in {'start', 'end', 'row'}}}
                if first.get('kind') == 'table' or first.get('sheet'):
                    # Keep native table headers together with their data rows,
                    # including one-column tables with no pipe separator.
                    blocks.append({'id': '', 'page_number': None, 'content_type': 'table', 'text': text, 'normalized_text': normalize_content(text), 'metadata': metadata})
                else:
                    blocks.extend(structured_blocks(text, page=None, metadata=metadata))
        for index, block in enumerate(blocks):
            block['id'] = f'block_{index}'
        if not extracted['text'].strip():
            raise InvalidDocumentError('Không đọc được nội dung tài liệu. Với bản scan/ảnh, hãy cấu hình OCR hoặc tải bản rõ hơn.')
        parsed.update(blocks=blocks, extraction_warnings=warnings, page_quality=assessments, ocr_pages=attempted, extraction_version=1)
        return extracted
