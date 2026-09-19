import { describe, expect, it } from "vitest";
import styles from "../styles.css?inline";

describe("global select design system", () => {
  it("defines native fallback and custom listbox states", () => {
    expect(styles).toMatch(/select:not\(\[multiple\]\)\s*\{[^}]*appearance:\s*none/s);
    expect(styles).toMatch(/select:not\(\[multiple\]\)\s*\{[^}]*background-image:/s);
    expect(styles).toMatch(/select:disabled\s*\{/);
    expect(styles).toMatch(/select option,\s*select optgroup\s*\{/);
    expect(styles).toMatch(/@media \(forced-colors: active\)[\s\S]*appearance:\s*auto/);
    expect(styles).toMatch(/@media \(max-width: 768px\)[\s\S]*select:not\(\[multiple\]\)\s*\{[^}]*min-height:\s*46px/s);
    expect(styles).toMatch(/@media \(max-width: 768px\)[\s\S]*\.list-toolbar > select,\s*\.list-toolbar > \.select-control\s*\{[^}]*flex:\s*0 0 auto/s);
    expect(styles).toMatch(/\.list-toolbar\s*\{[^}]*align-items:\s*flex-start/s);
    expect(styles).toMatch(/\.select-control-menu\s*\{[^}]*position:\s*fixed[^}]*z-index:\s*10000/s);
    expect(styles).toMatch(/\.select-control-option-active\s*\{[^}]*background:\s*var\(--primary-soft\)/s);
    expect(styles).toMatch(/\.select-control-option-selected \.select-control-option-mark\s*\{[^}]*background:\s*var\(--primary\)/s);
    expect(styles).toMatch(/@media \(max-width: 768px\)[\s\S]*\.select-control-trigger\s*\{[^}]*min-height:\s*46px/s);
  });
});
