// src/react-app/src/components/GimbalStatus.js
import React from "react";
import "../styles/GimbalStatus.css";

export default function GimbalStatus({
  angles = { az: 0, el: 0 },
  lastError,
  className = "",
}) {
  return (
    <div className={`gimbalStatus ${className}`}>
      <div className="statCard">
        <div className="statLabel">horizontal angle</div>
        <div className="statValue">
          {angles.az.toFixed(1)}°
        </div>
      </div>

      <div className="statCard">
        <div className="statLabel">vertical angle</div>
        <div className="statValue">
          {angles.el.toFixed(1)}°
        </div>
      </div>

      {lastError && (
        <div className="statError">
          err: {lastError}
        </div>
      )}
    </div>
  );
}
