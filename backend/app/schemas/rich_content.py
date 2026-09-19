"""Bounded teaching content, never arbitrary HTML, URLs or executable code."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DiagramPoint(ContentModel):
    x: float = Field(ge=0, le=2000)
    y: float = Field(ge=0, le=2000)


class DiagramObject(ContentModel):
    type: Literal["line", "circle", "rectangle", "text", "polyline"]
    x: float = Field(default=0, ge=0, le=2000)
    y: float = Field(default=0, ge=0, le=2000)
    x2: float = Field(default=0, ge=0, le=2000)
    y2: float = Field(default=0, ge=0, le=2000)
    width: float = Field(default=0, ge=0, le=2000)
    height: float = Field(default=0, ge=0, le=2000)
    radius: float = Field(default=0, ge=0, le=1000)
    text: str = Field(default="", max_length=300)
    points: list[DiagramPoint] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def required_geometry(self):
        if self.type == "polyline" and len(self.points) < 2:
            raise ValueError("A polyline needs at least two points")
        if self.type == "circle" and self.radius <= 0:
            raise ValueError("A circle needs a positive radius")
        if self.type == "rectangle" and min(self.width, self.height) <= 0:
            raise ValueError("A rectangle needs positive dimensions")
        return self


class DiagramSpec(ContentModel):
    type: Literal["drawing"] = "drawing"
    width: int = Field(default=640, ge=100, le=1600)
    height: int = Field(default=360, ge=100, le=1200)
    objects: list[DiagramObject] = Field(min_length=1, max_length=100)


class TextBlock(ContentModel):
    type: Literal["text"]
    content: str = Field(min_length=1, max_length=20000)


class LatexBlock(ContentModel):
    type: Literal["latex"]
    content: str = Field(min_length=1, max_length=2000)
    display: Literal["inline", "block"] = "block"


class TableBlock(ContentModel):
    type: Literal["table"]
    headers: list[str] = Field(min_length=1, max_length=12)
    rows: list[list[str]] = Field(min_length=1, max_length=100)
    caption: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def rectangular(self):
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Every table row must have the same number of columns")
        if any(len(cell) > 2000 for row in [self.headers, *self.rows] for cell in row):
            raise ValueError("Table cell is too long")
        return self


class ImageBlock(ContentModel):
    type: Literal["image"]
    src: str = Field(max_length=2000000, pattern=r"^data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=]+$")
    alt: str = Field(min_length=1, max_length=1000)
    caption: str = Field(default="", max_length=1000)


class DiagramBlock(ContentModel):
    type: Literal["diagram"]
    spec: DiagramSpec
    alt: str = Field(min_length=1, max_length=1000)
    caption: str = Field(default="", max_length=1000)


RichBlock = TextBlock | LatexBlock | TableBlock | ImageBlock | DiagramBlock
