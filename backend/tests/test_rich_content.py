from copy import deepcopy
from io import BytesIO
import base64
from zipfile import ZipFile

import pytest
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfReader

from app.services.rich_content import normalize_blocks, diagram_svg, diagram_png
from app.services.math_rendering import OfficeMathConverter, formula_png, math_segments
from app.services.export_service import ExportService
from app.services.pdf_export_service import PdfExportService
from app.agents.verification_agent import VerificationAgent
from tests.test_export import _exam_dict


def blocks():
    buffer = BytesIO()
    Image.new('RGB', (64, 48), 'blue').save(buffer, format='PNG')
    return [
        {'type': 'latex', 'content': r'v=\frac{s}{t}', 'display': 'block'},
        {'type': 'table', 'headers': ['t (s)', 's (m)'], 'rows': [['0', '0'], ['20', '100']], 'caption': 'Số liệu chuyển động'},
        {'type': 'image', 'src': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode(), 'alt': 'Ảnh thí nghiệm'},
        {'type': 'diagram', 'alt': 'Đồ thị quãng đường theo thời gian', 'spec': {'type': 'drawing', 'width': 400, 'height': 250, 'objects': [
            {'type': 'line', 'x': 30, 'y': 220, 'x2': 380, 'y2': 220},
            {'type': 'line', 'x': 30, 'y': 220, 'x2': 30, 'y2': 20},
            {'type': 'polyline', 'points': [{'x': 30, 'y': 220}, {'x': 350, 'y': 40}]},
            {'type': 'text', 'x': 60, 'y': 20, 'text': 's (m) <script>'},
        ]}},
    ]


def test_rich_serialization_and_safe_diagram():
    value = normalize_blocks(blocks())
    assert normalize_blocks(value) == value
    svg = diagram_svg(value[3]['spec'])
    assert '&lt;script&gt;' in svg and '<script>' not in svg
    assert diagram_png(value[3]['spec']).startswith(b'\x89PNG')
    assert normalize_blocks(None) == []


@pytest.mark.parametrize('block', [
    {'type': 'image', 'src': 'https://example.com/private.png', 'alt': 'x'},
    {'type': 'image', 'src': 'data:image/png;base64,YQ==', 'alt': 'x'},
    {'type': 'table', 'headers': ['a', 'b'], 'rows': [['a']]},
    {'type': 'latex', 'content': r'\input{/etc/passwd}'},
    {'type': 'latex', 'content': r'\frac{a}{b'},
    {'type': 'html', 'content': '<script>alert(1)</script>'},
])
def test_rejects_unsafe_or_invalid_blocks(block):
    with pytest.raises((ValueError, OSError, ValidationError)):
        normalize_blocks([block])


def test_math_conversion_and_delimiters():
    assert 'oMath' in OfficeMathConverter().omml(r'\frac{a}{b}').tag
    assert formula_png(r'F=ma').startswith(b'\x89PNG')
    assert [v for k, v, _ in math_segments(r'Tính $v=\frac{s}{t}$ và $$F=ma$$') if k == 'latex'] == [r'v=\frac{s}{t}', 'F=ma']


def test_word_contains_editable_math_table_and_embedded_images():
    data = _exam_dict()
    data['questions'][0]['content'] = r'Tính $v=\frac{s}{t}$.'
    data['questions'][0]['rich_content'] = blocks()
    before = deepcopy(data)
    document = ExportService().create_full_docx(data)
    output = BytesIO()
    document.save(output)
    with ZipFile(output) as archive:
        xml = archive.read('word/document.xml').decode()
        assert '<m:oMath' in xml and '<m:f>' in xml
        assert '<w:tbl>' in xml
        assert 'Số liệu chuyển động' in xml
        assert r'\frac' not in xml
        assert len([n for n in archive.namelist() if n.startswith('word/media/')]) == 2
    assert data == before


def test_pdf_renders_inline_math_and_all_blocks():
    data = _exam_dict()
    data['questions'][0]['content'] = r'Tính $v=\frac{s}{t}$.'
    data['questions'][0]['rich_content'] = blocks()
    output = PdfExportService().create_full_pdf(data)
    reader = PdfReader(BytesIO(output))
    assert any(page.images for page in reader.pages)
    assert 'Số liệu chuyển động' in '\n'.join(page.extract_text() for page in reader.pages)


def test_independent_solver_receives_rich_question_without_truth_values():
    q = {'type': 'true_false', 'content': 'Dựa vào hình', 'rich_content': blocks(), 'statements': [{'id': 's1', 'content': 'Đúng?', 'is_true': True}]}
    payload = VerificationAgent()._question_payload(q)
    assert payload['rich_content'][0] == q['rich_content'][0]
    assert 'src' not in payload['rich_content'][2]
    assert payload['rich_content'][2]['alt'] == 'Ảnh thí nghiệm'
    assert 'is_true' not in payload['statements'][0]


def test_pdf_inline_math_preserves_surrounding_spaces():
    from app.services.rich_export import pdf_paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    paragraph = pdf_paragraph('Tính $F=ma$ theo công thức.', getSampleStyleSheet()['BodyText'])
    texts = ''.join(fragment.text for fragment in paragraph.frags)
    assert 'Tính\xa0' in texts and '\xa0theo công thức.' in texts


def test_word_legacy_bare_fraction_after_question_label_is_math():
    data = _exam_dict()
    data['questions'][0]['content'] = r'\frac{a}{b}'
    document = ExportService().create_full_docx(data)
    xml = document._element.xml
    assert '<m:f>' in xml and r'\frac' not in xml


def test_word_falls_back_to_formula_image_when_omml_converter_fails(monkeypatch):
    monkeypatch.setattr(OfficeMathConverter, 'omml', lambda *args: (_ for _ in ()).throw(ValueError('unsupported OMML')))
    data = _exam_dict()
    data['questions'][0]['content'] = r'Tính $v=\frac{s}{t}$.'
    document = ExportService().create_full_docx(data)
    buffer = BytesIO()
    document.save(buffer)
    with ZipFile(buffer) as archive:
        assert any(name.startswith('word/media/') for name in archive.namelist())
        assert r'\frac' not in archive.read('word/document.xml').decode()
