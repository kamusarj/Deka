import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RichContent, { MathText } from "./RichContent";

describe("rich science content", () => {
  it("renders legacy text as escaped text", () => {
    const { container } = render(<MathText text={'Lá quang hợp. <script>alert(1)</script>'} />);
    expect(container).toHaveTextContent("Lá quang hợp.");
    expect(container.querySelector("script")).toBeNull();
  });
  it("renders inline and block LaTeX with KaTeX", () => {
    const { container } = render(<MathText text={String.raw`Tính $v=\frac{s}{t}$ và $$F=ma$$`} />);
    expect(container.querySelectorAll(".katex")).toHaveLength(2);
    expect(container.querySelectorAll(".katex-display")).toHaveLength(1);
    expect(container.querySelector("mfrac")).not.toBeNull();
  });
  it("renders table, embedded image and declarative diagram", () => {
    render(<RichContent blocks={[
      { type: "table", headers: ["t", "s"], rows: [["20", "100"]], caption: "Số liệu" },
      { type: "image", src: "data:image/png;base64,YQ==", alt: "Thí nghiệm" },
      { type: "diagram", alt: "Đồ thị", spec: { type: "drawing", width: 400, height: 250, objects: [{ type: "line", x: 0, y: 200, x2: 300, y2: 20 }] } },
    ]} />);
    expect(screen.getByRole("table")).toHaveTextContent("100");
    expect(screen.getByRole("img", { name: "Thí nghiệm" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Đồ thị" }).querySelector("line")).not.toBeNull();
  });
  it("does not load external images or trust active LaTeX", () => {
    const { container } = render(<><RichContent blocks={[{ type: "image", src: "https://private/secret", alt: "Ảnh" }]} /><MathText text={String.raw`$\href{javascript:alert(1)}{X}$`} /></>);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("a")).toBeNull();
  });
});
