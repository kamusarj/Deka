interface BrandMarkProps {
  className?: string;
}

/** A verified exam sheet: one product-specific mark shared by every surface. */
export default function BrandMark({ className = "" }: BrandMarkProps) {
  return (
    <span className={`brand-logo ${className}`.trim()} aria-hidden="true">
      <span className="brand-logo-glow" />
      <svg viewBox="0 0 32 32" focusable="false">
        <path className="brand-logo-sheet" d="M9.25 5.75h9.8l4.7 4.7v15.8h-14.5z" />
        <path className="brand-logo-fold" d="M19.05 5.75v4.7h4.7" />
        <path className="brand-logo-check" d="m12.1 17.3 2.55 2.55 5.35-6" />
      </svg>
    </span>
  );
}
