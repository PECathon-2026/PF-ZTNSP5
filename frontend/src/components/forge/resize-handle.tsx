"use client";

export function ResizeHandle({ label, value, min, max, direction = 1, onChange }: { label: string; value: number; min: number; max: number; direction?: number; onChange: (value: number) => void }) {
  function resize(next: number) { onChange(Math.min(max, Math.max(min, next))); }
  return <div className="forge-resize" role="separator" tabIndex={0} aria-label={label}
    aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={value}
    onKeyDown={(event) => {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); resize(value + (event.key === "ArrowRight" ? 10 : -10) * direction); }
      if (event.key === "Home") { event.preventDefault(); resize(min); }
      if (event.key === "End") { event.preventDefault(); resize(max); }
    }}
    onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); event.currentTarget.dataset.startX = String(event.clientX); event.currentTarget.dataset.startValue = String(value); }}
    onPointerMove={(event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) resize(Number(event.currentTarget.dataset.startValue) + (event.clientX - Number(event.currentTarget.dataset.startX)) * direction); }}
    onPointerUp={(event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }} />;
}
