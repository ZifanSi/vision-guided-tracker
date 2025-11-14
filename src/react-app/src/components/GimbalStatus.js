import React from "react";
import "../styles/GimbalStatus.css";

export default function GimbalStatus({
  mode,
  angles = { az: 0, el: 0 },
  lastError,
  className = "",
}) {
  // map backend mode → nice label
  const modeLabel =
    mode === "auto"   ? "ARMED" :
    mode === "manual" ? "IDLE"  :
    "—";

  return (
    <div className={`gimbalStatus ${className}`}>
      {/* Mode card */}
      <div className="statCard">
        <div className="statLabel">Mode</div>
        <div className="statValue">{modeLabel}</div>
      </div>

      {/* Pan */}
      <div className="statCard">
        <div className="statLabel">Pan Angle</div>
        <div className="statValue">
          {angles.az.toFixed(1)}°
        </div>
      </div>

      {/* Tilt */}
      <div className="statCard">
        <div className="statLabel">Tilt Angle</div>
        <div className="statValue">
          {angles.el.toFixed(1)}°
        </div>
      </div>

      {/* Static lens / ISO / shutter cards */}
      <div className="statCard">
        <div className="statLabel">Lens</div>
        <div className="statValue">24&nbsp;mm</div>
      </div>

      <div className="statCard">
        <div className="statLabel">ISO</div>
        <div className="statValue">100</div>
      </div>

      <div className="statCard">
        <div className="statLabel">Shutter</div>
        <div className="statValue">1/250&nbsp;s</div>
      </div>

      {lastError && (
        <div className="statError">
          err: {lastError}
        </div>
      )}
    </div>
  );
}
