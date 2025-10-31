import React, { useMemo } from "react";

export default function ZoomControl({
  value,
  onChange,
  min = 1,
  max = 8,
  step = 0.1,
  className = ""
}) {
  const clamped = useMemo(() => {
    if (typeof value !== "number") return min;
    return Math.min(max, Math.max(min, value));
  }, [value, min, max]);

  const zoomOut = () => onChange?.(Number(Math.max(min, clamped - step).toFixed(2)));
  const zoomIn  = () => onChange?.(Number(Math.min(max, clamped + step).toFixed(2)));
  const onSlider = (e) => onChange?.(Number(e.target.value));

  return (
    <div className={`panel ${className}`} style={{ padding: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Zoom</div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button className="pill" onClick={zoomOut} aria-label="Zoom out">−</button>
        <div style={{ minWidth: 70, textAlign: "center" }}>{clamped.toFixed(2)}×</div>
        <button className="pill" onClick={zoomIn} aria-label="Zoom in">+</button>
      </div>

      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={clamped}
        onChange={onSlider}
        style={{ width: "100%", marginTop: 10 }}
        aria-label="Zoom slider"
      />
    </div>
  );
}
