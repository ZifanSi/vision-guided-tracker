import React, { useMemo } from "react";

export default function SensitivityControl({
  value,
  onChange,
  min = 0.1,
  max = 5,
  step = 0.1,
  className = ""
}) {
  const clamped = useMemo(() => {
    if (typeof value !== "number") return min;
    return Math.min(max, Math.max(min, value));
  }, [value, min, max]);

  const dec = () => onChange?.(Number(Math.max(min, clamped - step).toFixed(2)));
  const inc = () => onChange?.(Number(Math.min(max, clamped + step).toFixed(2)));
  const onSlider = (e) => onChange?.(Number(e.target.value));

  return (
    <div className={`panel ${className}`} style={{ padding: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Sensitivity</div>
      <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 6 }}>
        Degrees per nudge
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button className="pill" onClick={dec} aria-label="Decrease sensitivity">−</button>
        <div style={{ minWidth: 70, textAlign: "center" }}>{clamped.toFixed(2)}°</div>
        <button className="pill" onClick={inc} aria-label="Increase sensitivity">+</button>
      </div>

      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={clamped}
        onChange={onSlider}
        style={{ width: "100%", marginTop: 10 }}
        aria-label="Sensitivity slider"
      />
    </div>
  );
}
