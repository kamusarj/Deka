"""Validate rich blocks and render declarative science diagrams safely."""

import base64
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont
from pydantic import TypeAdapter

from app.schemas.rich_content import DiagramSpec, RichBlock

_blocks = TypeAdapter(list[RichBlock])
FONT = Path(__file__).resolve().parents[1] / "assets/fonts/DejaVuSans.ttf"


def image_bytes(src: str) -> bytes:
    if not src.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")) or len(src) > 2000000:
        raise ValueError("Chỉ nhận ảnh PNG/JPEG được nhúng, tối đa 1,5 MB.")
    data = base64.b64decode(src.split(",", 1)[1], validate=True)
    with Image.open(BytesIO(data)) as image:
        if image.format not in {"PNG", "JPEG"} or image.width * image.height > 16000000:
            raise ValueError("Ảnh không hợp lệ hoặc vượt quá 16 triệu điểm ảnh.")
        image.verify()
    return data


def normalize_blocks(value) -> list[dict]:
    if value is None:
        return []
    if len(value) > 32:
        raise ValueError("Mỗi câu chỉ có tối đa 32 khối nội dung.")
    parsed = _blocks.validate_python(value)
    if sum(len(block.model_dump_json()) for block in parsed) > 4000000:
        raise ValueError("Nội dung bổ sung của câu hỏi vượt giới hạn 4 MB.")
    result = []
    for block in parsed:
        data = block.model_dump()
        from app.services.math_rendering import formula_png, require_renderable_math
        if block.type == "image":
            image_bytes(block.src)
        elif block.type == "latex":
            formula_png(block.content)
        elif block.type == "text":
            require_renderable_math(block.content)
        elif block.type == "table":
            for cell in [*block.headers, *(cell for row in block.rows for cell in row)]:
                require_renderable_math(cell)
        if data.get("caption"):
            require_renderable_math(data["caption"])
        result.append(data)
    return result


def diagram_svg(value: dict) -> str:
    spec = DiagramSpec.model_validate(value)
    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f"0 0 {spec.width} {spec.height}", "width": str(spec.width), "height": str(spec.height)})
    for item in spec.objects:
        attributes = {"stroke": "#18232d", "stroke-width": "2", "fill": "none"}
        if item.type == "line":
            attributes.update(x1=str(item.x), y1=str(item.y), x2=str(item.x2), y2=str(item.y2))
            ET.SubElement(root, "line", attributes)
        elif item.type == "circle":
            attributes.update(cx=str(item.x), cy=str(item.y), r=str(item.radius))
            ET.SubElement(root, "circle", attributes)
        elif item.type == "rectangle":
            attributes.update(x=str(item.x), y=str(item.y), width=str(item.width), height=str(item.height))
            ET.SubElement(root, "rect", attributes)
        elif item.type == "polyline":
            attributes["points"] = " ".join(f"{p.x},{p.y}" for p in item.points)
            ET.SubElement(root, "polyline", attributes)
        else:
            node = ET.SubElement(root, "text", {"x": str(item.x), "y": str(item.y), "font-size": "16", "font-family": "DejaVu Sans", "fill": "#18232d"})
            node.text = item.text
    return ET.tostring(root, encoding="unicode")


def diagram_png(value: dict) -> bytes:
    spec = DiagramSpec.model_validate(value)
    scale = 2
    image = Image.new("RGB", (spec.width * scale, spec.height * scale), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), 16 * scale)
    for item in spec.objects:
        x, y = item.x * scale, item.y * scale
        if item.type == "line":
            draw.line((x, y, item.x2 * scale, item.y2 * scale), fill="black", width=2 * scale)
        elif item.type == "circle":
            r = item.radius * scale
            draw.ellipse((x - r, y - r, x + r, y + r), outline="black", width=2 * scale)
        elif item.type == "rectangle":
            draw.rectangle((x, y, x + item.width * scale, y + item.height * scale), outline="black", width=2 * scale)
        elif item.type == "polyline":
            draw.line([(p.x * scale, p.y * scale) for p in item.points], fill="black", width=2 * scale)
        else:
            draw.text((x, y), item.text, font=font, fill="black", anchor="ls")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
