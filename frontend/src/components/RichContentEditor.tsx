import { useState } from "react";
import type { RichBlock, DiagramObject } from "../types";
import RichContent from "./RichContent";
import SelectControl from "./SelectControl";

export default function RichContentEditor({ blocks, onChange, disabled = false }: { blocks: RichBlock[]; onChange: (blocks: RichBlock[]) => void; disabled?: boolean }) {
  const [error, setError] = useState("");
  function update(index: number, value: RichBlock) { onChange(blocks.map((item, position) => position === index ? value : item)); }
  return <fieldset className="rich-content-editor" disabled={disabled}>
    <legend>Nội dung bổ sung</legend>
    <p className="muted">Công thức trong nội dung dùng $…$ hoặc $$…$$. Bảng và hình bên dưới được giữ khi lưu và xuất đề.</p>
    {blocks.map((block, index) => <fieldset key={index}>
      <legend>Khối {index + 1}</legend>
      {(block.type === "text" || block.type === "latex") && <label>{block.type === "latex" ? "Công thức LaTeX" : "Nội dung bổ sung"}<textarea value={block.content} onChange={(event) => update(index, { ...block, content: event.target.value })} /></label>}
      {block.type === "latex" && <label>Kiểu công thức<SelectControl
        ariaLabel={`Kiểu công thức khối ${index + 1}`}
        value={block.display}
        disabled={disabled}
        onChange={(display) => update(index, { ...block, display })}
        options={[{ value: "inline", label: "Trong dòng" }, { value: "block", label: "Riêng một dòng" }]}
      /></label>}
      {block.type === "table" && <>
        <label>Tiêu đề cột (cách nhau bằng |)<input value={block.headers.join(" | ")} onChange={(event) => update(index, { ...block, headers: event.target.value.split("|").map(value => value.trim()) })} /></label>
        <label>Các hàng (mỗi dòng một hàng, cột cách nhau bằng |)<textarea value={block.rows.map(row => row.join(" | ")).join("\n")} onChange={(event) => update(index, { ...block, rows: event.target.value.split("\n").map(row => row.split("|").map(cell => cell.trim())) })} /></label>
      </>}
      {(block.type === "image" || block.type === "diagram") && <label>Mô tả hình<input required value={block.alt} onChange={(event) => update(index, { ...block, alt: event.target.value })} /></label>}
      {"caption" in block && <label>Chú thích<input value={block.caption ?? ""} onChange={(event) => update(index, { ...block, caption: event.target.value })} /></label>}
      {block.type === "diagram" && <>
        {block.spec.objects.map((object, position) => {
          function updateObject(change: Partial<DiagramObject>) { if (block.type === "diagram") update(index, { ...block, spec: { ...block.spec, objects: block.spec.objects.map((item, i) => i === position ? { ...item, ...change } : item) } }); }
          return <fieldset key={position}><legend>Đối tượng {position + 1}</legend>
            <label>Loại đối tượng<SelectControl
              ariaLabel={`Loại đối tượng ${position + 1}, khối ${index + 1}`}
              value={object.type}
              disabled={disabled}
              onChange={(type) => updateObject({ type })}
              options={[
                { value: "line", label: "Đoạn thẳng" },
                { value: "text", label: "Nhãn" },
                { value: "circle", label: "Đường tròn" },
                { value: "rectangle", label: "Hình chữ nhật" },
                { value: "polyline", label: "Đường gấp khúc" },
              ]}
            /></label>
            {(object.type === "line" ? ["x", "y", "x2", "y2"] : object.type === "rectangle" ? ["x", "y", "width", "height"] : object.type === "circle" ? ["x", "y", "radius"] : ["x", "y"]).map(key => <label key={key}>{key}<input type="number" min="0" max="1600" value={Number(object[key as keyof DiagramObject] ?? 0)} onChange={(event) => updateObject({ [key]: Number(event.target.value) })} /></label>)}
            {object.type === "text" && <label>Nhãn hình<input value={object.text ?? ""} onChange={(event) => updateObject({ text: event.target.value })} /></label>}
            {object.type === "polyline" && <label>Các điểm x,y (mỗi dòng một điểm)<textarea value={object.points?.map(p => `${p.x},${p.y}`).join("\n") ?? ""} onChange={(event) => updateObject({ points: event.target.value.split("\n").map(line => { const [x, y] = line.split(",").map(Number); return { x, y }; }) })} /></label>}
          </fieldset>;
        })}
        <button type="button" className="secondary" onClick={() => update(index, { ...block, spec: { ...block.spec, objects: [...block.spec.objects, { type: "line", x: 40, y: 40, x2: 120, y2: 40 }] } })}>Thêm đối tượng</button>
      </>}
      <RichContent blocks={[block]} />
      <button type="button" className="secondary" onClick={() => onChange(blocks.filter((_, position) => position !== index))}>Xóa khối {index + 1}</button>
    </fieldset>)}
    <div className="question-review-actions">
      <button type="button" className="secondary" onClick={() => onChange([...blocks, { type: "latex", content: "", display: "block" }])}>Thêm công thức</button>
      <button type="button" className="secondary" onClick={() => onChange([...blocks, { type: "table", headers: ["Đại lượng", "Giá trị"], rows: [["", ""]], caption: "" }])}>Thêm bảng</button>
      <button type="button" className="secondary" onClick={() => onChange([...blocks, { type: "diagram", alt: "Hình minh họa", caption: "", spec: { type: "drawing", width: 640, height: 360, objects: [{ type: "line", x: 40, y: 300, x2: 600, y2: 300 }] } }])}>Thêm hình vẽ</button>
      <label>Thêm ảnh<input type="file" accept="image/png,image/jpeg" onChange={(event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        if (file.size > 1400000 || !["image/png", "image/jpeg"].includes(file.type)) { setError("Chỉ nhận ảnh PNG/JPEG tối đa 1,4 MB."); return; }
        const reader = new FileReader();
        reader.onload = () => { onChange([...blocks, { type: "image", src: String(reader.result), alt: file.name, caption: "" }]); setError(""); };
        reader.readAsDataURL(file);
      }} /></label>
    </div>
    {error && <p role="alert">{error}</p>}
  </fieldset>;
}
