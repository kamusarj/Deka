import { useEffect, useRef } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import type { DiagramSpec, RichBlock } from "../types";

export function Formula({ value, display = false }: { value: string; display?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    katex.render(value, ref.current, { displayMode: display, throwOnError: false, trust: false, strict: "warn", maxSize: 10, maxExpand: 100, output: "htmlAndMathml" });
  }, [value, display]);
  return <span ref={ref} className="math-formula" aria-label={`Công thức ${value}`} />;
}

export function MathText({ text }: { text?: string | null }) {
  const value = text ?? "";
  const pattern = /(?<!\\)\$\$(.+?)(?<!\\)\$\$|(?<!\\)\$([^$\n]+?)(?<!\\)\$|\\\[(.+?)\\\]|\\\((.+?)\\\)/gs;
  const matches = [...value.matchAll(pattern)];
  if (!matches.length && /^\s*\\(?:frac|sqrt|mathrm|text|sum|Delta|rho)\b/.test(value)) return <Formula value={value.trim()} />;
  let cursor = 0;
  const nodes = matches.flatMap((match, index) => {
    const prefix = value.slice(cursor, match.index);
    cursor = match.index! + match[0].length;
    return [prefix, <Formula key={index} value={match[1] ?? match[2] ?? match[3] ?? match[4]} display={Boolean(match[1] ?? match[3])} />];
  });
  return <>{nodes}{value.slice(cursor)}</>;
}

export function Diagram({ spec, alt }: { spec: DiagramSpec; alt: string }) {
  return <svg className="science-diagram" role="img" aria-label={alt} viewBox={`0 0 ${spec.width} ${spec.height}`} xmlns="http://www.w3.org/2000/svg">
    <title>{alt}</title>
    {spec.objects.map((item, index) => {
      const common = { stroke: "currentColor", strokeWidth: 2, fill: "none" };
      if (item.type === "line") return <line key={index} {...common} x1={item.x ?? 0} y1={item.y ?? 0} x2={item.x2 ?? 0} y2={item.y2 ?? 0} />;
      if (item.type === "circle") return <circle key={index} {...common} cx={item.x ?? 0} cy={item.y ?? 0} r={item.radius ?? 0} />;
      if (item.type === "rectangle") return <rect key={index} {...common} x={item.x ?? 0} y={item.y ?? 0} width={item.width ?? 0} height={item.height ?? 0} />;
      if (item.type === "polyline") return <polyline key={index} {...common} points={item.points?.map(p => `${p.x},${p.y}`).join(" ")} />;
      return <text key={index} x={item.x ?? 0} y={item.y ?? 0} fontSize="16" fill="currentColor">{item.text}</text>;
    })}
  </svg>;
}

export default function RichContent({ blocks }: { blocks?: RichBlock[] | null }) {
  if (!blocks?.length) return null;
  return <div className="rich-content">
    {blocks.map((block, index) => {
      if (block.type === "text") return <p key={index}><MathText text={block.content} /></p>;
      if (block.type === "latex") return <Formula key={index} value={block.content} display={block.display === "block"} />;
      if (block.type === "table") return <div className="table-wrapper" key={index}><table>
        {block.caption && <caption><MathText text={block.caption} /></caption>}
        <thead><tr>{block.headers.map((cell, column) => <th key={column}><MathText text={cell} /></th>)}</tr></thead>
        <tbody>{block.rows.map((row, position) => <tr key={position}>{row.map((cell, column) => <td key={column}><MathText text={cell} /></td>)}</tr>)}</tbody>
      </table></div>;
      if (block.type === "diagram") return <figure key={index}><Diagram spec={block.spec} alt={block.alt} />{block.caption && <figcaption><MathText text={block.caption} /></figcaption>}</figure>;
      if (block.type === "image") return <figure key={index}>
        {/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(block.src) ? <img src={block.src} alt={block.alt} loading="lazy" /> : <p>Ảnh không hợp lệ: {block.alt}</p>}
        {block.caption && <figcaption><MathText text={block.caption} /></figcaption>}
      </figure>;
      return null;
    })}
  </div>;
}
