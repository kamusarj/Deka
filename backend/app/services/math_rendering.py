"""LaTeX conversion without a TeX executable, shell escape or network access."""

from abc import ABC, abstractmethod
from functools import lru_cache
from io import BytesIO
import re
from threading import Lock

from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from fastapi import HTTPException
from PIL import Image

_math_lock = Lock()
_DELIMITERS = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$|(?<!\\)\$([^$\n]+?)(?<!\\)\$|\\\[(.+?)\\\]|\\\((.+?)\\\)", re.DOTALL)
_FORBIDDEN = re.compile(r"\\(?:input|include\w*|write\w*|read|def|gdef|edef|newcommand|renewcommand|csname|catcode|loop|href|url|html\w*|require|hspace|vspace|kern|mkern|rule|raisebox|fontsize)\b", re.I)


def math_segments(text: str):
    position = 0
    matches = list(_DELIMITERS.finditer(str(text)))
    if not matches and re.match(r"^\s*\\(?:frac|sqrt|mathrm|text|sum|Delta|rho)\b", str(text)):
        yield "latex", str(text).strip(), False
        return
    if not matches:
        # Legacy bare fractions may occur after an export label such as
        # 'Câu 1.' or 'Đáp án:'. Parse bounded brace groups without eval.
        cursor = 0
        for command in re.finditer(r"\\(?:frac|sqrt)\b", str(text)):
            if command.start() < cursor:
                continue
            end = command.end()
            groups = 2 if command.group() == r"\frac" else 1
            for _ in range(groups):
                while end < len(text) and text[end].isspace():
                    end += 1
                if end >= len(text) or text[end] != "{":
                    break
                depth = 1
                end += 1
                while end < len(text) and depth:
                    depth += (text[end] == "{") - (text[end] == "}")
                    end += 1
            if command.start() > cursor:
                yield "text", text[cursor:command.start()], False
            yield "latex", text[command.start():end], False
            cursor = end
        if cursor:
            if cursor < len(text):
                yield "text", text[cursor:], False
            return
    for match in matches:
        if match.start() > position:
            yield "text", text[position:match.start()], False
        yield "latex", next(value for value in match.groups() if value is not None), match.group(1) is not None or match.group(3) is not None
        position = match.end()
    if position < len(text):
        yield "text", text[position:], False


def validate_latex(expression):
    if not expression.strip() or len(expression) > 2000 or _FORBIDDEN.search(expression):
        raise ValueError("Công thức rỗng, quá dài hoặc chứa lệnh không hỗ trợ.")
    depth = 0
    for char in expression:
        depth += (char == "{") - (char == "}")
        if depth < 0 or depth > 32:
            raise ValueError("Cấu trúc ngoặc công thức không hợp lệ.")
    if depth:
        raise ValueError("Công thức thiếu dấu đóng ngoặc.")


class MathConverter(ABC):
    @abstractmethod
    def omml(self, expression: str):
        raise NotImplementedError


class OfficeMathConverter(MathConverter):
    def omml(self, expression: str):
        validate_latex(expression)
        from latex2mathml.converter import convert
        from mathml2omml import convert as to_omml
        value = to_omml(convert(expression))
        return parse_xml(value.replace("<m:oMath>", f"<m:oMath {nsdecls('m')}>", 1))


@lru_cache(maxsize=256)
def formula_png(expression: str) -> bytes:
    validate_latex(expression)
    from matplotlib.mathtext import math_to_image
    from matplotlib.font_manager import FontProperties
    buffer = BytesIO()
    # Matplotlib font/layout caches are shared; serialize rendering in workers.
    with _math_lock:
        math_to_image(f"${expression}$", buffer, prop=FontProperties(size=14), dpi=180, format="png", color="black")
    data = buffer.getvalue()
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 4000000:
            raise ValueError("Công thức vượt kích thước cho phép.")
    return data


def require_renderable_math(text: str):
    for kind, value, _ in math_segments(text):
        if kind == "latex":
            formula_png(value)


def math_error(error):
    return HTTPException(422, "Không render được công thức. Hãy kiểm tra cú pháp LaTeX và dùng các phép toán KHTN được hỗ trợ.")
