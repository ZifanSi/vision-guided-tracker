// src/react-app/src/components/GimbalStatus.js
import React from "react";

export default function GimbalStatus({ angles = { az: 0, el: 0 }, lastError, className = "" }) {
  return (
    <div className={`blank ${className}`} style={{ display: "grid", placeItems: "center", minHeight: 80 }}>
      <div>
        az: {angles.az.toFixed(1)}°, el: {angles.el.toFixed(1)}°
        {lastError ? <div style={{ color: "crimson", marginTop: 4 }}>err: {lastError}</div> : null}
      </div>
    </div>
  );
}
